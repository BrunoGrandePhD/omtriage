"""Command-line interface for the photo importer."""

import argparse
import logging
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from tqdm import tqdm

from . import __version__
from .constants import ALL_FORMATS, DEFAULT_SESSION_GAP, SUPPORTED_FORMATS
from .database import ImportDatabase
from .metadata import ExiftoolMetadataExtractor, MediaFileFactory, MetadataExtractor
from .models import MediaFile
from .organizer import create_session_structure, group_files, organize_sessions

console = Console()


def setup_logging(level: str) -> None:
    """Configure logging with rich output."""
    # Get the root logger and set its level
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Configure the handler
    handler = RichHandler(console=console, rich_tracebacks=True)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Remove any existing handlers and add our new one
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def count_media_files(directory: Path) -> tuple[int, int]:
    """Count the number of image and video files in a directory.

    Args:
        directory: Directory to count files in

    Returns:
        Tuple of (image_count, video_count)
    """
    image_count = 0
    video_count = 0

    for path in directory.rglob("*"):
        if path.is_symlink():
            continue
        file = MediaFile(path)
        if file.is_image:
            image_count += 1
        elif file.is_video:
            video_count += 1

    return image_count, video_count


def find_media_files(input_dir: Path, factory: MediaFileFactory) -> list[MediaFile]:
    """Find supported media files in the input directory."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Searching for media files in {input_dir}")

    paths: list[Path] = []
    # Use tqdm for progress tracking with conventional approach
    for path in tqdm(
        list(input_dir.rglob("*")), desc="Finding media files", unit="file"
    ):
        file = MediaFile(path)
        if file.is_image or file.is_video:
            paths.append(path)
            logger.debug(f"Found supported file: {path.name}")

    logger.debug(f"Found {len(paths)} supported files")
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
    logger = logging.getLogger(__name__)
    logger.info(f"Starting import from {input_dir} to {output_dir}")
    logger.debug(
        f"Session gap: {session_gap} hours, Force reimport: {force_reimport}, Dry run: {dry_run}"
    )

    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        return

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # Count input files
    input_images, input_videos = count_media_files(input_dir)
    logger.info(
        f"Found {input_images} images and {input_videos} videos in input directory"
    )

    # Create output directory if it doesn't exist
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created output directory: {output_dir}")

    # Initialize database
    db = ImportDatabase(db_path) if db_path else ImportDatabase()
    logger.debug(f"Using database at: {db.db_path}")

    # Create factory with metadata extractor
    extractor = metadata_extractor or ExiftoolMetadataExtractor()
    factory = MediaFileFactory(extractor)
    logger.debug(f"Using metadata extractor: {extractor.__class__.__name__}")

    # Find media files
    files = find_media_files(input_dir, factory)
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
    logger.debug(f"Created {len(groups)} file groups")
    sessions = organize_sessions(groups, session_gap)
    logger.debug(f"Organized into {len(sessions)} sessions")

    if dry_run:
        logger.info("Dry run completed, no files were modified")
        return

    # Import files with progress tracking
    for session in tqdm(sessions, desc="Importing files", unit="session"):
        logger.debug(f"Processing session with {len(session.groups)} groups")
        create_session_structure(session, output_dir)

    # Update import history
    for file in tqdm(files, desc="Updating import history", unit="file"):
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
    logger.info(
        f"Found {output_images} images and {output_videos} videos in output directory"
    )

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
