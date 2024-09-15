from functools import partial
from threading import RLock, Event

from PyQt6.QtCore import pyqtSignal, QObject, Qt, QTimer
from PyQt6.QtGui import QPixmap

from core import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_list_updated = pyqtSignal()

    def __init__(self, image_handler, thread_manager):
        super().__init__()
        self.image_handler = image_handler
        self.thread_manager = thread_manager
        self.shutdown_event = Event()
        self.is_loading = Event()
        self.is_loaded = Event()
        self.is_prefetched = Event()
        self.shuffled_indices = []

        self.event_bus = create_or_get_shared_event_bus()

        self.image_list_updated.connect(self.on_image_list_updated, Qt.ConnectionType.BlockingQueuedConnection)
        self.lock = RLock()
        self.image_handler.data_service.cache_manager.image_loaded.connect(self.on_image_loaded_from_cache)

    def display_image(self, index=None):
        with self.lock:
            image_path = self.image_handler.set_current_image_by_index(index)

            if image_path:
                
                self.thread_manager.submit_task(self._display_image_task, image_path)
            else:
                self.image_cleared.emit()

    def _display_image_task(self, image_path):
        """Task to load image asynchronously."""
        with self.lock:
            current_image_path = self.image_handler.data_service.get_current_image_path()
            if image_path != current_image_path:
                
                return

        
        image = self.image_handler.load_image_from_cache(image_path)
        if image:
            
            QTimer.singleShot(0, partial(self.process_image_data, image_path, image))
        else:
            pass  

    def on_image_loaded_from_cache(self, image_path):
        """Handle the image_loaded signal from CacheManager."""
        with self.lock:
            current_image_path = self.image_handler.data_service.get_current_image_path()
            if image_path != current_image_path:
                return
        image = self.image_handler.data_service.cache_manager.retrieve_image(image_path)
        if image:
            
            QTimer.singleShot(0, partial(self.process_image_data, image_path, image))
        else:
            logger.error(f"[ImageManager] Image {image_path} is not in cache despite 'image_loaded' signal.")

    def process_image_data(self, image_path, image):
        """Process the image data in the main thread."""
        pixmap = QPixmap.fromImage(image)
        self.image_loaded.emit(image_path, pixmap)
        self.is_loaded.set()
        self.is_loading.clear()
        if not any((self.image_handler.is_refreshing.is_set(), self.is_prefetched.is_set())):
            logger.debug(f'ImageManager prefetching after image data loaded for {image_path}')
            QTimer.singleShot(0, self.image_handler.prefetch_images_if_needed)
            self.is_prefetched.set()

    def refresh_image_list(self):
        """Trigger image list refresh with correct shutdown_event."""
        if self.shutdown_event.is_set():
            logger.info("[ImageManager] Shutdown initiated, not starting new refresh task.")
            return
        self.event_bus.emit('show_busy')
        self.image_handler.is_refreshing.set()
        self.is_prefetched.clear()

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
        if not any((self.is_loading.is_set(), self.is_loaded.is_set())):
            self.is_loading.set()
            logger.info(f'[ImageManager] No current image found, setting to first image')
            self.display_image()
        if self.image_handler.is_refreshing.is_set():
            self.image_handler.update_image_total()
        else:
            self.event_bus.emit('hide_busy')
            if not self.is_prefetched.is_set():
                self.image_handler.prefetch_images_if_needed()
                self.is_prefetched.set()

    def move_image(self, category):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.move_current_image(category)
        self.display_image()

    def delete_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.delete_current_image()
        self.display_image()

    def undo_last_action(self):
        self.is_prefetched.clear()
        with self.lock:
            last_action = self.image_handler.undo_last_action()
            if last_action:
                logger.info(f"[ImageManager] Undo last action for image: {last_action[1]}")
                self.display_image()
            else:
                logger.warning("[ImageManager] No action to undo.")

    def first_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.set_first_image()
        self.display_image()

    def last_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.set_last_image()
        self.display_image()

    def next_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.set_next_image()
        self.display_image()

    def previous_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.set_previous_image()
        self.display_image()

    def random_image(self):
        self.is_prefetched.clear()
        with self.lock:
            self.image_handler.set_random_image()
        self.display_image()
