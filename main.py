import logging

from src.core.sync_manager import PhotoSyncManager
from src.utils.path_utils import get_logs_dir


def setup_logging() -> None:
    """Configure logging for the application."""
    log_file = get_logs_dir() / "sync_photos.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )


def main():
    """Entry point of the application."""
    setup_logging()
    sync_manager = PhotoSyncManager()
    sync_manager.run()


if __name__ == "__main__":
    main()
