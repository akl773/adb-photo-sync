import mimetypes
import os
import subprocess
import time
from typing import Optional

import imageio.v2 as imageio
import pyheif
from PIL import Image
from tqdm import tqdm

LAST_SYNC_FILE = "last_sync_time.txt"


def delete_files_in_folder(folder_path: str) -> None:
    """ Delete all files in the specified folder, keeping the folder structure intact."""
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
            print(f"Deleted file: {file_path}")


def is_video_file(file_name: str) -> bool:
    """ Check if a file is a video based on its MIME type."""
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type is not None:
        return mime_type.startswith('video')
    return False


def convert_heic_to_jpg(file_path: str) -> Optional[str]:
    """Convert a HEIC image to JPG, delete the original HEIC file, and return the new JPG path."""
    try:
        # Attempt conversion with pyheif
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

    # Replace .heic with .jpg in the file path
    jpg_path = file_path.rsplit('.', 1)[0] + ".jpg"
    image.save(jpg_path, "JPEG")
    print(f"Converted {file_path} to {jpg_path}")

    # Delete the original HEIC file
    try:
        os.remove(file_path)
        print(f"Deleted original HEIC file: {file_path}")
    except OSError as e:
        print(f"Could not delete original HEIC file: {file_path}. Error: {e}")

    return jpg_path  # Return the path to the new JPG file


def calculate_metadata(sync_source_folder: str, last_sync_timestamp: Optional[float] = None,
                       convert_heic: bool = True) -> tuple[int, int, list[str]]:
    total_size = 0
    file_count = 0
    files_for_sync = []

    for root, _, files in os.walk(sync_source_folder):
        for file in files:
            file_path = os.path.join(root, file)

            # Handle HEIC to JPG conversion
            if convert_heic and file.lower().endswith(".heic"):
                print(f"Converting {file} to JPG...")
                file_path = convert_heic_to_jpg(file_path)  # Replace file_path with the path of the converted file
                if file_path is None:
                    continue  # Skip if the conversion failed

            # Check if it's a video file (no conversion needed)
            elif is_video_file(file):
                print(f"Video file detected: {file_path}")

            # Check if the file was modified after the last sync time
            if last_sync_timestamp is None or os.path.getmtime(file_path) > last_sync_timestamp:
                file_size = os.path.getsize(file_path)  # Get the file size

                # Only add if the file size is greater than zero
                if file_size > 0:
                    total_size += file_size
                    file_count += 1
                    files_for_sync.append(file_path)  # Use the file path here
                    print(f"Adding file: {file_path}, Size: {file_size} bytes")
                else:
                    print(f"Skipping zero-byte file: {file_path}")

    print(f"Total files for sync: {file_count}, Total size: {total_size} bytes")
    return file_count, total_size, files_for_sync


def get_last_sync_timestamp() -> Optional[float]:
    if os.path.exists(LAST_SYNC_FILE):
        with open(LAST_SYNC_FILE, "r") as sync_file:
            return float(sync_file.read().strip())
    return None


def update_last_sync_timestamp() -> None:
    with open(LAST_SYNC_FILE, "w") as sync_file:
        sync_file.write(str(time.time()))


def get_connected_devices() -> list[str]:
    """
    Get a list of devices connected via ADB.

    Returns:
        list[str]: A list of device IDs connected via ADB.
    """
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        devices = [line.split()[0] for line in lines[1:] if "device" in line]  # Ignore the first line (header)
        return devices
    except subprocess.CalledProcessError:
        print("Failed to run 'adb devices'. Make sure ADB is installed and accessible.")
        return []


def select_device(devices: list[str]) -> str:
    """
    Prompt the user to select a device if multiple devices are connected.

    Args:
        devices (list[str]): List of device IDs.

    Returns:
        str: The selected device ID.
    """
    if len(devices) == 1:
        return devices[0]  # Only one device, no need to prompt
    else:
        print("Multiple devices detected. Please select one:")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device}")

        while True:
            try:
                choice = int(input(f"Select device [1-{len(devices)}]: "))
                if 1 <= choice <= len(devices):
                    return devices[choice - 1]
                else:
                    print(f"Invalid choice. Please select a number between 1 and {len(devices)}.")
            except ValueError:
                print("Invalid input. Please enter a number.")


def adb_push_files(source_dir: str, target_dir: str, files_for_transfer: list[str]) -> None:
    # Get connected devices
    devices = get_connected_devices()

    if not devices:
        print("No devices connected. Please connect a device and try again.")
        return

    # Select a device if multiple are connected
    selected_device = select_device(devices)
    print(f"Using device: {selected_device}")

    # Track whether all files were pushed successfully
    all_files_pushed = True

    # Start the file transfer with tqdm progress bar
    with tqdm(total=len(files_for_transfer), unit="file", desc="Transferring files") as progress_bar:
        for local_file_path in files_for_transfer:
            # Get the relative path within source_dir to recreate the folder structure
            relative_path = os.path.relpath(local_file_path, source_dir)
            android_target_path = os.path.join(target_dir, relative_path)

            # Ensure the target directory exists on Android
            remote_dir = os.path.dirname(android_target_path)
            subprocess.run(["adb", "-s", selected_device, "shell", "mkdir", "-p", remote_dir])

            # Push the file to the selected device
            result = subprocess.run(["adb", "-s", selected_device, "push", local_file_path, android_target_path],
                                    capture_output=True)

            # Update progress bar
            progress_bar.update(1)

            # Check if the push was successful
            if result.returncode == 0:
                # Broadcast the reindex event so the file appears in the gallery
                broadcast_result = subprocess.run(
                    ["adb", "-s", selected_device, "shell", "am", "broadcast", "-a",
                     "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                     "-d", f"file://{android_target_path}"],
                    capture_output=True
                )
                if broadcast_result.returncode == 0:
                    print(f"Reindex broadcast sent for {android_target_path}")
                else:
                    print(f"Failed to send reindex broadcast for {android_target_path}")
            else:
                print(f"\nFailed to push {local_file_path}.")
                all_files_pushed = False

    # If all files were pushed successfully, update the sync time
    if all_files_pushed:
        update_last_sync_timestamp()
        print("All files pushed successfully.")

        # Prompt for deletion if sync was successful
        delete_confirm = input(
            "Files will be deleted from your Mac unless you type 'n'. Proceed? (default: yes): ").strip().lower()
        if delete_confirm != 'n':
            delete_files_in_folder(source_dir)
            print(f"Deleted all files from {source_dir}.")
        else:
            print("Files were not deleted.")
    else:
        print("Some files failed to push. Please check and try again.")


def get_user_confirmation(prompt: str, default: str, valid_options: dict) -> bool | int | str | float | None:
    """
    Generalized user prompt function.

    Args:
        prompt (str): The prompt message to display to the user.
        default (str): The default response if the user presses Enter.
        valid_options (dict): A dictionary where keys are valid responses and values are the return values.

    Returns:
        str: The value associated with the user’s response in `valid_options`.
    """
    while True:
        user_input = input(f"{prompt} [{'/'.join(valid_options.keys())}, default: {default}]: ").strip().lower()
        if user_input == '':
            return valid_options[default]
        elif user_input in valid_options:
            return valid_options[user_input]
        else:
            print(f"Invalid choice. Please enter one of {', '.join(valid_options.keys())}.")


def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    source_folder = os.path.join(repo_dir, "photos")
    target_folder = "/storage/self/primary/Cinematography/syncPhotos"

    convert_heic = get_user_confirmation(
        prompt="Convert HEIC to JPG?",
        default='y', valid_options={'y': True, 'n': False}
    )
    sync_mode = get_user_confirmation(
        "Choose sync mode: (1) Sync All or (2) Sync Only New Files",
        default='1', valid_options={'1': '1', '2': '2'}
    )
    last_sync_timestamp = None if sync_mode == '1' else get_last_sync_timestamp()

    num_files, total_size_bytes, files_to_sync = calculate_metadata(
        sync_source_folder=source_folder,
        last_sync_timestamp=last_sync_timestamp,
        convert_heic=convert_heic
    )

    if num_files == 0:
        print("No new files to sync.")
        return

    print(f"Total photos/files to transfer: {num_files}")
    print(f"Total size: {total_size_bytes / (1024 * 1024):.2f} MB\n")

    start_confirm = get_user_confirmation(
        prompt="Start the transfer?", default='y',
        valid_options={'y': True, 'n': False}
    )
    if start_confirm:
        adb_push_files(source_folder, target_folder, files_to_sync)
    else:
        print("Transfer cancelled.")
        return


if __name__ == "__main__":
    main()
