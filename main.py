import os
import subprocess
import shutil

def adb_push_all(source_folder, target_folder):
    # Check if adb is accessible
    try:
        subprocess.run(["adb", "devices"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("ADB is not installed or not accessible in PATH.")
        return

    # Track whether all files were pushed successfully
    all_pushed = True

    # Walk through the source folder
    for root, dirs, files in os.walk(source_folder):
        # Get the relative path of the current directory within the source folder
        rel_path = os.path.relpath(root, source_folder)
        target_path = os.path.join(target_folder, rel_path)

        # Push each file individually to the target path on Android
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(target_path, file)

            print(f"Pushing {local_file} to {remote_file}...")
            result = subprocess.run(["adb", "push", local_file, remote_file])

            # Check if the push was successful
            if result.returncode != 0:
                print(f"Failed to push {local_file}.")
                all_pushed = False

    # If all files were pushed successfully, prompt for deletion
    if all_pushed:
        delete_confirm = input("All files pushed successfully. Files will be deleted from your Mac unless you type 'n'. Proceed? (default: yes): ").strip().lower()
        if delete_confirm != 'n':
            shutil.rmtree(source_folder)
            print(f"Deleted all files from {source_folder}.")
        else:
            print("Files were not deleted.")
    else:
        print("Some files failed to push. Please check and try again.")

if __name__ == "__main__":
    # Define source and target folders
    source_folder = os.path.expanduser("~/Photos")  # Your Mac's Photos folder
    target_folder = "/storage/self/primary/Download"  # Target folder on Android

    adb_push_all(source_folder, target_folder)
