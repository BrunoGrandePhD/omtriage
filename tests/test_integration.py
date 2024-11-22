"""Integration tests for the photo importer."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from omtriage.cli import import_files
from omtriage.database import ImportDatabase


def test_full_import_workflow(mock_sd_card, output_dir, mock_files, mock_exiftool):
    """Test complete import workflow with various file types."""
    # Run import
    import_files(mock_sd_card, output_dir)
    
    # Verify output structure
    assert (output_dir / "2024-01-15-AM").exists()
    assert (output_dir / "2024-01-15-PM").exists()
    assert (output_dir / "2024-01-16-AM").exists()
    
    # Check image organization
    am_session = output_dir / "2024-01-15-AM"
    assert (am_session / "images" / "P1150001.ORF").exists()
    assert (am_session / "images" / "P1150001.JPG").exists()
    assert (am_session / "videos" / "P1150002.MOV").exists()
    
    # Check database tracking
    db = ImportDatabase(output_dir)
    stats = db.get_import_stats()
    assert stats["total_files"] == len(mock_files)
    assert stats["unique_days"] == 2


def test_incremental_import(mock_sd_card, output_dir, mock_exiftool, create_mock_exif):
    """Test importing files in multiple batches."""
    # Create initial files
    base_time = datetime(2024, 1, 15, 10, 30)
    initial_files = [
        {
            "name": "P1150001.ORF",
            "time": base_time,
            "size": 1024
        },
        {
            "name": "P1150001.JPG",
            "time": base_time,
            "size": 512
        }
    ]
    
    # Create files and exif data
    for file_info in initial_files:
        path = mock_sd_card / file_info["name"]
        path.write_bytes(b"x" * file_info["size"])
        create_mock_exif(path, file_info["time"])
    
    # First import
    import_files(mock_sd_card, output_dir)
    
    # Add new files
    new_files = [
        {
            "name": "P1150002.MOV",
            "time": base_time + timedelta(minutes=30),
            "size": 2048
        }
    ]
    
    for file_info in new_files:
        path = mock_sd_card / file_info["name"]
        path.write_bytes(b"x" * file_info["size"])
        create_mock_exif(path, file_info["time"])
    
    # Second import
    import_files(mock_sd_card, output_dir)
    
    # Verify results
    am_session = output_dir / "2024-01-15-AM"
    assert (am_session / "images" / "P1150001.ORF").exists()
    assert (am_session / "images" / "P1150001.JPG").exists()
    assert (am_session / "videos" / "P1150002.MOV").exists()
    
    # Check database
    db = ImportDatabase(output_dir)
    stats = db.get_import_stats()
    assert stats["total_files"] == len(initial_files) + len(new_files)


def test_reimport_with_modifications(
    mock_sd_card, output_dir, mock_files, mock_exiftool, create_mock_exif
):
    """Test reimporting with modified files."""
    # Initial import
    import_files(mock_sd_card, output_dir)
    
    # Modify a file
    test_file = mock_sd_card / "P1150001.ORF"
    test_file.write_bytes(b"x" * 2048)  # Change size
    
    # Reimport with force
    import_files(mock_sd_card, output_dir, force_reimport=True)
    
    # Check if file was updated
    imported_file = output_dir / "2024-01-15-AM/images/P1150001.ORF"
    assert imported_file.stat().st_size == 2048


def test_error_recovery(mock_sd_card, output_dir, mock_exiftool, create_mock_exif):
    """Test recovery from errors during import."""
    # Create valid file
    valid_file = mock_sd_card / "valid.ORF"
    valid_file.write_bytes(b"x" * 1024)
    create_mock_exif(
        valid_file,
        datetime(2024, 1, 15, 10, 30)
    )
    
    # Create file that will cause metadata extraction to fail
    invalid_file = mock_sd_card / "invalid.ORF"
    invalid_file.write_bytes(b"x" * 1024)
    create_mock_exif(invalid_file, None)  # Invalid date
    
    # Import should continue despite error
    import_files(mock_sd_card, output_dir)
    
    # Valid file should be imported
    assert (
        output_dir / "2024-01-15-AM/images/valid.ORF"
    ).exists()
