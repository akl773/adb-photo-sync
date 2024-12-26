import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from tqdm import tqdm

from config import SyncConfig
from utils import get_user_confirmation, get_typed_input

logger = logging.getLogger(__name__)


class ADBError(Exception):
    """Base exception for ADB-related errors."""
    pass


class DeviceConnectionError(ADBError):
    """Raised when there are issues with device connection."""
    pass


class FileTransferError(ADBError):
    """Raised when file transfer fails."""
    pass


class BroadcastError(ADBError):
    """Raised when broadcasting intent fails."""
    pass


class DeviceStatus(Enum):
    """Enumeration of possible device states."""
    DEVICE = auto()  # Device is connected and authorized
    UNAUTHORIZED = auto()  # Device is connected but not authorized
    OFFLINE = auto()  # Device is offline
    UNKNOWN = auto()  # Unknown device state


@dataclass
class DeviceInfo:
    """Container for device information."""
    id: str
    status: DeviceStatus
    model: Optional[str] = None
    manufacturer: Optional[str] = None


class ADBDeviceManager:
    """
    Manages ADB device interactions including device selection and file transfer.

    Attributes:
        selected_device (Optional[DeviceInfo]): Currently selected device
        _adb_command_timeout (int): Timeout for ADB commands in seconds
        _max_retries (int): Maximum number of retries for failed operations
    """

    _adb_command_timeout = 30  # seconds
    _max_retries = 3
    _chunk_size = 10 * 1024 * 1024  # 10MB chunks for large file transfers

    def __init__(self):
        """Initialize the ADB Device Manager."""
        self.selected_device: Optional[DeviceInfo] = None
        self._verify_adb_installation()

    def _verify_adb_installation(self) -> None:
        """
        Verify ADB is installed and accessible.

        Raises:
            DeviceConnectionError: If ADB is not installed or accessible
        """
        try:
            result = self._run_adb_command(['version'])
            logger.debug(f"ADB version: {result.stdout.splitlines()[0]}")
        except subprocess.CalledProcessError as e:
            raise DeviceConnectionError("ADB is not installed or accessible") from e

    def select_device(self) -> Optional[DeviceInfo]:
        """
        Select an ADB device, prompting user if multiple devices are connected.

        Returns:
            Optional[DeviceInfo]: Selected device information if successful

        Raises:
            DeviceConnectionError: If no devices are connected or device selection fails
        """
        try:
            devices = self._get_connected_devices()
            if not devices:
                raise DeviceConnectionError("No devices connected. Please connect a device and try again.")

            if len(devices) == 1:
                self.selected_device = devices[0]
            else:
                self.selected_device = self._prompt_for_device_choice(devices)

            self._fetch_device_details()
            logger.info(f"Selected device: {self.selected_device.model} ({self.selected_device.id})")
            return self.selected_device

        except Exception as e:
            logger.error(f"Error selecting device: {str(e)}")
            raise DeviceConnectionError(f"Failed to select device: {str(e)}") from e

    def _get_connected_devices(self) -> List[DeviceInfo]:
        """
        Get list of connected ADB devices with their status.

        Returns:
            List[DeviceInfo]: List of connected devices

        Raises:
            DeviceConnectionError: If unable to get device list
        """
        try:
            result = self._run_adb_command(['devices', '-l'])
            devices: List[DeviceInfo] = []

            for line in result.stdout.strip().split('\n')[1:]:  # Skip first line (header)
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    device_id = parts[0]
                    status = DeviceStatus[parts[1].upper()]
                    if status == DeviceStatus.DEVICE:
                        devices.append(DeviceInfo(id=device_id, status=status))

            return devices

        except Exception as e:
            raise DeviceConnectionError(f"Failed to get device list: {str(e)}") from e

    def _fetch_device_details(self) -> None:
        """Fetch additional device details like model and manufacturer."""
        if not self.selected_device:
            return

        try:
            # Get device model
            result = self._run_adb_command(['-s', self.selected_device.id, 'shell', 'getprop', 'ro.product.model'])
            self.selected_device.model = result.stdout.strip()

            # Get manufacturer
            result = self._run_adb_command(
                ['-s', self.selected_device.id, 'shell', 'getprop', 'ro.product.manufacturer'])
            self.selected_device.manufacturer = result.stdout.strip()

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to fetch device details: {str(e)}")

    def _prompt_for_device_choice(self, devices: List[DeviceInfo]) -> DeviceInfo:
        """
        Prompt user to select a device from multiple connected devices.

        Args:
            devices: List of connected devices

        Returns:
            DeviceInfo: Selected device information
        """
        print("\nMultiple devices detected. Please select one:")
        for i, device in enumerate(devices, 1):
            manufacturer = device.manufacturer or "Unknown"
            model = device.model or "Unknown"
            print(f"{i}. {manufacturer} {model} ({device.id})")

        while True:
            try:
                choice = get_typed_input(
                    prompt=f"Select device",
                    input_type=int,
                    validator=lambda x: 1 <= x <= len(devices)
                )
                if choice is None:
                    raise DeviceConnectionError("Device selection cancelled")
                return devices[choice - 1]
            except ValueError:
                print("Invalid input. Please enter a number.")

    def push_files(self, source_dir: str, target_dir: str, files_for_transfer: List[str]) -> bool:
        """
        Push files to selected device and trigger media scan.

        Args:
            source_dir: Source directory path
            target_dir: Target directory path on device
            files_for_transfer: List of files to transfer

        Returns:
            bool: True if all files were transferred successfully

        Raises:
            FileTransferError: If file transfer fails
        """
        if not self.selected_device:
            self.select_device()

        source_path = Path(source_dir)
        target_path = Path(target_dir)

        try:
            total_size = sum(os.path.getsize(f) for f in files_for_transfer)
            transferred_files: List[str] = []

            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Transferring files") as pbar:
                for local_file in files_for_transfer:
                    try:
                        android_path = self._push_file(
                            source_path,
                            target_path,
                            local_file,
                            progress_callback=pbar.update
                        )
                        if android_path:
                            transferred_files.append(android_path)
                    except FileTransferError as e:
                        logger.error(f"Failed to transfer {local_file}: {str(e)}")
                        continue

            # Send reindex broadcasts in batches
            if transferred_files:
                self._batch_reindex_broadcasts(transferred_files)
                SyncConfig.update_last_sync_timestamp()
                logger.info(f"Successfully transferred {len(transferred_files)} files")
                return True

            return False

        except Exception as e:
            raise FileTransferError(f"File transfer failed: {str(e)}") from e

    def _push_file(
            self,
            source_dir: Path,
            target_dir: Path,
            local_file: str,
            progress_callback: callable
    ) -> Optional[str]:
        """
        Push single file to device with retry logic.

        Args:
            source_dir: Source directory path
            target_dir: Target directory path
            local_file: Local file path
            progress_callback: Callback for progress updates

        Returns:
            Optional[str]: Target path on device if successful
        """
        relative_path = Path(local_file).relative_to(source_dir)
        android_target = target_dir / relative_path

        for attempt in range(self._max_retries):
            try:
                # Create target directory
                self._run_adb_command([
                    '-s', self.selected_device.id,
                    'shell', 'mkdir', '-p',
                    str(android_target.parent)
                ])

                # Push file
                result = self._run_adb_command([
                    '-s', self.selected_device.id,
                    'push',
                    local_file,
                    str(android_target)
                ])

                if "bytes in" in result.stderr:  # Successful transfer
                    progress_callback(os.path.getsize(local_file))
                    return str(android_target)

            except subprocess.CalledProcessError as e:
                logger.warning(f"Transfer attempt {attempt + 1} failed: {str(e)}")
                if attempt < self._max_retries - 1:
                    time.sleep(1)  # Wait before retry
                continue

        return None

    def _batch_reindex_broadcasts(self, file_paths: List[str], batch_size: int = 10) -> None:
        """
        Send media scanner broadcasts in batches.

        Args:
            file_paths: List of file paths to reindex
            batch_size: Number of files per batch
        """
        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i + batch_size]
            try:
                self._send_reindex_broadcast(batch)
            except BroadcastError as e:
                logger.warning(f"Failed to send reindex broadcast for batch: {str(e)}")

    def _send_reindex_broadcast(self, file_paths: List[str]) -> None:
        """
        Send media scanner broadcast for files.

        Args:
            file_paths: List of file paths to reindex

        Raises:
            BroadcastError: If broadcast fails
        """
        try:
            paths_arg = ' '.join([f"file://{path}" for path in file_paths])
            self._run_adb_command([
                '-s', self.selected_device.id,
                'shell', 'am', 'broadcast',
                '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE',
                '-d', paths_arg
            ])
        except subprocess.CalledProcessError as e:
            raise BroadcastError(f"Failed to send reindex broadcast: {str(e)}") from e

    def _run_adb_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """
        Run ADB command with timeout and capture output.

        Args:
            command: Command and arguments to run

        Returns:
            subprocess.CompletedProcess: Command result

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        try:
            return subprocess.run(
                ['adb'] + command,
                capture_output=True,
                text=True,
                timeout=self._adb_command_timeout,
                check=True
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"ADB command timed out: {' '.join(command)}")
            raise DeviceConnectionError("ADB command timed out") from e
