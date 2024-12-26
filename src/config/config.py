import os
import time
from pathlib import Path
from typing import Optional


class SyncConfig:
    """Configuration options for file synchronization."""

    def __init__(self, convert_heic: bool = True, sync_all: bool = True):
        self.convert_heic = convert_heic
        self.sync_all = sync_all
        self._root_dir = Path(__file__).resolve().parent.parent.parent
        self.last_sync_timestamp = None if sync_all else self.get_last_sync_timestamp()

    @property
    def last_sync_file(self) -> Path:
        """Get the path to the last sync timestamp file."""
        return self._root_dir / "last_sync_time.txt"

    def get_last_sync_timestamp(self) -> Optional[float]:
        """Get the last sync timestamp from a file."""
        if self.last_sync_file.exists():
            return float(self.last_sync_file.read_text().strip())
        return None

    @staticmethod
    def update_last_sync_timestamp() -> None:
        """Update the last sync timestamp file with the current time."""
        sync_file = Path(__file__).resolve().parent.parent.parent / "last_sync_time.txt"
        sync_file.write_text(str(time.time()))
