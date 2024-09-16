import os
import pickle
import threading
import time
from collections import OrderedDict

from PyQt6.QtCore import QObject, QCoreApplication, pyqtSignal
from PyQt6.QtGui import QImage
from fasteners import ReaderWriterLock
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core import config
from core import logger


class CacheManager(QObject):
    """
    A class to manage the caching of images, including loading, refreshing, and handling metadata.
    """
    image_loaded = pyqtSignal(str)

    def __init__(self, cache_dir, thread_manager, image_directories, max_size=500, debounce_interval=0.5,
                 stability_check_interval=1,
                 stability_check_retries=3):
        super().__init__()
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.debounce_interval = debounce_interval
        self.stability_check_interval = stability_check_interval
        self.stability_check_retries = stability_check_retries
        self.cache_dir = cache_dir
        self.thread_manager = thread_manager
        self.image_directories = image_directories
        self.max_size = max_size
        self.metadata_cache = OrderedDict()
        self.metadata_manager = MetadataManager(self.cache_dir, self.thread_manager)
        self.image_cache = OrderedDict()
        self.currently_loading = set()
        self.cache_lock = threading.Lock()
        self.debounce_tasks = {}
        self.moveToThread(QCoreApplication.instance().thread())
        self._setup_cache_directory()
        self.initialize_watchdog()
        self.currently_active_requests = set()

    def retrieve_image(self, image_path, active_request=False):
        """
        Retrieve an image from the cache, or load it from disk if not present in the cache.

        :param image_path: The path to the image file.
        :type image_path: str
        :param active_request: A flag indicating if this is an active request that requires the image.
        :type active_request: bool
        :return: The cached image or None if loading is in progress.
        :rtype: QImage or None
        """
        """Retrieve image from cache or load from disk if not available."""
        with self.cache_lock:
            image = self.image_cache.get(image_path)
            if image:
                logger.debug(f"[CacheManager] Image found in cache for {image_path}")
                self.image_cache.move_to_end(image_path)
                return image
            elif image_path in self.currently_loading:
                logger.debug(f"[CacheManager] Image is currently being loaded: {image_path}")
                return None
            else:
                logger.debug(f"[CacheManager] Image not found in cache, loading from disk: {image_path}")
                self.currently_loading.add(image_path)
                if active_request:
                    self.currently_active_requests.add(image_path)
                self.thread_manager.submit_task(self._load_image_task, image_path)
                return None

    def _load_image_task(self, image_path):
        """
        Load an image from the disk and store it in the cache.

        :param image_path: The path of the image to load.
        :type image_path: str
        """
        """Load image from disk and insert into cache."""
        image = QImage(image_path)
        if not image.isNull():
            logger.debug(f"[CacheManager] Loaded image from disk: {image_path}")
            with self.cache_lock:
                self.image_cache[image_path] = image
                self.currently_loading.discard(image_path)
                self.image_cache.move_to_end(image_path)

                if len(self.image_cache) > self.max_size:
                    removed_item = self.image_cache.popitem(last=False)
                    logger.debug(f"[CacheManager] Cache size exceeded, removing oldest item: {removed_item[0]}")
            file_size = os.path.getsize(image_path)
            last_modified = os.path.getmtime(image_path)
            metadata = {
                'size': image.size(),
                'file_size': file_size,
                'last_modified': last_modified
            }
            self.metadata_manager.save_metadata(image_path, metadata)
            self.metadata_cache[image_path] = metadata
            if image_path in self.currently_active_requests:
                self.image_loaded.emit(image_path)
                self.currently_active_requests.discard(image_path)
        else:
            logger.error(f"[CacheManager] Failed to load image from disk: {image_path}")
            with self.cache_lock:
                self.currently_loading.discard(image_path)

    def refresh_cache(self, image_path):
        """
        Refresh the cache for a specific image asynchronously.

        :param image_path: The path of the image to refresh in the cache.
        :type image_path: str
        """
        """Asynchronously refresh the cache for the given image."""
        logger.info(f"[CacheManager] Refreshing cache for {image_path}")
        if self.metadata_manager._file_is_ready(image_path):
            self.thread_manager.submit_task(self._refresh_task, image_path)
        else:
            logger.warning(f"[CacheManager] Skipping cache refresh for {image_path} - file is not ready.")

    def _refresh_task(self, image_path):
        """
        Internal task to refresh the cache for an image.

        :param image_path: The path of the image to refresh.
        :type image_path: str
        """
        """Actual cache refresh task."""
        with self.cache_lock:
            self.image_cache.pop(image_path, None)
            self.currently_loading.discard(image_path)
        self._load_image_task(image_path)

    def _debounced_cache_refresh(self, image_path):
        """Submit the cache refresh task to the thread pool with a debouncing mechanism."""

        def debounced_task():
            if self.debounce_tasks.get(image_path):
                del self.debounce_tasks[image_path]
            self.refresh_cache(image_path)

        if image_path not in self.debounce_tasks:
            future_task = self.thread_manager.submit_task(debounced_task)
            self.debounce_tasks[image_path] = future_task

    def shutdown(self):
        """
        Gracefully shut down the CacheManager, including the watchdog observer and metadata manager.
        """
        """
        Perform necessary cleanup for the MetadataManager.
        """
        """Gracefully shutdown the watchdog observer and remaining cache operations."""
        logger.info("[CacheManager] Initiating shutdown.")
        self.shutdown_watchdog()
        self.metadata_manager.shutdown()

    def initialize_watchdog(self):
        """
        Initialize the watchdog observer to monitor changes in the image directories, excluding
        specific subdirectories that match `dest_folders` or `delete_folders`.
        """
        event_handler = CacheEventHandler(self)
        self.watchdog_observer = Observer()

        # Set to store directories that should be excluded
        directories_to_exclude = set()

        # Loop through each start directory and find corresponding subdirectories to exclude
        for start_dir in self.image_directories:
            # Exclude subdirectories from dest_folders
            if start_dir in self.dest_folders:
                # dest_folders contains a dictionary mapping category names to folder paths
                for dest_subfolder in self.dest_folders[start_dir].values():
                    directories_to_exclude.add(os.path.normpath(dest_subfolder))

            # Exclude the folder listed in delete_folders for this start_dir
            if start_dir in self.delete_folders:
                delete_folder = self.delete_folders[start_dir]
                directories_to_exclude.add(os.path.normpath(delete_folder))

        # Schedule the observer for each start directory, but exclude directories in directories_to_exclude
        for directory in self.image_directories:
            if os.path.normpath(directory) not in directories_to_exclude:
                self.watchdog_observer.schedule(event_handler, directory, recursive=True)

        self.watchdog_observer.start()
        logger.info(f"[CacheManager] Watchdog started, monitoring directories excluding: {directories_to_exclude}")
        self.thread_manager.submit_task(self._monitor_watchdog)

    def _monitor_watchdog(self):
        """Monitor the watchdog observer and restart if it crashes."""
        while not self.thread_manager.is_shutting_down:
            if not self.watchdog_observer.is_alive():
                self.restart_watchdog()
            time.sleep(self.stability_check_interval)

    def restart_watchdog(self):
        """
        Restart the watchdog observer if it crashes.
        """
        """Restart the watchdog observer in case of failure."""
        logger.warning("[CacheManager] Watchdog observer crashed. Restarting...")
        self.shutdown_watchdog()
        self.initialize_watchdog()

    def shutdown_watchdog(self):
        """
        Gracefully shut down the CacheManager, including the watchdog observer and metadata manager.
        """
        """
        Perform necessary cleanup for the MetadataManager.
        """
        """Stop the watchdog observer."""
        if hasattr(self, 'watchdog_observer') and self.watchdog_observer.is_alive():
            self.watchdog_observer.stop()
            self.watchdog_observer.join()
            logger.info("[CacheManager] Watchdog observer stopped.")

    def _setup_cache_directory(self):
        """
        Set up the cache directory by creating it if it does not exist.
        """
        """Ensure the cache directory exists."""
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
                logger.info(f"[CacheManager] Cache directory created: {self.cache_dir}")
            except OSError as e:
                logger.error(f"[CacheManager] Failed to create cache directory: {e}")
        else:
            logger.info(f"[CacheManager] Cache directory already exists: {self.cache_dir}")

    def get_metadata(self, image_path):
        """
        Retrieve metadata for an image from the cache or load it from disk if not available.

        :param image_path: The path of the image to retrieve metadata for.
        :type image_path: str
        :return: The metadata of the image or None if not found.
        :rtype: dict or None
        """
        """Retrieve metadata from cache or load from disk if not cached."""
        if image_path in self.metadata_cache:
            self.metadata_cache.move_to_end(image_path)
            return self.metadata_cache[image_path]

        metadata = self.metadata_manager.load_metadata(image_path)
        if metadata:
            self.metadata_cache[image_path] = metadata
            if len(self.metadata_cache) > self.max_size:
                self.metadata_cache.popitem(last=False)
        return metadata


class MetadataManager:
    """
    A class to manage the metadata of images, including saving and loading metadata.
    """

    def __init__(self, cache_dir, thread_manager):
        """Initialize MetadataManager with the cache directory and ThreadManager."""
        self.cache_dir = cache_dir
        self.thread_manager = thread_manager
        self.lock = ReaderWriterLock()

    def save_metadata(self, image_path, metadata):
        """
        Save metadata for an image asynchronously.

        :param image_path: The path of the image.
        :type image_path: str
        :param metadata: The metadata to save.
        :type metadata: dict
        """

        def async_save():
            cache_path = self.get_cache_path(image_path)
            current_metadata = self.load_metadata(image_path)

            if current_metadata != metadata:
                with self.lock.write_lock():
                    with open(cache_path, 'wb') as f:
                        pickle.dump(metadata, f)
                logger.debug(f"[MetadataManager] Metadata saved for {image_path}.")

        self.thread_manager.submit_task(async_save)

    def load_metadata(self, image_path):
        """
        Load metadata from the disk in a thread-safe manner.

        :param image_path: The path of the image to load metadata for.
        :type image_path: str
        :return: The loaded metadata or None if not found.
        :rtype: dict or None
        """
        """Load metadata from disk with thread-safe reading."""
        cache_path = self.get_cache_path(image_path)
        if os.path.exists(cache_path):
            with self.lock.read_lock():
                try:
                    with open(cache_path, 'rb') as f:
                        return pickle.load(f)
                except Exception as e:
                    logger.error(f"[MetadataManager] Failed to load metadata for {image_path}: {e}")
                    return None
        return None

    def get_cache_path(self, image_path):
        """
        Generate the file path for the metadata cache of an image.

        :param image_path: The path of the image.
        :type image_path: str
        :return: The cache file path for the image.
        :rtype: str
        """
        """Generate the file path for the metadata cache."""
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def shutdown(self):
        """
        Gracefully shut down the CacheManager, including the watchdog observer and metadata manager.
        """
        """
        Perform necessary cleanup for the MetadataManager.
        """
        """Perform any necessary cleanup for MetadataManager."""
        logger.info("[MetadataManager] Shutting down MetadataManager.")

    def _file_is_ready(self, image_path):
        """Check if the file is ready for reading."""

        return True


class CacheEventHandler(FileSystemEventHandler):
    """
    A class to handle filesystem events related to the image cache, such as file creation, modification, and deletion.
    """

    def __init__(self, cache_manager):
        """Initialize event handler with reference to CacheManager."""
        super().__init__()
        self.cache_manager = cache_manager

    def on_modified(self, event):
        """
        Handle file modification events to refresh the cache.

        :param event: The filesystem event that triggered the modification.
        :type event: FileSystemEvent
        """
        """Handle file modified events."""
        if not event.is_directory:
            self.cache_manager._debounced_cache_refresh(event.src_path)

    def on_created(self, event):
        """
        Handle file creation events to refresh the cache.

        :param event: The filesystem event that triggered the creation.
        :type event: FileSystemEvent
        """
        """Handle file created events."""
        if not event.is_directory:
            self.cache_manager._debounced_cache_refresh(event.src_path)

    def on_deleted(self, event):
        """
        Handle file deletion events by removing the image from the cache.

        :param event: The filesystem event that triggered the deletion.
        :type event: FileSystemEvent
        """
        """Handle file deleted events."""
        if not event.is_directory:
            with self.cache_manager.cache_lock:
                self.cache_manager.image_cache.pop(event.src_path, None)
                self.cache_manager.currently_loading.discard(event.src_path)
                logger.info(f"[CacheManager] Removed deleted image from cache: {event.src_path}")
            self.cache_manager.metadata_manager.save_metadata(event.src_path, None)
