# image_cache.py
import logger

from PIL import Image


class ImageCache:
    def __init__(self):
        self.cache = {}
    def load_image(self, image_path):
        if image_path in self.cache:
            return self.cache[image_path]
        image = Image.open(image_path)
        self.cache[image_path] = image
        logger.info(f"Loaded image: {image_path}")
        return image

    def clear(self):
        self.cache.clear()
        logger.info("Cleared image cache")
