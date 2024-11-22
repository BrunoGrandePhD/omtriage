import argparse
import logging
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import exiftool

EXIFTOOL_BATCH_SIZE = 100
FORMATS = ["orf", "ori", "jpg", "mov"]

# Set up the logger at the module level
logger = logging.getLogger(__name__)


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@dataclass
class Photo:
    files: list[Path]
    capture_datetime: datetime

    @property
    def available_formats(self):
        return [file.suffix.lower().lstrip(".") for file in self.files]

    def get_format(self, format: str) -> Path | None:
        for file in self.files:
            if file.suffix.lower().lstrip(".") == format:
                return file
        return None


@dataclass
class Session:
    photos: list[Photo]

    @property
    def start_time(self) -> datetime:
        return self.photos[0].capture_datetime

    @property
    def end_time(self) -> datetime:
        return self.photos[-1].capture_datetime

    @property
    def session_type(self) -> str:
        return "AM" if self.start_time.hour < 14 else "PM"

    @property
    def image_count(self) -> int:
        return len(self.photos)


def get_tags_dict(
    paths: list[Path], names: list[str], batch_size: int = EXIFTOOL_BATCH_SIZE
) -> dict[Path, dict[str, Any | None]]:
    result = {}
    with exiftool.ExifToolHelper() as et:
        for i in range(0, len(paths), batch_size):
            logger.info(
                f"Processing files {i} to {i + batch_size} (out of {len(paths)})"
            )
            batch = paths[i : i + batch_size]
            files = [str(file) for file in batch]
            output = et.get_tags(files, names)
            output_dict = dict(zip(batch, output))
            result.update(output_dict)

    logger.debug(f"Tags: {result}")
    return result


def get_tag_dict(paths: list[Path], names: list[str]) -> dict[Path, Any | None]:
    tags = get_tags_dict(paths, names)

    result = {}
    for file, tag_values in tags.items():
        final_value = None
        for tag in names:
            if tag in tag_values:
                final_value = tag_values[tag]
                break
        if final_value is None:
            logger.warning(f"Tags {names} not found for {file}.")
        result[file] = final_value

    return result


def get_tag(paths: list[Path], names: list[str]) -> list[Any | None]:
    tags = get_tag_dict(paths, names)
    return [tags[file] for file in paths]


def get_capture_datetime(paths: list[Path]) -> dict[Path, datetime | None]:
    date_names = ["EXIF:CreateDate", "QuickTime:CreateDate"]
    tags = get_tag_dict(paths, date_names)

    result = {}
    for file, date_str in tags.items():
        capture_time = None
        if date_str:
            capture_time = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

        if not capture_time:
            logger.warning(f"No capture datetime found for {file}. Tags: {tags}")
        result[file] = capture_time

    return result


def generate_photos(paths: list[Path]) -> list[Photo]:
    # Get capture datetimes for all files
    capture_datetimes = get_capture_datetime(paths)

    # Generate a list of files and filter them for valid file extensions
    paths_by_prefix = defaultdict(list)
    for path in paths:
        prefix = path.parent / path.stem
        paths_by_prefix[prefix].append(path)

    # Create Photo objects for each group of files with the same prefix
    photos = []
    for paths in paths_by_prefix.values():
        first_file = paths[0]
        capture_datetime = capture_datetimes[first_file]
        photo = Photo(paths, capture_datetime)
        photos.append(photo)

    return photos


def organize_photos(
    photos: list[Photo], session_gap_hours: float = 3.0
) -> list[Session]:
    # Sort photos by capture datetime, putting None values at the end
    sorted_photos = sorted(
        photos, key=lambda x: (x.capture_datetime is None, x.capture_datetime)
    )

    sessions = []
    current_session_photos = []

    for photo in sorted_photos:
        if not photo.capture_datetime:
            logger.warning(
                f"Photo without capture datetime: {photo.folder}/{photo.prefix}"
            )
            if current_session_photos:
                current_session_photos.append(photo)
            else:
                sessions.append(Session([photo]))
            continue

        if not current_session_photos:
            current_session_photos.append(photo)
        else:
            if current_session_photos[-1].capture_datetime:
                time_diff = (
                    photo.capture_datetime - current_session_photos[-1].capture_datetime
                ).total_seconds() / 3600

                if time_diff > session_gap_hours:
                    # End the current session and start a new one
                    sessions.append(Session(current_session_photos))
                    current_session_photos = [photo]
                else:
                    current_session_photos.append(photo)
            else:
                current_session_photos.append(photo)

    # Add the last session
    if current_session_photos:
        sessions.append(Session(current_session_photos))

    # Log sessions, their image count, and start and end times
    for i, session in enumerate(sessions, 1):
        logger.info(f"Session {i}:")
        logger.info(f"  Image count: {session.image_count}")
        logger.info(f"  Start time: {session.start_time}")
        logger.info(f"  End time: {session.end_time}")

    return sessions


class FileManager:
    def __init__(self, sessions: list[Session], output_dir: Path):
        self.sessions = sessions
        self.output_dir = output_dir
        self.jpegs_dir = self._create_directory("JPEGs")
        self.movs_dir = self._create_directory("MOVs")

    def _create_directory(self, name: str) -> Path:
        directory = self.output_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def copy_files_to_output(self):
        for folder_name, sessions in self.sessions_by_name.items():
            for index, session in enumerate(sessions, start=1):
                if len(sessions) > 1:
                    folder_name += f"-{index}"
                self._copy_session(session, folder_name)
        logger.info("File copying complete.")

    @property
    def sessions_by_name(self) -> dict[tuple[str, str], list[Session]]:
        sessions_by_name = defaultdict(list)
        for session in self.sessions:
            date_str = session.start_time.strftime("%Y-%m-%d")
            session_name = f"{date_str}-{session.session_type}"
            sessions_by_name[session_name].append(session)
        return sessions_by_name

    def _copy_session(self, session: Session, session_name: str):
        session_output_dir = self._create_directory(session_name)
        for photo in session.photos:
            self._copy_photo(photo, session_output_dir)

    def _copy_photo(self, photo: Photo, session_output_dir: Path):
        for file in photo.files:
            output_dir = self._determine_output_dir(file, session_output_dir, photo)
            output_path = self._copy_file(file, output_dir)

            # If JPEG is available, symlink the ORF file for comparison
            format = file.suffix.lower().lstrip(".")
            jpg_file = photo.get_format("jpg")
            if format == "orf" and jpg_file:
                jpg_output_dir = self._determine_output_dir(
                    jpg_file, session_output_dir, photo
                )
                source_path = jpg_output_dir / file.name
                try:
                    source_path.symlink_to(output_path)
                    logger.debug(f"Symlinked {source_path} to {output_path}")
                except Exception as e:
                    logger.error(f"Failed to symlink {source_path}: {e}")
                if not source_path.exists():
                    msg = f"Symlink {source_path} isn't valid (target: {output_path})"
                    raise FileNotFoundError(msg)

    def _determine_output_dir(
        self, file: Path, session_output_dir: Path, photo: Photo
    ) -> Path:
        output_dir = session_output_dir

        # Triage JPEGs separately if an ORF file is available
        orf_file = photo.get_format("orf")
        format = file.suffix.lower().lstrip(".")
        if format == "jpg" and orf_file:
            height_names = ["EXIF:ImageHeight", "EXIF:ExifImageHeight"]
            width_names = ["EXIF:ImageWidth", "EXIF:ExifImageWidth"]
            jpg_height, orf_height = get_tag([file, orf_file], height_names)
            jpg_width, orf_width = get_tag([file, orf_file], width_names)

            # Keep the JPEG if it's a higher resolution (high-res mode)
            if jpg_height * jpg_width <= orf_height * orf_width:
                output_dir = self.jpegs_dir / session_output_dir.name

        # Triage MOVs separately
        if format == "mov":
            output_dir = self.movs_dir / session_output_dir.name

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _copy_file(self, file: Path, output_dir: Path) -> Path:
        # Append ORF extensions to ORI files to clarify format
        dest_filename = file.name
        format = file.suffix.lower().lstrip(".")
        if format == "ori":
            dest_filename += ".ORF"

        output_path = output_dir / dest_filename
        try:
            shutil.copy2(file, output_path)
            logger.debug(f"Copied {file} to {output_path}")
        except Exception as e:
            logger.error(f"Failed to copy {file}: {e}")

        return output_path


def copy_files_to_output(sessions: list[Session], output_dir: Path):
    file_manager = FileManager(sessions, output_dir)
    file_manager.copy_files_to_output()


def get_paths(directory: Path, extensions: list[str]) -> list[Path]:
    paths = []
    lowercase_extensions = [ext.lower() for ext in extensions]
    for file in directory.rglob("*"):
        if file.is_file():
            file_extension = file.suffix.lower().lstrip(".")
            if file_extension in lowercase_extensions:
                paths.append(file)
    return paths


def compare_files(input_paths: list[Path], output_paths: list[Path]) -> list[str]:
    input_files = set(path.name for path in input_paths)
    output_files = set(path.name for path in output_paths)

    missing_files = []
    for file in input_files:
        if file.lower().endswith(".ori"):
            if file + ".ORF" not in output_files:
                missing_files.append(file)
        elif file not in output_files:
            missing_files.append(file)

    return missing_files


def parse_arguments():
    parser = argparse.ArgumentParser(description="Import images and videos.")
    parser.add_argument("input_dir", type=Path, help="Path to the input directory")
    parser.add_argument("output_dir", type=Path, help="Path to the output directory")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase output verbosity"
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    setup_logging(args.verbose)

    input_dir = args.input_dir
    output_dir = args.output_dir
    extensions = FORMATS

    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"File extensions to process: {', '.join(extensions)}")

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process files
    input_files = get_paths(input_dir, extensions)
    photos = generate_photos(input_files)
    sessions = organize_photos(photos)
    copy_files_to_output(sessions, output_dir)

    # Compare files and print missing ones
    output_files = get_paths(output_dir, extensions)
    missing_files = compare_files(input_files, output_files)

    if not missing_files:
        logger.info("All files were successfully copied to the output directory.")
    else:
        logger.error(f"The following files are missing in the output directory:")
        for file in missing_files:
            logger.error(f"  - {file}")
        logger.error(f"Total missing files: {len(missing_files)}")


if __name__ == "__main__":
    main()
