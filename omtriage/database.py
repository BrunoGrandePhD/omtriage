"""Database management for tracking imported files."""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from .constants import DB_SCHEMA, DEFAULT_DB_PATH
from .models import MediaFile

logger = logging.getLogger(__name__)


class ImportDatabase:
    """Manages the database of imported files."""

    def __init__(self, output_dir: Optional[Path] = None, db_path: Optional[Union[Path, str]] = None):
        """Initialize database.
        
        Args:
            output_dir: Legacy parameter for backward compatibility
            db_path: Custom path for the database file. If not provided,
                    uses ~/.omtriage/import_history.db
        """
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            self.db_path = DEFAULT_DB_PATH
            
        # Create parent directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the SQLite database for tracking imported files."""
        with self._get_db() as conn:
            conn.executescript(DB_SCHEMA)

    @contextmanager
    def _get_db(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_file_imported(self, file: MediaFile) -> bool:
        """Check if a file has already been imported."""
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM imported_files 
                WHERE filename = ? AND file_size = ? AND creation_date = ?
                """,
                (
                    file.path.name,
                    file.file_size,
                    file.creation_date.isoformat()
                )
            )
            return cursor.fetchone() is not None

    def mark_file_imported(self, file: MediaFile) -> None:
        """Mark a file as imported in the database."""
        with self._get_db() as conn:
            conn.execute(
                """
                INSERT INTO imported_files 
                (filename, file_size, creation_date, original_name, capture_time, import_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file.path.name,
                    file.file_size,
                    file.creation_date.isoformat(),
                    file.path.name,
                    file.capture_time.isoformat() if file.capture_time else None,
                    datetime.now().isoformat()
                )
            )

    def clear_history(self) -> None:
        """Clear all import history."""
        with self._get_db() as conn:
            conn.execute("DELETE FROM imported_files")

    def get_import_stats(self) -> dict:
        """Get statistics about imported files."""
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_files,
                    SUM(CASE WHEN capture_time IS NOT NULL THEN 1 ELSE 0 END) as files_with_metadata,
                    COUNT(DISTINCT strftime('%Y-%m-%d', capture_time)) as unique_days,
                    SUM(file_size) as total_size
                FROM imported_files
                """
            )
            row = cursor.fetchone()
            return {
                'total_files': row[0],
                'files_with_metadata': row[1],
                'unique_days': row[2],
                'total_size': row[3]
            }
