"""Stub implementation of metadata extraction for testing."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from omtriage.metadata import MetadataExtractor
from omtriage.models import MediaFile, MediaMetadata


class StubMetadataExtractor:
    """Test stub for metadata extraction that uses file timestamps."""
    
    def extract_metadata(self, paths: List[Path]) -> Dict[str, MediaMetadata]:
        """Extract metadata from files using their timestamps.
        
        This stub implementation uses the file's modification time as the capture time,
        which is set explicitly in our test fixtures.
        
        Args:
            paths: List of paths to extract metadata from
            
        Returns:
            A dictionary mapping filenames to MediaMetadata objects
        """
        metadata_map = {}
        for path in paths:
            # Use the file's mtime as the capture time since we set it explicitly in tests
            capture_time = datetime.fromtimestamp(path.stat().st_mtime)
            metadata_map[path.name] = MediaMetadata(capture_time=capture_time)
            
        return metadata_map
