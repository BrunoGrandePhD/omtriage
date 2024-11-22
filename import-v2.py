#!/usr/bin/env python3

"""
Photo and Video Import Tool

This script organizes photos and videos from a camera SD card into a structured directory layout.
Files are organized by date and session, with special handling for different file formats.

Features:
- Organizes files by capture date and session (AM/PM)
- Separates images and videos into different directories
- Special handling for ORF/ORI files and their JPEG counterparts
- Progress tracking and validation
- Detailed logging
"""

import argparse
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import sqlite3
from contextlib import contextmanager

import exiftool
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Configure logging
logger = logging.getLogger(__name__)
console = Console()

# Constants
SUPPORTED_FORMATS = {
    'images': {'orf', 'ori', 'jpg', 'jpeg'},
    'videos': {'mov', 'mp4'},
}
ALL_FORMATS = {fmt for formats in SUPPORTED_FORMATS.values() for fmt in formats}
AFTERNOON_HOUR = 14  # 2 PM
DEFAULT_SESSION_GAP = 3.0  # hours
EXIFTOOL_BATCH_SIZE = 100
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS imported_files (
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    creation_date TEXT NOT NULL,
    original_name TEXT NOT NULL,
    capture_time TEXT,
    import_time TEXT NOT NULL,
    PRIMARY KEY (filename, file_size, creation_date)
);
CREATE INDEX IF NOT EXISTS idx_capture_time ON imported_files(capture_time);
"""


class SessionType(Enum):
    """Session types based on start time."""
    MORNING = auto()
    AFTERNOON = auto()

    @classmethod
    def from_datetime(cls, dt: datetime) -> 'SessionType':
        """Determine session type from datetime."""
        return cls.AFTERNOON if dt.hour >= AFTERNOON_HOUR else cls.MORNING

    def __str__(self) -> str:
        return 'PM' if self == SessionType.AFTERNOON else 'AM'


@dataclass
class MediaFile:
    """Represents a media file with its metadata."""
    path: Path
    capture_time: Optional[datetime] = None
    format: str = field(init=False)
    creation_date: datetime = field(init=False)
    file_size: int = field(init=False)
    
    def __post_init__(self):
        """Initialize derived attributes."""
        self.format = self.path.suffix.lower().lstrip('.')
        if self.format == 'ori':
            self.format = 'orf'  # Treat ORI as ORF
        stat = self.path.stat()
        self.creation_date = datetime.fromtimestamp(stat.st_ctime)
        self.file_size = stat.st_size

    @property
    def is_image(self) -> bool:
        """Check if the file is an image."""
        return self.format in SUPPORTED_FORMATS['images']

    @property
    def is_video(self) -> bool:
        """Check if the file is a video."""
        return self.format in SUPPORTED_FORMATS['videos']

    @property
    def output_name(self) -> str:
        """Get the output filename."""
        name = self.path.name
        if self.path.suffix.lower() == '.ori':
            name += '.ORF'
        return name


@dataclass
class MediaGroup:
    """Group of related media files (e.g., ORF+JPEG pair)."""
    files: List[MediaFile]
    capture_time: Optional[datetime] = field(init=False)

    def __post_init__(self):
        """Initialize capture time from files."""
        times = [f.capture_time for f in self.files if f.capture_time]
        self.capture_time = min(times) if times else None

    def get_by_format(self, format: str) -> Optional[MediaFile]:
        """Get file of specific format if it exists."""
        return next((f for f in self.files if f.format == format), None)


@dataclass
class Session:
    """Group of media files captured within a time window."""
    groups: List[MediaGroup]
    type: SessionType
    number: int = 1

    @property
    def start_time(self) -> datetime:
        """Get session start time."""
        return min(g.capture_time for g in self.groups if g.capture_time)

    def format_name(self, base_dir: Optional[str] = None) -> str:
        """Format session directory name."""
        date_str = self.start_time.strftime('%Y-%m-%d')
        name = f"{date_str}-{self.type}"
        if self.number > 1:
            name += f"-{self.number}"
        return str(Path(base_dir) / name) if base_dir else name


class MediaOrganizer:
    """Main class for organizing media files."""

    def __init__(self, input_dir: Path, output_dir: Path, session_gap: float = DEFAULT_SESSION_GAP):
        """Initialize organizer with directories and settings."""
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.session_gap = timedelta(hours=session_gap)
        self.jpeg_dir = output_dir / "JPEGs"
        self.video_dir = output_dir / "Videos"
        self.db_path = output_dir / ".import_history.db"
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database for tracking imported files."""
        with self._get_db() as conn:
            conn.executescript(DB_SCHEMA)

    @contextmanager
    def _get_db(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _is_file_imported(self, file: MediaFile) -> bool:
        """Check if a file has already been imported."""
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM imported_files 
                WHERE filename = ? AND file_size = ? AND creation_date = ?
                """,
                (
                    file.path.name,
                    file.file_size,
                    file.creation_date.isoformat()
                )
            )
            return cursor.fetchone() is not None

    def _mark_file_imported(self, file: MediaFile) -> None:
        """Mark a file as imported in the database."""
        with self._get_db() as conn:
            conn.execute(
                """
                INSERT INTO imported_files 
                (filename, file_size, creation_date, original_name, capture_time, import_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file.path.name,
                    file.file_size,
                    file.creation_date.isoformat(),
                    file.path.name,
                    file.capture_time.isoformat() if file.capture_time else None,
                    datetime.now().isoformat()
                )
            )

    def organize(self) -> None:
        """Main organization process."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            # Scan input directory
            scan_task = progress.add_task("Scanning input directory...", total=None)
            media_files = self._scan_directory()
            progress.update(scan_task, completed=True)

            # Extract metadata
            meta_task = progress.add_task("Extracting metadata...", total=len(media_files))
            media_files = self._extract_metadata(media_files, progress, meta_task)

            # Group files
            group_task = progress.add_task("Grouping files...", total=None)
            groups = self._group_files(media_files)
            progress.update(group_task, completed=True)

            # Create sessions
            session_task = progress.add_task("Creating sessions...", total=None)
            sessions = self._create_sessions(groups)
            progress.update(session_task, completed=True)

            # Copy files
            copy_task = progress.add_task("Copying files...", total=len(media_files))
            self._copy_files(sessions, progress, copy_task)

    def _scan_directory(self) -> List[MediaFile]:
        """Scan input directory for media files."""
        # Pre-compute stats for all files to avoid multiple stat calls
        files = []
        logger.info("Scanning input directory...")
        total_files = 0
        skipped_files = 0

        for ext in ALL_FORMATS:
            pattern = f"**/*.{ext}"
            for path in self.input_dir.glob(pattern):
                total_files += 1
                media_file = MediaFile(path)
                if not self._is_file_imported(media_file):
                    files.append(media_file)
                else:
                    skipped_files += 1
                    logger.debug(f"Skipping previously imported file: {path}")
        
        logger.info(f"Found {total_files} files ({skipped_files} already imported)")
        return files

    def _extract_metadata(
        self, files: List[MediaFile], progress: Progress, task_id: int
    ) -> List[MediaFile]:
        """Extract metadata from media files."""
        with exiftool.ExifToolHelper() as et:
            for i in range(0, len(files), EXIFTOOL_BATCH_SIZE):
                batch = files[i:i + EXIFTOOL_BATCH_SIZE]
                paths = [str(f.path) for f in batch]
                try:
                    metadata = et.get_tags(paths, ["DateTimeOriginal", "CreateDate"])
                    for file, meta in zip(batch, metadata):
                        date_str = meta.get("EXIF:DateTimeOriginal") or meta.get("QuickTime:CreateDate")
                        if date_str:
                            file.capture_time = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except Exception as e:
                    logger.error(f"Error reading metadata: {e}")
                progress.update(task_id, advance=len(batch))
        return files

    def _group_files(self, files: List[MediaFile]) -> List[MediaGroup]:
        """Group related files together."""
        groups: Dict[str, List[MediaFile]] = {}
        for file in files:
            # Use filename without extension as group key
            key = file.path.stem
            if file.format == 'jpg':
                # Check if there's a corresponding ORF file
                orf_key = key
                if orf_key in groups and any(f.format == 'orf' for f in groups[orf_key]):
                    key += '_jpeg'  # Separate JPEG with ORF counterpart
            groups.setdefault(key, []).append(file)
        return [MediaGroup(files) for files in groups.values()]

    def _create_sessions(self, groups: List[MediaGroup]) -> List[Session]:
        """Create sessions from media groups."""
        # Sort groups by capture time
        valid_groups = [g for g in groups if g.capture_time]
        valid_groups.sort(key=lambda g: g.capture_time)
        
        sessions = []
        current_groups = []
        current_type = None
        
        for group in valid_groups:
            if not current_groups:
                current_groups = [group]
                current_type = SessionType.from_datetime(group.capture_time)
                continue

            time_gap = (group.capture_time - current_groups[-1].capture_time).total_seconds() / 3600
            new_type = SessionType.from_datetime(group.capture_time)

            if time_gap > self.session_gap.total_seconds() / 3600 or new_type != current_type:
                # End current session and start new one
                sessions.append(Session(current_groups, current_type))
                current_groups = [group]
                current_type = new_type
            else:
                current_groups.append(group)

        if current_groups:
            sessions.append(Session(current_groups, current_type))

        # Number sessions of the same type on the same day
        by_date_type: Dict[Tuple[str, SessionType], List[Session]] = {}
        for session in sessions:
            key = (session.start_time.date().isoformat(), session.type)
            by_date_type.setdefault(key, []).append(session)

        for sessions_list in by_date_type.values():
            if len(sessions_list) > 1:
                for i, session in enumerate(sessions_list, 1):
                    session.number = i

        return sessions

    def _copy_files(self, sessions: List[Session], progress: Progress, task_id: int) -> None:
        """Copy files to their destinations."""
        for session in sessions:
            session_dir = self.output_dir / session.format_name()
            session_dir.mkdir(parents=True, exist_ok=True)

            for group in session.groups:
                for file in group.files:
                    try:
                        # Determine destination directory
                        if file.is_video:
                            dest_dir = self.video_dir / session.format_name()
                        elif file.format == 'jpg' and group.get_by_format('orf'):
                            dest_dir = self.jpeg_dir / session.format_name()
                        else:
                            dest_dir = session_dir

                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest_path = dest_dir / file.output_name

                        # Copy file
                        shutil.copy2(file.path, dest_path)
                        logger.debug(f"Copied {file.path} to {dest_path}")
                        self._mark_file_imported(file)

                        # Create symlink for JPEGs with ORF counterparts
                        if file.format == 'jpg' and (orf_file := group.get_by_format('orf')):
                            orf_dest = session_dir / orf_file.output_name
                            link_path = dest_path.with_suffix('.orf')
                            try:
                                link_path.symlink_to(orf_dest)
                                logger.debug(f"Created symlink {link_path} -> {orf_dest}")
                            except Exception as e:
                                logger.error(f"Failed to create symlink: {e}")

                    except Exception as e:
                        logger.error(f"Failed to copy {file.path}: {e}")

                    progress.update(task_id, advance=1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Input directory (SD card)")
    parser.add_argument("output_dir", type=Path, help="Output directory")
    parser.add_argument(
        "--session-gap",
        type=float,
        default=DEFAULT_SESSION_GAP,
        help=f"Hours between sessions (default: {DEFAULT_SESSION_GAP})"
    )
    parser.add_argument(
        "--log-level",
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help="Set logging level"
    )
    parser.add_argument(
        "--force-reimport",
        action="store_true",
        help="Force reimport of previously imported files"
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Validate directories
    if not args.input_dir.exists():
        console.print(f"[red]Error:[/red] Input directory {args.input_dir} does not exist")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        organizer = MediaOrganizer(args.input_dir, args.output_dir, args.session_gap)
        if args.force_reimport:
            organizer._get_db().execute("DELETE FROM imported_files")
        organizer.organize()
        console.print("[green]✓[/green] Import completed successfully!")
    except KeyboardInterrupt:
        console.print("\n[yellow]Import cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
