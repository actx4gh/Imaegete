import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from natsort import os_sorted

from core import config, logger
from core.exceptions import ImaegeteError
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from image_processing.data_management.file_operations import move_image_and_cleanup


class ImageHandler:
    """
    A class to manage image handling operations, including image list management,
    prefetching, moving, and deleting images.
    """

    def __init__(self, thread_manager, data_service):
        """
        Initialize the ImageHandler with a thread manager and data service.

        Sets up necessary components such as event bus, destination folders,
        and image list management.

        :param thread_manager: The thread manager for handling asynchronous tasks.
        :param data_service: The service responsible for managing image data.
        """
        self.thread_manager = thread_manager
        self.event_bus = create_or_get_shared_event_bus()
        self.data_service = data_service
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self._start_dirs = []
        self.shuffled_indices = []

        self.lock = threading.RLock()
        self.is_refreshing = threading.Event()
        self.image_list_open_condition = threading.Condition(self.lock)

        self.data_service.set_image_list([])
        self.data_service.set_sorted_images([])

    @property
    def start_dirs(self):
        """
        Get the list of start directories, sorted if not already cached.

        :return: A sorted list of start directories.
        :rtype: list
        """
        if not self._start_dirs:
            self._start_dirs = os_sorted(config.start_dirs)
        return self._start_dirs

    def add_image_to_list(self, image_path, index=None):
        """
        Add a new image to the image list at the specified index or at the end.

        :param str image_path: Path to the image file.
        :param int index: The position to insert the image. If None, append to the end.
        """
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

        :param str image_path: Path to the image file to be removed.
        """
        with self.lock:
            image_list = self.data_service.get_image_list()
            if image_path in image_list:
                image_list.remove(image_path)
            self.data_service.set_image_list(image_list)

    def set_first_image(self):
        """
        Set the first image in the list as the current image.
        """
        with self.lock:
            if len(self.data_service.get_image_list()) > 0:
                self.set_current_image_by_index(0)

    def set_last_image(self):
        """
        Set the last image in the list as the current image.
        """
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                last_index = len(image_list) - 1
                self.set_current_image_by_index(last_index)

    def pop_image(self):
        """
        Pop an image from the current index in the image list.

        Removes the image at the current index from the image list and updates the current index accordingly.

        :return: A tuple containing the original index of the image and the image path.
        :rtype: tuple(int, str)
        """
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
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                next_index = (self.data_service.get_current_index() + 1) % len(image_list)
                self.set_current_image_by_index(next_index)

    def set_previous_image(self):
        """
        Set the previous image in the list as the current image.
        """
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                previous_index = (self.data_service.get_current_index() - 1) % len(image_list)
                self.set_current_image_by_index(previous_index)

    def set_current_image_by_index(self, index=None):
        """
        Set the image at the specified index as the current image.

        If an index is provided, the image at that position is set as the current image. If no index is provided,
        the current index is set to 0 if not already set. Returns the path of the current image if available.

        :param int index: The position to set the current image. If None, the index defaults to 0 if not already set.
        :return: The path of the current image, or None if no image is set.
        :rtype: str or None
        """
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
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                if not hasattr(self, 'shuffled_indices') or not self.shuffled_indices:
                    self.shuffled_indices = list(range(len(image_list)))
                    random.shuffle(self.shuffled_indices)
                    logger.info("[ImageHandler] shuffling the list.")

                random_index = self.shuffled_indices.pop(0)
                self.set_current_image_by_index(random_index)

    def has_current_image(self):
        """
        Check if there is a valid current image.

        :return: True if there is a current image, False otherwise.
        :rtype: bool
        """
        return bool(self.data_service.get_current_image_path())

    def prefetch_images(self, depth=3, max_prefetch=10):
        """
        Prefetch images around the current image for faster loading.

        :param int depth: Number of images ahead and behind the current image to prefetch.
        :param int max_prefetch: Maximum number of images to prefetch.
        """
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
                    logger.debug(f"[ImageHandler] Skipping already cached image: {image_path}")
                else:
                    logger.debug(f"[ImageHandler] Prefetching uncached image: {image_path}")

                    self.data_service.cache_manager.retrieve_image(image_path)
                    self.data_service.cache_manager.get_metadata(image_path)

    def load_image_from_cache(self, image_path):
        """
        Load an image from the cache or disk.

        Attempts to retrieve the image from the cache. If the image is not cached, it will load it from disk.

        :param str image_path: The path to the image to load.
        :return: The loaded image.
        :rtype: object
        """
        logger.debug(f"[ImageHandler] Loading image from cache or disk: {image_path}")
        image = self.data_service.cache_manager.retrieve_image(image_path, active_request=True)
        return image

    def prefetch_images_if_needed(self):
        """
        Prefetch images around the current image for faster loading.
        """
        if not self.is_refreshing.is_set():
            self.prefetch_images()

    def delete_current_image(self):
        """
        Delete the current image by moving it to the delete folder and removing it from the list.
        """

        original_index, image_path = self.pop_image()
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        delete_folder = self.delete_folders.get(start_dir)
        if delete_folder:
            self.thread_manager.submit_task(self._move_image_task, image_path, start_dir, delete_folder)
        else:
            logger.error(f"[ImageHandler] Delete folder not configured for start directory {start_dir}")
        self.data_service.append_sorted_images(('delete', image_path, original_index))

    def move_current_image(self, category):
        """
        Move the current image to a specific category folder.

        :param str category: The category to move the image to.
        """
        original_index, image_path = self.pop_image()
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        dest_folder = self.dest_folders[start_dir].get(category)
        if not dest_folder:
            logger.error(
                f"[ImageHandler] Destination folder not found for category {category} in directory {start_dir}")
            return

        self.thread_manager.submit_task(self._move_image_task, image_path, start_dir, dest_folder)
        self.data_service.append_sorted_images(('move', image_path, category, original_index))

    def _move_image_task(self, image_path, source_dir, dest_dir):
        """
        Move an image from the source directory to the destination directory.

        This method handles moving an image file and cleaning up the source directory after the move.
        If an error occurs during the move, it logs the error.

        :param str image_path: The path to the image to be moved.
        :param str source_dir: The directory from which the image is being moved.
        :param str dest_dir: The directory to which the image is being moved.
        """
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
        Undo the last move or delete action.

        This method retrieves the most recent action (either a move or delete) from the sorted images list
        and reverses it. The image is restored to its original state, and the current index is updated accordingly.

        :return: A tuple representing the last undone action, including the action type, image path, and additional details.
        :rtype: tuple or None
        """
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
        """
        Task to undo the last action on an image.

        Depending on the action type ('delete' or 'move'), it restores the image to its original location.

        :param str image_path: The path of the image to undo the action for.
        :param str action_type: The type of action to undo ('delete' or 'move').
        :param list rest: Additional information required for the undo operation (e.g., category).
        :raises ImaegeteError: If the action type is unrecognized.
        """
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

        :param Signal signal: A signal to emit when the refresh is complete.
        :param Event shutdown_event: Event to signal if the operation should be stopped.
        """
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

        :param Signal signal: A signal to emit when the refresh is complete.
        :param Event shutdown_event: Event to signal if the operation should be stopped.
        """
        logger.debug("[ImageHandler] Starting image list refresh.")

        start_time = time.time()
        with self.lock:
            self.data_service.set_image_list([])

        def process_files_in_directory(directory):
            thread_id = threading.get_ident()
            logger.debug(f'[ImageHandler thread {thread_id}] processing {directory}')
            folders_to_skip = []

            # For self.dest_folders, extract the subfolder paths for each start_dir
            for start_dir, subfolders in self.dest_folders.items():
                if os.path.normpath(start_dir) == os.path.normpath(directory):
                    # Add each subfolder path to the skip list
                    folders_to_skip.extend(subfolders.values())

            # For self.delete_folders, extract the folder paths directly
            for start_dir, delete_folder in self.delete_folders.items():
                if os.path.normpath(start_dir) == os.path.normpath(directory):
                    # Add the delete folder to the skip list
                    folders_to_skip.append(delete_folder)
            logger.debug(f'[ImageHandler thread {thread_id}] skipping {folders_to_skip}')
            processed_images = self._process_files_in_directory(directory, shutdown_event, signal,
                                                                folders_to_skip=folders_to_skip)
            if self.start_dirs.index(directory) == 0:
                with self.image_list_open_condition:
                    self.start_dirs.remove(directory)
                    self.image_list_open_condition.notify_all()
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
        logger.debug(
            f"[ImageHandler] sending final emission with image list total {self.data_service.get_image_list_len()}")
        signal.emit()
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"[ImageHandler] Time taken to refresh image list: {elapsed_time:.4f} seconds")

    def _process_files_in_directory(self, directory, shutdown_event, signal, folders_to_skip):
        """
        Process image files in the given directory with dynamic batch sizing.

        Walks through the directory, processes images in batches, and adjusts batch size based on processing time.
        Skips directories in `folders_to_skip` and handles a shutdown event if triggered.

        :param str directory: Directory path to process.
        :param threading.Event shutdown_event: Event to signal when to stop processing.
        :param signal: Signal object to emit when a batch is processed.
        :param list folders_to_skip: List of directories to skip.
        :return: List of processed image file paths.
        :rtype: list
        """
        batch_images = []
        initial_batch_size = 50
        min_batch_size = 10
        max_batch_size = 1000
        batch_size = initial_batch_size
        target_batch_time = 0.1

        for root, _, files in os.walk(directory):
            if os.path.normpath(root) in map(os.path.normpath, folders_to_skip):
                logger.debug(f"[ImageHandler] Skipping directory: {root}")
                continue  # Skip this directory

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

                # This is where the execution needs to wait if this directory isn't the first in start_dirs
                with self.image_list_open_condition:
                    while batch_images and self.start_dirs[0] != directory:
                        logger.debug(f"Thread {threading.get_ident()} waiting to add images from {directory}")
                        self.image_list_open_condition.wait()  # Wait for a signal that the directory is first

                # Process the batch when it's eligible
                if batch_images and self.start_dirs[0] == directory:
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

    #
    #    def _process_files_in_directory(self, directory, shutdown_event, signal, folders_to_skip):
    #        """
    #        Process image files in the given directory with dynamic batch sizing.
    #
    #        Walks through the directory, processes images in batches, and adjusts batch size based on processing time.
    #        Skips directories in `folders_to_skip` and handles a shutdown event if triggered.
    #
    #        :param str directory: Directory path to process.
    #        :param threading.Event shutdown_event: Event to signal when to stop processing.
    #        :param signal: Signal object to emit when a batch is processed.
    #        :param list folders_to_skip: List of directories to skip.
    #        :return: List of processed image file paths.
    #        :rtype: list
    #        """
    #        batch_images = []
    #        initial_batch_size = 50
    #        min_batch_size = 10
    #        max_batch_size = 1000
    #        batch_size = initial_batch_size
    #        target_batch_time = 0.1
    #
    #        for root, _, files in os.walk(directory):
    #            if os.path.normpath(root) in map(os.path.normpath, folders_to_skip):
    #                logger.debug(f"[ImageHandler] Skipping directory: {root}")
    #                continue  # Skip this directory
    #            sorted_files = os_sorted(files)
    #            i = 0
    #            while i < len(sorted_files):
    #                start_time = time.time()
    #                batch_images.clear()
    #                batch_count = 0
    #
    #                while batch_count < batch_size and i < len(sorted_files):
    #                    file = sorted_files[i]
    #                    i += 1
    #
    #                    if self.is_image_file(file):
    #                        file_path = os.path.join(root, file)
    #                        batch_images.append(file_path)
    #                        batch_count += 1
    #                    else:
    #                        continue
    #
    #                    if shutdown_event.is_set():
    #                        logger.debug("[ImageHandler] Shutdown initiated, stopping after file processing.")
    #                        return batch_images
    #
    #                if batch_images and self.start_dirs[0] in directory:
    #                    with self.lock:
    #                        image_list = self.data_service.get_image_list()
    #                        if not image_list:
    #                            self.data_service.set_image_list(batch_images.copy())
    #                            self.data_service.set_current_index(0)
    #                        else:
    #                            image_list.extend(batch_images)
    #                            self.data_service.set_image_list(image_list)
    #
    #                    if signal:
    #                        signal.emit()
    #
    #                end_time = time.time()
    #                batch_processing_time = end_time - start_time
    #
    #                if batch_processing_time < target_batch_time and batch_size < max_batch_size:
    #
    #                    batch_size = min(batch_size * 2, max_batch_size)
    #                elif batch_processing_time > target_batch_time and batch_size > min_batch_size:
    #
    #                    batch_size = max(batch_size // 2, min_batch_size)
    #
    #                logger.debug(f"[ImageHandler] Batch size adjusted to: {batch_size}")
    #
    #        return batch_images

    def find_start_directory(self, image_path):
        """
        Find the start directory for the given image.

        :param str image_path: The path to the image.
        :return: The start directory corresponding to the image.
        :rtype: str
        """
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def is_image_file(self, filename):
        """
        Check if a given file is a valid image format.

        :param str filename: The name of the file to check.
        :return: True if the file is a valid image format, False otherwise.
        :rtype: bool
        """
        valid_extensions = ['.webp', '.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def shutdown(self):
        """
        Shut down the cache manager.

        This method triggers the shutdown process for the cache manager to release resources and stop any ongoing operations.
        """

        self.data_service.cache_manager.shutdown()
