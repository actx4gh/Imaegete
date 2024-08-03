# image_cache.py
from PIL import Image
import logging

class ImageCache:
    def __init__(self):
        self.cache = {}

    def load_image(self, image_path):
        if image_path in self.cache:
            logging.getLogger('image_sorter').info(f"Using cached image for {image_path}")
            return self.cache[image_path]
        image = Image.open(image_path)
        self.cache[image_path] = image
        logging.getLogger('image_sorter').info(f"Loaded image: {image_path}")
        return image

    def clear(self):
        self.cache.clear()
        logging.getLogger('image_sorter').info("Cleared image cache")
