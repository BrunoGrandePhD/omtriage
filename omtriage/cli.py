"""Command-line interface for the photo importer."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Union

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .constants import ALL_FORMATS, DEFAULT_SESSION_GAP
from .database import ImportDatabase
from .metadata import extract_metadata
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


def find_media_files(input_dir: Path) -> List[MediaFile]:
    """Find supported media files in the input directory."""
    files = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning for media files...", total=None)
        for format in ALL_FORMATS:
            # Search for both lowercase and uppercase extensions
            files.extend(MediaFile(p) for p in input_dir.rglob(f"*.{format.lower()}"))
            files.extend(MediaFile(p) for p in input_dir.rglob(f"*.{format.upper()}"))
        progress.update(task, completed=True)

    return files


def import_files(
    input_dir: Path,
    output_dir: Path,
    session_gap: float = DEFAULT_SESSION_GAP,
    force_reimport: bool = False,
    dry_run: bool = False,
    log_level: str = "INFO",
    db_path: Optional[Union[Path, str]] = None,
) -> None:
    """Import and organize media files.

    Args:
        input_dir: Directory containing media files
        output_dir: Directory to store organized files
        session_gap: Hours between sessions
        force_reimport: Ignore previous import history
        dry_run: Show what would be done without making changes
        log_level: Logging level
        db_path: Custom path for the database file
    """
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    if force_reimport:
        logger.warning(
            "Force reimport enabled - previous import history will be ignored"
        )
    db = ImportDatabase(db_path=db_path)
    if force_reimport:
        db.clear_history()

    # Find media files
    files = find_media_files(input_dir)
    if not files:
        logger.warning("No supported media files found")
        return
    logger.info(f"Found {len(files)} media files")

    # Filter already imported files
    if not force_reimport:
        files = [f for f in files if not db.is_file_imported(f)]
        if not files:
            logger.info("All files have already been imported")
            return
        logger.info(f"{len(files)} files to import")

    # Extract metadata
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting metadata...", total=None)
        extract_metadata(files)
        progress.update(task, completed=True)

    # Group and organize files
    groups = group_files(files)
    sessions = organize_sessions(groups, session_gap)
    if not sessions:
        logger.warning("No valid sessions found")
        return

    # Create session structure
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Organizing files...", total=len(sessions))
        for session in sessions:
            create_session_structure(session, output_dir, dry_run)
            if not dry_run:
                for group in session.groups:
                    for file in group.files:
                        db.mark_file_imported(file)
            progress.update(task, advance=1)

    # Print summary
    if not dry_run:
        stats = db.get_import_stats()
        console.print("\n[bold green]Import Summary:[/]")
        console.print(f"Total files: {stats['total_files']}")
        console.print(f"Files with metadata: {stats['files_with_metadata']}")
        console.print(f"Unique days: {stats['unique_days']}")
        console.print(f"Total size: {stats['total_size'] / (1024*1024*1024):.2f} GB")


def main() -> None:
    """Entry point for the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Import and organize photos from camera SD cards."
    )
    parser.add_argument(
        "input_dir", type=Path, help="Directory containing media files to import"
    )
    parser.add_argument(
        "output_dir", type=Path, help="Directory to store organized media files"
    )
    parser.add_argument(
        "--session-gap",
        type=float,
        default=DEFAULT_SESSION_GAP,
        help=f"Hours between sessions (default: {DEFAULT_SESSION_GAP})",
    )
    parser.add_argument(
        "--force-reimport", action="store_true", help="Ignore previous import history"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
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
