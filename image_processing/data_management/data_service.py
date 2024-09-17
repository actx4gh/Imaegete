class ImageDataService:
    """
    A class to manage image data, including the image list, current image path, and cache manager.
    """
    def __init__(self):
        self._current_image_path = None
        self._image_list = []
        self._sorted_images = []
        self._current_index = 0
        self.cache_manager = None

    def get_image_path(self, index):
        """
        Get the image path at the specified index.

        :param int index: The index of the image.
        :return: The image path at the given index or None if out of bounds.
        :rtype: str or None
        """
        if 0 <= index < len(self._image_list):
            return self._image_list[index]
        return None

    def get_current_image_path(self):
        """
        Get the current image path.

        :return: The current image path.
        :rtype: str
        """
        return self._current_image_path

    def set_current_image_path(self, image_path):
        """
        Set the current image path.

        :param str image_path: The path of the current image.
        """
        self._current_image_path = image_path

    def get_sorted_images(self):
        """
        Get the list of sorted images.

        :return: The sorted images.
        :rtype: list
        """
        return self._sorted_images

    def set_sorted_images(self, sorted_images):
        """
        Set the list of sorted images.

        :param list sorted_images: The list of sorted images.
        """
        self._sorted_images = sorted_images

    def pop_sorted_images(self, index=None):
        """
        Remove and return the last item from the sorted images list, or the item at the given index.

        :param int index: The index of the image to pop. If None, pop the last image.
        :return: The popped sorted image.
        :rtype: tuple
        """
        if index is None:
            index = len(self._sorted_images) - 1
        return self._sorted_images.pop(index)

    def pop_image_list(self, index=None):
        """
        Remove and return the last item from the image list, or the item at the given index.

        :param int index: The index of the image to pop. If None, pop the last image.
        :return: The popped image.
        :rtype: str
        """
        if index is None:
            index = len(self._image_list) - 1
        return self._image_list.pop(index)

    def append_sorted_images(self, sorted_tuple):
        """
        Append a tuple to the sorted images list.

        :param tuple sorted_tuple: The tuple to append to the sorted images list.
        """
        self._sorted_images.append(sorted_tuple)

    def get_image_list_len(self):
        """
        Get the length of the image list.

        :return: The number of images in the image list.
        :rtype: int
        """
        return len(self._image_list)

    def get_image_list(self):
        """
        Get the image list.

        :return: The list of images.
        :rtype: list
        """
        return self._image_list

    def set_image_list(self, image_list):
        """
        Set the image list.

        :param list image_list: The list of images.
        """
        self._image_list = image_list

    def get_current_index(self):
        """
        Get the current index of the image being viewed.

        :return: The current index.
        :rtype: int
        """
        return self._current_index

    def set_current_index(self, index):
        """
        Set the current index and update the current image path accordingly.

        :param int index: The index to set as current.
        """
        self._current_index = index
        if len(self._image_list) >= index + 1:
            self.set_current_image_to_current_index()

    def set_current_image_to_current_index(self):
        """
        Set the current image path based on the current index.
        """
        self._current_image_path = self._image_list[self._current_index]

    def set_cache_manager(self, cache_manager):
        """
        Set the cache manager for managing image caching.

        :param CacheManager cache_manager: The cache manager to set.
        """
        self.cache_manager = cache_manager

    def get_cache_manager(self):
        """
        Get the cache manager for managing image caching.

        :return: The cache manager.
        :rtype: CacheManager
        """
        return self.cache_manager
