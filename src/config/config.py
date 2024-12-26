import os
import time
from typing import Optional

LAST_SYNC_FILE = "last_sync_time.txt"


class SyncConfig:
    """Configuration options for file synchronization."""

    def __init__(self, convert_heic: bool = True, sync_all: bool = True):
        self.convert_heic = convert_heic
        self.sync_all = sync_all
        self.last_sync_timestamp = None if sync_all else self.get_last_sync_timestamp()

    @staticmethod
    def get_last_sync_timestamp() -> Optional[float]:
        """Get the last sync timestamp from a file."""
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, "r") as sync_file:
                return float(sync_file.read().strip())
        return None

    @staticmethod
    def update_last_sync_timestamp() -> None:
        """Update the last sync timestamp file with the current time."""
        with open(LAST_SYNC_FILE, "w") as sync_file:
            sync_file.write(str(time.time()))
