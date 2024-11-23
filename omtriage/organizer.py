"""Media file organization and grouping logic."""

import logging
import os
import shutil
from datetime import datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .constants import AFTERNOON_HOUR, DEFAULT_SESSION_GAP
from .models import MediaFile, MediaGroup, Session, SessionType

logger = logging.getLogger(__name__)


def group_files(files: List[MediaFile]) -> List[MediaGroup]:
    """Group related files (e.g., ORF+JPEG pairs)."""
    logger.debug(f"Grouping {len(files)} files")

    # Sort files by name without extension to group related files
    sorted_files = sorted(files, key=lambda f: f.path.stem)
    groups: List[MediaGroup] = []

    for key, related_files in groupby(sorted_files, key=lambda f: f.path.stem):
        logger.debug(f"Created new group for {key}")
        groups.append(MediaGroup(list(related_files)))

    logger.debug(f"Created {len(groups)} file groups")
    return groups


def organize_sessions(
    groups: List[MediaGroup], session_gap: float = DEFAULT_SESSION_GAP
) -> List[Session]:
    """Organize media groups into sessions based on capture time gaps."""
    logger.debug(
        f"Organizing {len(groups)} groups into sessions with {session_gap} hour gap"
    )

    if not groups:
        logger.debug("No groups to organize")
        return []

    sorted_groups = sorted(groups, key=lambda g: g.capture_time)
    logger.debug(f"Sorted {len(sorted_groups)} groups by capture time")

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

    logger.debug(f"Created {len(sessions)} sessions")
    # Number sessions on the same day
    _number_sessions(sessions)

    return sessions


def _number_sessions(sessions: List[Session]) -> None:
    """Number sessions that occur on the same day."""
    by_date: Dict[str, List[Session]] = {}
    for session in sessions:
        date = session.start_time.date().isoformat()
        by_date.setdefault(date, []).append(session)

    for date_sessions in by_date.values():
        if len(date_sessions) > 1:
            for i, session in enumerate(date_sessions, 1):
                session.number = i


def create_session_structure(
    session: Session, base_dir: Path, dry_run: bool = False
) -> None:
    """Create directory structure for a session."""
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

    if not dry_run:
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
                    logger.debug(
                        f"Found JPEG+ORF pair: {file.path.name} and {orf_file.path.name}"
                    )
                else:
                    target_dir = image_dir

            source = file.path
            target = target_dir / source.name

            if not dry_run:
                logger.debug(f"Copying {source.name} to {target}")
                if target.exists():
                    target.unlink()
                target.hardlink_to(source)

                # Create symbolic link to ORF file if this is a JPEG duplicate
                if file is jpg_file and orf_file:
                    orf_target = image_dir / orf_file.path.name
                    symlink_target = jpeg_dir / f"original_{orf_file.path.name}"
                    if symlink_target.exists():
                        symlink_target.unlink()
                    # Create relative symlink
                    rel_path = os.path.relpath(orf_target, jpeg_dir)
                    symlink_target.symlink_to(rel_path)
                    logger.debug(
                        f"Created symbolic link from {symlink_target} to {rel_path}"
                    )
