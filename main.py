import os
import subprocess
import time
from typing import Optional, List

import imageio.v2 as imageio
import pyheif
from PIL import Image
from tqdm import tqdm

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


class FileSyncManager:
    """Manages file synchronization, including HEIC conversion and pushing files."""

    def __init__(self, source_dir: str, target_dir: str, config: SyncConfig):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.config = config

    def calculate_metadata(self) -> tuple[int, int, List[str]]:
        """Calculate the total size and number of files to sync, optionally converting HEIC to JPG."""
        total_size = 0
        file_count = 0
        files_for_sync = []

        for root, _, files in os.walk(self.source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_path = self._handle_heic_conversion(file, file_path)

                # Skip if no valid path after HEIC conversion
                if not file_path:
                    continue

                # Add files modified after the last sync time
                if self._should_sync_file(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > 0:
                        total_size += file_size
                        file_count += 1
                        files_for_sync.append(file_path)
                        print(f"Adding file: {file_path}, Size: {file_size} bytes")
                    else:
                        print(f"Skipping zero-byte file: {file_path}")

        return file_count, total_size, files_for_sync

    def _handle_heic_conversion(self, file: str, file_path: str) -> Optional[str]:
        """Convert HEIC to JPG if applicable, return the updated file path."""
        if self.config.convert_heic and file.lower().endswith(".heic"):
            print(f"Converting {file} to JPG...")
            return self.convert_heic_to_jpg(file_path)
        return file_path

    def _should_sync_file(self, file_path: str) -> bool:
        """Determine if the file should be synced based on the last sync timestamp."""
        return self.config.last_sync_timestamp is None or os.path.getmtime(file_path) > self.config.last_sync_timestamp

    @staticmethod
    def convert_heic_to_jpg(file_path: str) -> Optional[str]:
        """Convert a HEIC image to JPG, delete the original HEIC file, and return the new JPG path."""
        try:
            heif_file = pyheif.read(file_path)
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride
            )
        except Exception:
            print(f"pyheif failed to read {file_path}, trying imageio as a fallback.")
            try:
                image = Image.fromarray(imageio.imread(file_path))
            except Exception:
                print(f"imageio also failed to read {file_path}. Skipping conversion.")
                return None  # Return None if both methods fail

        jpg_path = file_path.rsplit('.', 1)[0] + ".jpg"
        image.save(jpg_path, "JPEG")
        print(f"Converted {file_path} to {jpg_path}")
        os.remove(file_path)
        return jpg_path


class ADBDeviceManager:
    """Manages ADB device interactions like selecting a device and pushing files."""

    def __init__(self):
        self.selected_device = None

    def select_device(self):
        """Select an ADB device if multiple devices are connected."""
        devices = self.get_connected_devices()
        if not devices:
            print("No devices connected. Please connect a device and try again.")
            return None

        if len(devices) == 1:
            self.selected_device = devices[0]
        else:
            self.selected_device = self._prompt_for_device_choice(devices)
        print(f"Using device: {self.selected_device}")

    @staticmethod
    def get_connected_devices() -> List[str]:
        """Get a list of devices connected via ADB."""
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")
            devices = [line.split()[0] for line in lines[1:] if "device" in line]
            return devices
        except subprocess.CalledProcessError:
            print("Failed to run 'adb devices'. Make sure ADB is installed and accessible.")
            return []

    @staticmethod
    def _prompt_for_device_choice(devices: List[str]) -> str:
        """Prompt the user to select a device if multiple devices are connected."""
        print("Multiple devices detected. Please select one:")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device}")
        return ADBDeviceManager._get_device_choice(devices)

    @staticmethod
    def _get_device_choice(devices: List[str]) -> str:
        """Get the user’s choice for the device to use."""
        while True:
            try:
                choice = int(input(f"Select device [1-{len(devices)}]: "))
                if 1 <= choice <= len(devices):
                    return devices[choice - 1]
                print(f"Invalid choice. Please select a number between 1 and {len(devices)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def push_files(self, source_dir: str, target_dir: str, files_for_transfer: List[str]) -> None:
        """Push files via ADB to the selected device and send reindex broadcast."""
        if not self.selected_device:
            self.select_device()

        all_files_pushed = True
        with tqdm(total=len(files_for_transfer), unit="file", desc="Transferring files") as progress_bar:
            for local_file_path in files_for_transfer:
                android_target_path = self._push_file(source_dir, target_dir, local_file_path)
                progress_bar.update(1)

                if android_target_path:
                    self._send_reindex_broadcast(android_target_path)
                else:
                    all_files_pushed = False

        if all_files_pushed:
            SyncConfig.update_last_sync_timestamp()
            print("All files pushed successfully.")

    def _push_file(self, source_dir: str, target_dir: str, local_file_path: str) -> Optional[str]:
        """Push a single file to the selected Android device."""
        relative_path = os.path.relpath(local_file_path, source_dir)
        android_target_path = os.path.join(target_dir, relative_path)

        subprocess.run(
            ["adb", "-s", self.selected_device, "shell", "mkdir", "-p", os.path.dirname(android_target_path)])
        result = subprocess.run(["adb", "-s", self.selected_device, "push", local_file_path, android_target_path],
                                capture_output=True)

        if result.returncode == 0:
            return android_target_path
        print(f"Failed to push {local_file_path}.")
        return None

    def _send_reindex_broadcast(self, android_target_path: str) -> None:
        """Send reindex broadcast so the file appears in the Android gallery."""
        result = subprocess.run(
            ["adb", "-s", self.selected_device, "shell", "am", "broadcast", "-a",
             "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
             "-d", f"file://{android_target_path}"], capture_output=True)
        if result.returncode == 0:
            print(f"Reindex broadcast sent for {android_target_path}")
        else:
            print(f"Failed to send reindex broadcast for {android_target_path}")


def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    source_folder = os.path.join(repo_dir, "photos")
    target_folder = "/storage/self/primary/Cinematography/syncPhotos"

    # Configure sync settings
    convert_heic = get_user_confirmation("Convert HEIC to JPG?", 'y', {'y': True, 'n': False})
    sync_mode = get_user_confirmation("Choose sync mode: (1) Sync All or (2) Sync Only New Files", '1',
                                      {'1': '1', '2': '2'})
    config = SyncConfig(convert_heic=convert_heic, sync_all=(sync_mode == '1'))

    # Calculate files to sync
    file_manager = FileSyncManager(source_folder, target_folder, config)
    num_files, total_size_bytes, files_to_sync = file_manager.calculate_metadata()

    if num_files == 0:
        print("No new files to sync.")
        return

    print(f"Total photos/files to transfer: {num_files}")
    print(f"Total size: {total_size_bytes / (1024 * 1024):.2f} MB\n")

    # Start the file transfer process
    start_confirm = get_user_confirmation("Start the transfer?", 'y', {'y': True, 'n': False})
    if start_confirm:
        adb_manager = ADBDeviceManager()
        adb_manager.push_files(source_folder, target_folder, files_to_sync)
    else:
        print("Transfer cancelled.")


def get_user_confirmation(prompt: str, default: str, valid_options: dict) -> Optional[bool]:
    """Generalized user prompt function."""
    while True:
        user_input = input(f"{prompt} [{'/'.join(valid_options.keys())}, default: {default}]: ").strip().lower()
        if user_input == '':
            return valid_options[default]
        if user_input in valid_options:
            return valid_options[user_input]
        print(f"Invalid choice. Please enter one of {', '.join(valid_options.keys())}.")


if __name__ == "__main__":
    main()
