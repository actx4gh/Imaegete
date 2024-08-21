from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

import logger
from .image_cache import ImageCache


class ThreadedImageLoader(QThread):
    image_loaded = pyqtSignal(str, object)

    def __init__(self, image_path, cache: ImageCache):
        super().__init__()
        self.image_path = image_path
        self.cache = cache

    def run(self):
        if self.image_path in self.cache.cache:
            logger.info(f"ThreadedImageLoader: Cache hit for image {self.image_path}")
            image = self.cache.cache[self.image_path]
        else:
            logger.info(f"ThreadedImageLoader: Loading image {self.image_path}")
            try:
                image = Image.open(self.image_path)
                self.cache.cache[self.image_path] = image
                logger.info(f"ThreadedImageLoader: Successfully loaded image {self.image_path}")
            except Exception as e:
                logger.error(f"ThreadedImageLoader: Failed to load image {self.image_path}: {e}")
                image = None
        self.image_loaded.emit(self.image_path, image)
