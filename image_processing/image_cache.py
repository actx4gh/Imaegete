import os
import pickle
import platform
from collections import OrderedDict

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap, QPixmapCache

import config
import logger

if config.platform_name == 'Linux':
    import inotify.adapters
elif config.platform_name == 'Windows' or config.platform_name == 'Darwin':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler


class ImageCache:
    def __init__(self, app_name='ImageSorter', refresh_image_list_callback=None, ensure_valid_index_callback=None,
                 image_list_changed_callback=None,
                 max_size=100):
        self.app_name = app_name
        self.metadata_cache = OrderedDict()
        self.max_size = max_size
        self.cache_dir = config.cache_dir

        if not os.path.exists(self.cache_dir):
            logger.debug(f'Creating new cache dir {self.cache_dir}')
            os.makedirs(self.cache_dir)
        else:
            logger.debug(f'Found existing cache dir {self.cache_dir}')

        new_cache_limit = 204800  # Example: set to 200 MB (204800 KB)
        QPixmapCache.setCacheLimit(new_cache_limit)
        logger.info(f"QPixmapCache limit set to: {new_cache_limit} KB")

        self.refresh_image_list_callback = refresh_image_list_callback
        self.ensure_valid_index_callback = ensure_valid_index_callback
        self.image_list_changed_callback = image_list_changed_callback  # Added callback for status bar updates

        # Initialize watchdog or inotify
        if config.platform_name in ('Windows', 'Darwin'):
            self._init_watchdog()
        elif config.platform_name == 'Linux':
            self._init_inotify()

    def get_cache_path(self, image_path):
        """Generate a file path for the cached image and metadata."""
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def save_cache_to_disk(self, image_path, metadata):
        """Save metadata to disk."""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.debug(f'Created cache directory: {self.cache_dir}')
        cache_path = self.get_cache_path(image_path)
        with open(cache_path, 'wb') as f:
            pickle.dump(metadata, f)
        logger.info(f"Metadata saved to disk for {image_path} at {cache_path}")

    def load_cache_from_disk(self, image_path):
        """Load metadata from disk."""
        cache_path = self.get_cache_path(image_path)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    metadata = pickle.load(f)
                logger.info(f"Metadata loaded from disk for {image_path} from {cache_path}")
                return metadata
            except EOFError:
                logger.error(f"Failed to load metadata for {image_path}: EOFError")
        else:
            logger.warning(f"No cache file found for {image_path} at {cache_path}")
        return None

    def add_to_cache(self, image_path, pixmap=None, metadata=None):
        """Add pixmap and metadata to the cache."""
        if pixmap and not pixmap.isNull():
            QPixmapCache.insert(image_path, pixmap)  # Insert pixmap into cache

        # Update LRU for metadata
        if metadata:
            if image_path in self.metadata_cache:
                # Move the existing item to the end (most recently used)
                self.metadata_cache.move_to_end(image_path)
            self.metadata_cache[image_path] = metadata
            if len(self.metadata_cache) > self.max_size:
                # Remove the least recently used item
                self.metadata_cache.popitem(last=False)
            self.save_cache_to_disk(image_path, metadata)

    def get_pixmap(self, image_path):
        """Get the pixmap from QPixmapCache using consistent key."""
        pixmap = QPixmapCache.find(image_path)
        if pixmap:
            # Move to end to mark as recently used
            self.metadata_cache.move_to_end(image_path)
            return pixmap
        return None

    def get_metadata(self, image_path):
        """Retrieve metadata for an image from the cache or load from disk."""
        if image_path in self.metadata_cache:
            # Move to end to mark as recently used
            self.metadata_cache.move_to_end(image_path)
            return self.metadata_cache[image_path]

        # Load from disk if not in memory
        metadata = self.load_cache_from_disk(image_path)
        if metadata:
            self.metadata_cache[image_path] = metadata
            self.metadata_cache.move_to_end(image_path)
        return metadata or {}

    def load_image(self, image_path):
        """Load an image from the cache or file system."""
        pixmap = self.get_pixmap(image_path)
        if pixmap:
            return pixmap

        # If not in cache, load the image and metadata
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            logger.error(f"Failed to load image: {image_path}")
            return None

        metadata = self.extract_metadata(image_path, pixmap)
        self.add_to_cache(image_path, pixmap, metadata)
        return pixmap

    def extract_metadata(self, image_path, pixmap):
        stat_info = os.stat(image_path)
        metadata = {
            'size': pixmap.size(),
            'format': pixmap.cacheKey(),
            'last_modified': stat_info.st_mtime,  # Unix timestamp
            'file_size': stat_info.st_size,
        }
        logger.debug(f'Extracted metadata {metadata} from {image_path}')
        # Platform-specific optimization
        if platform.system() == 'Linux':
            metadata['inode'] = stat_info.st_ino  # Add inode for Linux

        return metadata

    def monitor_file_changes(self):
        """Monitor file changes and update the cache if needed."""
        if config.platform_name == 'Linux':
            # Initialize inotify for Linux
            self._init_inotify()
        elif config.platform_name in ('Windows', 'Darwin'):
            # Initialize watchdog for Windows and macOS
            self._init_watchdog()

    def _init_inotify(self):
        """Set up inotify for Linux."""
        i = inotify.adapters.Inotify()
        i.add_watch(self.cache_dir)
        for event in i.event_gen(yield_nones=False):
            (_, type_names, path, filename) = event
            if 'IN_CLOSE_WRITE' in type_names:
                image_path = os.path.join(path, filename)
                self.update_cache_if_modified(image_path)

    def _init_watchdog(self):
        """Set up watchdog for Windows and macOS."""
        event_handler = ImageCacheEventHandler(
            self,
            self.refresh_image_list_callback,
            self.ensure_valid_index_callback,
            self.image_list_changed_callback  # Pass the missing callback here
        )
        observer = Observer()

        # Monitor all start_dirs
        for start_dir in config.start_dirs:
            observer.schedule(event_handler, start_dir, recursive=True)

        observer.start()
        logger.info(f"Watchdog started, monitoring directories: {config.start_dirs}")

    def update_cache_if_modified(self, image_path):
        """Check if a file has changed and update cache accordingly."""
        if image_path in self.metadata_cache:
            current_metadata = self.metadata_cache[image_path]
            stat_info = os.stat(image_path)
            if config.platform_name == 'Linux':
                if stat_info.st_ino != current_metadata.get('inode'):
                    self.refresh_cache(image_path)
            else:
                if stat_info.st_mtime > current_metadata.get('last_modified', 0):
                    self.refresh_cache(image_path)



class ImageCacheEventHandler(FileSystemEventHandler):
    """Event handler for watchdog to handle file system events with event batching."""

    def __init__(self, image_cache, refresh_image_list_callback, ensure_valid_index_callback,
                 image_list_changed_callback):
        super().__init__()
        self.image_cache = image_cache
        self.refresh_image_list_callback = refresh_image_list_callback
        self.ensure_valid_index_callback = ensure_valid_index_callback
        self.image_list_changed_callback = image_list_changed_callback

        self.refresh_scheduled = False  # Flag to check if refresh is already scheduled

    def on_modified(self, event):
        logger.debug(f"on_modified event {event.src_path}")
        if not event.is_directory:
            self.image_cache.update_cache_if_modified(event.src_path)
            self.schedule_refresh()

    def on_created(self, event):
        logger.debug(f"on_created event {event.src_path}")
        if not event.is_directory:
            self.schedule_refresh()

    def on_deleted(self, event):
        logger.debug(f"on_deleted event {event.src_path}")
        if not event.is_directory:
            self.schedule_refresh()

    def schedule_refresh(self):
        """Schedule a refresh if not already scheduled."""
        if not self.refresh_scheduled:
            logger.debug("Scheduling refresh_image_list")
            self.refresh_scheduled = True
            self.refresh_image_list_callback()
            QTimer.singleShot(0, self.image_list_changed_callback)  # Emit on the main thread
            self.refresh_scheduled = False
