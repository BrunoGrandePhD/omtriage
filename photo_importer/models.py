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
    def from_datetime(cls, dt: datetime) -> 'SessionType':
        """Determine session type from datetime."""
        from .constants import AFTERNOON_HOUR
        return cls.AFTERNOON if dt.hour >= AFTERNOON_HOUR else cls.MORNING

    def __str__(self) -> str:
        return 'PM' if self == SessionType.AFTERNOON else 'AM'


@dataclass
class MediaFile:
    """Represents a media file with its metadata."""
    path: Path
    capture_time: Optional[datetime] = None
    format: str = field(init=False)
    creation_date: datetime = field(init=False)
    file_size: int = field(init=False)
    
    def __post_init__(self):
        """Initialize derived attributes."""
        self.format = self.path.suffix.lower().lstrip('.')
        if self.format == 'ori':
            self.format = 'orf'  # Treat ORI as ORF
        stat = self.path.stat()
        self.creation_date = datetime.fromtimestamp(stat.st_ctime)
        self.file_size = stat.st_size

    @property
    def is_image(self) -> bool:
        """Check if the file is an image."""
        return self.format in SUPPORTED_FORMATS['images']

    @property
    def is_video(self) -> bool:
        """Check if the file is a video."""
        return self.format in SUPPORTED_FORMATS['videos']

    @property
    def output_name(self) -> str:
        """Get the output filename."""
        name = self.path.name
        if self.path.suffix.lower() == '.ori':
            name += '.ORF'
        return name


@dataclass
class MediaGroup:
    """Group of related media files (e.g., ORF+JPEG pair)."""
    files: List[MediaFile]
    capture_time: Optional[datetime] = field(init=False)

    def __post_init__(self):
        """Initialize capture time from files."""
        times = [f.capture_time for f in self.files if f.capture_time]
        self.capture_time = min(times) if times else None

    def get_by_format(self, format: str) -> Optional[MediaFile]:
        """Get file of specific format if it exists."""
        return next((f for f in self.files if f.format == format), None)


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
        date_str = self.start_time.strftime('%Y-%m-%d')
        name = f"{date_str}-{self.type}"
        if self.number > 1:
            name += f"-{self.number}"
        return str(Path(base_dir) / name) if base_dir else name
