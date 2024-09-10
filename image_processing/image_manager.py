import random
from threading import RLock, Event

from PyQt6.QtCore import pyqtSignal, QObject, Qt

from core import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_list_updated = pyqtSignal()
    image_list_populated = pyqtSignal()

    def __init__(self, image_handler, thread_manager, data_service):
        super().__init__()
        self.image_handler = image_handler
        self.thread_manager = thread_manager
        self.data_service = data_service
        self.shutdown_event = Event()
        self.is_loading = Event()
        self.shuffled_indices = []

        # Get the shared event bus
        self.event_bus = create_or_get_shared_event_bus()

        self.image_list_updated.connect(self.on_image_list_updated, Qt.ConnectionType.BlockingQueuedConnection)
        self.data_service.set_current_index(0)
        self.data_service.set_current_image_path(None)
        self.lock = RLock()

    def refresh_image_list(self):
        """Trigger image list refresh with correct shutdown_event."""
        if self.shutdown_event.is_set():
            logger.info("[ImageManager] Shutdown initiated, not starting new refresh task.")
            return
        self.event_bus.emit('show_busy')
        self.image_handler.is_refreshing.set()

        logger.info("[ImageManager] Triggering image list refresh.")
        self.thread_manager.submit_task(self._refresh_image_list_task, self.image_list_updated, self.shutdown_event)

    def _refresh_image_list_task(self, signal, shutdown_event):
        """Pass the same shutdown_event to the image handler."""
        self.image_handler.refresh_image_list(signal=signal, shutdown_event=shutdown_event)

    def shutdown(self):
        """Shutdown the ImageManager, ThreadManager, and CacheManager."""
        logger.info("[ImageManager] Initiating shutdown.")
        self.shutdown_event.set()
        self.thread_manager.shutdown()
        self.data_service.cache_manager.shutdown()
        logger.info("[ImageManager] Shutdown complete.")

    def on_image_list_updated(self):
        if not self.data_service.get_current_image_path() and self.data_service.get_image_path(0):
            if self.is_loading.is_set():
                return
            self.is_loading.set()
            logger.info(f'[ImageManager] Got first image')
            self.data_service.set_current_index(0)
            self.load_image()
        else:
            self.event_bus.emit('update_image_total')
        if not self.image_handler.is_refreshing.is_set():
            self.event_bus.emit('hide_busy')

    def next_image(self):
        """Navigate to the next image."""
        with self.lock:
            if len(self.data_service.get_image_list()) > 0:
                self.data_service.set_current_index(
                    (self.data_service.get_current_index() + 1) % len(self.data_service.get_image_list()))
            else:
                self.data_service.set_current_index(0)
        self.load_image()

    def previous_image(self):
        """Navigate to the previous image."""
        with self.lock:
            if len(self.data_service.get_image_list()) > 0:
                self.data_service.set_current_index(
                    (self.data_service.get_current_index() - 1) % len(self.data_service.get_image_list()))
            else:
                self.data_service.set_current_index(0)
        self.load_image()

    def move_image(self, category):
        with self.lock:
            current_image = self.data_service.get_image_path(self.data_service.get_current_index())
            if current_image:
                self.image_handler.move_image(current_image, category)
                logger.info(f"[ImageManager] Moved image: {current_image} to {category}")
                self.next_image()  # Move to the next image after moving

    def delete_image(self):
        with self.lock:
            current_image = self.data_service.get_image_path(self.data_service.get_current_index())
            if current_image:
                self.image_handler.delete_image(current_image)
                logger.info(f"[ImageManager] Deleted image: {current_image}")
                self.next_image()  # Move to the next image after deletion

    def undo_last_action(self):
        with self.lock:
            last_action = self.image_handler.undo_last_action()
            if last_action:
                logger.info(f"[ImageManager] Undo last action for image: {last_action[1]}")
                self.load_image()
            else:
                logger.warning("[ImageManager] No action to undo.")

    def first_image(self):
        with self.lock:
            self.data_service.set_current_index(0)
        self.load_image()

    def last_image(self):
        with self.lock:
            # Set the current index to the last image
            self.data_service.set_current_index(len(self.data_service.get_image_list()) - 1)
        self.load_image()

    def random_image(self):
        """Display a random image without repeating until all images have been shown."""
        with self.lock:
            if not self.shuffled_indices:
                self.shuffled_indices = list(range(len(self.data_service.get_image_list())))
                random.shuffle(self.shuffled_indices)
                logger.info("[ImageManager] All images have been shown. Reshuffling the list.")

            next_index = self.shuffled_indices.pop(0)
            self.data_service.set_current_index(next_index)

        self.load_image()

        logger.info(
            f"[ImageManager] Displaying random image at index {self.data_service.get_current_index()}: {self.data_service.get_current_image_path()}")

    def load_image(self, index=None):
        with self.lock:
            if index:
                self.data_service.set_current_index(index)
            elif not isinstance(self.data_service.get_current_index(), int):
                self.data_service.set_current_index(0)

            image_path = self.data_service.get_current_image_path()
            if image_path:
                # if self.data_service.get_current_image_path() == image_path:
                #    return
                self.thread_manager.submit_task(self._load_image_task, image_path)
            else:
                self.image_cleared.emit()

    def _load_image_task(self, image_path):
        """Task to load image asynchronously."""
        pixmap = self.data_service.cache_manager.retrieve_pixmap(image_path)
        if pixmap:
            with self.lock:
                self.data_service.set_current_image_path(image_path)
                self.image_loaded.emit(image_path, pixmap)
                self.current_pixmap = pixmap
        else:
            with self.lock:
                self.image_cleared.emit()
        self.is_loading.clear()

    def prefetch_images(self):
        """Prefetch images around the current index asynchronously using ThreadManager."""
        self.thread_manager.submit_task(self._prefetch_images_task)

    def _prefetch_images_task(self):
        """Task to prefetch images around the current index."""
        total_images = len(self.data_service.get_image_list())
        if total_images == 0:
            return

        prefetch_indices = [(self.data_service.get_current_index() + i) % total_images for i in range(1, 4)]
        prefetch_indices += [(self.data_service.get_current_index() - i) % total_images for i in range(1, 4)]

        for index in prefetch_indices:
            image_path = self.data_service.get_image_path(index)
            if image_path and not self.data_service.cache_manager.retrieve_pixmap(image_path):
                self._load_image_task(image_path)
