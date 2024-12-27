import time
from pathlib import Path
from typing import Optional

from src.utils.path_utils import get_project_root


class SyncConfig:
    """Configuration options for file synchronization."""

    def __init__(self, convert_heic: bool = True, sync_all: bool = True):
        self.convert_heic = convert_heic
        self.sync_all = sync_all
        self.last_sync_timestamp = None if sync_all else self.get_last_sync_timestamp()

    @property
    def last_sync_file(self) -> Path:
        """Get the path to the last sync timestamp file."""
        return get_project_root() / "last_sync_time.txt"

    def get_last_sync_timestamp(self) -> Optional[float]:
        """Get the last sync timestamp from a file."""
        if self.last_sync_file.exists():
            return float(self.last_sync_file.read_text().strip())
        return None

    def update_last_sync_timestamp(self) -> None:
        """Update the last sync timestamp file with the current time."""
        self.last_sync_file.write_text(str(time.time()))
