import os

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QPixmap

import logger
from .image_handler import ImageHandler
from .image_cache import ImageCache
from .image_loader import ThreadedImageLoader


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    cache_image_signal = pyqtSignal(str, QPixmap, dict)

    def __init__(self, app_name='ImageSorter'):
        super().__init__()
        self.app_name = app_name
        self.image_handler = ImageHandler()
        self.image_cache = ImageCache(app_name=self.app_name, max_size=20)
        self.current_index = 0
        self.loader_thread = None
        self.current_image_path = None  # Track the current image path
        self.current_metadata = None  # Store the current metadata in memory
        self.current_pixmap = None  # Store the current pixmap in memory
        self.cache_image_signal.connect(self.cache_image_in_main_thread)

    def cache_image_in_main_thread(self, image_path, pixmap, metadata):
        """This method runs in the main thread to safely insert into QPixmapCache."""
        self.image_cache.add_to_cache(image_path, pixmap, metadata)

    def on_image_loaded(self, image_path, image):
        logger.debug(f"on_image_loaded called with image_path: {image_path}")

        if image is None:
            logger.error(f"Image is None for path: {image_path}")
            return

        # Check if the pixmap is already cached in QPixmapCache
        cached_metadata = self.image_cache.get_metadata(image_path)
        if not self.image_cache.get_pixmap(image_path):
            logger.debug(f"Pixmap not found in QPixmapCache for {image_path}, caching now.")
            self.cache_image_signal.emit(image_path, image, cached_metadata)

        self.current_image_path = image_path
        self.current_metadata = self.image_cache.get_metadata(image_path)
        self.current_pixmap = image

        self.image_loaded.emit(image_path, image)

    def load_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            image_path = os.path.join(self.image_handler.source_folder,
                                      self.image_handler.image_list[self.current_index])
            if self.current_image_path == image_path and self.current_pixmap is not None:
                logger.info(f"Using in-memory data for image at index {self.current_index}: {image_path}")
                self.image_loaded.emit(image_path, self.current_pixmap)
                return

            logger.info(f"Request to load image at index {self.current_index}: {image_path}")
            self.current_pixmap = self.image_cache.get_pixmap(image_path)
            if self.current_pixmap:
                logger.info(f"Using cached image for {image_path}")
                cached_metadata = self.image_cache.get_metadata(image_path)
                if cached_metadata:
                    self.current_image_path = image_path
                    self.current_metadata = cached_metadata
                    self.image_loaded.emit(image_path, self.current_pixmap)
                    return
                else:
                    logger.warning(f"Metadata missing for cached image {image_path}")
            else:
                self.current_pixmap = None  # Reset current pixmap if not found in cache

            # Pass the pixmap (which might be None) to the async loader
            self.load_image_async(image_path, self.current_pixmap)
        else:
            self.image_cleared.emit()

    def load_image_async(self, image_path, pixmap=None):
        # If pixmap is provided, use it directly; otherwise, proceed with async loading
        if pixmap is not None:
            logger.info(f"Using provided pixmap for {image_path}")
            self.on_image_loaded(image_path, pixmap)
            return

        if self.loader_thread is not None:
            self.loader_thread.quit()
            self.loader_thread.wait()

        logger.info(f"Loading image asynchronously: {image_path}")
        self.loader_thread = ThreadedImageLoader(image_path)
        self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.start()

    def next_image(self):
        if self.current_index < len(self.image_handler.image_list) - 1:
            self.current_index += 1
            logger.info(f"Moving to next image: index {self.current_index}")
            self.load_image()
        else:
            logger.info("No next image available")

    def previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            logger.info(f"Moving to previous image: index {self.current_index}")
            self.load_image()
        else:
            logger.info("No previous image available")

    def move_image(self, category):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Moving image: {current_image} to category {category}")
            self.image_handler.move_image(current_image, category)
            self.refresh_image_list()
            self.ensure_valid_index_after_delete()
            self.load_image()

    def delete_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Deleting image at index {self.current_index}: {current_image}")
            self.image_handler.delete_image(current_image)
            self.refresh_image_list()
            self.ensure_valid_index_after_delete()
            self.load_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            logger.info(f"Undo last action: {last_action}")
            self.refresh_image_list()
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

    def refresh_image_list(self):
        self.image_handler.refresh_image_list()
        logger.info(f"Image list refreshed: {self.image_handler.image_list}")

    def get_current_image_path(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            return os.path.join(self.image_handler.source_folder, self.image_handler.image_list[self.current_index])
        return None

    def get_current_image_index(self):
        return self.current_index

    def stop_threads(self):
        if self.loader_thread is not None:
            self.loader_thread.quit()
            self.loader_thread.wait()
