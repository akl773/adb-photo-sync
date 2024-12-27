import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path: Absolute path to the project root directory

    Note:
        Uses @lru_cache to cache the result since project root won't change during execution
    """
    try:
        current_file = Path(__file__).resolve()
        root_dir = current_file.parent.parent.parent

        logger.debug(f"Project root resolved to: {root_dir}")
        return root_dir

    except Exception as e:
        logger.error(f"Failed to resolve project root: {str(e)}")
        raise RuntimeError(f"Could not determine project root: {str(e)}")


def get_data_dir() -> Path:
    """Get the data directory path."""
    return get_project_root() / "data"


def get_photos_dir() -> Path:
    """Get the photos directory path."""
    photos_dir = get_data_dir() / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    return photos_dir


def get_logs_dir() -> Path:
    """Get the logs directory path."""
    logs_dir = get_project_root() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir
