# image_loader.py
from PIL import Image
from PyQt5.QtCore import QThread, pyqtSignal

import logger


class ThreadedImageLoader(QThread):
    image_loaded = pyqtSignal(str, object)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self):
        logger.info(f"ThreadedImageLoader: Loading image {self.image_path}")
        try:
            image = Image.open(self.image_path)
            logger.info(f"ThreadedImageLoader: Successfully loaded image {self.image_path}")
            self.image_loaded.emit(self.image_path, image)
        except Exception as e:
            logger.error(f"ThreadedImageLoader: Failed to load image {self.image_path}: {e}")
            self.image_loaded.emit(self.image_path, None)
