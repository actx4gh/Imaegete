import os

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QPixmap

import logger
from config import IMAGE_CACHE_MAX_SIZE
from .image_cache import ImageCache
from .image_handler import ImageHandler
from .image_loader import ThreadedImageLoader


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    cache_image_signal = pyqtSignal(str, QPixmap, dict)
    image_list_updated = pyqtSignal()
    image_list_changed = pyqtSignal()

    def __init__(self, app_name='ImageSorter'):
        super().__init__()
        self.app_name = app_name
        self.image_handler = ImageHandler()
        self.image_cache = ImageCache(
            app_name=self.app_name,
            refresh_image_list_callback=self.image_handler.refresh_image_list,
            ensure_valid_index_callback=self.ensure_valid_index,
            image_list_changed_callback=self.image_list_changed,
            max_size=IMAGE_CACHE_MAX_SIZE
        )
        self.current_index = 0
        self.loader_thread = None
        self.current_image_path = None  # Track the current image path
        self.current_metadata = None  # Store the current metadata in memory
        self.current_pixmap = None  # Store the current pixmap in memory
        self.cache_image_signal.connect(self.cache_image_in_main_thread)
        self.image_list_updated.connect(self.on_image_list_updated)
        logger.debug("Connected image_list_changed to update_status_bar")

    def on_image_list_updated(self):
        """Handle actions when the image list is updated."""
        if self.current_image_path and self.current_image_path in self.image_handler.image_list:
            # Update current index based on the current image path
            self.current_index = self.image_handler.image_list.index(self.current_image_path)
        else:
            # If the current image path is not found, set index to 0
            self.current_index = 0

        self.ensure_valid_index()  # Ensure the current index is valid
        self.load_image()  # Reload the current image

    def refresh_image_list(self):
        self.image_handler.refresh_image_list()
        self.image_list_updated.emit()  # Emit signal after refreshing

    def cache_image_in_main_thread(self, image_path, pixmap, metadata):
        """This method runs in the main thread to safely insert into QPixmapCache."""
        self.image_cache.add_to_cache(image_path, pixmap, metadata)

    def on_image_loaded(self, image_path, image):
        logger.debug(f"on_image_loaded called with image_path: {image_path}")

        if image is None:
            logger.error(f"Image is None for path: {image_path}")
            return

        # Force loading and caching of metadata if not already present
        cached_metadata = self.image_cache.get_metadata(image_path)
        if not cached_metadata:
            logger.debug(f"Metadata not found for {image_path}, loading now.")
            cached_metadata = self.image_cache.extract_metadata(image_path, image)
            self.cache_image_signal.emit(image_path, image, cached_metadata)

        # Ensure pixmap is cached
        if not self.image_cache.get_pixmap(image_path):
            logger.debug(f"Pixmap not found in QPixmapCache for {image_path}, caching now.")
            self.cache_image_signal.emit(image_path, image, cached_metadata)

        self.current_image_path = image_path
        self.current_metadata = cached_metadata
        self.current_pixmap = image

        # Emit image loaded signal after ensuring metadata and pixmap are cached
        self.image_loaded.emit(image_path, image)

    def load_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            image_path = self.get_absolute_image_path(self.current_index)
            if self.current_image_path == image_path and self.current_pixmap is not None:
                self.image_loaded.emit(image_path, self.current_pixmap)
                return

            self.current_pixmap = self.image_cache.get_pixmap(image_path)
            if self.current_pixmap:
                self.current_image_path = image_path
                f"self.current_image_path set to {image_path}"
                self.current_metadata = self.image_cache.get_metadata(image_path)
                self.image_loaded.emit(image_path, self.current_pixmap)
            else:
                # Load image asynchronously
                self.load_image_async(image_path)
        else:
            self.image_cleared.emit()

    def get_absolute_image_path(self, index):
        if index < 0 or index >= len(self.image_handler.image_list):
            return None

        image_path = self.image_handler.image_list[index]
        if os.path.exists(image_path):
            return image_path
        logger.error(f"Image path not found for index {index}: {image_path}")
        return None

    def load_image_async(self, image_path, pixmap=None, prefetch=False):
        """Load an image asynchronously, with an option for pre-fetching."""
        if pixmap is not None:
            logger.info(f"Using provided pixmap for {image_path}")
            self.on_image_loaded(image_path, pixmap)
            return

        if self.loader_thread is not None:
            self.loader_thread.quit()
            self.loader_thread.wait()

        logger.info(f"Loading image asynchronously: {image_path} (Prefetch: {prefetch})")
        self.loader_thread = ThreadedImageLoader(image_path)
        if prefetch:
            self.loader_thread.image_loaded.connect(lambda path, img: self.on_image_prefetched(path, img))
        else:
            self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.start()

    def next_image(self):
        # Refresh the image list and update the current index based on the latest list
        self.refresh_image_list()
        if self.current_image_path in self.image_handler.image_list:
            self.current_index = self.image_handler.image_list.index(self.current_image_path)
        else:
            # If the current image path is not found, set to the first image
            self.current_index = 0

        # Navigate to the next image
        if self.current_index < len(self.image_handler.image_list) - 1:
            self.current_index += 1
            logger.info(f"Moving to next image: index {self.current_index}")
        else:
            # Wrap around to the first image
            self.current_index = 0
            logger.info("Wrapped around to the first image")

        self.load_image()
        self.pre_fetch_images(self.current_index + 1, self.current_index + 3)

    def on_image_prefetched(self, image_path, image):
        """Handle images loaded as a result of pre-fetching."""
        logger.debug(f"Image prefetched: {image_path}")
        if image is None:
            logger.error(f"Prefetched image is None for path: {image_path}")
            return

        # Add to cache but do not emit signals or update display
        cached_metadata = self.image_cache.get_metadata(image_path)
        if not self.image_cache.get_pixmap(image_path):
            self.cache_image_signal.emit(image_path, image, cached_metadata)

    def pre_fetch_images(self, start_index, end_index):
        """Pre-fetch images asynchronously to reduce loading time."""
        for i in range(start_index, min(end_index, len(self.image_handler.image_list))):
            image_path = self.get_absolute_image_path(i)
            if not self.image_cache.get_pixmap(image_path):
                logger.debug(f"Prefetching {image_path}")
                self.load_image_async(image_path, prefetch=True)
            # Ensure metadata is prefetched and cached
            cached_metadata = self.image_cache.get_metadata(image_path)
            if not cached_metadata:
                logger.debug(f"Prefetching metadata for {image_path}")
                metadata = self.image_cache.extract_metadata(image_path, QPixmap(image_path))
                self.cache_image_signal.emit(image_path, QPixmap(), metadata)

    def previous_image(self):
        # Refresh the image list and update the current index based on the latest list
        self.refresh_image_list()
        if self.current_image_path in self.image_handler.image_list:
            self.current_index = self.image_handler.image_list.index(self.current_image_path)
        else:
            # If the current image path is not found, set to the last image
            self.current_index = len(self.image_handler.image_list) - 1

        # Navigate to the previous image
        if self.current_index > 0:
            self.current_index -= 1
            logger.info(f"Moving to previous image: index {self.current_index}")
        else:
            # Correctly navigate to the last image if at the first
            self.current_index = len(self.image_handler.image_list) - 1
            logger.info("Wrapped around to the last image")

        self.load_image()

    def move_image(self, category):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Moving image: {current_image} to category {category}")
            self.image_handler.move_image(current_image, category)
            self.image_handler.refresh_image_list()

            # Update current index based on the current image path
            if self.current_image_path in self.image_handler.image_list:
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                # If the current image path is not found, set index to 0
                self.current_index = 0

            self.ensure_valid_index()  # Ensure the current index is valid
            self.load_image()

    def delete_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Deleting image at index {self.current_index}: {current_image}")
            self.image_handler.delete_image(current_image)
            self.refresh_image_list()  # Explicitly call refresh to update the image list
            self.ensure_valid_index_after_delete()
            self.load_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            logger.info(f"Undo last action: {last_action}")
            self.image_handler.refresh_image_list()
            if last_action[0] == 'delete':
                self.current_index = self.image_handler.image_list.index(last_action[1])
            elif last_action[0] == 'move':
                self.current_index = self.image_handler.image_list.index(last_action[1])
            self.load_image()

    def first_image(self):
        self.current_index = 0
        self.load_image()

    def last_image(self):
        self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()

    def ensure_valid_index(self):
        if self.current_index >= len(self.image_handler.image_list):
            self.current_index = len(self.image_handler.image_list) - 1
        if self.current_index < 0:
            self.current_index = 0
        logger.info(f"Ensuring valid index: {self.current_index}")

    def ensure_valid_index_after_delete(self):
        if self.current_index >= len(self.image_handler.image_list):
            self.current_index = len(self.image_handler.image_list) - 1
        logger.info(f"Ensuring valid index after delete: {self.current_index}")

    def get_current_image_path(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            return self.image_handler.image_list[self.current_index]
        return None

    def get_current_image_index(self):
        return self.current_index

    def stop_threads(self):
        if self.loader_thread is not None:
            self.loader_thread.quit()
            self.loader_thread.wait()
