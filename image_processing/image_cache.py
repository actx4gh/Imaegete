import os
import pickle
import platform
from collections import OrderedDict

import psutil
from PyQt6.QtGui import QPixmapCache

import config
import logger
from .image_utils import load_image_with_qpixmap

if config.platform_name == 'Linux':
    import inotify.adapters
elif config.platform_name == 'Windows' or config.platform_name == 'Darwin':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler


class ImageCache:
    def __init__(self, app_name='ImageSorter', max_size=500):
        self.app_name = app_name
        self.max_size = max_size  # Increased size for better performance with large datasets
        self.ensure_valid_index_callback = None
        self.refresh_image_list_callback = None
        self.image_list_changed_callback = None
        self.metadata_cache = OrderedDict()
        self.cache_dir = config.cache_dir

        if not os.path.exists(self.cache_dir):
            logger.debug(f'Creating new cache dir {self.cache_dir}')
            os.makedirs(self.cache_dir)
        else:
            logger.debug(f'Found existing cache dir {self.cache_dir}')

        self.dynamic_cache_adjustment()

    def dynamic_cache_adjustment(self):
        """Adjust cache size dynamically based on available system memory."""
        memory_info = psutil.virtual_memory()
        # Set cache size to be a percentage of available memory, up to a max limit
        available_memory_mb = memory_info.available // (1024 * 1024)
        new_cache_size = min(available_memory_mb // 10, self.max_size)
        QPixmapCache.setCacheLimit(new_cache_size * 1024)  # QPixmapCache uses KB
        logger.info(f"Dynamically adjusted QPixmapCache limit to: {new_cache_size} MB")

    def get_pixmap(self, image_path):
        """Get the pixmap from QPixmapCache using consistent key."""
        pixmap = QPixmapCache.find(image_path)
        if pixmap:
            # Only move to end if the key exists
            if image_path in self.metadata_cache:
                self.metadata_cache.move_to_end(image_path)
            else:
                # Load metadata if not present
                metadata = self.load_cache_from_disk(image_path)
                if metadata:
                    self.metadata_cache[image_path] = metadata
                    self.metadata_cache.move_to_end(image_path)
            return pixmap
        return None

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
        else:
            # Add new images directly without refreshing the entire list
            self.refresh_cache(image_path)

    def initialize_watchdog(self):
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
        """Save metadata to disk with error handling."""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                logger.debug(f'Created cache directory: {self.cache_dir}')

            cache_path = self.get_cache_path(image_path)
            with open(cache_path, 'wb') as f:
                pickle.dump(metadata, f)
            logger.info(f"Metadata saved to disk for {image_path} at {cache_path}")
        except PermissionError as e:
            logger.error(f"Permission denied while saving cache for {image_path}: {e}")
        except IOError as e:
            logger.error(f"I/O error while saving cache for {image_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while saving cache for {image_path}: {e}")

    def load_cache_from_disk(self, image_path):
        """Load metadata from disk with error handling."""
        cache_path = self.get_cache_path(image_path)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    metadata = pickle.load(f)
                logger.info(f"Metadata loaded from disk for {image_path} from {cache_path}")
                return metadata
            except (EOFError, pickle.PickleError) as e:
                logger.error(f"Failed to load metadata for {image_path}: {e}")
            except PermissionError as e:
                logger.error(f"Permission denied while loading cache for {image_path}: {e}")
            except IOError as e:
                logger.error(f"I/O error while loading cache for {image_path}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error while loading cache for {image_path}: {e}")
        else:
            logger.warning(f"No cache file found for {image_path} at {cache_path}")
        return None

    def refresh_cache(self, image_path):
        logger.info(f"Refreshing cache for {image_path}")
        self.dynamic_cache_adjustment()

        # Remove old cache entries
        if image_path in self.metadata_cache:
            del self.metadata_cache[image_path]
        QPixmapCache.remove(image_path)

        # Reload the image and metadata if it still exists
        if os.path.exists(image_path):
            self.load_image(image_path)
        else:
            # If the image is deleted, emit signal to update the list
            if self.image_list_changed_callback:
                self.image_list_changed_callback.emit(image_path, True)

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

    def add_to_cache(self, image_path, pixmap=None, metadata=None):
        self.dynamic_cache_adjustment()
        if pixmap and not pixmap.isNull():
            QPixmapCache.insert(image_path, pixmap)  # Insert pixmap into cache

        if metadata and self.metadata_cache[image_path] != metadata:
            self.metadata_cache[image_path] = metadata
            self.save_cache_to_disk(image_path, metadata)
            self.metadata_cache.move_to_end(image_path)
        while len(self.metadata_cache) > self.max_size:
            removed_path, _ = self.metadata_cache.popitem(last=False)
            QPixmapCache.remove(removed_path)
            logger.info(f"Evicted {removed_path} from cache due to size limit.")

    def load_image(self, image_path):
        """Load an image from the cache or file system."""
        pixmap = self.get_pixmap(image_path)
        if pixmap:
            return pixmap

        # If not in cache, load the image and metadata
        pixmap = load_image_with_qpixmap(image_path)
        if pixmap is None:
            logger.error(f"Failed to load image: {image_path}")
            return None

        metadata = self.extract_metadata(image_path, pixmap)
        self.add_to_cache(image_path, pixmap, metadata)
        return pixmap

    def extract_metadata(self, image_path, pixmap=None):
        """Extract metadata from the image file with error handling."""
        try:
            stat_info = os.stat(image_path)
        except FileNotFoundError:
            logger.error(f"File not found: {image_path}")
            return {}
        except PermissionError:
            logger.error(f"Permission denied for file: {image_path}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error accessing file metadata for {image_path}: {e}")
            return {}

        metadata = {
            'size': pixmap.size() if pixmap else None,
            'format': pixmap.cacheKey() if pixmap else None,
            'last_modified': stat_info.st_mtime,
            'file_size': stat_info.st_size,
        }
        logger.debug(f'Extracted metadata {metadata} from {image_path}')

        if platform.system() == 'Linux':
            metadata['inode'] = stat_info.st_ino

        self.metadata_cache[image_path] = metadata
        self.save_cache_to_disk(image_path, metadata)

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

        # Ensure all callbacks are set before proceeding
        if not all([
            self.refresh_image_list_callback,
            self.ensure_valid_index_callback,
            self.image_list_changed_callback
        ]):
            logger.error("Cannot initialize watchdog: Callbacks are not properly configured.")
            return

        event_handler = ImageCacheEventHandler(
            self,
            self.refresh_image_list_callback,
            self.ensure_valid_index_callback,
            self.image_list_changed_callback
        )

        observer = Observer()

        # Monitor all start_dirs
        for start_dir in config.start_dirs:
            observer.schedule(event_handler, start_dir, recursive=True)

        observer.start()
        logger.info(f"Watchdog started, monitoring directories: {config.start_dirs}")

    def set_refresh_image_list_callback(self, callback):
        self.refresh_image_list_callback = callback

    def set_ensure_valid_index_callback(self, callback):
        self.ensure_valid_index_callback = callback

    def set_image_list_changed_callback(self, callback):
        self.image_list_changed_callback = callback


class ImageCacheEventHandler(FileSystemEventHandler):
    """Event handler for watchdog to handle file system events with event batching."""

    def __init__(self, image_cache, refresh_image_list_callback, ensure_valid_index_callback,
                 image_list_changed_callback):
        super().__init__()
        self.image_cache = image_cache
        self.refresh_image_list_callback = refresh_image_list_callback
        self.ensure_valid_index_callback = ensure_valid_index_callback
        self.image_list_changed_callback = image_list_changed_callback

    def on_modified(self, event):
        logger.debug(f"on_modified event {event.src_path}")
        if not event.is_directory:
            self.image_cache.update_cache_if_modified(event.src_path)  # Correct usage

    def on_created(self, event):
        logger.debug(f"on_created event {event.src_path}")
        if not event.is_directory:
            self.image_cache.refresh_cache(event.src_path)
            self.image_cache.image_list_changed_callback.emit(event.src_path, False)

    def on_deleted(self, event):
        logger.debug(f"on_deleted event {event.src_path}")
        if not event.is_directory:
            self.image_cache.refresh_cache(event.src_path)
            self.image_cache.image_list_changed_callback.emit(event.src_path, True)
