from PyQt6.QtCore import QObject, pyqtSignal, Qt, QMutexLocker, QRecursiveMutex, QThread, QMutex, QTimer
from PyQt6.QtGui import QPixmap

from core import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class ImageManager(QObject):
    """
    A class to manage image loading, displaying, and caching operations for the application.
    """
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_list_updated = pyqtSignal()
    image_ready = pyqtSignal(str, object)  # New signal

    def __init__(self, image_handler):
        super().__init__()
        self.image_handler = image_handler
        self.is_loading = False
        self.is_loaded = False
        self.is_prefetched = False
        self.loading_images = set()  # QSet to track currently loading images
        self.shutdown_mutex = QMutex()
        self.shutdown_flag = False
        self.lock = QRecursiveMutex()

        self.event_bus = create_or_get_shared_event_bus()
        self.image_list_updated.connect(self.on_image_list_updated, Qt.ConnectionType.QueuedConnection)
        self.lock = QRecursiveMutex()
        self.image_handler.data_service.cache_manager.request_display_update.connect(
            self.display_image, Qt.ConnectionType.QueuedConnection)
        self.current_displayed_image = None

        # Connect the image_ready signal to send_image_to_display
        self.image_ready.connect(self.send_image_to_display)

    def is_shutting_down(self):
        with QMutexLocker(self.shutdown_mutex):
            return self.shutdown_flag

    def display_image(self, image_path=None, index=None):
        """
        Display the image at the specified index.

        :param int index: The index of the image to display. If None, the current image is displayed.
        :param str image_path:
        """
        with QMutexLocker(self.lock):
            if self.is_shutting_down():
                logger.debug(f"[ImageManager] shutting down before running display image task")
                return
            if not any((image_path, index)) and self.image_handler.has_current_image():
                image_path = self.image_handler.data_service.get_current_image_path()
            if not image_path and index is not None:
                image_path = self.image_handler.set_current_image_by_index(index)
            if image_path:
                self._display_image_task(image_path)
            else:
                self.image_cleared.emit()

    def _display_image_task(self, image_path):
        """
        Handle the event when an image is loaded from cache, with deduplication.
        """

        def task():
            thread_id = int(QThread.currentThreadId())

            # Deduplication check: skip if the image is already being loaded
            with QMutexLocker(self.lock):
                if self.is_shutting_down():
                    logger.debug(f"[ImageManager thread {thread_id}] shutting down before loading image for display")
                    return
                if image_path in self.loading_images:
                    logger.info(f"[ImageManager thread {thread_id}] Image {image_path} is already loading, skipping task.")
                    return
                self.loading_images.add(image_path)

            self.event_bus.emit('show_busy')
            logger.info(
                f"[ImageManager thread {thread_id}] Request to display image {image_path}, attempting to retrieve from cache"
            )

            image = self.image_handler.load_image_from_cache(image_path, background=False)

            with QMutexLocker(self.lock):
                # Remove the image from the loading set once loading is complete
                self.loading_images.discard(image_path)

            if image:
                logger.info(f"[ImageManager thread {thread_id}] {image_path} retrieved successfully from cache.")
                # Emit the signal to display the image
                self.image_ready.emit(image_path, image)
            else:
                logger.error(
                    f"[ImageManager thread {thread_id}] Image {image_path} could not be cached. Moving to next available."
                )

        # Submit the task to the ThreadManager
        self.image_handler.thread_manager.submit_task(task)

    def send_image_to_display(self, image_path, image):
        """
        Process the loaded image data and emit the signal to display it.

        :param str image_path: The path of the image being processed.
        :param QImage image: The image data to process.
        """
        thread_id = int(QThread.currentThreadId())
        logger.debug(f"[ImageManager thread {thread_id}] {image_path} waiting for lock before displaying image.")
        with QMutexLocker(self.lock):
            if self.is_shutting_down():
                logger.debug(
                    f"[ImageManager thread {thread_id}] shutting down before displaying loaded image.")
                return None
            pixmap = QPixmap.fromImage(image)
            self.image_loaded.emit(image_path, pixmap)
            self.is_loaded = True
            self.is_loading = False
            self.current_displayed_image = image_path
            if not self.image_handler.is_refreshing:
                self.event_bus.emit('hide_busy')
            if not self.image_handler.is_refreshing and not self.is_prefetched:
                logger.debug(f'[ImageManager] Prefetching with QTimer after image data loaded for {image_path}')
                QTimer.singleShot(0, self.image_handler.prefetch_images_if_needed)
                self.is_prefetched = True

    def refresh_image_list(self):
        """
        Refresh the image list and ensure the shutdown flag is respected.
        """
        with QMutexLocker(self.lock):
            if self.is_shutting_down():
                logger.info("[ImageManager] Shutdown initiated, not starting new refresh task.")
                return
        self.event_bus.emit('show_busy')
        self.image_handler.is_refreshing = True
        self.is_prefetched = False

        logger.info("[ImageManager] Triggering image list refresh.")
        self.image_handler.refresh_image_list(signal=self.image_list_updated)

    def shutdown(self):
        """
        Shutdown the ImageManager safely.
        """
        logger.info("[ImageManager] Initiating shutdown.")
        with QMutexLocker(self.lock):
            self.shutdown_flag = True
        self.image_handler.shutdown()
        logger.info("[ImageManager] Shutdown complete.")

    def on_image_list_updated(self):
        """
        Handle the event when the image list is updated.
        """
        logger.debug(f'[ImageManager] on_image_list_updated called, waiting for lock to load image')
        with QMutexLocker(self.lock):
            if self.is_shutting_down():
                logger.debug(f'[ImageManager] shutting down before taking action after signal of image list update')
                return
            logger.debug(f'[ImageManager] on_image_list_updated lock obtained')
            if not self.is_loading or not self.is_loaded or \
                    self.image_handler.data_service.get_current_image_path() != self.current_displayed_image:
                self.is_loading = True
                logger.debug(f'[ImageManager] No current image found, setting to first image')
                self.display_image()
            if self.image_handler.is_refreshing:
                logger.debug(f'[ImageManager] on_image_list_updated image already displayed, updating status bar')
                self.image_handler.update_image_total()
            else:
                logger.debug(f'[ImageManager] on_image_list_updated image refresh complete, hiding busy indicator')
                self.event_bus.emit('hide_busy')
                if not self.is_prefetched and not self.is_loading:
                    self.image_handler.prefetch_images_if_needed()
                    self.is_prefetched = True

    def move_image(self, category):
        """
        Move the current image to a specific category.

        :param str category: The category to which the image will be moved.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
        self.image_handler.move_current_image(category)
        self.display_image()

    def delete_image(self):
        """
        Delete the current image by removing it from the list and updating the display.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
        self.image_handler.delete_current_image()
        self.display_image()

    def undo_last_action(self):
        """
        Undo the last action taken on the current image, such as a move or delete.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            last_action = self.image_handler.undo_last_action()
        if last_action:
            logger.info(f"[ImageManager] Undo last action for image: {last_action[1]}")
            self.display_image()
        else:
            logger.warning("[ImageManager] No action to undo.")

    def first_image(self):
        """
        Set and display the first image in the list.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            self.image_handler.set_first_image()
        self.display_image()

    def last_image(self):
        """
        Set and display the last image in the list.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            self.image_handler.set_last_image()
        self.display_image()

    def next_image(self):
        """
        Set and display the next image in the list.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            self.image_handler.set_next_image()
        self.display_image()

    def previous_image(self):
        """
        Set and display the previous image in the list.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            self.image_handler.set_previous_image()
        self.display_image()

    def random_image(self):
        """
        Set and display a random image from the list.
        """
        with QMutexLocker(self.lock):
            self.is_prefetched = False
            self.image_handler.set_random_image()
        self.display_image()
