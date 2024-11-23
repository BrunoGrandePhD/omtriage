"""Models for representing media files and sessions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from .constants import SUPPORTED_FORMATS


class SessionType(Enum):
    """Session types based on start time."""

    MORNING = auto()
    AFTERNOON = auto()

    @classmethod
    def from_datetime(cls, dt: datetime) -> "SessionType":
        """Determine session type from datetime."""
        from .constants import AFTERNOON_HOUR

        return cls.AFTERNOON if dt.hour >= AFTERNOON_HOUR else cls.MORNING

    def __str__(self) -> str:
        return "PM" if self == SessionType.AFTERNOON else "AM"


@dataclass
class MediaMetadata:
    """Metadata extracted from a media file."""

    capture_time: Optional[datetime] = None
    format: str = field(init=False)

    def __post_init__(self):
        """Initialize derived attributes."""
        self.format = "orf"  # Treat ORI as ORF


@dataclass
class MediaFile:
    """Represents a media file with its metadata."""

    path: Path
    metadata: Optional[MediaMetadata] = None

    @property
    def capture_time(self) -> Optional[datetime]:
        """Get capture time from metadata or fallback to file creation time."""
        if self.metadata and self.metadata.capture_time:
            return self.metadata.capture_time
        return self.creation_date

    @property
    def creation_date(self) -> datetime:
        """Get file creation date."""
        return datetime.fromtimestamp(self.path.stat().st_ctime)

    @property
    def file_size(self) -> int:
        """Get file size in bytes."""
        return self.path.stat().st_size

    @property
    def format(self) -> str:
        """Get the file format (extension without dot, in lowercase)."""
        return self.path.suffix.lower().lstrip(".")

    @property
    def is_image(self) -> bool:
        """Check if the file is an image."""
        return self.format in SUPPORTED_FORMATS["images"]

    @property
    def is_video(self) -> bool:
        """Check if the file is a video."""
        return self.format in SUPPORTED_FORMATS["videos"]

    @property
    def output_name(self) -> str:
        """Get the output filename."""
        name = self.path.name
        if self.format == "ori":
            name += ".ORF"
        return name


@dataclass
class MediaGroup:
    """Group of related media files (e.g., ORF+JPEG pair)."""

    files: List[MediaFile]
    capture_time: datetime = field(init=False)

    def __post_init__(self):
        """Initialize capture time from files."""
        times = [f.capture_time for f in self.files if f.capture_time]
        if times:
            self.capture_time = min(times)
        else:
            raise ValueError("No valid capture times found in group")

    def get_by_format(self, format: str) -> Optional[MediaFile]:
        """Get file of specific format if it exists."""
        return next((file for file in self.files if file.format == format), None)


@dataclass
class Session:
    """Group of media files captured within a time window."""

    groups: List[MediaGroup]
    type: SessionType
    number: int = 1

    @property
    def start_time(self) -> datetime:
        """Get session start time."""
        return min(g.capture_time for g in self.groups if g.capture_time)

    def format_name(self, base_dir: Optional[str] = None) -> str:
        """Format session directory name."""
        date_str = self.start_time.strftime("%Y-%m-%d")
        name = f"{date_str}-{self.type}"
        if self.number > 1:
            name += f"-{self.number}"
        return str(Path(base_dir) / name) if base_dir else name
