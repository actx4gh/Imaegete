from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

import logger


class ThreadedImageLoader(QThread):
    image_loaded = pyqtSignal(str, object)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        logger.info(f"ThreadedImageLoader: Loading image {self.image_path}")
        image = QPixmap(self.image_path)
        if image.isNull():
            logger.error(f"ThreadedImageLoader: Failed to load image {self.image_path}")
            image = None

        # Emit the signal to notify that the image has been loaded
        self.image_loaded.emit(self.image_path, image)
