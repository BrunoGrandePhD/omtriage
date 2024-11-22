"""Media file metadata extraction using exiftool."""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .constants import EXIFTOOL_BATCH_SIZE
from .models import MediaFile

logger = logging.getLogger(__name__)


def extract_metadata(files: List[MediaFile]) -> None:
    """Extract metadata from media files using exiftool."""
    if not files:
        return

    # Process files in batches to avoid command line length limits
    for i in range(0, len(files), EXIFTOOL_BATCH_SIZE):
        batch = files[i:i + EXIFTOOL_BATCH_SIZE]
        _process_batch(batch)


def _process_batch(files: List[MediaFile]) -> None:
    """Process a batch of files with exiftool."""
    try:
        cmd = [
            'exiftool', '-json', '-createdate', '-datetimeoriginal',
            *[str(f.path) for f in files]
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata_list = json.loads(result.stdout)

        # Match metadata with files
        file_map = {f.path.name: f for f in files}
        for metadata in metadata_list:
            filename = Path(metadata.get('SourceFile', '')).name
            if file := file_map.get(filename):
                _update_file_metadata(file, metadata)

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running exiftool: {e.stderr}")
    except json.JSONDecodeError:
        logger.error("Error parsing exiftool output")
    except Exception as e:
        logger.error(f"Unexpected error during metadata extraction: {e}")


def _update_file_metadata(file: MediaFile, metadata: Dict) -> None:
    """Update a MediaFile with extracted metadata."""
    # Try different date fields in order of preference
    date_fields = ['DateTimeOriginal', 'CreateDate']
    
    for field in date_fields:
        if date_str := metadata.get(field):
            try:
                # Handle common date formats
                formats = [
                    '%Y:%m:%d %H:%M:%S',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y:%m:%d %H:%M:%S%z'
                ]
                for fmt in formats:
                    try:
                        file.capture_time = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                if file.capture_time:
                    break
            except Exception as e:
                logger.warning(f"Error parsing date {date_str} for {file.path.name}: {e}")

    if not file.capture_time:
        logger.warning(f"No valid capture time found for {file.path.name}")
        file.capture_time = file.creation_date
