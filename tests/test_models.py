"""Test cases for data models."""

from datetime import datetime
from pathlib import Path

import pytest

from omtriage.models import MediaFile, MediaGroup, Session, SessionType


def test_session_type():
    """Test session type determination from datetime."""
    # Morning (AM)
    dt = datetime(2024, 1, 15, 10, 30)
    assert SessionType.from_datetime(dt) == SessionType.MORNING
    assert str(SessionType.from_datetime(dt)) == "AM"
    
    # Afternoon (PM)
    dt = datetime(2024, 1, 15, 15, 30)
    assert SessionType.from_datetime(dt) == SessionType.AFTERNOON
    assert str(SessionType.from_datetime(dt)) == "PM"


def test_media_file(mock_sd_card):
    """Test MediaFile initialization and properties."""
    # Create test file
    path = mock_sd_card / "test.ORF"
    path.write_bytes(b"x" * 1024)
    
    # Test basic properties
    media = MediaFile(path)
    assert media.format == "orf"
    assert media.file_size == 1024
    assert media.is_image
    assert not media.is_video
    
    # Test ORI -> ORF conversion
    path = mock_sd_card / "test.ORI"
    path.write_bytes(b"x" * 1024)
    media = MediaFile(path)
    assert media.format == "orf"
    assert media.output_name == "test.ORI.ORF"


def test_media_group(mock_sd_card):
    """Test MediaGroup functionality."""
    # Create test files
    files = []
    for ext in ["ORF", "JPG"]:
        path = mock_sd_card / f"test.{ext}"
        path.write_bytes(b"x" * 1024)
        files.append(MediaFile(path))
    
    # Set capture time for testing
    capture_time = datetime(2024, 1, 15, 10, 30)
    files[0].capture_time = capture_time
    
    # Test group properties
    group = MediaGroup(files)
    assert group.capture_time == capture_time
    assert group.get_by_format("orf") == files[0]
    assert group.get_by_format("jpg") == files[1]
    assert group.get_by_format("mov") is None


def test_session(mock_sd_card):
    """Test Session functionality."""
    # Create test files
    files = []
    for i, ext in enumerate(["ORF", "JPG"]):
        path = mock_sd_card / f"test{i}.{ext}"
        path.write_bytes(b"x" * 1024)
        media = MediaFile(path)
        media.capture_time = datetime(2024, 1, 15, 10, 30)
        files.append(media)
    
    # Create groups and session
    groups = [MediaGroup([files[0], files[1]])]
    session = Session(groups, SessionType.MORNING)
    
    # Test session properties
    assert session.start_time == datetime(2024, 1, 15, 10, 30)
    assert session.format_name() == "2024-01-15-AM"
    assert session.format_name("/output") == "/output/2024-01-15-AM"
    
    # Test session numbering
    session.number = 2
    assert session.format_name() == "2024-01-15-AM-2"
