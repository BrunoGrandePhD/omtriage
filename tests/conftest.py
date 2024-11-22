"""Test configuration and fixtures."""

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pytest


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def mock_sd_card(temp_dir):
    """Create a mock SD card directory with sample files."""
    sd_dir = temp_dir / "DCIM" / "100OLYMP"
    sd_dir.mkdir(parents=True)
    return sd_dir


@pytest.fixture
def output_dir(temp_dir):
    """Create a temporary output directory."""
    out_dir = temp_dir / "output"
    out_dir.mkdir()
    return out_dir


@pytest.fixture
def mock_files(mock_sd_card):
    """Create mock media files with different timestamps."""
    files: List[Dict] = []
    base_time = datetime(2024, 1, 15, 10, 30)  # 10:30 AM
    
    # Morning session (10:30 AM)
    files.extend([
        {
            "name": "P1150001.ORF",
            "time": base_time,
            "size": 1024
        },
        {
            "name": "P1150001.JPG",
            "time": base_time,
            "size": 512
        },
        {
            "name": "P1150002.MOV",
            "time": base_time + timedelta(minutes=5),
            "size": 2048
        }
    ])
    
    # Afternoon session (3:30 PM)
    base_time = datetime(2024, 1, 15, 15, 30)
    files.extend([
        {
            "name": "P1150003.ORF",
            "time": base_time,
            "size": 1024
        },
        {
            "name": "P1150003.JPG",
            "time": base_time,
            "size": 512
        }
    ])
    
    # Next day morning (9:30 AM)
    base_time = datetime(2024, 1, 16, 9, 30)
    files.extend([
        {
            "name": "P1160001.ORF",
            "time": base_time,
            "size": 1024
        },
        {
            "name": "P1160001.JPG",
            "time": base_time,
            "size": 512
        }
    ])
    
    # Create the files
    for file_info in files:
        path = mock_sd_card / file_info["name"]
        path.write_bytes(b"x" * file_info["size"])
        # Create mock exiftool output
        _create_mock_exif(path, file_info["time"])
    
    return files


def _create_mock_exif(file_path: Path, capture_time: datetime):
    """Create mock exiftool output for a file."""
    exif_data = [{
        "SourceFile": str(file_path),
        "DateTimeOriginal": capture_time.strftime("%Y:%m:%d %H:%M:%S"),
        "CreateDate": capture_time.strftime("%Y:%m:%d %H:%M:%S")
    }]
    
    # Write mock exiftool output
    exif_path = file_path.parent / f"{file_path.name}_exif.json"
    exif_path.write_text(json.dumps(exif_data))


@pytest.fixture
def mock_exiftool(monkeypatch):
    """Mock exiftool command to use our mock data."""
    def mock_run(cmd, *args, **kwargs):
        if cmd[0] != "exiftool":
            return subprocess.run(cmd, *args, **kwargs)
        
        # Parse file paths from command
        files = [Path(arg) for arg in cmd if not arg.startswith("-")]
        
        # Collect mock exif data
        all_data = []
        for file in files:
            exif_path = file.parent / f"{file.name}_exif.json"
            if exif_path.exists():
                all_data.extend(json.loads(exif_path.read_text()))
        
        # Create mock CompletedProcess
        return subprocess.CompletedProcess(
            cmd, 0, 
            stdout=json.dumps(all_data),
            stderr=""
        )
    
    monkeypatch.setattr(subprocess, "run", mock_run)


@pytest.fixture(autouse=True)
def cleanup(request, temp_dir):
    """Clean up temporary files after each test."""
    def cleanup_files():
        shutil.rmtree(temp_dir)
    request.addfinalizer(cleanup_files)
