from collections import OrderedDict
from PIL import Image
import logger

class ImageCache:
    def __init__(self, max_size=10):
        self.cache = OrderedDict()
        self.max_size = max_size

    def load_image(self, image_path):
        if image_path in self.cache:
            self.cache.move_to_end(image_path)
            return self.cache[image_path]

        image = Image.open(image_path)
        self.cache[image_path] = image
        logger.info(f"Loaded image: {image_path}")

        if len(self.cache) > self.max_size:
            oldest = self.cache.popitem(last=False)
            logger.info(f"Evicted oldest cached image: {oldest[0]}")

        return image

    def clear(self):
        self.cache.clear()
        logger.info("Cleared image cache")