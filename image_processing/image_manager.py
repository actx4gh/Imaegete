import os
import random
from threading import RLock, Event

import numpy
from PyQt6.QtCore import pyqtSignal, QObject, QThread, Qt
from PyQt6.QtGui import QPixmap

import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class RefreshImageListWorker(QThread):
    image_list_populated = pyqtSignal()

    def __init__(self, image_handler):
        super().__init__()
        self.image_handler = image_handler
        self.thread_started = Event()  # Event to signal thread is alive
        self.thread_id = QThread.currentThreadId()
        # self.thread_memory_address = id(QThread.currentThread())

    def run(self):
        # Signal that the thread is now alive
        self.thread_started.set()

        # Perform the thread's work
        logger.debug(f'[RefreshImageListWorker {self.thread_id}] Running thread to refresh image list')
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

    def __init__(self, image_handler, image_cache, app_name='ImageSorter'):
        logger.debug("[ImageManager] Initializing ImageManager.")
        super().__init__()
        self.app_name = app_name
        self.event_bus = create_or_get_shared_event_bus()
        self.image_handler = image_handler
        self.image_cache = image_cache
        self.current_index = 0
        self.current_image_path = None
        self.current_metadata = None
        self.current_pixmap = None
        self.shuffled_indices = []
        self.lock = RLock()
        self.watchdog_started = False
        self._start_refresh_worker()

    def _start_refresh_worker(self):
        self.refresh_thread = RefreshImageListWorker(self.image_handler)
        # Ensure the signal is connected before starting the thread
        logger.debug("[ImageManager] Connecting image_list_populated signal to on_image_list_populated.")
        self.refresh_thread.image_list_populated.connect(self.on_image_list_populated,
                                                         Qt.ConnectionType.BlockingQueuedConnection)
        logger.debug("[ImageManager] Connected image_list_populated signal to on_image_list_populated.")

        self.refresh_thread.start()
        self.refresh_thread.wait_until_alive()

        logger.debug("[ImageManager] initialized.")
        # if not self.watchdog_started:
        #    self.image_cache.initialize_watchdog()
        #    self.watchdog_started = True

    def get_current_image_path(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            return self.image_handler.image_list[self.current_index]  # deque supports index-based access

    def next_image(self):
        """Navigate to the next image."""
        with self.lock:
            if self.current_image_path in self.image_handler.image_list:
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                self.current_index = 0

            if self.current_index < len(self.image_handler.image_list) - 1:
                self.current_index += 1
            else:
                self.current_index = 0  # Wrap around
        self.load_image()

    def previous_image(self):
        """Navigate to the previous image."""
        with self.lock:
            if self.current_image_path in self.image_handler.image_list:
                self.current_index = self.image_handler.image_list.index(self.current_image_path)
            else:
                self.current_index = len(self.image_handler.image_list) - 1

            if self.current_index > 0:
                self.current_index -= 1
            else:
                self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()

    def get_current_image_index(self):
        return self.current_index

    def on_image_list_populated(self):
        logger.debug('[ImageManager] Entering on_image_list_populated')
        if not self.current_image_path:
            logger.debug(f'[ImageManager] Got first image')
            with self.lock:
                self.current_index = 0
            self.load_image()
        else:
            self.event_bus.emit('status_update')

    def load_image(self, offset=None, lower=-3, upper=3):
        if offset is not None:
            index = self.current_index + offset
        else:
            index = self.current_index
        logger.debug(f"[ImageManager] Loading image at index: {index}")
        if index < len(self.image_handler.image_list) and self.current_index >= 0:
            image_path, pixmap = self.get_absolute_image_path_and_cached(index)

            if image_path:
                with self.lock:
                    self.current_pixmap = pixmap or self.image_cache.retrieve_pixmap(image_path)
                    self.current_metadata = self.image_cache.get_metadata(image_path)
                if self.current_pixmap:
                    self.current_image_path = image_path
                    self.image_loaded.emit(image_path, self.current_pixmap)
                    self.prefetch_images(lower, upper)
                else:
                    logger.error(f"[ImageManager] Failed to load image: {image_path}")
                    self.image_cleared.emit()
            else:
                logger.error("[ImageManager] No valid image path found to load.")
                self.image_cleared.emit()
        else:
            logger.debug("[ImageManager] No images available to load or index out of bounds, clearing image display.")
            self.image_cleared.emit()

    def prefetch_images(self, lower, upper):
        max_prefetch = 10
        total = len(self.image_handler.image_list)
        prev_index = (self.current_index + -1) % total
        next_index = (self.current_index + 1) % total
        behind = numpy.arange(prev_index, prev_index + lower, -1) % total
        ahead = numpy.arange(next_index, next_index + upper) % total
        logger.debug(
            f"[ImageManager] Starting prefetch of indexes {list(behind)} and {list(ahead)} from index {self.current_index} with a total of {total} images")

        prefetch_indices = [item for pair in zip(ahead, behind) for item in pair]
        if max_prefetch < len(prefetch_indices):
            prefetch_indices = prefetch_indices[:max_prefetch]
            logger.warn(f"[ImageManager] reduced number of prefetch items to max_prefetch {max_prefetch}")

        # Iterate over the combined indices, respecting the max_prefetch limit
        for i in prefetch_indices:
            if self.image_cache.find_pixmap(self.image_handler.image_list[i]):
                logger.warn(f"[ImageManager] Skipping prefetch index {i} image found in cache")
                continue
            image_path, _ = self.get_absolute_image_path_and_cached(i)
            if image_path is None:
                logger.error(f"[ImageManager] Skipping prefetch for invalid image path at index {i}")
                continue

            logger.debug(f"[ImageManager] Prefetching image at index {i} {image_path}")
            pixmap = self.image_cache.retrieve_pixmap(image_path)
            metadata = self.image_cache.get_metadata(image_path)
            if pixmap and metadata:
                logger.debug(f"[ImageManager] {image_path} prefetched")

    def on_image_loaded(self, image_path, pixmap):
        if pixmap is None:
            logger.error(f"[ImageManager] Image is None for path: {image_path}")
            return

        with self.lock:
            self.current_metadata = self.image_cache.get_metadata(image_path)
            if not self.current_metadata:
                logger.debug(f"[ImageManager] Metadata not found for {image_path}, loading now.")
                self.current_metadata = self.image_cache.extract_metadata(image_path, pixmap)

            self.current_pixmap = self.image_cache.retrieve_pixmap(image_path)
        # if not self.current_pixmap and self.current_pixmap != pixmap:
        #    logger.debug(f"Pixmap not found in QPixmapCache for {image_path}, caching now.")
        #    self.cache_image_signal.emit(image_path, pixmap, self.current_metadata)

        with self.lock:
            self.current_image_path = image_path
        self.image_loaded.emit(image_path, pixmap)

    def on_image_prefetched(self, image_path, pixmap):
        """Handle images loaded as a result of pre-fetching."""
        logger.debug(f"[ImageManager] Image prefetched: {image_path}")
        if pixmap is None:
            logger.error(f"[ImageManager] Prefetched image is None for path: {image_path}")
            return

        # Add to cache but do not emit signals or update display
        cached_metadata = self.image_cache.get_metadata(image_path)
        if not self.image_cache.retrieve_pixmap(image_path):
            self.cache_image_signal.emit(image_path, pixmap, cached_metadata)

    def move_image(self, category):
        with self.lock:
            if 0 <= self.current_index < len(self.image_handler.image_list):
                current_image = self.image_handler.image_list[self.current_index]
                original_index = self.current_index

                logger.info(f"[ImageManager] Moving image: {current_image} to category {category}")

                if self.current_index < len(self.image_handler.image_list):
                    if self.current_index == len(self.image_handler.image_list) - 1:
                        load_offset = -1
                        self.current_index = (self.current_index - 1)
                    else:
                        load_offset = +1
                    future_image_list_size = len(self.image_handler.image_list) - 1
                else:
                    self.current_index = max(len(self.image_handler.image_list) - 1, 0)

                self.ensure_valid_index()
                self.load_image(offset=load_offset)

                self.image_handler.move_image(current_image, category, original_index)
                self.image_list_updated.emit()
            else:
                logger.error("[ImageManager] Attempted to move image with invalid index or empty image list.")

    def delete_image(self):
        with self.lock:
            if 0 <= self.current_index < len(self.image_handler.image_list):
                current_image = self.image_handler.image_list[self.current_index]
                original_index = self.current_index

                logger.info(f"[ImageManager] Deleting image at index {self.current_index}: {current_image}")

                if self.current_index < len(self.image_handler.image_list):
                    if self.current_index == len(self.image_handler.image_list) - 1:
                        load_offset = -1
                        self.current_index = (self.current_index - 1)
                    else:
                        load_offset = +1
                else:
                    self.current_index = max(len(self.image_handler.image_list) - 1, 0)

                self.ensure_valid_index()
                self.load_image(offset=load_offset)
                self.image_handler.delete_image(current_image, original_index)
                self.image_list_updated.emit()

            else:
                logger.error("[ImageManager] Attempted to delete image with invalid index or empty image list.")

    # In image_manager.py

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            logger.debug(f'[ImageManager] Undo last action - got last_action {last_action}')
            action_type, image_path, *rest = last_action
            original_index = rest[-1]  # Correctly extract the original index

            if image_path in self.image_handler.image_list:
                self.current_index = original_index  # Ensure this is set to the integer index
                self.current_image_path = image_path
                logger.debug(
                    f'[ImageManager] undo_last_action set current_index to {self.current_index}, current_image_path to {self.current_image_path}')

            self.ensure_valid_index()
            self.load_image()
            self.image_handler.complete_undo_last_action(image_path, action_type, rest)
            self.image_list_updated.emit()
        else:
            logger.warning("[ImageManager] No action to undo.")

    def first_image(self):
        with self.lock:
            self.current_index = 0
        self.load_image()

    def last_image(self):
        with self.lock:
            # Set the current index to the last image
            self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()

    def random_image(self):
        """Display a random image without repeating until all images have been shown."""
        with self.lock:
            if not self.shuffled_indices:
                self.shuffled_indices = list(range(len(self.image_handler.image_list)))
                random.shuffle(self.shuffled_indices)
                logger.info("[ImageManager] All images have been shown. Reshuffling the list.")

            next_index = self.shuffled_indices.pop(0)
            self.current_index = next_index

        self.load_image()

        logger.info(
            f"[ImageManager] Displaying random image at index {self.current_index}: {self.get_current_image_path()}")

    def get_absolute_image_path_and_cached(self, index):
        """Returns the absolute path of an image at the specified index."""
        if index < 0 or index >= len(self.image_handler.image_list):
            logger.error(f"[ImageManager] Index {index} out of bounds for image list.")
            return None, None

        image_path = self.image_handler.image_list[index]
        if not image_path:
            logger.error(f"[ImageManager] Image path is None for index {index}.")
            return None, None

        pixmap = None
        if not os.path.exists(image_path):
            pixmap = self.image_cache.find_pixmap(image_path)
            if pixmap:
                logger.debug(f"[ImageManager] Got cached pixmap for image {image_path}")

        if not any((image_path, pixmap)):
            logger.error(
                f"[ImageManager] No cached pixmap or image found at stored path for index {index}: {image_path}")

        return image_path, pixmap

    def ensure_valid_index(self):
        with self.lock:
            if self.current_index >= len(self.image_handler.image_list):
                self.current_index = len(self.image_handler.image_list) - 1
            if self.current_index < 0:
                self.current_index = 0
        logger.info(f"[ImageManager] Ensuring valid index: {self.current_index}")

    def shutdown(self):
        """Clean up and stop all threads and components gracefully."""
        logger.info("[ImageManager] Initiating shutdown for ImageManager.")

        # Stop the watchdog observer first if it has started
        if hasattr(self.image_cache, 'watchdog_observer'):
            try:
                # Ensure the watchdog observer is running before attempting to stop it
                if self.image_cache.watchdog_observer.is_alive():
                    logger.info("[ImageManager] Stopping watchdog observer.")
                    self.image_cache.watchdog_observer.stop()
                    self.image_cache.watchdog_observer.join(timeout=5)
                    logger.info("[ImageManager] Watchdog observer stopped.")
                else:
                    logger.warning("[ImageManager] Watchdog observer was not running or not started.")
            except Exception as e:
                logger.error(f"[ImageManager] Error while stopping watchdog observer: {e}")
        else:
            logger.warning("[ImageManager] Watchdog observer not found during shutdown.")

        # Continue shutting down other components
        if self.refresh_thread and self.refresh_thread.isRunning():
            logger.info("[ImageManager] Stopping the refresh thread.")
            self.refresh_thread.quit()
            self.refresh_thread.wait()
            logger.info("[ImageManager] Refresh thread stopped.")

        # Shutdown ImageCache and MetadataManager thread pools
        if self.image_cache.event_pool:
            logger.info("[ImageManager] Shutting down ImageCache thread pool.")
            self.image_cache.event_pool.shutdown(wait=True)
            logger.info("[ImageManager] ImageCache thread pool shutdown complete.")

        if self.image_cache.metadata_manager.metadata_pool:
            logger.info("[ImageManager] Shutting down MetadataManager thread pool.")
            self.image_cache.metadata_manager.metadata_pool.shutdown(wait=True)
            logger.info("[ImageManager] MetadataManager thread pool shutdown complete.")

        logger.info("[ImageManager] All threads successfully stopped. Application shutdown complete.")