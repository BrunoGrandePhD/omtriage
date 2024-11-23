"""Metadata extraction from media files."""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Protocol

from .constants import EXIFTOOL_BATCH_SIZE
from .models import MediaFile, MediaMetadata

logger = logging.getLogger(__name__)


class MetadataExtractor(Protocol):
    """Protocol for metadata extraction."""

    def extract_metadata(self, paths: List[Path]) -> Dict[str, MediaMetadata]:
        """Extract metadata from a batch of files and return a map of filename to metadata."""
        ...


class MediaFileFactory:
    """Factory for creating MediaFile objects with metadata."""

    def __init__(self, extractor: MetadataExtractor):
        """Initialize factory with a metadata extractor."""
        self._extractor = extractor
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized MediaFileFactory with {extractor.__class__.__name__}")

    def create_media_files(self, paths: List[Path]) -> List[MediaFile]:
        """Create MediaFile objects with extracted metadata."""
        self.logger.debug(f"Creating MediaFile objects for {len(paths)} paths")
        if not paths:
            self.logger.info("No paths provided, returning empty list")
            return []

        media_files = []
        # Process paths in batches to avoid command line length limits
        for i in range(0, len(paths), EXIFTOOL_BATCH_SIZE):
            batch_paths = paths[i : i + EXIFTOOL_BATCH_SIZE]
            self.logger.debug(f"Processing batch of {len(batch_paths)} paths")
            metadata_map = self._extractor.extract_metadata(batch_paths)

            # Create MediaFile objects with metadata
            for path in batch_paths:
                try:
                    media_files.append(
                        MediaFile(path=path, metadata=metadata_map[path.name])
                    )
                    self.logger.debug(f"Created MediaFile for {path.name}")
                except Exception as e:
                    self.logger.error(f"Failed to create MediaFile for {path}: {e}")

        self.logger.debug(f"Successfully created {len(media_files)} MediaFile objects")
        return media_files


class ExiftoolMetadataExtractor:
    """Extracts metadata using exiftool."""

    def __init__(self):
        """Initialize the metadata extractor."""
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing ExiftoolMetadataExtractor")

    def extract_metadata(self, paths: List[Path]) -> Dict[str, MediaMetadata]:
        """Extract metadata from a batch of files and return a map of filename to metadata."""
        self.logger.debug(f"Extracting metadata from {len(paths)} paths")
        try:
            # Run exiftool
            cmd = [
                "exiftool",
                "-json",
                "-createdate",
                "-datetimeoriginal",
                *[str(p) for p in paths],
            ]
            self.logger.debug(f"Running exiftool with command: {cmd}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            metadata_list = json.loads(result.stdout)
            self.logger.debug(f"Successfully extracted {len(metadata_list)} metadata entries")

            # Create a map of filenames to metadata
            metadata_map = {}
            for metadata in metadata_list:
                filename = Path(metadata.get("SourceFile", "")).name
                capture_time = self._extract_capture_time(metadata, paths[0])
                metadata_map[filename] = MediaMetadata(capture_time=capture_time)
                self.logger.debug(f"Extracted metadata for {filename}")

            # Ensure all paths have metadata entries
            for path in paths:
                if path.name not in metadata_map:
                    capture_time = datetime.fromtimestamp(path.stat().st_ctime_ns / 1e9)
                    metadata_map[path.name] = MediaMetadata(capture_time=capture_time)
                    self.logger.debug(f"Using file creation time for {path.name}")

            self.logger.debug(f"Successfully extracted metadata for {len(metadata_map)} files")
            return metadata_map

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running exiftool: {e.stderr}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing exiftool output: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during metadata extraction: {e}")

        # If anything fails, fall back to file creation times
        self.logger.debug("Falling back to file creation times")
        return {
            p.name: MediaMetadata(
                capture_time=datetime.fromtimestamp(p.stat().st_ctime_ns / 1e9)
            )
            for p in paths
        }

    def _extract_capture_time(self, metadata: Dict, path: Path) -> datetime:
        """Extract capture time from metadata dictionary."""
        # Try different date fields in order of preference
        date_fields = ["DateTimeOriginal", "CreateDate"]

        for field in date_fields:
            if date_str := metadata.get(field):
                try:
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except ValueError as e:
                    self.logger.warning(
                        f"Error parsing date {date_str} for {path.name}: {e}"
                    )

        # Fall back to file creation time
        self.logger.warning(f"No valid capture time found for {path.name}")
        return datetime.fromtimestamp(path.stat().st_ctime_ns / 1e9)
