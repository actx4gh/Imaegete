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

from core import logger


class CacheManager(QObject):
    image_loaded = pyqtSignal(str)

    def __init__(self, cache_dir, thread_manager, image_directories, max_size=500, debounce_interval=0.5,
                 stability_check_interval=1,
                 stability_check_retries=3):
        super().__init__()
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
        """Load image from disk and insert into cache."""
        image = QImage(image_path)
        if not image.isNull():
            logger.debug(f"[CacheManager] Loaded image from disk: {image_path}")
            with self.cache_lock:
                self.image_cache[image_path] = image
                self.currently_loading.discard(image_path)
                self.image_cache.move_to_end(image_path)
                # Limit cache size
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
        """Asynchronously refresh the cache for the given image."""
        logger.info(f"[CacheManager] Refreshing cache for {image_path}")
        if self.metadata_manager._file_is_ready(image_path):
            self.thread_manager.submit_task(self._refresh_task, image_path)
        else:
            logger.warning(f"[CacheManager] Skipping cache refresh for {image_path} - file is not ready.")

    def _refresh_task(self, image_path):
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
        """Gracefully shutdown the watchdog observer and remaining cache operations."""
        logger.info("[CacheManager] Initiating shutdown.")
        self.shutdown_watchdog()
        self.metadata_manager.shutdown()

    def initialize_watchdog(self):
        """Initialize the watchdog to monitor changes in the image directories."""
        event_handler = CacheEventHandler(self)
        self.watchdog_observer = Observer()
        for directory in self.image_directories:
            self.watchdog_observer.schedule(event_handler, directory, recursive=True)
        self.watchdog_observer.start()
        logger.info(f"[CacheManager] Watchdog started, monitoring directories: {self.image_directories}")

        self.thread_manager.submit_task(self._monitor_watchdog)

    def _monitor_watchdog(self):
        """Monitor the watchdog observer and restart if it crashes."""
        while not self.thread_manager.is_shutting_down:
            if not self.watchdog_observer.is_alive():
                self.restart_watchdog()
            time.sleep(self.stability_check_interval)

    def restart_watchdog(self):
        """Restart the watchdog observer in case of failure."""
        logger.warning("[CacheManager] Watchdog observer crashed. Restarting...")
        self.shutdown_watchdog()
        self.initialize_watchdog()

    def shutdown_watchdog(self):
        """Stop the watchdog observer."""
        if hasattr(self, 'watchdog_observer') and self.watchdog_observer.is_alive():
            self.watchdog_observer.stop()
            self.watchdog_observer.join()
            logger.info("[CacheManager] Watchdog observer stopped.")

    def _setup_cache_directory(self):
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
    def __init__(self, cache_dir, thread_manager):
        """Initialize MetadataManager with the cache directory and ThreadManager."""
        self.cache_dir = cache_dir
        self.thread_manager = thread_manager
        self.lock = ReaderWriterLock()

    def save_metadata(self, image_path, metadata):
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
        """Generate the file path for the metadata cache."""
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def shutdown(self):
        """Perform any necessary cleanup for MetadataManager."""
        logger.info("[MetadataManager] Shutting down MetadataManager.")

    def _file_is_ready(self, image_path):
        """Check if the file is ready for reading."""
        # Implement a method to check if the file is stable (not being written to)
        # For simplicity, we'll assume the file is always ready
        return True


class CacheEventHandler(FileSystemEventHandler):
    def __init__(self, cache_manager):
        """Initialize event handler with reference to CacheManager."""
        super().__init__()
        self.cache_manager = cache_manager

    def on_modified(self, event):
        """Handle file modified events."""
        if not event.is_directory:
            self.cache_manager._debounced_cache_refresh(event.src_path)

    def on_created(self, event):
        """Handle file created events."""
        if not event.is_directory:
            self.cache_manager._debounced_cache_refresh(event.src_path)

    def on_deleted(self, event):
        """Handle file deleted events."""
        if not event.is_directory:
            with self.cache_manager.cache_lock:
                self.cache_manager.image_cache.pop(event.src_path, None)
                self.cache_manager.currently_loading.discard(event.src_path)
                logger.info(f"[CacheManager] Removed deleted image from cache: {event.src_path}")
            self.cache_manager.metadata_manager.save_metadata(event.src_path, None)
