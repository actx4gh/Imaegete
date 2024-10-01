from imaegete.core.logger import logger


class ImageCacheHandler:
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager

    def cache_image(self, image_path, image):
        logger.debug(f"[ImageCacheHandler] Caching image: {image_path}")
        self.cache_manager.add_to_cache(image_path, image)

    def get_cached_image(self, image_path, background=True):
        return self.cache_manager.retrieve_image(image_path, background=background)
