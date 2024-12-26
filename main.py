from src.core.sync_manager import PhotoSyncManager


def main():
    """Entry point of the application."""
    sync_manager = PhotoSyncManager()
    sync_manager.run()


if __name__ == "__main__":
    main()
