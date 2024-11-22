"""Constants used throughout the package."""

from pathlib import Path

SUPPORTED_FORMATS = {
    'images': {'orf', 'ori', 'jpg', 'jpeg'},
    'videos': {'mov', 'mp4'},
}

ALL_FORMATS = {fmt for formats in SUPPORTED_FORMATS.values() for fmt in formats}
AFTERNOON_HOUR = 14  # 2 PM
DEFAULT_SESSION_GAP = 3.0  # hours
EXIFTOOL_BATCH_SIZE = 100

# Database configuration
DEFAULT_DB_PATH = Path.home() / ".cache" / "omtriage" / "import_history.db"

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS imported_files (
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    creation_date TEXT NOT NULL,
    original_name TEXT NOT NULL,
    capture_time TEXT,
    import_time TEXT NOT NULL,
    PRIMARY KEY (filename, file_size, creation_date)
);
"""
