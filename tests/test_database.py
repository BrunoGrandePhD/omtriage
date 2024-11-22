"""Test cases for import database."""

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from photo_importer.database import ImportDatabase
from photo_importer.models import MediaFile


def test_database_initialization(output_dir):
    """Test database creation and schema initialization."""
    db = ImportDatabase(output_dir)
    assert db.db_path.exists()
    
    # Check schema
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='imported_files'
            """
        )
        assert cursor.fetchone() is not None


def test_mark_and_check_imported(mock_sd_card, output_dir):
    """Test marking and checking imported files."""
    # Create test file
    path = mock_sd_card / "test.ORF"
    path.write_bytes(b"x" * 1024)
    media = MediaFile(path)
    media.capture_time = datetime(2024, 1, 15, 10, 30)
    
    # Initialize database
    db = ImportDatabase(output_dir)
    
    # Check initial state
    assert not db.is_file_imported(media)
    
    # Mark as imported
    db.mark_file_imported(media)
    assert db.is_file_imported(media)


def test_import_deduplication(mock_sd_card, output_dir):
    """Test file deduplication based on composite key."""
    # Create original file
    path = mock_sd_card / "test.ORF"
    path.write_bytes(b"x" * 1024)
    original = MediaFile(path)
    
    # Create duplicate with same properties
    dup_path = mock_sd_card / "duplicate.ORF"
    dup_path.write_bytes(b"x" * 1024)  # Same size
    duplicate = MediaFile(dup_path)
    
    # Initialize database
    db = ImportDatabase(output_dir)
    
    # Mark original as imported
    db.mark_file_imported(original)
    
    # Duplicate should not be detected as imported (different name)
    assert not db.is_file_imported(duplicate)
    
    # Create another duplicate with same name
    same_name_path = mock_sd_card / "test.ORF"
    same_name_path.write_bytes(b"x" * 2048)  # Different size
    same_name = MediaFile(same_name_path)
    
    # Should not be detected as imported (different size)
    assert not db.is_file_imported(same_name)


def test_clear_history(mock_sd_card, output_dir):
    """Test clearing import history."""
    # Create test file
    path = mock_sd_card / "test.ORF"
    path.write_bytes(b"x" * 1024)
    media = MediaFile(path)
    
    # Initialize database and mark file as imported
    db = ImportDatabase(output_dir)
    db.mark_file_imported(media)
    assert db.is_file_imported(media)
    
    # Clear history
    db.clear_history()
    assert not db.is_file_imported(media)


def test_import_stats(mock_sd_card, output_dir, mock_files):
    """Test import statistics."""
    # Create MediaFile objects
    media_files = [
        MediaFile(mock_sd_card / file_info["name"])
        for file_info in mock_files
    ]
    
    # Set capture times
    for media_file, file_info in zip(media_files, mock_files):
        media_file.capture_time = file_info["time"]
    
    # Initialize database and import files
    db = ImportDatabase(output_dir)
    for media in media_files:
        db.mark_file_imported(media)
    
    # Check statistics
    stats = db.get_import_stats()
    assert stats["total_files"] == len(mock_files)
    assert stats["files_with_metadata"] == len(mock_files)  # All have capture times
    assert stats["unique_days"] == 2  # Jan 15 and Jan 16
    assert stats["total_size"] == sum(f["size"] for f in mock_files)
