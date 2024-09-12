class ImageDataService:
    def __init__(self):
        self._current_image_path = None
        self._image_list = []
        self._sorted_images = []
        self._current_index = 0
        self.cache_manager = None

    def get_image_path(self, index):
        """Return the image path at the given index."""
        if 0 <= index < len(self._image_list):
            return self._image_list[index]
        return None

    def get_current_image_path(self):
        return self._current_image_path

    def set_current_image_path(self, image_path):
        self._current_image_path = image_path

    def get_sorted_images(self):
        return self._sorted_images

    def set_sorted_images(self, sorted_images):
        self._sorted_images = sorted_images

    def pop_sorted_images(self):
        return self._sorted_images.pop()

    def get_image_list(self):
        return self._image_list

    def set_image_list(self, image_list):
        self._image_list = image_list

    def get_current_index(self):
        return self._current_index

    def set_current_index(self, index):
        self._current_index = index
        if len(self._image_list) >= index + 1:
            self._current_image_path = self._image_list[index]

    def set_cache_manager(self, cache_manager):
        self.cache_manager = cache_manager

    def get_cache_manager(self):
        return self.cache_manager
