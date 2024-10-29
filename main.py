import os
import subprocess
import shutil
from typing import Optional

from tqdm import tqdm
import time

LAST_SYNC_FILE = "last_sync_time.txt"


def calculate_metadata(sync_source_folder: str, last_sync_timestamp: Optional[float] = None) -> tuple[
    int, int, list[str]]:
    total_size = 0
    file_count = 0
    files_for_sync = []

    for root, _, files in os.walk(sync_source_folder):
        for file in files:
            file_path = os.path.join(root, file)
            # Check if the file was modified after the last sync time
            if last_sync_timestamp is None or os.path.getmtime(file_path) > last_sync_timestamp:
                total_size += os.path.getsize(file_path)
                file_count += 1
                files_for_sync.append(file_path)

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
            shutil.rmtree(source_dir)
            print(f"Deleted all files from {source_dir}.")
        else:
            print("Files were not deleted.")
    else:
        print("Some files failed to push. Please check and try again.")


def get_sync_mode():
    while True:
        sync_mode = input("Choose sync mode: (1) Sync All or (2) Sync Only New Files: ").strip()
        if sync_mode not in ['1', '2']:
            print("Invalid choice. Please enter '1' or '2'.")
        else:
            return sync_mode


if __name__ == "__main__":
    # Define source and target folders
    source_folder = os.path.expanduser("~/photos")  # source folder
    target_folder = "/storage/self/primary/Download"  # target folder

    # Calculate metadata and list of files to sync
    num_files, total_size_bytes, files_to_sync = calculate_metadata(
        sync_source_folder=source_folder,
        last_sync_timestamp=None if get_sync_mode() == '1' else get_last_sync_timestamp())

    print(f"Total photos/files to transfer: {num_files}")
    print(f"Total size: {total_size_bytes / (1024 * 1024):.2f} MB\n")

    # Confirm before starting the transfer
    start_confirm = input("Start the transfer? (y/N): ").strip().lower()
    if start_confirm != 'y':
        print("Transfer cancelled.")
    else:
        adb_push_files(source_folder, target_folder, files_to_sync)
