
# adb-photo-sync

A Python script to sync photos and files between a Mac and an Android device using ADB, with customizable sync modes. 
The script calculates metadata like the number of files, their total size, and estimated transfer time. 
It also includes a progress bar for tracking and has an option to delete synced files from the Mac after a successful transfer.

## Features
- **Customizable Sync Modes**: Choose to sync all files or only files added/modified since the last sync.
- **Progress Monitoring**: Real-time progress bar with estimated transfer time and file count.
- **Automatic Deletion**: Option to delete original files on Mac after successful transfer.
- **Metadata Display**: Shows number of files, total size, and estimated time before starting the sync.

## Requirements
- Python 3.9 or later
- `adb` (Android Debug Bridge) installed and accessible in PATH
- `tqdm` library for the progress bar. Install with:

  ```bash
  pip install tqdm
  ```

## Device Preparation
Make sure your Android device is connected to the Mac via ADB. Enable **Developer Options** and **USB Debugging** on your Android device. You can test the connection with:
```bash
adb devices
```

This should show your device as connected. If you don’t see your device, ensure ADB is installed and working properly.

## Usage
1. Clone this repository to your local machine.
2. Navigate to the project directory and ensure `adb` and Python dependencies are properly set up.
3. Run the script:

   ```bash
   python3 adb-photo-sync.py
   ```

4. Follow the prompts:
   - Choose a sync mode: Sync All files or Sync Only New Files.
   - Confirm the transfer based on file metadata.
   - After a successful sync, you can choose to delete the original files from your Mac.

## File Structure
- `adb-photo-sync.py`: Main script file for syncing files.
- `last_sync_time.txt`: Stores the timestamp of the last sync for incremental syncing.

## Example
To run the sync with full features:
```bash
python3 adb-photo-sync.py
```

## License
This project is licensed under the MIT License.
