import logging
import os
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import imageio.v2 as imageio
import pyheif
from PIL import Image

from config import SyncConfig

logger = logging.getLogger(__name__)


class SyncError(Exception):
    """Base exception for sync-related errors."""
    pass


class FileConversionError(SyncError):
    """Raised when file conversion fails."""
    pass


class FileSizeError(SyncError):
    """Raised when file size validation fails."""
    pass


class ConversionMethod(Enum):
    """Enumeration of available image conversion methods."""
    PYHEIF = auto()
    IMAGEIO = auto()


@dataclass
class FileMetadata:
    """Container for file metadata."""
    path: Path
    size: int
    modified_time: float


class MediaFileProcessor:
    """
    Manages file synchronization operations including HEIC conversion and file metadata.

    Attributes:
        source_dir (Path): Source directory for files
        target_dir (Path): Target directory for synced files
        config (SyncConfig): Sync configuration settings
        _supported_formats (Dict[str, str]): Mapping of source to target formats
    """

    _supported_formats = {
        '.heic': '.jpg',
        '.HEIC': '.jpg'
    }

    def __init__(self, source_dir: str, target_dir: str, config: SyncConfig):
        """
        Initialize the FileSyncManager.

        Args:
            source_dir: Source directory path
            target_dir: Target directory path
            config: Sync configuration object
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.config = config

        if not self.source_dir.exists():
            raise ValueError(f"Source directory does not exist: {source_dir}")

    def calculate_metadata(self) -> Tuple[int, int, List[str]]:
        """
        Calculate total size and number of files to sync, handling format conversions.

        Returns:
            Tuple containing:
                - Number of files to sync
                - Total size in bytes
                - List of file paths to sync

        Raises:
            SyncError: If there's an error during metadata calculation
        """
        try:
            total_size = 0
            file_count = 0
            files_for_sync: List[str] = []

            logger.info(f"Starting metadata calculation from {self.source_dir}")

            for file_path in self._scan_directory():
                try:
                    processed_path = self._process_file(file_path)
                    if not processed_path:
                        continue

                    metadata = self._get_file_metadata(processed_path)
                    if not metadata:
                        continue

                    if self._should_sync_file(metadata):
                        self._validate_file_size(metadata)
                        total_size += metadata.size
                        file_count += 1
                        files_for_sync.append(str(metadata.path))
                        logger.debug(f"Added file: {metadata.path}, Size: {metadata.size:,} bytes")

                except (FileConversionError, FileSizeError) as e:
                    logger.warning(f"Skipping file {file_path}: {str(e)}")
                    continue

            logger.info(f"Metadata calculation complete. Found {file_count:,} files totaling {total_size:,} bytes")
            return file_count, total_size, files_for_sync

        except Exception as e:
            logger.error(f"Error calculating metadata: {str(e)}")
            raise SyncError(f"Failed to calculate sync metadata: {str(e)}") from e

    def _scan_directory(self) -> List[Path]:
        """Scan source directory for files recursively."""
        files: List[Path] = []
        try:
            for path in self.source_dir.rglob('*'):
                if path.is_file():
                    files.append(path)
        except Exception as e:
            logger.error(f"Error scanning directory: {str(e)}")
            raise SyncError(f"Failed to scan directory: {str(e)}") from e
        return files

    def _process_file(self, file_path: Path) -> Optional[Path]:
        """Process a file, converting if necessary."""
        try:
            if self.config.convert_heic and file_path.suffix in self._supported_formats:
                logger.info(f"Converting {file_path.name} to JPG...")
                return self.convert_heic_to_jpg(file_path)
            return file_path
        except FileConversionError:
            return None

    def _get_file_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """Get file metadata including size and modification time."""
        try:
            return FileMetadata(
                path=file_path,
                size=file_path.stat().st_size,
                modified_time=file_path.stat().st_mtime
            )
        except Exception as e:
            logger.error(f"Error getting metadata for {file_path}: {str(e)}")
            return None

    def _should_sync_file(self, metadata: FileMetadata) -> bool:
        """
        Determine if a file should be synced based on configuration.

        Args:
            metadata: File metadata object

        Returns:
            bool: True if file should be synced, False otherwise
        """
        return (
                self.config.sync_all or
                self.config.last_sync_timestamp is None or
                metadata.modified_time > self.config.last_sync_timestamp
        )

    def _validate_file_size(self, metadata: FileMetadata) -> None:
        """
        Validate file size meets requirements.

        Args:
            metadata: File metadata object

        Raises:
            FileSizeError: If file size validation fails
        """
        if metadata.size == 0:
            raise FileSizeError(f"Zero-byte file: {metadata.path}")

        # Add additional size validations as needed
        max_size = 1024 * 1024 * 1024  # 1GB
        if metadata.size > max_size:
            raise FileSizeError(f"File exceeds maximum size: {metadata.path}")

    @staticmethod
    def convert_heic_to_jpg(file_path: Path) -> Optional[Path]:
        """
        Convert HEIC image to JPG format.

        Args:
            file_path: Path to HEIC file

        Returns:
            Optional[Path]: Path to converted JPG file if successful, None otherwise

        Raises:
            FileConversionError: If conversion fails
        """
        jpg_path = file_path.with_suffix('.jpg')

        conversion_methods = {
            ConversionMethod.PYHEIF: MediaFileProcessor._convert_with_pyheif,
            ConversionMethod.IMAGEIO: MediaFileProcessor._convert_with_imageio
        }

        for method, converter in conversion_methods.items():
            try:
                logger.info(f"Attempting conversion with {method.name}")
                image = converter(file_path)
                if image:
                    image.save(jpg_path, "JPEG", quality=95)
                    logger.info(f"Successfully converted {file_path} to {jpg_path}")
                    file_path.unlink()  # Remove original HEIC file
                    return jpg_path
            except Exception as e:
                logger.warning(f"{method.name} conversion failed: {str(e)}")
                continue

        raise FileConversionError(f"All conversion methods failed for {file_path}")

    @staticmethod
    def _convert_with_pyheif(file_path: Path) -> Optional[Image.Image]:
        """Convert HEIC to PIL Image using pyheif."""
        try:
            heif_file = pyheif.read(str(file_path))
            return Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride
            )
        except Exception as e:
            logger.debug(f"pyheif conversion failed: {str(e)}")
            return None

    @staticmethod
    def _convert_with_imageio(file_path: Path) -> Optional[Image.Image]:
        """Convert HEIC to PIL Image using imageio."""
        try:
            return Image.fromarray(imageio.imread(str(file_path)))
        except Exception as e:
            logger.debug(f"imageio conversion failed: {str(e)}")
            return None
