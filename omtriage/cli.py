"""Command-line interface for the photo importer."""

import argparse
import functools
import logging
from pathlib import Path
from typing import Optional

from . import __version__
from .constants import DEFAULT_SESSION_GAP
from .database import ImportDatabase
from .logging import setup_logging, track
from .metadata import ExiftoolMetadataExtractor, MediaFileFactory, MetadataExtractor
from .models import MediaFile
from .organizer import _are_on_same_device, create_session_structure, group_files, organize_sessions
from .utils import is_image_file, is_video_file

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _find_media_paths(directory: Path) -> list[Path]:
    """Find all media files in a directory recursively.

    Args:
        directory: Directory to search in

    Returns:
        List of paths to media files
    """
    logger.debug(f"Finding media files in {directory}")
    media_paths = []
    for path in directory.rglob("*"):
        if path.is_symlink():
            continue
        if is_image_file(path) or is_video_file(path):
            media_paths.append(path)
    return media_paths


def count_media_files(directory: Path) -> tuple[int, int]:
    """Count the number of image and video files in a directory.

    Args:
        directory: Directory to count files in

    Returns:
        Tuple of (image_count, video_count)
    """
    image_count = 0
    video_count = 0

    for path in _find_media_paths(directory):
        if is_image_file(path):
            image_count += 1
        else:  # Must be a video file since _find_media_paths only returns media files
            video_count += 1

    logger.info(f"Found {image_count} images and {video_count} videos in {directory}")
    return image_count, video_count


def create_media_files(input_dir: Path, factory: MediaFileFactory) -> list[MediaFile]:
    """Find supported media files in the input directory."""
    paths = _find_media_paths(input_dir)
    return factory.create_media_files(paths)


def import_files(
    input_dir: Path,
    output_dir: Path,
    session_gap: float = DEFAULT_SESSION_GAP,
    force_reimport: bool = False,
    dry_run: bool = False,
    log_level: str = "INFO",
    db_path: Optional[Path] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
) -> None:
    """Import and organize media files."""
    setup_logging(log_level)
    logger.info("Starting import:\n" f"  {input_dir} -> {output_dir}")
    logger.info(
        f"Settings:\n"
        f"  Session gap: {session_gap:.1f} hours\n"
        f"  Force reimport: {force_reimport}\n"
        f"  Dry run: {dry_run}"
    )

    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # Count input files
    input_images, input_videos = count_media_files(input_dir)
    logger.debug(f"Found {input_images} images and {input_videos} videos in input directory")

    # Create output directory if it doesn't exist
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created output directory: {output_dir}")

    # Initialize database
    db = ImportDatabase(db_path) if db_path else ImportDatabase()
    logger.info(f"Using the import history stored in {db.db_path}")

    # Create factory with metadata extractor
    extractor = metadata_extractor or ExiftoolMetadataExtractor()
    factory = MediaFileFactory(extractor)
    logger.debug(f"Using metadata extractor: {extractor.__class__.__name__}")

    # Find media files
    files = create_media_files(input_dir, factory)
    if not files:
        logger.info("No media files found")
        return

    # Check import history
    if not force_reimport and not dry_run:
        original_count = len(files)
        files = [f for f in files if not db.is_file_imported(f)]
        skipped_count = original_count - len(files)
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} previously imported files")
        if not files:
            logger.info("All files have already been imported")
            return
        logger.info(f"{len(files)} files to import")

    # Group and organize files
    groups = group_files(files)
    sessions = organize_sessions(groups, session_gap)

    if dry_run:
        logger.info("Sessions:")
        for session in sessions:
            logger.info(f"  - {session.format_name()}")
        logger.info("Dry run completed, no files were modified")
        return

    # Determine if we can use hardlinks (check once for all files)
    use_hardlinks = _are_on_same_device(input_dir, output_dir)
    logger.info(
        f"{'Using hardlinks' if use_hardlinks else 'Using file copies'} "
        f"for all files (determined by comparing input and output directories)"
    )

    # Import files with progress tracking
    for session in track(sessions, description="Importing files"):
        logger.debug(f"Processing session with {len(session.groups)} groups")
        create_session_structure(session, output_dir, use_hardlinks=use_hardlinks)

    # Update import history
    for file in track(files, description="Updating import history"):
        db.mark_file_imported(file)
        logger.debug(f"Marked as imported: {file.path.name}")

    # Clean up empty directories
    empty_dirs = 0
    # Iterate over directories in reverse order to delete nested directories first
    for dirpath in sorted(output_dir.rglob("*/"), key=lambda p: p.parts, reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
            empty_dirs += 1
    if empty_dirs > 0:
        logger.debug(f"Removed {empty_dirs} empty directories")

    # Count output files and verify
    output_images, output_videos = count_media_files(output_dir)
    logger.info(f"Found {output_images} images and {output_videos} videos in output directory")

    # Check if any files are missing
    if output_images != input_images or output_videos != input_videos:
        error_msg = (
            f"File count mismatch! Input: {input_images} images, {input_videos} videos. "
            f"Output: {output_images} images, {output_videos} videos."
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("Import completed successfully")


def main() -> None:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description=f"Import and organize media files (v{__version__})"
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing media files",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory to organize files into",
    )
    parser.add_argument(
        "--session-gap",
        type=float,
        default=DEFAULT_SESSION_GAP,
        help=f"Hours between sessions (default: {DEFAULT_SESSION_GAP})",
    )
    parser.add_argument(
        "--force-reimport",
        action="store_true",
        help="Force reimport of previously imported files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--import-history",
        type=Path,
        help="Custom path for the import history database",
    )

    args = parser.parse_args()

    import_files(
        args.input_dir,
        args.output_dir,
        args.session_gap,
        args.force_reimport,
        args.dry_run,
        args.log_level,
        db_path=args.import_history,
    )


if __name__ == "__main__":
    main()
