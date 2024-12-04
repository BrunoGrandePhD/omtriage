import logging
from typing import Sequence

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import track as rich_track

console = Console()


def setup_logging(level: str) -> None:
    """Configure logging with rich output."""
    # Get the root logger and set its level
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Configure the handler
    handler = RichHandler(console=console, rich_tracebacks=True)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Remove any existing handlers and add our new one
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def track(*args, **kwargs) -> Sequence:
    """Wrap rich's track function to use the global console."""
    description = kwargs.pop("description", "")
    description = " " * 29 + description
    return rich_track(*args, **kwargs, description=description, console=console)
