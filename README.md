
# adb-photo-sync

A Python script to sync photos and files between a Mac and an Android device using ADB, with options to convert HEIC files to JPG, and customizable sync modes.
The script calculates metadata like the number of files, their total size, and provides a progress bar for tracking. After a successful sync, there’s an option to delete only the files from the source folder, keeping the folder structure intact.

## Features
- **HEIC to JPG Conversion**: Optionally converts HEIC files to JPG before transfer, with fallbacks in case of conversion issues.
- **Customizable Sync Modes**: Choose to sync all files or only those added/modified since the last sync.
- **Progress Monitoring**: Real-time progress bar with file count tracking.
- **Selective Deletion**: Deletes only files in the source folder post-transfer, preserving folder structure.
- **Metadata Display**: Shows the number of files, total size, and estimated time before starting the sync.

## Requirements
- Python 3.9 or later
- `adb` (Android Debug Bridge) installed and accessible in PATH
- Additional dependencies (install with `pip`):
  ```bash
  pip install -r requirements.txt
  ```

## Device Preparation
Ensure your Android device is connected to the Mac via ADB. Enable **Developer Options** and **USB Debugging** on your Android device. You can verify the connection with:
```bash
adb devices
```

This should list your device as connected. If you don’t see your device, make sure ADB is correctly installed and functioning.

## Usage
1. Clone this repository.
2. Navigate to the project directory and ensure `adb` and Python dependencies are correctly set up.
3. Run the script:
   ```bash
   python3 main.py
   ```

4. Follow the prompts:
   - Choose to convert HEIC files (default is to convert).
   - Select sync mode: Sync All files or Sync Only New Files.
   - Confirm the transfer based on file metadata.
   - After a successful sync, confirm if you'd like to delete files from the source folder.

## File Structure
- `main.py`: Main script file for syncing files.
- `last_sync_time.txt`: Stores the timestamp of the last sync for incremental syncing.

## Example
To run the sync with full features:
```bash
python3 main.py
```

## License
This project is licensed under the MIT License.
