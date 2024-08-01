from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PIL import Image
import logging

class BaseImageLoader(QThread):
    image_loaded = pyqtSignal(object)  # Signal to emit the loaded image, can be PIL Image or QImage
    finished_loading = pyqtSignal()

    def __init__(self, image_handler, index):
        super().__init__()
        self.image_handler = image_handler
        self.index = index
        self._is_running = True
        logging.info(f"[ImageLoader] Initialized for image index {index}")

    def run(self):
        logging.info("[ImageLoader] run method started")
        try:
            if not self._is_running:
                logging.info("[ImageLoader] run method stopped before loading image")
                return
            logging.info(f"[ImageLoader] Loading image at index: {self.index}")
            image = self.image_handler.load_image(self.index)
            if image:
                loaded_image = self.process_image(image)
                logging.info("[ImageLoader] Image processed")
                if self._is_running:
                    logging.info("[ImageLoader] Emitting image_loaded signal")
                    self.image_loaded.emit(loaded_image)
        except Exception as e:
            logging.error(f"[ImageLoader] Error loading image: {e}")
        finally:
            logging.info("[ImageLoader] Emitting finished_loading signal")
            self.finished_loading.emit()
            logging.info("[ImageLoader] Finished")

    def process_image(self, image):
        raise NotImplementedError("process_image must be implemented in derived classes")

    def stop(self):
        logging.info("[ImageLoader] Stopping")
        self._is_running = False
        self.quit()
        logging.info("[ImageLoader] Waiting for thread to finish")
        self.wait()
        logging.info("[ImageLoader] Stopped")

class NonGPUImageLoader(BaseImageLoader):
    def process_image(self, image):
        """Convert PIL Image to QImage."""
        image = image.convert("RGBA")  # Use RGBA to ensure correct handling
        data = image.tobytes("raw", "RGBA")
        qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return qimage

class GPUImageLoader(BaseImageLoader):
    def process_image(self, image):
        """Return the PIL image as is for GPU processing."""
        return image
