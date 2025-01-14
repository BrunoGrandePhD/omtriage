"""Media file organization and grouping logic."""

import logging
import os
import shutil
from itertools import groupby
from pathlib import Path
from typing import Dict, List

from .constants import AFTERNOON_HOUR, DEFAULT_SESSION_GAP
from .models import MediaFile, MediaGroup, Session, SessionType

logger = logging.getLogger(__name__)


def group_files(files: List[MediaFile]) -> List[MediaGroup]:
    """Group related files (e.g., ORF+JPEG pairs)."""
    logger.info(f"Grouping {len(files)} files by capture (e.g., OFR+JPEG pairs)")

    # Sort files by name without extension to group related files
    sorted_files = sorted(files, key=lambda f: f.path.stem)
    groups: List[MediaGroup] = []

    for key, related_files in groupby(sorted_files, key=lambda f: f.path.stem):
        logger.debug(f"Created new group for {key}")
        groups.append(MediaGroup(list(related_files)))

    logger.info(f"Identified {len(groups)} captures")
    return groups


def organize_sessions(
    groups: List[MediaGroup], session_gap: float = DEFAULT_SESSION_GAP
) -> List[Session]:
    """Organize media groups into sessions based on capture time gaps."""
    if not groups:
        logger.debug("No groups to organize")
        return []

    logger.info(f"Organizing {len(groups)} captures into sessions")
    sorted_groups = sorted(groups, key=lambda g: g.capture_time)
    logger.debug(f"Sorted {len(sorted_groups)} captures by capture time")

    sessions: List[Session] = []
    current_groups: List[MediaGroup] = [sorted_groups[0]]
    current_type = SessionType.from_datetime(sorted_groups[0].capture_time)
    current_date = sorted_groups[0].capture_time.date()

    for group in sorted_groups[1:]:
        prev_time = current_groups[-1].capture_time
        curr_time = group.capture_time
        time_diff = (curr_time - prev_time).total_seconds() / 3600
        curr_type = SessionType.from_datetime(curr_time)
        curr_date = curr_time.date()

        # Start new session if:
        # 1. Date changes
        # 2. Time gap exceeds threshold
        if curr_date != current_date or time_diff > session_gap:
            logger.debug(
                f"Found session gap of {time_diff:.1f} hours between {prev_time} and {curr_time}"
            )
            sessions.append(Session(current_groups, current_type))
            current_groups = []
            current_type = curr_type
            current_date = curr_date

        current_groups.append(group)

    # Add final session
    if current_groups:
        sessions.append(Session(current_groups, current_type))

    logger.info(f"Identified {len(sessions)} sessions")
    # Number sessions on the same day
    _number_sessions(sessions)

    return sessions


def _number_sessions(sessions: List[Session]) -> None:
    """Number sessions that occur on the same day."""
    by_date_and_type: Dict[tuple[str, SessionType], List[Session]] = {}
    for session in sessions:
        date = session.start_time.date().isoformat()
        key = (date, session.type)
        by_date_and_type.setdefault(key, []).append(session)

    for date_sessions in by_date_and_type.values():
        if len(date_sessions) > 1:
            for i, session in enumerate(date_sessions, 1):
                session.number = i


def _are_on_same_device(path1: Path, path2: Path) -> bool:
    """Check if two paths are on the same device/disk."""
    # Ensure parent directory exists for path2 since it might not exist yet
    path2_stat = os.stat(path2.parent) if not path2.exists() else os.stat(path2)
    return os.stat(path1).st_dev == path2_stat.st_dev


def create_session_structure(
    session: Session,
    base_dir: Path,
    use_hardlinks: bool = False,
    overwrite: bool = False,
) -> None:
    """Create directory structure for a session.

    Args:
        session: Session to create structure for
        base_dir: Base directory for organizing files
        use_hardlinks: If True, use hard links, if False use copies.
        overwrite: If True, overwrite existing files
    """
    logger = logging.getLogger(__name__)
    logger.debug(f"Creating session structure in {base_dir}")

    # Create session directory with date and time info
    date_str = session.start_time.strftime("%Y-%m-%d")
    am_pm = "AM" if session.start_time.hour < AFTERNOON_HOUR else "PM"
    session_name = f"{date_str}-{am_pm}"
    logger.debug(f"Session directory name will be: {session_name}")

    # Create main directories
    image_dir = base_dir / "images" / session_name
    video_dir = base_dir / "videos" / session_name
    jpeg_dir = base_dir / "images" / "jpeg_duplicates" / session_name

    image_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    jpeg_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created directories: {image_dir}, {video_dir}, and {jpeg_dir}")

    # Copy files to appropriate directories
    for group in session.groups:
        # Check for ORF+JPEG pairs
        orf_file = group.get_by_format("orf")
        jpg_file = group.get_by_format("jpg") or group.get_by_format("jpeg")

        for file in group.files:
            if file.is_video:
                target_dir = video_dir
            else:
                # If this is a JPEG and we have an ORF file, put it in the jpeg_duplicates folder
                if file is jpg_file and orf_file:
                    target_dir = jpeg_dir
                    logger.debug(f"Found JPEG+ORF pair: {file.path} and {orf_file.path}")
                else:
                    target_dir = image_dir

            source = file.path
            target = target_dir / file.output_name

            if target.exists() and overwrite:
                logger.debug(f"Overwriting file: {target}")
                target.unlink()

            target_dir.mkdir(parents=True, exist_ok=True)
            if use_hardlinks:
                logger.debug(f"Hardlinking: {source.name} -> {target}")
                target.hardlink_to(source)
            else:
                logger.debug(f"Copying: {source.name} -> {target}")
                shutil.copy2(source, target)

        # Clean up empty directories
        # Iterate over directories in reverse order to delete nested directories first
        for dirpath in sorted(base_dir.rglob("*/"), key=lambda p: p.parts, reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                dirpath.rmdir()
