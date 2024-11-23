"""Test fixtures for omtriage."""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.metadata_stub import StubMetadataExtractor


def create_media_files(
    camera_dir: Path,
    base_names: list[str],
    formats: list[str],
    base_time: datetime | None = None,
    time_increment: timedelta = timedelta(minutes=1),
) -> None:
    """Create test media files with timestamps.

    Args:
        camera_dir: Directory to create files in
        base_names: List of base names (e.g., ["_7164001", "_7164002"])
        formats: List of formats (e.g., ["JPG", "ORF"])
        base_time: Optional base time for files (defaults to current time)
        time_increment: Time increment between base names (default: 1 minute)
    """
    timestamp = base_time or datetime.now()

    for base_name in base_names:
        # Create all format variants with the same timestamp
        for fmt in formats:
            path = camera_dir / f"{base_name}.{fmt}"
            path.touch()
            os.utime(path, (timestamp.timestamp(), timestamp.timestamp()))

        # Increment timestamp for next base name
        timestamp += time_increment


@pytest.fixture
def metadata_extractor():
    """Provide a stub metadata extractor for testing."""
    yield StubMetadataExtractor()


@pytest.fixture
def basic_media_dir(tmp_path):
    """Create a simple media directory with a few test files.

    Returns:
        Path to input directory containing basic media files
    """
    camera_dir = tmp_path / "302OMSYS"
    camera_dir.mkdir()

    # Create a few simple test files
    base_time = datetime(2023, 11, 1, 10, 30)  # 10:30 AM
    files = [f"_7164{i:03d}" for i in range(1, 4)]
    create_media_files(camera_dir, files, ["ORF"], base_time)

    yield camera_dir


@pytest.fixture
def paired_media_dir(tmp_path):
    """Create a media directory with paired files (JPG+ORF).

    Returns:
        Path to input directory containing paired media files
    """
    camera_dir = tmp_path / "302OMSYS"
    camera_dir.mkdir()

    # Create paired JPG+ORF files
    base_time = datetime(2023, 11, 1, 10, 30)
    files = [f"_7164{i:03d}" for i in range(1, 4)]
    create_media_files(camera_dir, files, ["JPG", "ORF"], base_time)

    yield camera_dir


@pytest.fixture
def continuous_session_dir(tmp_path):
    """Create a media directory with a continuous session spanning AM/PM boundary.

    Returns:
        Path to input directory containing continuous session files
    """
    camera_dir = tmp_path / "302OMSYS"
    camera_dir.mkdir()

    # Create continuous session spanning 1:45 PM to 2:15 PM
    start_time = datetime(2023, 11, 1, 13, 45)
    files = [f"_7198{i:03d}" for i in range(461, 467)]
    create_media_files(camera_dir, files, ["ORF"], start_time, timedelta(minutes=5))

    yield camera_dir


@pytest.fixture
def multi_session_dir(tmp_path):
    """Create a media directory with multiple sessions across different days.

    Returns:
        Path to input directory containing multi-session files
    """
    camera_dir = tmp_path / "302OMSYS"
    camera_dir.mkdir()

    base_date = datetime(2023, 11, 1)

    # Morning session (10:30 AM)
    morning_time = base_date.replace(hour=10, minute=30)
    morning_files = [f"_7164{i:03d}" for i in range(1, 4)]
    create_media_files(camera_dir, morning_files, ["JPG", "ORF"], morning_time)

    # Afternoon session (2:45 PM)
    afternoon_time = base_date.replace(hour=14, minute=45)
    afternoon_files = [f"_7165{i:03d}" for i in range(190, 193)]
    create_media_files(camera_dir, afternoon_files, ["JPG", "ORF"], afternoon_time)

    # Next day morning (9:15 AM)
    next_day = base_date + timedelta(days=1)
    morning_time = next_day.replace(hour=9, minute=15)
    morning_files = [f"_7176{i:03d}" for i in range(557, 560)]
    create_media_files(camera_dir, morning_files, ["MOV"], morning_time)

    yield camera_dir
