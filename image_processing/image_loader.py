from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PIL import Image
import logging

class ImageLoader(QThread):
    image_loaded = pyqtSignal(object)  # Signal to emit the loaded image, can be PIL Image or QImage
    finished_loading = pyqtSignal()

    def __init__(self, image_handler, index):
        super().__init__()
        self.image_handler = image_handler
        self.index = index
        self._is_running = True
        self.logger = logging.getLogger('image_sorter')
        self.logger.info(f"[ImageLoader] Initialized for image index {index}")

    def run(self):
        self.logger.info("[ImageLoader] run method started")
        try:
            if not self._is_running:
                self.logger.info("[ImageLoader] run method stopped before loading image")
                return
            self.logger.info(f"[ImageLoader] Loading image at index: {self.index}")
            image = self.image_handler.load_image(self.index)
            if image:
                loaded_image = self.process_image(image)
                self.logger.info("[ImageLoader] Image processed")
                if self._is_running:
                    self.logger.info("[ImageLoader] Emitting image_loaded signal")
                    self.image_loaded.emit(loaded_image)
        except Exception as e:
            self.logger.error(f"[ImageLoader] Error loading image: {e}")
        finally:
            self.logger.info("[ImageLoader] Emitting finished_loading signal")
            self.finished_loading.emit()
            self.logger.info("[ImageLoader] Finished")

    def process_image(self, image):
        """Convert PIL Image to QImage."""
        image = image.convert("RGBA")  # Use RGBA to ensure correct handling
        data = image.tobytes("raw", "RGBA")
        qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return qimage

    def stop(self):
        self.logger.info("[ImageLoader] Stopping")
        self._is_running = False
        self.quit()
        self.logger.info("[ImageLoader] Waiting for thread to finish")
        self.wait()
        self.logger.info("[ImageLoader] Stopped")
