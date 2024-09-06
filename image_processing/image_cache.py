import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from PyQt6.QtGui import QPixmapCache, QPixmap

import config
import logger

if config.platform_name == 'Linux':
    import inotify.adapters
    import fcntl
elif config.platform_name in ('Windows', 'Darwin'):
    import msvcrt
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

executor = ThreadPoolExecutor(max_workers=4)


class MetadataManager:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.metadata_pool = ThreadPoolExecutor(max_workers=3)

    def save_metadata(self, image_path, metadata):
        """Save metadata asynchronously."""
        cache_path = self.get_cache_path(image_path)

        def async_save():
            with open(cache_path, 'wb') as f:
                pickle.dump(metadata, f)
            logger.info(f"[MetadataManager] Metadata saved for {image_path}.")

        executor.submit(async_save)

    def load_metadata(self, image_path):
        """Load metadata with non-blocking file integrity check."""
        cache_path = self.get_cache_path(image_path)
        if self._file_is_ready(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except (EOFError, pickle.UnpicklingError):
                logger.error(f"[MetadataManager] Failed to load metadata for {image_path}.")
                os.remove(cache_path)
                return None
        else:
            logger.warning(f"[MetadataManager] File {cache_path} is not ready.")
        return None

    def _file_is_ready(self, file_path):
        """Check if the file is ready by attempting to acquire a non-blocking lock."""
        try:
            with open(file_path, 'rb') as f:
                if 'linux' in config.platform_name.lower():
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Try to lock exclusively without blocking
                    fcntl.flock(f, fcntl.LOCK_UN)  # Unlock immediately
                elif 'windows' in config.platform_name.lower():
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, os.path.getsize(file_path))
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, os.path.getsize(file_path))
            return True
        except (IOError, OSError):
            return False

    def get_cache_path(self, image_path):
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def has_metadata(self, image_path):
        cache_path = self.get_cache_path(image_path)
        return os.path.exists(cache_path)

    def regenerate_metadata(self, image_path):
        # Placeholder for actual metadata extraction logic
        # Replace with actual logic to extract metadata from the image file
        try:
            # Example logic: extract metadata from the image (implement this based on your needs)
            metadata = {
                "example_key": "example_value"
            }
            return metadata
        except Exception as e:
            logger.error(f"[MetadataManager] Error regenerating metadata for {image_path}: {e}")
            return None


class ImageCache:
    def __init__(self, max_size=500, debounce_interval=0.5, stability_check_interval=1, stability_check_retries=3):
        self.max_size = max_size  # Cache limit in MB
        self.cache_dir = config.cache_dir
        self.metadata_manager = MetadataManager(self.cache_dir)
        self._setup_cache_directory()
        QPixmapCache.setCacheLimit(self.max_size * 1024)  # Convert MB to KB for QPixmapCache
        self.debounce_interval = debounce_interval  # Time to wait before processing events
        self.stability_check_interval = stability_check_interval  # Time between stability checks
        self.stability_check_retries = stability_check_retries  # Number of retries to check stability/
        self.event_pool = ThreadPoolExecutor(max_workers=5)  # Thread pool for handling events
        self.initialize_watchdog()

    def _file_is_stable(self, image_path):
        """Check if the file's size is stable over time."""
        previous_size = -1
        retries = 0

        while retries < self.stability_check_retries:
            current_size = os.path.getsize(image_path)
            if current_size == previous_size:
                return True  # File size is stable
            previous_size = current_size
            retries += 1
            time.sleep(self.stability_check_interval)

        logger.warning(f"[ImageCache] File {image_path} is not stable after {self.stability_check_retries} retries.")
        return False

    def refresh_cache(self, image_path):
        """Asynchronously refresh the cache, but only if the file is stable."""
        logger.info(f"[ImageCache] Refreshing cache for {image_path}")
        if self.metadata_manager._file_is_ready(image_path):
            self.event_pool.submit(self._refresh_task, image_path)
        else:
            logger.warning(f"[ImageCache] Skipping cache refresh for {image_path} - file is not ready.")

    def _refresh_task(self, image_path):
        """Actual cache refresh task."""
        QPixmapCache.remove(image_path)
        pixmap = self._load_pixmap_from_disk(image_path)
        if pixmap:
            self.add_to_cache(image_path, pixmap)

    def _load_pixmap_from_disk(self, image_path):
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            return pixmap
        return None

    def add_to_cache(self, image_path, pixmap):
        """Add pixmap to cache asynchronously."""
        QPixmapCache.insert(image_path, pixmap)
        metadata = {'size': pixmap.size(), 'cache_key': pixmap.cacheKey()}
        self.metadata_manager.save_metadata(image_path, metadata)

    def initialize_watchdog(self):
        """Initialize the watchdog or inotify system based on platform."""
        if config.platform_name in ('Windows', 'Darwin'):
            self._init_watchdog()
        elif config.platform_name == 'Linux':
            self._init_inotify()

    def _init_inotify(self):
        i = inotify.adapters.Inotify()
        i.add_watch(self.cache_dir)

        for event in i.event_gen(yield_nones=False):
            (_, type_names, path, filename) = event
            if 'IN_CLOSE_WRITE' in type_names:
                image_path = os.path.join(path, filename)
                # Debounce the events and submit to the thread pool
                self._debounced_cache_refresh(image_path)

    def _init_watchdog(self):
        event_handler = ImageCacheEventHandler(self)
        observer = Observer()

        for start_dir in config.start_dirs:
            observer.schedule(event_handler, start_dir, recursive=True)

        observer.start()
        logger.info(f"[ImageCache] Watchdog started, monitoring directories: {config.start_dirs}")

    def _batch_cache_refresh(self, image_paths):
        """Batch cache refresh to handle multiple file system events at once."""
        for image_path in image_paths:
            self._debounced_cache_refresh(image_path)

    def _debounced_cache_refresh(self, image_path):
        """Submit the cache refresh to the thread pool with a debounce interval."""

        def debounced_task():
            time.sleep(self.debounce_interval)
            self.refresh_cache(image_path)

        # Submit the cache refresh task to the thread pool
        self.event_pool.submit(debounced_task)

    def _setup_cache_directory(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    @lru_cache(maxsize=128)
    def retrieve_pixmap(self, image_path):
        """Retrieve the pixmap from cache or load it from disk if not found."""
        pixmap = self.find_pixmap(image_path)  # Check if it's in the cache
        if pixmap:
            logger.debug(f"[ImageCache] Pixmap found in cache for {image_path}")
        else:
            pixmap = self._load_pixmap_from_disk(image_path)  # Load from disk if not in cache
            if pixmap:
                self._cache_pixmap(image_path, pixmap)  # Cache it if loaded from disk
                logger.info(f"[ImageCache] Loaded pixmap from disk and cached: {image_path}")
        return pixmap

    def find_pixmap(self, image_path):
        return QPixmapCache.find(image_path)

    def _cache_pixmap(self, image_path, pixmap):
        """Internal method to add pixmap to cache and save metadata."""
        if not pixmap.isNull():
            QPixmapCache.insert(image_path, pixmap)
            metadata = {'size': pixmap.size(), 'cache_key': pixmap.cacheKey()}
            self.metadata_manager.save_metadata(image_path, metadata)

    def get_metadata(self, image_path):
        return self.metadata_manager.load_metadata(image_path)


class ImageCacheEventHandler(FileSystemEventHandler):
    def __init__(self, image_cache):
        super().__init__()
        self.image_cache = image_cache

    def on_modified(self, event):
        if not event.is_directory:
            self.image_cache._debounced_cache_refresh(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.image_cache._debounced_cache_refresh(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.image_cache.refresh_cache(event.src_path)
