# threaded_image_loader.py
from PyQt5.QtCore import QThread, pyqtSignal
from PIL import Image
import logging

class ThreadedImageLoader(QThread):
    image_loaded = pyqtSignal(str, object)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        self.logger = logging.getLogger('image_sorter')

    def run(self):
        self.logger.info(f"ThreadedImageLoader: Loading image {self.image_path}")
        try:
            image = Image.open(self.image_path)
            self.logger.info(f"ThreadedImageLoader: Successfully loaded image {self.image_path}")
            self.image_loaded.emit(self.image_path, image)
        except Exception as e:
            self.logger.error(f"ThreadedImageLoader: Failed to load image {self.image_path}: {e}")
            self.image_loaded.emit(self.image_path, None)
