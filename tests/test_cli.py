"""Test cases for command-line interface."""

import logging
from pathlib import Path

import pytest
from rich.console import Console

from photo_importer.cli import find_media_files, import_files, setup_logging


def test_setup_logging():
    """Test logging configuration."""
    setup_logging("DEBUG")
    logger = logging.getLogger()
    assert logger.level == logging.DEBUG
    
    setup_logging("INFO")
    assert logger.level == logging.INFO


def test_find_media_files(mock_sd_card, mock_files):
    """Test finding media files in directory."""
    files = find_media_files(mock_sd_card)
    
    # Check number of files
    assert len(files) == len(mock_files)
    
    # Check file types
    extensions = {f.format for f in files}
    assert "orf" in extensions
    assert "jpg" in extensions
    assert "mov" in extensions


def test_find_media_files_empty_dir(temp_dir):
    """Test finding media files in empty directory."""
    empty_dir = temp_dir / "empty"
    empty_dir.mkdir()
    files = find_media_files(empty_dir)
    assert len(files) == 0


def test_import_files_basic(mock_sd_card, output_dir, mock_files, mock_exiftool):
    """Test basic file import functionality."""
    import_files(mock_sd_card, output_dir)
    
    # Check output structure
    assert (output_dir / "2024-01-15-AM").exists()
    assert (output_dir / "2024-01-15-PM").exists()
    assert (output_dir / "2024-01-16-AM").exists()
    
    # Check database
    assert (output_dir / ".import_history.db").exists()


def test_import_files_force_reimport(
    mock_sd_card, output_dir, mock_files, mock_exiftool
):
    """Test force reimport option."""
    # First import
    import_files(mock_sd_card, output_dir)
    
    # Second import with force
    import_files(mock_sd_card, output_dir, force_reimport=True)
    
    # Files should be reimported
    stats_path = output_dir / ".import_history.db"
    assert stats_path.exists()


def test_import_files_dry_run(mock_sd_card, output_dir, mock_files, mock_exiftool):
    """Test dry run mode."""
    import_files(mock_sd_card, output_dir, dry_run=True)
    
    # Check that no files were created
    assert not list(output_dir.glob("*"))
    assert not (output_dir / ".import_history.db").exists()


def test_import_files_custom_session_gap(
    mock_sd_card, output_dir, mock_files, mock_exiftool
):
    """Test custom session gap."""
    # Import with 1-hour gap
    import_files(mock_sd_card, output_dir, session_gap=1.0)
    
    # Should create more sessions due to smaller gap
    sessions = list(output_dir.glob("2024-01-15-*"))
    assert len(sessions) > 2  # More than default


def test_import_files_invalid_input_dir(output_dir):
    """Test handling of invalid input directory."""
    with pytest.raises(SystemExit):
        import_files(Path("/nonexistent"), output_dir)


def test_import_files_no_media_files(temp_dir, output_dir):
    """Test handling of directory with no media files."""
    empty_dir = temp_dir / "empty"
    empty_dir.mkdir()
    import_files(empty_dir, output_dir)
    
    # No files should be created
    assert not list(output_dir.glob("*"))
    assert not (output_dir / ".import_history.db").exists()
