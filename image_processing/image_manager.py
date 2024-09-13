from threading import RLock, Event
import traceback

from PyQt6.QtCore import pyqtSignal, QObject, Qt, QCoreApplication, QTimer

from core import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_list_updated = pyqtSignal()
    image_list_populated = pyqtSignal()

    def __init__(self, image_handler, thread_manager):
        super().__init__()
        self.image_handler = image_handler
        self.thread_manager = thread_manager
        self.shutdown_event = Event()
        self.is_loading = Event()
        self.shuffled_indices = []

        self.event_bus = create_or_get_shared_event_bus()

        self.image_list_updated.connect(self.on_image_list_updated, Qt.ConnectionType.BlockingQueuedConnection)
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
        self.image_handler.shutdown()
        logger.info("[ImageManager] Shutdown complete.")

    def on_image_list_updated(self):
        if not self.image_handler.has_current_image():
            if self.is_loading.is_set():
                return
            self.is_loading.set()
            logger.info(f'[ImageManager] No current image found, setting to first image')
            self.image_handler.set_first_image()
            self.load_image()
        else:

            self.image_handler.update_image_total()

        if not self.image_handler.is_refreshing.is_set():
            self.event_bus.emit('hide_busy')
            self.image_handler.prefetch_images_if_needed()

    def move_image(self, category):
        with self.lock:
            self.image_handler.move_current_image(category)

    def delete_image(self):
        with self.lock:
            self.image_handler.delete_current_image()

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
            self.image_handler.set_first_image()
        self.load_image()

    def last_image(self):
        with self.lock:
            self.image_handler.set_last_image()
        self.load_image()

    def next_image(self):
        """Delegate to ImageHandler to move to the next image."""
        with self.lock:
            self.image_handler.set_next_image()
        self.load_image()

    def previous_image(self):
        """Delegate to ImageHandler to move to the previous image."""
        with self.lock:
            self.image_handler.set_previous_image()
        self.load_image()

    def random_image(self):
        """Delegate to ImageHandler to select a random image."""
        with self.lock:
            self.image_handler.set_random_image()
        self.load_image()

    def load_image(self, index=None):
        logger.debug(f"Call stack for image_manager.load_image {traceback.format_stack()}")
        with self.lock:
            image_path = self.image_handler.set_current_image_by_index(index)

            if image_path:
                #self.thread_manager.submit_task(self._load_image_task, image_path)
                self._load_image_task(image_path)
            else:
                self.image_cleared.emit()

    def _load_image_task(self, image_path):
        """Task to load image asynchronously."""
        logger.debug(f"Call stack for image_manager._load_image_task {traceback.format_stack()}")

        pixmap = self.image_handler.load_image_from_cache(image_path)

        with self.lock:
            if pixmap:

                self.image_loaded.emit(image_path, pixmap)
                self.current_pixmap = pixmap
                QCoreApplication.processEvents()

                # Start prefetching after the GUI is updated using a timer to delay it slightly
                QTimer.singleShot(0, self.image_handler.prefetch_images_if_needed)
            else:

                self.image_cleared.emit()

        self.is_loading.clear()
