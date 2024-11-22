"""Media file organization and grouping logic."""

import logging
from datetime import datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .constants import DEFAULT_SESSION_GAP
from .models import MediaFile, MediaGroup, Session, SessionType

logger = logging.getLogger(__name__)


def group_files(files: List[MediaFile]) -> List[MediaGroup]:
    """Group related files (e.g., ORF+JPEG pairs)."""
    # Sort files by name without extension to group related files
    sorted_files = sorted(files, key=lambda f: f.path.stem)
    groups: List[MediaGroup] = []

    for stem, related_files in groupby(sorted_files, key=lambda f: f.path.stem):
        groups.append(MediaGroup(list(related_files)))

    return groups


def organize_sessions(
    groups: List[MediaGroup], session_gap: float = DEFAULT_SESSION_GAP
) -> List[Session]:
    """Organize media groups into sessions based on capture time gaps."""
    if not groups:
        return []

    # Sort groups by capture time
    valid_groups = [g for g in groups if g.capture_time]
    if not valid_groups:
        logger.warning("No groups with valid capture times found")
        return []

    sorted_groups = sorted(valid_groups, key=lambda g: g.capture_time)
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
            sessions.append(Session(current_groups, current_type))
            current_groups = []
            current_type = curr_type
            current_date = curr_date

        current_groups.append(group)

    # Add final session
    if current_groups:
        sessions.append(Session(current_groups, current_type))

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
    session_dir = base_dir / session.format_name()
    image_dir = session_dir / "images"
    video_dir = session_dir / "videos"

    if not dry_run:
        session_dir.mkdir(parents=True, exist_ok=True)
        image_dir.mkdir(exist_ok=True)
        video_dir.mkdir(exist_ok=True)

    for group in session.groups:
        for file in group.files:
            if file.is_image:
                target_dir = image_dir
            elif file.is_video:
                target_dir = video_dir
            else:
                logger.warning(f"Unsupported file type: {file.path}")
                continue

            target_path = target_dir / file.output_name
            if not dry_run:
                if target_path.exists():
                    target_path.unlink()
                target_path.hardlink_to(file.path)
