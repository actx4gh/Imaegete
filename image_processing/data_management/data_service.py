import natsort
from PyQt6.QtCore import QRecursiveMutex, QMutexLocker

from core import logger


class ImageDataService:
    """
    A class to manage image data, including the image list, current image path, and cache manager.
    This version handles thread safety, so modules like ImageHandler, ImageManager, and CacheManager
    no longer need to handle their own locking.
    """

    def __init__(self):
        self._current_image_path = None
        self._image_list = []
        self._sorted_images = []
        self._current_index = 0
        self.cache_manager = None
        self.lock = QRecursiveMutex()  # Central lock to ensure thread safety

    def get_image_path(self, index):
        """
        Get the image path at the specified index.

        :param int index: The index of the image.
        :return: The image path at the given index or None if out of bounds.
        :rtype: str or None
        """
        with QMutexLocker(self.lock):
            if 0 <= index < len(self._image_list):
                return self._image_list[index]
            return None

    def get_current_image_path(self):
        """
        Get the current image path.

        :return: The current image path.
        :rtype: str
        """
        with QMutexLocker(self.lock):
            return self._current_image_path

    def set_current_image_path(self, image_path):
        """
        Set the current image path.

        :param str image_path: The path of the current image.
        """
        with QMutexLocker(self.lock):
            self._current_image_path = image_path

    def get_sorted_images(self):
        """
        Get the list of sorted images.

        :return: The sorted images.
        :rtype: list
        """
        with QMutexLocker(self.lock):
            return self._sorted_images.copy()

    def set_sorted_images(self, sorted_images):
        """
        Set the list of sorted images.

        :param list sorted_images: The list of sorted images.
        """
        with QMutexLocker(self.lock):
            self._sorted_images = sorted_images

    def pop_sorted_images(self, index=None):
        """
        Remove and return the last item from the sorted images list, or the item at the given index.

        :param int index: The index of the image to pop. If None, pop the last image.
        :return: The popped sorted image.
        :rtype: tuple
        """
        with QMutexLocker(self.lock):
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
        with QMutexLocker(self.lock):
            if index is None:
                index = len(self._image_list) - 1
            return self._image_list.pop(index)

    def append_sorted_images(self, sorted_tuple):
        """
        Append a tuple to the sorted images list.

        :param tuple sorted_tuple: The tuple to append to the sorted images list.
        """
        with QMutexLocker(self.lock):
            self._sorted_images.append(sorted_tuple)

    def get_image_list_len(self):
        """
        Get the length of the image list.

        :return: The number of images in the image list.
        :rtype: int
        """
        with QMutexLocker(self.lock):
            return len(self._image_list)

    def get_image_list(self):
        """
        Get the image list.

        :return: The list of images.
        :rtype: list
        """
        with QMutexLocker(self.lock):
            return self._image_list.copy()

    def image_is_current(self, image_path):
        """
        Check if the provided image path is the current image.

        :param str image_path: The path of the image to check.
        :return: True if the image is current, False otherwise.
        :rtype: bool
        """
        with QMutexLocker(self.lock):
            return self._current_index == self._image_list.index(image_path)

    def extend_image_list(self, image_list):
        """
        Set the image list.

        :param list image_list: The list of images.
        """
        with QMutexLocker(self.lock):
            self._image_list.extend(image_list)

    def set_image_list(self, image_list):
        """
        Set the image list.

        :param list image_list: The list of images.
        """
        with QMutexLocker(self.lock):
            self._image_list = image_list

    def insert_sorted_image(self, image_path):
        """
        Insert an image into the image list while maintaining order based on os_sort_key.

        :param str image_path: The path of the image to insert.
        """
        with QMutexLocker(self.lock):
            new_item_key = natsort.os_sort_key(image_path)

            index = 0
            while index < len(self._image_list):
                current_item_key = natsort.os_sort_key(self._image_list[index])

                if new_item_key < current_item_key:
                    break
                index += 1

            self._image_list.insert(index, image_path)

            if self._current_image_path in self._image_list:
                self._current_index = self._image_list.index(self._current_image_path)

    def remove_image(self, image_path):
        """
        Remove an image from the image list and update the current index accordingly.

        :param str image_path: The path of the image to remove.
        """
        with QMutexLocker(self.lock):
            if image_path in self._image_list:
                original_index = self._image_list.index(image_path)
                self._image_list.remove(image_path)

                if self._current_image_path in self._image_list:
                    self._current_index = self._image_list.index(self._current_image_path)
                elif self._image_list:
                    if self._current_index == len(self._image_list):
                        self._current_index = self._image_list[-1]
                    self.set_current_image_to_current_index()
                else:
                    self._current_image_path = None
                    self._current_index = None
                    logger.info(f'[DataService] Removed last image from image list')
            else:
                raise ValueError(f"Image {image_path} not found in the list.")

    def get_current_index(self):
        """
        Get the current index of the image being viewed.

        :return: The current index.
        :rtype: int
        """
        with QMutexLocker(self.lock):
            return self._current_index

    def set_current_index(self, index):
        """
        Set the current index and update the current image path accordingly.

        :param int index: The index to set as current.
        """
        with QMutexLocker(self.lock):
            self._current_index = index
            if len(self._image_list) >= index + 1:
                self.set_current_image_to_current_index()

    def get_index_for_image(self, image_path):
        """
        Get the index of a specific image.

        :param str image_path: The image path to look up.
        :return: The index of the image in the list.
        :rtype: int
        """
        with QMutexLocker(self.lock):
            return self._image_list.index(image_path)

    def set_current_image_to_current_index(self):
        """
        Set the current image path based on the current index.
        """
        with QMutexLocker(self.lock):
            self._current_image_path = self._image_list[self._current_index]

    def set_cache_manager(self, cache_manager):
        """
        Set the cache manager for managing image caching.

        :param CacheManager cache_manager: The cache manager to set.
        """
        with QMutexLocker(self.lock):
            self.cache_manager = cache_manager

    def get_cache_manager(self):
        """
        Get the cache manager for managing image caching.

        :return: The cache manager.
        :rtype: CacheManager
        """
        with QMutexLocker(self.lock):
            return self.cache_manager
