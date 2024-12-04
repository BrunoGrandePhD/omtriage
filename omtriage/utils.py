"""Utility functions for media file operations."""

from pathlib import Path
from typing import Union

from .constants import SUPPORTED_FORMATS


def get_file_format(path: Union[str, Path]) -> str:
    """Get the file format (extension without dot, in lowercase)."""
    if isinstance(path, str):
        path = Path(path)
    return path.suffix.lower().lstrip(".")


def is_image_file(path: Union[str, Path]) -> bool:
    """Check if the file is an image based on its extension.
    
    Args:
        path: Path to the file, either as string or Path object
        
    Returns:
        bool: True if the file is an image, False otherwise
    """
    return get_file_format(path) in SUPPORTED_FORMATS["images"]


def is_video_file(path: Union[str, Path]) -> bool:
    """Check if the file is a video based on its extension.
    
    Args:
        path: Path to the file, either as string or Path object
        
    Returns:
        bool: True if the file is a video, False otherwise
    """
    return get_file_format(path) in SUPPORTED_FORMATS["videos"]
