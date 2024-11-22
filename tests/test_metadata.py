"""Test cases for metadata extraction."""

import json
from datetime import datetime

import pytest

from omtriage.metadata import extract_metadata
from omtriage.models import MediaFile


def test_extract_metadata(mock_sd_card, mock_exiftool, mock_files):
    """Test metadata extraction from files."""
    # Create MediaFile objects
    media_files = [
        MediaFile(mock_sd_card / file_info["name"]) for file_info in mock_files
    ]

    # Extract metadata
    extract_metadata(media_files)

    # Verify capture times
    for media_file, file_info in zip(media_files, mock_files):
        assert media_file.capture_time == file_info["time"]


def test_extract_metadata_empty_list(mock_exiftool):
    """Test metadata extraction with empty file list."""
    extract_metadata([])  # Should not raise any errors


def test_extract_metadata_batch_processing(mock_sd_card, mock_exiftool, create_mock_exif):
    """Test metadata extraction with batch processing."""
    # Create many files to test batch processing
    files = []
    base_time = datetime(2024, 1, 15, 10, 30)

    for i in range(150):  # More than EXIFTOOL_BATCH_SIZE
        path = mock_sd_card / f"test{i:04d}.ORF"
        path.write_bytes(b"x" * 1024)
        create_mock_exif(path, base_time)
        files.append(MediaFile(path))

    # Extract metadata
    extract_metadata(files)

    # Verify all files were processed
    for file in files:
        assert file.capture_time == base_time


def test_extract_metadata_missing_data(mock_sd_card, mock_exiftool):
    """Test metadata extraction with missing EXIF data."""
    # Create file without EXIF data
    path = mock_sd_card / "no_exif.ORF"
    path.write_bytes(b"x" * 1024)
    media_file = MediaFile(path)

    # Extract metadata
    extract_metadata([media_file])

    # Should fall back to creation time
    assert media_file.capture_time == media_file.creation_date


def test_extract_metadata_invalid_date(mock_sd_card, mock_exiftool):
    """Test metadata extraction with invalid date format."""
    path = mock_sd_card / "invalid_date.ORF"
    path.write_bytes(b"x" * 1024)

    # Create invalid EXIF data
    exif_data = [
        {
            "SourceFile": str(path),
            "DateTimeOriginal": "invalid-date-format",
            "CreateDate": "invalid-date-format",
        }
    ]

    # Write mock exiftool output
    exif_path = path.parent / f"{path.name}_exif.json"
    exif_path.write_text(json.dumps(exif_data))

    media_file = MediaFile(path)
    extract_metadata([media_file])

    # Should fall back to creation time
    assert media_file.capture_time == media_file.creation_date
