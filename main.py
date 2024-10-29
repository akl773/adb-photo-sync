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
    """Delete all files in the specified folder, keeping the folder structure intact."""
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)
            print(f"Deleted file: {file_path}")


def confirm_heic_conversion() -> bool:
    """Ask user for confirmation to convert HEIC to JPG with default as convert."""
    convert_confirm = input("Convert HEIC files to JPG before transfer? (Y/n): ").strip().lower()
    return convert_confirm != 'n'  # Default to convert if user just presses Enter or inputs 'y'


def convert_heic_to_jpg(file_path: str) -> str:
    """Convert a HEIC image to JPG. Attempt pyheif first, fallback to imageio, or skip if both fail."""
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
            # Attempt conversion with imageio
            image = Image.fromarray(imageio.imread(file_path))
        except Exception:
            print(f"imageio also failed to read {file_path}. Skipping conversion.")
            return file_path  # Return original HEIC path if both methods fail

    # Save the converted image as JPG
    jpg_path = file_path.replace(".heic", ".jpg")
    image.save(jpg_path, "JPEG")
    return jpg_path


def calculate_metadata(sync_source_folder: str, last_sync_timestamp: Optional[float] = None,
                       convert_heic: bool = True) -> tuple[int, int, list[str]]:
    total_size = 0
    file_count = 0
    files_for_sync = []

    for root, _, files in os.walk(sync_source_folder):
        for file in files:
            file_path = os.path.join(root, file)

            # Convert HEIC to JPG if the user confirmed
            if convert_heic and file.lower().endswith(".heic"):
                print(f"Converting {file} to JPG...")
                file_path = convert_heic_to_jpg(file_path)

            # Check if the file was modified after the last sync time
            if last_sync_timestamp is None or os.path.getmtime(file_path) > last_sync_timestamp:
                file_size = os.path.getsize(file_path)

                # Only add if the file size is greater than zero
                if file_size > 0:
                    total_size += file_size
                    file_count += 1
                    files_for_sync.append(file_path)
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


def adb_push_files(source_dir: str, target_dir: str, files_for_transfer: list[str]) -> None:
    # Check if adb is accessible
    try:
        subprocess.run(["adb", "devices"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("ADB is not installed or not accessible in PATH.")
        return

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
            subprocess.run(["adb", "shell", "mkdir", "-p", remote_dir])

            # Push the file
            result = subprocess.run(["adb", "push", local_file_path, android_target_path], capture_output=True)

            # Update progress bar
            progress_bar.update(1)

            # Check if the push was successful
            if result.returncode != 0:
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


def get_sync_mode():
    while True:
        sync_mode = input("Choose sync mode: (1) Sync All or (2) Sync Only New Files [default: 1]: ").strip()
        if sync_mode == '':
            return '1'  # Default to '1' if the user presses Enter
        elif sync_mode in ['1', '2']:
            return sync_mode
        else:
            print("Invalid choice. Please enter '1' or '2'.")


def main():
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    source_folder = os.path.join(repo_dir, "photos")
    target_folder = "/storage/self/primary/syncPhotos"

    convert_heic = confirm_heic_conversion()
    sync_mode = get_sync_mode()
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

    start_confirm = input("Start the transfer? (y/N): ").strip().lower()
    if start_confirm != 'y':
        print("Transfer cancelled.")
    else:
        adb_push_files(source_folder, target_folder, files_to_sync)


if __name__ == "__main__":
    main()
