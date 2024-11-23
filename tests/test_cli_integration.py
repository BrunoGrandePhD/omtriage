"""Integration tests for the CLI module."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from omtriage.cli import import_files


def test_basic_import(basic_media_dir, tmp_path, metadata_extractor):
    """Test basic media import functionality."""
    output_dir = tmp_path / "output"

    # Run import
    import_files(
        input_dir=basic_media_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )

    # Verify files were imported
    assert (output_dir / "images" / "2023-11-01-AM").exists()


def test_reimport_prevention(basic_media_dir, tmp_path, metadata_extractor):
    """Test that files are not reimported if already present."""
    output_dir = tmp_path / "output"

    # Run import twice
    import_files(
        input_dir=basic_media_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )
    # Count number of files before the second import
    n_files_before = len([p for p in output_dir.rglob("*") if p.is_file()])

    import_files(
        input_dir=basic_media_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )
    n_files_after = len([p for p in output_dir.rglob("*") if p.is_file()])

    # Verify no files were reimported
    assert n_files_before == n_files_after


def test_dry_run(basic_media_dir, tmp_path, metadata_extractor):
    """Test dry run mode."""
    output_dir = tmp_path / "output"

    # Run import in dry run mode
    import_files(
        input_dir=basic_media_dir.parent,
        output_dir=output_dir,
        dry_run=True,
        metadata_extractor=metadata_extractor,
    )

    # Verify no files were actually imported
    assert not output_dir.exists() or not any(output_dir.iterdir())


def test_paired_files(paired_media_dir, tmp_path, metadata_extractor):
    """Test handling of paired files (e.g., JPG+ORF)."""
    output_dir = tmp_path / "output"

    # Run import
    import_files(
        input_dir=paired_media_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )

    input_jpg_files = list(paired_media_dir.rglob("*.JPG"))
    output_jpg_files = list(output_dir.rglob("*.JPG"))
    assert len(input_jpg_files) == len(output_jpg_files)
    assert all("jpeg_duplicates" in str(f) for f in output_jpg_files)


def test_continuous_session(continuous_session_dir, tmp_path, metadata_extractor):
    """Test handling of continuous sessions across AM/PM boundary."""
    output_dir = tmp_path / "output"

    # Run import
    import_files(
        input_dir=continuous_session_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )

    session_dirs = list((output_dir / "images").glob("*/"))
    assert len(session_dirs) == 1


def test_multiple_sessions(multi_session_dir, tmp_path, metadata_extractor):
    """Test handling of multiple sessions in different days."""
    output_dir = tmp_path / "output"

    # Run import
    import_files(
        input_dir=multi_session_dir.parent,
        output_dir=output_dir,
        metadata_extractor=metadata_extractor,
    )

    session_dirs = list((output_dir / "images").glob("*/"))
    assert len(session_dirs) == 3
