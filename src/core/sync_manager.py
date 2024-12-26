import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config.config import SyncConfig
from src.core.adb_manager import ADBDeviceManager
from src.core.media_processor import MediaFileProcessor
from src.utils.utils import get_user_confirmation

logger = logging.getLogger(__name__)

@dataclass
class SyncSettings:
    """Data class to store sync configuration settings."""
    convert_heic: bool
    sync_all: bool
    source_dir: Path
    target_dir: Path

class PhotoSyncManager:
    """Main class responsible for managing the photo synchronization process."""

    SYNC_MODES: Dict[str, Tuple[str, bool]] = {
        '1': ('Sync All', True),
        '2': ('Sync Only New Files', False)
    }

    def __init__(self) -> None:
        # Get the project root directory (2 levels up from this file)
        self.project_root = Path(__file__).resolve().parent.parent.parent

        # Define paths relative to project root
        self.source_folder = self.project_root / "data" / "photos"
        self.target_folder = Path("/storage/self/primary/Cinematography/syncPhotos")

        # Ensure the photos directory exists
        self.source_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using source folder: {self.source_folder}")

    def get_sync_settings(self) -> Optional[SyncSettings]:
        """
        Collect sync settings from user input.

        Returns:
            Optional[SyncSettings]: Configuration settings if successful, None if cancelled
        """
        try:
            # Get HEIC conversion preference with proper typing
            heic_options: Dict[str, bool] = {'y': True, 'n': False}
            convert_heic = get_user_confirmation(
                prompt="Convert HEIC to JPG?",
                default='y',
                valid_options=heic_options,
            )

            if convert_heic is None:
                logger.warning("HEIC conversion preference selection cancelled")
                return None

            # Get sync mode with proper typing
            sync_mode_prompt = "Choose sync mode:\n" + "\n".join(
                f"({k}) {v[0]}" for k, v in self.SYNC_MODES.items()
            )

            sync_mode_options: Dict[str, str] = {
                k: k for k in self.SYNC_MODES.keys()
            }

            sync_mode = get_user_confirmation(
                prompt=sync_mode_prompt,
                default='1',
                valid_options=sync_mode_options,
            )

            if sync_mode is None:
                logger.warning("Sync mode selection cancelled")
                return None

            return SyncSettings(
                convert_heic=convert_heic,
                sync_all=self.SYNC_MODES[sync_mode][1],
                source_dir=self.source_folder,
                target_dir=self.target_folder
            )

        except KeyboardInterrupt:
            logger.info("Configuration cancelled by user")
            return None
        except Exception as e:
            logger.error(f"Error during configuration: {str(e)}")
            return None

    def prepare_sync(self, settings: SyncSettings) -> Optional[Tuple[int, float, List[str]]]:
        """
        Prepare synchronization by calculating required files and metadata.

        Args:
            settings: SyncSettings object containing configuration

        Returns:
            Optional[Tuple]: (number of files, total size in bytes, files to sync) if successful
        """
        try:
            config = SyncConfig(
                convert_heic=settings.convert_heic,
                sync_all=settings.sync_all
            )

            file_manager = MediaFileProcessor(
                str(settings.source_dir),
                str(settings.target_dir),
                config
            )

            return file_manager.calculate_metadata()

        except Exception as e:
            logger.error(f"Error preparing sync: {str(e)}")
            return None

    def execute_sync(self, settings: SyncSettings, files_to_sync: List[str]) -> bool:
        """
        Execute the file synchronization process.

        Args:
            settings: SyncSettings object containing configuration
            files_to_sync: List of files to be synchronized

        Returns:
            bool: True if sync was successful, False otherwise
        """
        try:
            # Get final confirmation with proper typing
            confirm_options: Dict[str, bool] = {'y': True, 'n': False}
            start_confirm = get_user_confirmation(
                prompt="Start the transfer?",
                default='y',
                valid_options=confirm_options,
            )

            if start_confirm is None or not start_confirm:
                logger.info("Transfer cancelled by user")
                return False

            adb_manager = ADBDeviceManager()
            adb_manager.push_files(
                str(settings.source_dir),
                str(settings.target_dir),
                files_to_sync
            )
            return True

        except Exception as e:
            logger.error(f"Error during sync execution: {str(e)}")
            return False

    def run(self) -> None:
        """Main execution flow of the photo synchronization process."""
        logger.info("Starting photo sync process")

        try:
            # Get sync settings
            settings = self.get_sync_settings()
            if not settings:
                logger.info("Sync settings configuration cancelled")
                return

            # Prepare sync metadata
            sync_data = self.prepare_sync(settings)
            if not sync_data:
                logger.error("Failed to prepare sync metadata")
                return

            num_files, total_size_bytes, files_to_sync = sync_data

            if num_files == 0:
                logger.info("No new files to sync")
                return

            # Display sync summary
            logger.info(f"Total photos/files to transfer: {num_files}")
            logger.info(f"Total size: {total_size_bytes / (1024 * 1024):.2f} MB")

            # Execute sync
            if self.execute_sync(settings, files_to_sync):
                logger.info("Photo sync completed successfully")
            else:
                logger.error("Photo sync failed or was cancelled")

        except KeyboardInterrupt:
            logger.info("Process interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error during sync process: {str(e)}")