"""Test cases for file organization."""

from datetime import datetime, timedelta

import pytest

from omtriage.models import MediaFile, MediaGroup, Session, SessionType
from omtriage.organizer import (
    group_files,
    organize_sessions,
    create_session_structure
)


def test_group_files(mock_sd_card, mock_files):
    """Test grouping of related files."""
    # Create MediaFile objects
    media_files = [
        MediaFile(mock_sd_card / file_info["name"])
        for file_info in mock_files
    ]
    
    # Group files
    groups = group_files(media_files)
    
    # Verify grouping
    assert len(groups) == 4  # P1150001, P1150002, P1150003, P1160001
    
    # Check RAW+JPEG pair
    raw_jpeg_group = next(g for g in groups if len(g.files) == 2)
    assert any(f.format == "orf" for f in raw_jpeg_group.files)
    assert any(f.format == "jpg" for f in raw_jpeg_group.files)
    
    # Check video file
    video_group = next(g for g in groups if g.files[0].is_video)
    assert len(video_group.files) == 1
    assert video_group.files[0].format == "mov"


def test_organize_sessions(mock_sd_card, mock_files):
    """Test session organization."""
    # Create MediaFile objects and groups
    media_files = [
        MediaFile(mock_sd_card / file_info["name"])
        for file_info in mock_files
    ]
    
    # Set capture times
    for media_file, file_info in zip(media_files, mock_files):
        media_file.capture_time = file_info["time"]
    
    # Group and organize
    groups = group_files(media_files)
    sessions = organize_sessions(groups)
    
    # Verify sessions
    assert len(sessions) == 3  # Jan 15 AM, Jan 15 PM, Jan 16 AM
    
    # Check session types
    assert sessions[0].type == SessionType.MORNING
    assert sessions[1].type == SessionType.AFTERNOON
    assert sessions[2].type == SessionType.MORNING
    
    # Check file distribution
    assert len(sessions[0].groups) == 2  # RAW+JPEG pair and video
    assert len(sessions[1].groups) == 1  # RAW+JPEG pair
    assert len(sessions[2].groups) == 1  # RAW+JPEG pair


def test_organize_sessions_custom_gap():
    """Test session organization with custom time gap."""
    # Create test data
    files = []
    base_time = datetime(2024, 1, 15, 10, 30)
    
    # Create files 2 hours apart
    for i in range(3):
        media = MediaFile(Path(f"test{i}.ORF"))
        media.capture_time = base_time + timedelta(hours=2 * i)
        files.append(media)
    
    groups = [MediaGroup([f]) for f in files]
    
    # With 3-hour gap (default)
    sessions = organize_sessions(groups)
    assert len(sessions) == 1  # All files in one session
    
    # With 1-hour gap
    sessions = organize_sessions(groups, session_gap=1.0)
    assert len(sessions) == 3  # Each file in its own session


def test_create_session_structure(mock_sd_card, output_dir, mock_files):
    """Test creation of session directory structure."""
    # Create MediaFile objects for morning session
    morning_files = [
        MediaFile(mock_sd_card / info["name"])
        for info in mock_files[:3]  # First three files (RAW+JPEG pair and video)
    ]
    
    # Set capture times
    for media_file, file_info in zip(morning_files, mock_files[:3]):
        media_file.capture_time = file_info["time"]
    
    # Create session
    groups = group_files(morning_files)
    session = Session(groups, SessionType.MORNING)
    
    # Create directory structure
    create_session_structure(session, output_dir)
    
    # Verify directory structure
    session_dir = output_dir / "2024-01-15-AM"
    assert session_dir.exists()
    assert (session_dir / "images").exists()
    assert (session_dir / "videos").exists()
    
    # Verify files
    image_dir = session_dir / "images"
    video_dir = session_dir / "videos"
    
    assert (image_dir / "P1150001.ORF").exists()
    assert (image_dir / "P1150001.JPG").exists()
    assert (video_dir / "P1150002.MOV").exists()


def test_create_session_structure_dry_run(mock_sd_card, output_dir, mock_files):
    """Test dry run mode of directory structure creation."""
    # Create MediaFile objects
    media_files = [
        MediaFile(mock_sd_card / info["name"])
        for info in mock_files[:2]  # Just RAW+JPEG pair
    ]
    
    # Set capture times
    for media_file, file_info in zip(media_files, mock_files[:2]):
        media_file.capture_time = file_info["time"]
    
    # Create session
    groups = group_files(media_files)
    session = Session(groups, SessionType.MORNING)
    
    # Create directory structure in dry run mode
    create_session_structure(session, output_dir, dry_run=True)
    
    # Verify nothing was created
    session_dir = output_dir / "2024-01-15-AM"
    assert not session_dir.exists()
