import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from threading import RLock, Event

import numpy as np
from natsort import os_sorted

from core import config, logger
from core.exceptions import ImaegeteError
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from image_processing.data_management.file_operations import move_image_and_cleanup


class ImageHandler:
    """
    A class to manage image handling operations, including image list management, prefetching, moving, and deleting images.
    """

    def __init__(self, thread_manager, data_service):
        self.thread_manager = thread_manager
        self.event_bus = create_or_get_shared_event_bus()
        self.data_service = data_service
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self._start_dirs = []
        self.shuffled_indices = []

        self.lock = RLock()
        self.is_refreshing = Event()

        self.data_service.set_image_list([])
        self.data_service.set_sorted_images([])

    @property
    def start_dirs(self):
        if not self._start_dirs:
            self._start_dirs = os_sorted(config.start_dirs)
        return self._start_dirs

    def add_image_to_list(self, image_path, index=None):
        """
        Add a new image to the image list at the specified index or at the end.

        :param image_path: Path to the image file.
        :type image_path: str
        :param index: The position to insert the image. If None, append to the end.
        :type index: int, optional
        """
        """Add a new image to the image list at the specified index or at the end."""
        image_list = self.data_service.get_image_list()
        if self.is_image_file(image_path) and image_path not in image_list:
            with self.lock:
                if index is not None:
                    image_list.insert(index, image_path)
                else:
                    image_list.append(image_path)
            self.data_service.set_image_list(image_list)

    def remove_image_from_list(self, image_path):
        """
        Remove an image from the image list.

        :param image_path: Path to the image file to be removed.
        :type image_path: str
        """
        """Remove an image from the image list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if image_path in image_list:
                image_list.remove(image_path)
            self.data_service.set_image_list(image_list)

    def set_first_image(self):
        """
        Set the first image in the list as the current image.
        """
        """Navigate to the first image (index 0) and update the data service."""
        with self.lock:
            if len(self.data_service.get_image_list()) > 0:
                self.set_current_image_by_index(0)

    def set_last_image(self):
        """
        Set the last image in the list as the current image.
        """
        """Navigate to the last image in the list and update the data service."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                last_index = len(image_list) - 1
                self.set_current_image_by_index(last_index)

    def pop_image(self):
        with self.lock:
            image_list = self.data_service.get_image_list()
            original_index = self.data_service.get_current_index()
            image_path = self.data_service.pop_image_list(original_index)
            if original_index == len(image_list):
                self.data_service.set_current_index(len(image_list) - 1)
            else:
                self.data_service.set_current_image_to_current_index()
            return original_index, image_path

    def set_next_image(self):
        """
        Set the next image in the list as the current image.
        """
        """Set the index to the next image in the list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                next_index = (self.data_service.get_current_index() + 1) % len(image_list)
                self.set_current_image_by_index(next_index)

    def set_previous_image(self):
        """
        Set the previous image in the list as the current image.
        """
        """Set the index to the previous image in the list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                previous_index = (self.data_service.get_current_index() - 1) % len(image_list)
                self.set_current_image_by_index(previous_index)

    def set_current_image_by_index(self, index=None):
        """
        Set the image at a specified index as the current image.

        :param index: The index of the image to set as current. If None, the first image is set.
        :type index: int, optional
        """
        """Set the current image index and return the current image path."""
        with self.lock:

            if index is not None:
                self.data_service.set_current_index(index)
            elif not isinstance(self.data_service.get_current_index(), int):

                self.data_service.set_current_index(0)

            image_path = self.data_service.get_current_image_path()

            if image_path:
                self.data_service.set_current_image_path(image_path)
                return image_path

            return None

    def set_random_image(self):
        """
        Set a random image from the list as the current image, avoiding repeats until all images have been shown.
        """
        """Set the index to a random image, avoiding repeats until all have been shown."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                if not hasattr(self, 'shuffled_indices') or not self.shuffled_indices:
                    self.shuffled_indices = list(range(len(image_list)))
                    random.shuffle(self.shuffled_indices)
                    logger.info("[ImageHandler] All images shown, reshuffling the list.")

                random_index = self.shuffled_indices.pop(0)
                self.set_current_image_by_index(random_index)

    def has_current_image(self):
        """
        Check if there is a valid current image.

        :return: True if there is a current image, False otherwise.
        :rtype: bool
        """
        """Check if a valid current image exists."""
        return bool(self.data_service.get_current_image_path())

    def prefetch_images(self, depth=3, max_prefetch=10):
        """
        Prefetch images around the current image for faster loading.

        :param depth: Number of images ahead and behind the current image to prefetch.
        :type depth: int
        :param max_prefetch: Maximum number of images to prefetch.
        :type max_prefetch: int
        """
        """Handle prefetching of images."""
        total_images = len(self.data_service.get_image_list())
        if total_images == 0:
            return

        prev_index = (self.data_service.get_current_index() + -1) % total_images
        next_index = (self.data_service.get_current_index() + 1) % total_images
        behind = np.arange(prev_index, prev_index - depth, -1) % total_images
        ahead = np.arange(next_index, next_index + depth) % total_images

        logger.debug(
            f"[ImageHandler] Starting prefetch of indexes {list(behind)} and {list(ahead)} from index {self.data_service.get_current_index()} with a total of {total_images} images")

        prefetch_indices = [item for pair in zip(ahead, behind) for item in pair]

        if len(prefetch_indices) > max_prefetch:
            prefetch_indices = prefetch_indices[:max_prefetch]
            logger.warn(f"[ImageHandler] Reduced number of prefetch items to max_prefetch {max_prefetch}")

        for index in prefetch_indices:
            image_path = self.data_service.get_image_path(index)
            if image_path:
                image = self.data_service.cache_manager.retrieve_image(image_path)
                if image:
                    logger.info(f"[ImageHandler] Skipping already cached image: {image_path}")
                else:
                    logger.info(f"[ImageHandler] Prefetching uncached image: {image_path}")
                    
                    self.data_service.cache_manager.retrieve_image(image_path)
                    self.data_service.cache_manager.get_metadata(image_path)

    def load_image_from_cache(self, image_path):
        logger.debug(f"Loading image from cache or disk: {image_path}")
        image = self.data_service.cache_manager.retrieve_image(image_path, active_request=True)
        return image

    def prefetch_images_if_needed(self):
        """
        Prefetch images around the current image for faster loading.

        :param depth: Number of images ahead and behind the current image to prefetch.
        :type depth: int
        :param max_prefetch: Maximum number of images to prefetch.
        :type max_prefetch: int
        """
        """Check if prefetching is needed and perform prefetching."""
        if not self.is_refreshing.is_set():
            self.prefetch_images()

    def delete_current_image(self):
        """
        Delete the current image by moving it to the delete folder and removing it from the list.
        """
        """Move image to the delete folder and remove from the list."""

        original_index, image_path = self.pop_image()
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        delete_folder = self.delete_folders.get(start_dir)
        if delete_folder:
            logger.info(f"[ImageHandler] Moving {image_path} to delete folder.")
            self.thread_manager.submit_task(self._move_image_task, image_path, start_dir, delete_folder)
        else:
            logger.error(f"[ImageHandler] Delete folder not configured for start directory {start_dir}")
        self.data_service.append_sorted_images(('delete', image_path, original_index))

    def move_current_image(self, category):
        """
        Move the current image to a specific category folder.

        :param category: The category to move the image to.
        :type category: str
        """
        """Move an image to the specified category folder asynchronously."""
        original_index, image_path = self.pop_image()
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        logger.info(f"[ImageHandler] Moving image: {image_path}")

        dest_folder = self.dest_folders[start_dir].get(category)
        if not dest_folder:
            logger.error(
                f"[ImageHandler] Destination folder not found for category {category} in directory {start_dir}")
            return

        self.thread_manager.submit_task(self._move_image_task, image_path, start_dir, dest_folder)
        self.data_service.append_sorted_images(('move', image_path, category, original_index))

    def _move_image_task(self, image_path, source_dir, dest_dir):
        with self.lock:
            try:
                move_image_and_cleanup(image_path, source_dir, dest_dir)
                logger.info(f"[ImageHandler] Moved {image_path} from {source_dir} to {dest_dir}")
            except Exception as e:
                logger.error(f"[ImageHandler] Error moving image {image_path}: {e}")

    def update_image_total(self):
        """Emit an event to update the image total based on the image list size."""
        if len(self.data_service.get_image_list()) > 0:
            self.event_bus.emit('update_image_total')

    def undo_last_action(self):
        """
        Undo the last action (either move or delete).
        """
        """Undo the last move or delete action."""
        if not self.data_service.get_sorted_images():
            logger.warning("[ImageHandler] No actions to undo.")
            return

        last_action = self.data_service.pop_sorted_images()
        action_type, image_path, *rest = last_action
        original_index = rest[-1]
        self.thread_manager.submit_task(self._undo_action_task, image_path, action_type, rest)
        self.add_image_to_list(image_path, original_index)
        self.data_service.set_current_index(original_index)
        return last_action

    def _undo_action_task(self, image_path, action_type, rest):
        """Task to undo the last action."""
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        if action_type == 'delete':
            source_dir = self.delete_folders.get(start_dir)
            dest_dir = start_dir
        elif action_type == 'move':
            category = rest[0]
            source_dir = self.dest_folders[start_dir].get(category)
            dest_dir = start_dir
        else:
            raise ImaegeteError(f"Action type {action_type} unrecognized")

        self._move_image_task(image_path, source_dir, dest_dir)

    def refresh_image_list(self, signal=None, shutdown_event=None):
        """
        Refresh the image list by scanning the directories for images.

        :param signal: A signal to emit when the refresh is complete.
        :type signal: Signal
        :param shutdown_event: Event to signal if the operation should be stopped.
        :type shutdown_event: Event
        """
        """Submit task to refresh the image list asynchronously and log the time taken."""
        if shutdown_event and shutdown_event.is_set():
            logger.info("[ImageHandler] Shutdown initiated, not starting new refresh task.")
            return

        self.is_refreshing.set()
        logger.debug("[ImageHandler] Submitting refresh image list task.")

        start_time = time.time()
        self.thread_manager.submit_task(self._refresh_image_list_task, signal, shutdown_event)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.debug(f"[ImageHandler] Time taken to submit the image list refresh task: {elapsed_time:.4f} seconds")

    def _refresh_image_list_task(self, signal=None, shutdown_event=None):
        """
        Refresh the image list by scanning the directories for images.

        :param signal: A signal to emit when the refresh is complete.
        :type signal: Signal
        :param shutdown_event: Event to signal if the operation should be stopped.
        :type shutdown_event: Event
        """
        """Task to refresh the image list with respect to shutdown events and log the time taken."""
        logger.debug("[ImageHandler] Starting image list refresh.")

        start_time = time.time()
        with self.lock:
            self.data_service.set_image_list([])

        def process_files_in_directory(directory):
            processed_images = self._process_files_in_directory(directory, shutdown_event, signal)
            if self.start_dirs.index(directory) == 0:
                self.start_dirs.remove(directory)
            return processed_images

        with ThreadPoolExecutor() as executor:
            
            futures = [executor.submit(process_files_in_directory, d) for d in self.start_dirs]

            try:
                
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"[ImageHandler] Error during image list refresh: {e}")
            finally:
                executor.shutdown(wait=False)

        if self.is_refreshing.is_set():
            self.is_refreshing.clear()
        logger.info(
            f"[ImageHandler] sending final emission with image list total {self.data_service.get_image_list_len()}")
        signal.emit()
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"[ImageHandler] Time taken to refresh image list: {elapsed_time:.4f} seconds")

    def _process_files_in_directory(self, directory, shutdown_event, signal):
        """Process image files in the directory with dynamic batch sizing and return the list of image paths."""
        batch_images = []
        initial_batch_size = 50  
        min_batch_size = 10
        max_batch_size = 1000
        batch_size = initial_batch_size
        target_batch_time = 0.1  

        for root, _, files in os.walk(directory):
            sorted_files = os_sorted(files)
            i = 0
            while i < len(sorted_files):
                start_time = time.time()
                batch_images.clear()
                batch_count = 0

                
                while batch_count < batch_size and i < len(sorted_files):
                    file = sorted_files[i]
                    i += 1

                    if self.is_image_file(file):
                        file_path = os.path.join(root, file)
                        batch_images.append(file_path)
                        batch_count += 1  
                    else:
                        continue

                    if shutdown_event.is_set():
                        logger.debug("[ImageHandler] Shutdown initiated, stopping after file processing.")
                        return batch_images  

                
                if batch_images and self.start_dirs[0] in directory:
                    with self.lock:
                        image_list = self.data_service.get_image_list()
                        if not image_list:
                            self.data_service.set_image_list(batch_images.copy())
                            self.data_service.set_current_index(0)
                        else:
                            image_list.extend(batch_images)
                            self.data_service.set_image_list(image_list)

                    if signal:
                        signal.emit()

                
                end_time = time.time()
                batch_processing_time = end_time - start_time

                
                if batch_processing_time < target_batch_time and batch_size < max_batch_size:
                    
                    batch_size = min(batch_size * 2, max_batch_size)
                elif batch_processing_time > target_batch_time and batch_size > min_batch_size:
                    
                    batch_size = max(batch_size // 2, min_batch_size)

                logger.debug(f"[ImageHandler] Batch size adjusted to: {batch_size}")

        
        return batch_images  

    def find_start_directory(self, image_path):
        """
        Find the start directory for the given image.

        :param image_path: The path to the image.
        :type image_path: str
        :return: The start directory corresponding to the image.
        :rtype: str
        """
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def is_image_file(self, filename):
        """
        Check if a given file is a valid image format.

        :param filename: The name of the file to check.
        :type filename: str
        :return: True if the file is a valid image format, False otherwise.
        :rtype: bool
        """
        """Check if the file is a valid image format."""
        valid_extensions = ['.webp', '.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def shutdown(self):
        self.data_service.cache_manager.shutdown()
