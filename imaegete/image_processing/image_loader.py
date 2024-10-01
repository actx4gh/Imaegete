from imaegete.core.logger import logger


class ImageLoader:
    def __init__(self, cache_handler, thread_manager):
        self.cache_handler = cache_handler
        self.thread_manager = thread_manager

    def load_image(self, image_path):
        logger.debug(f"[ImageLoader] Loading image: {image_path}")
        return self.cache_handler.get_cached_image(image_path, background=False)

    def load_image_async(self, image_path, callback):
        def task():
            image = self.load_image(image_path)
            callback(image)

        self.thread_manager.submit_task(task)
