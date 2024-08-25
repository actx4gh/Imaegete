from PyQt6.QtCore import QThread, pyqtSignal

import logger
from .image_utils import load_image_with_qpixmap


class ThreadedImageLoader(QThread):
    image_loaded = pyqtSignal(str, object)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        logger.info(f"ThreadedImageLoader: Loading image {self.image_path}")
        image = load_image_with_qpixmap(self.image_path)  # Use the utility function
        if image is None:
            logger.error(f"ThreadedImageLoader: Failed to load image {self.image_path}")

        # Emit the signal to notify that the image has been loaded
        self.image_loaded.emit(self.image_path, image)
