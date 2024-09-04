# image_manager.py

import os
import random
from threading import RLock, Event

from PyQt6.QtCore import pyqtSignal, QObject, QThread, Qt
from PyQt6.QtGui import QPixmap

import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from .image_loader import ThreadedImageLoader


class RefreshImageListThread(QThread):
    image_list_populated = pyqtSignal()

    def __init__(self, image_handler):
        super().__init__()
        self.image_handler = image_handler
        self.thread_started = Event()  # Event to signal thread is alive

    def run(self):
        # Signal that the thread is now alive
        self.thread_started.set()

        # Perform the thread's work
        logger.debug('Running thread to refresh image list')
        self.image_handler.refresh_image_list(signal=self.image_list_populated)

    def wait_until_alive(self):
        """
        Blocks until the thread is marked as alive (i.e., has started running).
        """
        self.thread_started.wait()


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    cache_image_signal = pyqtSignal(str, QPixmap, dict)
    image_list_updated = pyqtSignal()
    image_list_changed = pyqtSignal(str, bool)
    image_list_populated = pyqtSignal()  # New signal

    def __init__(self, image_handler, image_cache, app_name='ImageSorter', ):
        logger.debug("Initializing ImageManager.")
        super().__init__()
        self.app_name = app_name
        self.event_bus = create_or_get_shared_event_bus()
        self.image_handler = image_handler
        self.image_cache = image_cache
        self.image_cache.set_refresh_image_list_callback(self.image_handler.refresh_image_list)
        self.image_cache.set_ensure_valid_index_callback(self.ensure_valid_index)
        self.image_cache.set_image_list_changed_callback(self.image_list_changed)
        self.current_index = 0
        self.loader_thread = None
        self.current_image_path = None
        self.current_metadata = None
        self.current_pixmap = None
        self.shuffled_indices = []
        self.lock = RLock()
        self.cache_image_signal.connect(self.cache_image_in_main_thread)
        self.image_list_updated.connect(self.on_image_list_updated)
        self.watchdog_started = False

    def _start_refresh_worker(self):
        self.refresh_thread = RefreshImageListThread(self.image_handler)
        # Ensure the signal is connected before starting the thread
        logger.debug("Connecting image_list_populated signal to on_image_list_populated.")
        self.refresh_thread.image_list_populated.connect(self.on_image_list_populated,
                                                         Qt.ConnectionType.BlockingQueuedConnection)
        logger.debug("Connected image_list_populated signal to on_image_list_populated.")

        self.refresh_thread.start()
        self.refresh_thread.wait_until_alive()

        logger.debug("ImageManager initialized.")
        if not self.watchdog_started:
            self.image_cache.initialize_watchdog()
            self.watchdog_started = True

    def on_image_list_populated(self):
        logger.debug('entering on_image_list_populated')
        if self.image_handler.first_image and not self.current_image_path:
            logger.debug(f'got first image')
            with self.lock:
                self.current_index = 0
            self.load_image()
            self.pre_fetch_images(self.current_index + 1, self.current_index + 3)
        else:
            self.event_bus.emit('status_update')

    def random_image(self):
        """Display a random image without repeating until all images have been shown."""
        with self.lock:
            if not self.shuffled_indices:
                # Reshuffle only if we've exhausted all images
                self.shuffled_indices = list(range(len(self.image_handler.image_list)))
                random.shuffle(self.shuffled_indices)
                logger.info("All images have been shown. Reshuffling the list.")

            next_index = self.shuffled_indices.pop(0)
            self.current_index = next_index  # Update current index to the new random index

            # Load the randomly selected image
            self.load_image()
            logger.info(f"Displaying random image at index {self.current_index}: {self.get_current_image_path()}")

    def on_image_list_updated(self):
        with self.lock:
            if self.current_image_path and self.current_image_path in self.image_handler.image_list:
                # Update current index based on the current image path
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                if self.current_index < len(self.image_handler.image_list):
                    self.current_index = min(self.current_index, len(self.image_handler.image_list) - 1)
                else:
                    self.current_index = max(len(self.image_handler.image_list) - 1, 0)

        self.ensure_valid_index()
        self.load_image()

    def load_image(self, image_path=None):
        logger.debug(f"Loading image at index: {self.current_index}")

        # Ensure current_index is within the range of image list
        if self.current_index < len(self.image_handler.image_list) and self.current_index >= 0:
            image_path = self.get_absolute_image_path(self.current_index)
            if not self.current_image_path and self.image_handler.first_image:
                image_path = self.image_handler.first_image

            if image_path:
                logger.debug(f"Waiting to acquire lock before loading image pixmap from cache")
                with self.lock:
                    self.current_pixmap = self.image_cache.load_image(image_path)
                    logger.debug(f"Lock acquired, Pixmap loaded from cache")
                if self.current_pixmap:
                    logger.debug(f"Waiting to acquire lock before setting shared vars for image_path / metadata")
                    with self.lock:
                        self.current_image_path = image_path
                        self.current_metadata = self.image_cache.get_metadata(image_path)
                        logger.debug(f"Lock acquired, shared vars set")
                    logger.debug(f"Emitting signal that image manager is ready for image to be loaded")
                    self.image_loaded.emit(image_path, self.current_pixmap)
                else:
                    logger.error(f"Failed to load image: {image_path}")
                    self.image_cleared.emit()
            else:
                logger.error("No valid image path found to load.")
                self.image_cleared.emit()
        else:
            logger.debug("No images available to load or index out of bounds, clearing image display.")
            self.image_cleared.emit()

    def refresh_image_list(self, emit=True):
        self._start_refresh_worker()
        with self.lock:
            self.shuffled_indices = []
        if emit:
            self.image_list_updated.emit()  # Emit signal after refreshing

    def cache_image_in_main_thread(self, image_path, pixmap, metadata):
        """This method runs in the main thread to safely insert into QPixmapCache."""
        self.image_cache.add_to_cache(image_path, pixmap, metadata)

    def on_image_loaded(self, image_path, image):
        logger.debug(f"on_image_loaded called with image_path: {image_path}")
        cache = False
        if image is None:
            logger.error(f"Image is None for path: {image_path}")
            return

        with self.lock:
            self.current_metadata = self.image_cache.get_metadata(image_path)
            if not self.current_metadata:
                logger.debug(f"Metadata not found for {image_path}, loading now.")
                self.current_metadata = self.image_cache.extract_metadata(image_path, image)
                cache = True

            self.current_pixmap = self.image_cache.get_pixmap(image_path)
        if not self.current_pixmap and self.current_pixmap != image:
            logger.debug(f"Pixmap not found in QPixmapCache for {image_path}, caching now.")
            cache = True

        if cache:
            self.cache_image_signal.emit(image_path, image, self.current_metadata)
        with self.lock:
            self.current_image_path = image_path

    def get_absolute_image_path(self, index):
        """Returns the absolute path of an image at the specified index."""
        if index < 0 or index >= len(self.image_handler.image_list):
            logger.error(f"Index {index} out of bounds for image list.")
            return None

        image_path = self.image_handler.image_list[index]
        if not image_path:
            logger.error(f"Image path is None for index {index}.")
            return None

        if os.path.exists(image_path):
            return image_path
        else:
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
            self.loader_thread = None

        logger.info(f"Loading image asynchronously: {image_path} (Prefetch: {prefetch})")
        self.loader_thread = ThreadedImageLoader(image_path)
        if prefetch:
            logger.info(f"Connecting image_loaded signal to on_image_prefetched")
            self.loader_thread.image_loaded.connect(lambda path, img: self.on_image_prefetched(path, img))
        else:
            logger.info(f"Connecting image_loaded signal to on_image_loaded")
            self.loader_thread.image_loaded.connect(self.on_image_loaded)
        self.loader_thread.start()

    def next_image(self):
        with self.lock:
            if self.current_image_path in self.image_handler.image_list:
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                self.current_index = 0

            # Navigate to the next image
            if self.current_index < len(self.image_handler.image_list) - 1:
                self.current_index += 1
                logger.info(f"Moving to next image: index {self.current_index}")
            else:
                self.current_index = 0  # Wrap around to the first image
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
        max_prefetch = 5  # Limit the number of images to prefetch at a time
        for i in range(start_index, min(end_index, len(self.image_handler.image_list))):
            if i - start_index >= max_prefetch:
                break

            image_path = self.get_absolute_image_path(i)
            if image_path is None:
                logger.error(f"Skipping prefetch for invalid image path at index {i}")
                continue

            pixmap = self.image_cache.get_pixmap(image_path)
            if not pixmap:
                logger.debug(f"Prefetching {image_path}")
                self.load_image_async(image_path, prefetch=True)

            # Ensure metadata is prefetched and cached
            metadata = self.image_cache.get_metadata(image_path)
            if not metadata:
                logger.debug(f"Prefetching metadata for {image_path}")
                self.image_cache.extract_metadata(image_path, QPixmap(image_path))

    def previous_image(self):
        with self.lock:
            if self.current_image_path in self.image_handler.image_list:
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                self.current_index = len(self.image_handler.image_list) - 1

            # Navigate to the previous image
            if self.current_index > 0:
                self.current_index -= 1
                logger.info(f"Moving to previous image: index {self.current_index}")
            else:
                self.current_index = len(self.image_handler.image_list) - 1  # Wrap around to the last image
                logger.info("Wrapped around to the last image")

        self.load_image()
        self.pre_fetch_images(self.current_index - 3, self.current_index - 1)

    def first_image(self):
        with self.lock:
            self.current_index = 0
        self.load_image()
        self.pre_fetch_images(self.current_index + 1, self.current_index + 3)

    def last_image(self):
        with self.lock:
            self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()
        self.pre_fetch_images(self.current_index - 3, self.current_index - 1)

    def move_image(self, category):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Moving image: {current_image} to category {category}")
            self.image_handler.move_image(current_image, category)

            with self.lock:
                if self.current_image_path in self.image_handler.image_list:
                    self.current_index = self.image_handler.image_list.index(self.current_image_path)
                else:
                    # Adjust index to point to the next or previous image if available
                    if self.current_index < len(self.image_handler.image_list):
                        self.current_index = min(self.current_index, len(self.image_handler.image_list) - 1)
                    else:
                        # If no images left or index out of bounds, reset to last valid index
                        self.current_index = max(len(self.image_handler.image_list) - 1, 0)

            self.ensure_valid_index()  # Ensure the current index is valid
            self.load_image()

    def delete_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            logger.info(f"Deleting image at index {self.current_index}: {current_image}")
            self.image_handler.delete_image(current_image)

            # Directly remove the image from the image list
            self.image_handler.remove_image_from_list(current_image)

            # Adjust current index
            self.ensure_valid_index_after_delete()
            self.load_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            logger.info(f"Undo last action: {last_action}")

            # Directly update the image list based on the action undone
            image_path = last_action[1]
            if last_action[0] == 'delete':
                self.image_handler.add_image_to_list(image_path)
            elif last_action[0] == 'move':
                self.image_handler.add_image_to_list(image_path)

            # Check if the restored image file exists before proceeding
            if os.path.exists(image_path):
                pixmap = self.image_cache.load_image(image_path)
                if pixmap:
                    metadata = self.image_cache.extract_metadata(image_path, pixmap)
                    self.image_cache.add_to_cache(image_path, pixmap, metadata)
            else:
                logger.error(f"File not found during undo operation: {image_path}")
                # Optionally, remove it from the list or handle accordingly
                self.image_handler.remove_image_from_list(image_path)

            # Update current index to point to the restored image
            if image_path in self.image_handler.image_list:
                with self.lock:
                    self.current_index = self.image_handler.image_list.index(image_path)

            # Ensure the index is valid and refresh the display
            self.ensure_valid_index()
            self.load_image()
            self.image_list_updated.emit()

    def ensure_valid_index(self):
        with self.lock:
            if self.current_index >= len(self.image_handler.image_list):
                self.current_index = len(self.image_handler.image_list) - 1
            if self.current_index < 0:
                self.current_index = 0
        logger.info(f"Ensuring valid index: {self.current_index}")

    def ensure_valid_index_after_delete(self):
        if self.current_index >= len(self.image_handler.image_list):
            with self.lock:
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
