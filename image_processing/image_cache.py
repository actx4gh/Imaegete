import os
import pickle
import platform
from collections import OrderedDict

from PyQt6.QtGui import QPixmap, QPixmapCache

import config
import logger

class ImageCache:
    def __init__(self, app_name='ImageSorter', max_size=100):  # Increased max_size to 100
        self.app_name = app_name
        self.metadata_cache = OrderedDict()
        self.max_size = max_size
        self.cache_dir = config.cache_dir
        if not os.path.exists(self.cache_dir):
            logger.debug(f'Creating new cache dir {self.cache_dir}')
            os.makedirs(self.cache_dir)
        else:
            logger.debug(f'Found existing cache dir {self.cache_dir}')

        # Check and log the current QPixmapCache limit
        current_cache_limit = QPixmapCache.cacheLimit()
        logger.info(f"Current QPixmapCache limit: {current_cache_limit} KB")

        new_cache_limit = 204800  # Example: set to 200 MB (204800 KB)
        QPixmapCache.setCacheLimit(new_cache_limit)
        logger.info(f"QPixmapCache limit set to: {new_cache_limit} KB")

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

    def get_pixmap(self, image_path):
        """Get the pixmap from QPixmapCache using consistent key."""
        # Ensure consistent cache key usage
        pixmap = QPixmapCache.find(image_path)
        if pixmap:
            logger.info(f"Pixmap found in QPixmapCache for {image_path}")
            return pixmap
        else:
            logger.info(f"Pixmap not found in QPixmapCache for {image_path}")

    def add_to_cache(self, image_path, pixmap=None, metadata=None):
        """Add pixmap and metadata to the cache."""

        if not any((pixmap, metadata)):
            logger.error(f"add_to_cache requires either pixmap, metadata, or both to be passed")

        if pixmap:
            if not pixmap.isNull():  # Verify pixmap validity
                logger.debug(f"Caching pixmap for {image_path}, size: {pixmap.size()}, cache key: {pixmap.cacheKey()}")
                insertion_success = QPixmapCache.insert(image_path, pixmap)
                if insertion_success:
                    logger.info(f"Pixmap successfully inserted into QPixmapCache for {image_path}")
                else:
                    logger.error(f"Failed to insert pixmap into QPixmapCache for {image_path}")
            else:
                logger.error(f"Cannot cache an invalid or null pixmap for {image_path}")

        if not metadata:
            metadata = self.extract_metadata(image_path, pixmap)
        if len(self.metadata_cache) >= self.max_size:
            self.metadata_cache.popitem(last=False)  # Remove the least recently used item
        self.metadata_cache[image_path] = metadata
        self.save_cache_to_disk(image_path, metadata)  # Save metadata to disk
        logger.info(f"Cache updated for {image_path}")

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

        # Platform-specific optimization
        if platform.system() == 'Linux':
            metadata['inode'] = stat_info.st_ino  # Add inode for Linux

        return metadata

    def get_metadata(self, image_path):
        """Retrieve metadata for an image from the cache or load from disk."""
        if image_path in self.metadata_cache:
            return self.metadata_cache[image_path]

        # If not in memory cache, try to load it from disk
        metadata = self.load_cache_from_disk(image_path)
        if metadata:
            self.metadata_cache[image_path] = metadata  # Add back to in-memory cache
            return metadata

        return {}
