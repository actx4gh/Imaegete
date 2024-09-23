import os
import random
import time

import numpy as np
from PyQt6.QtCore import QObject, QMutexLocker, QRecursiveMutex, QMutex, QWaitCondition, QThread
from natsort import os_sorted

from core import config, logger
from core.exceptions import ImaegeteError
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from image_processing.data_management.file_operations import move_image_and_cleanup, is_image_file


class ImageHandler(QObject):
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
        super().__init__()
        self.thread_manager = thread_manager
        self.event_bus = create_or_get_shared_event_bus()
        self.data_service = data_service
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self._start_dirs = []
        self._shuffled_indices = []

        self.lock = QRecursiveMutex()
        self.is_refreshing = False
        self.image_list_open_condition = QWaitCondition()

        self.data_service.set_image_list([])
        self.data_service.set_sorted_images([])
        self.prefetched_random_images = []

        self.shutdown_flag = False
        self.shutdown_mutex = QMutex()

    def prefetch_random_images(self, prefetch_num=3):
        """
        Prefetch up to a specified number of random images, but ensures that the total number
        of prefetched images never exceeds the prefetch_num limit.

        :param int prefetch_num: The maximum number of images to prefetch (default is 3).
        """
        with QMutexLocker(self.lock):
            # Only prefetch if the total prefetched images is less than prefetch_num
            while len(self.prefetched_random_images) < prefetch_num:
                if self.data_service.get_image_list_len() <= prefetch_num:
                    logger.debug('[ImageHandler] Not enough images in the list to prefetch.')
                    break

                available_indices = list(set(self.shuffled_indices) - set(self.prefetched_random_images))
                if not available_indices:
                    logger.debug('[ImageHandler] No available indices to prefetch.')
                    break

                # Prefetch a random image and add it to the prefetched list
                random_index = random.choice(available_indices)
                self.prefetched_random_images.append(random_index)
                image_path = self.data_service.get_image_path(random_index)

                self._retrieve_image_data(image_path)

        logger.debug(f'[ImageHandler] Prefetched random image indexes: {self.prefetched_random_images[:prefetch_num]}')

    def _retrieve_image_data(self, image_path):
        """
        Retrieve the image data from cache and its metadata. This is a helper function
        to separate out the image fetching and metadata retrieval logic.

        :param str image_path: The path to the image to be prefetched.
        """
        self.data_service.cache_manager.retrieve_image(image_path)
        self.data_service.cache_manager.get_metadata(image_path)

    @property
    def start_dirs(self):
        """
        Get the list of start directories, sorted if not already cached.

        :return: A sorted list of start directories.
        :rtype: list
        """
        with QMutexLocker(self.lock):
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
        if is_image_file(image_path) and image_path not in image_list:
            with QMutexLocker(self.lock):
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
        with QMutexLocker(self.lock):
            image_list = self.data_service.get_image_list()
            if image_path in image_list:
                image_list.remove(image_path)
            self.data_service.set_image_list(image_list)

    def set_first_image(self):
        """
        Set the first image in the list as the current image.
        """
        with QMutexLocker(self.lock):
            if len(self.data_service.get_image_list()) > 0:
                self.set_current_image_by_index(0)

    def set_last_image(self):
        """
        Set the last image in the list as the current image.
        """
        with QMutexLocker(self.lock):
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
        with QMutexLocker(self.lock):
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
        with QMutexLocker(self.lock):
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                next_index = (self.data_service.get_current_index() + 1) % len(image_list)
                self.set_current_image_by_index(next_index)

    def set_previous_image(self):
        """
        Set the previous image in the list as the current image.
        """
        with QMutexLocker(self.lock):
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                previous_index = (self.data_service.get_current_index() - 1) % len(image_list)
                self.set_current_image_by_index(previous_index)

    def set_current_image_by_index(self, index=None):
        """
        Sets the image at the specified index as the current image.

        If you provide an index, the image at that position becomes the current image. If you do not provide an index and the current index is not already set, it defaults to 0. Returns the path of the current image if available.

        :param int index: The position to set as the current image. If None, defaults to 0 if not already set.
        :return: The path of the current image, or None if no image is set.
        :rtype: str or None
        """
        with QMutexLocker(self.lock):

            if index is not None:
                self.data_service.set_current_index(index)
            elif not isinstance(self.data_service.get_current_index(), int):

                self.data_service.set_current_index(0)

            image_path = self.data_service.get_current_image_path()

            if image_path:
                self.data_service.set_current_image_path(image_path)
                return image_path

            return None

    @property
    def shuffled_indices(self):
        if not self._shuffled_indices:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                self._shuffled_indices = list(range(len(image_list)))
                random.shuffle(self._shuffled_indices)
                logger.info("[ImageHandler] Initializing the shuffled list.")
        return self._shuffled_indices

    def set_random_image(self):
        """
        Set a random image from the list. If prefetched random images exist, use the first one.
        Otherwise, use the original random image selection logic.
        """
        with QMutexLocker(self.lock):
            if self.prefetched_random_images:
                random_index = self.prefetched_random_images.pop(0)
                logger.debug(f'[ImageHandler] Setting index to prefetched random image {random_index}')
                self.set_current_image_by_index(random_index)
            else:
                image_list = self.data_service.get_image_list()
                if len(image_list) > 0:
                    random_index = self.shuffled_indices.pop(0)
                    logger.debug(f'[ImageHandler] Setting index to non-prefetched random image {random_index}')
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
                if self.data_service.cache_manager.is_cached(image_path):
                    logger.debug(f"[ImageHandler] Skipping already cached image: {image_path}")
                else:
                    logger.debug(f"[ImageHandler] Prefetching uncached image: {image_path}")

                    self.data_service.cache_manager.retrieve_image(image_path)
                    self.data_service.cache_manager.get_metadata(image_path)

    def load_image_from_cache(self, image_path, background=True):
        """
        Load an image from the cache or disk.

        Attempts to retrieve the image from the cache. If the image is not cached, it will load it from disk.

        :param str image_path: The path to the image to load.
        :return: The loaded image.
        :rtype: object
        """
        logger.debug(f"[ImageHandler] Loading image from cache or disk: {image_path}")
        image = self.data_service.cache_manager.retrieve_image(image_path, active_request=True, background=background)
        return image

    def prefetch_images_if_needed(self):
        """
        Prefetch images around the current image for faster loading.
        """
        with QMutexLocker(self.lock):
            should_prefetch = not self.is_refreshing

        if should_prefetch:
            self.prefetch_images()
            self.prefetch_random_images()

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
            self.thread_manager.submit_task(self._move_image_task, image_path=image_path, source_dir=start_dir,
                                            dest_dir=delete_folder)
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

        self.thread_manager.submit_task(self._move_image_task, image_path=image_path, source_dir=start_dir,
                                        dest_dir=dest_folder)
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
        try:
            # No need to hold the lock here
            self.data_service.cache_manager.shutdown_watchdog()
            move_image_and_cleanup(image_path, source_dir, dest_dir)
            self.data_service.cache_manager.initialize_watchdog()
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
        self.thread_manager.submit_task(self._move_image_task, image_path=image_path, action_type=action_type,
                                        rest=rest)
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

    def refresh_image_list(self, signal=None):
        """
        Refresh the image list by scanning the directories for images.

        :param Signal signal: A signal to emit when the refresh is complete.
        """
        if self.is_shutdown():
            logger.info("[ImageHandler] Shutdown initiated, not starting new refresh task.")
            return
        with QMutexLocker(self.lock):
            self.is_refreshing = True
        logger.debug("[ImageHandler] Submitting refresh image list task.")

        self.thread_manager.submit_task(self._refresh_image_list_task, signal=signal)

    def _refresh_image_list_task(self, signal=None):
        """
        Refresh the image list by scanning the directories for images.

        :param Signal signal: A signal to emit when the refresh is complete.
        """
        thread_id = int(QThread.currentThreadId())
        logger.info(f"[ImageHandler refresh_image_list_task thread {thread_id}] Starting image list refresh.")

        with QMutexLocker(self.lock):
            if self.is_shutdown():
                logger.debug(
                    f"[ImageHandler thread {thread_id}] Shutdown initiated, stopping batch processing before taking any steps.")
                return
            self.data_service.set_image_list([])

        def process_files_in_directory(directory):
            thread_id = int(QThread.currentThreadId())
            logger.info(f'[ImageHandler process_files_in_directory thread {thread_id}] processing {directory}')
            try:
                folders_to_skip = []

                for start_dir, subfolders in self.dest_folders.items():
                    if os.path.normpath(start_dir) == os.path.normpath(directory):
                        folders_to_skip.extend(subfolders.values())

                for start_dir, delete_folder in self.delete_folders.items():
                    if self.is_shutdown():
                        logger.debug(
                            f"[ImageHandler thread {thread_id}] Shutdown initiated, stopping batch processing while generating skip folders.")
                        return
                    if os.path.normpath(start_dir) == os.path.normpath(directory):
                        folders_to_skip.append(delete_folder)
                logger.debug(f'[ImageHandler thread {thread_id}] skipping {folders_to_skip}')
                self._process_files_in_directory(directory, signal=signal,
                                                 folders_to_skip=folders_to_skip, thread_id=thread_id)
                with QMutexLocker(self.lock):
                    if directory in self._start_dirs:
                        self._start_dirs.remove(directory)
                        self.image_list_open_condition.wakeAll()
                logger.info(
                    f'[ImageHandler process_files_in_directory thread {thread_id}] Completed processing {directory}')
            except Exception as e:
                logger.error(f"[ImageHandler thread {thread_id}] Error processing directory {directory}: {e}")

        with QMutexLocker(self.lock):
            dirs_to_process = self.start_dirs.copy()
        for d in dirs_to_process:
            if self.is_shutdown():
                logger.debug(
                    f"[ImageHandler thread {thread_id}] Shutdown initiated, stopping batch processing before submitting tasks.")
                return
            logger.debug(f'[ImageHandler thread {thread_id}] spawning new thread to process directory {d}')
            self.thread_manager.submit_task(process_files_in_directory, directory=d, tag="refresh_image_list",
                                            on_finished=self.thread_manager.task_finished_callback)

        # Wait for all tasks to complete
        logger.info(
            f"[ImageHandler thread {thread_id}] Active threads before waitForDone: {self.thread_manager.thread_pool.activeThreadCount()}")
        # Waiting for all "refresh_image_list" tagged tasks to complete
        self.thread_manager.wait_for_tagged_tasks("refresh_image_list")
        logger.info(
            f"[ImageHandler thread {thread_id}] Active threads after waitForDone: {self.thread_manager.thread_pool.activeThreadCount()}")

        with QMutexLocker(self.lock):
            self.is_refreshing = False

        if self.is_shutdown():
            logger.debug(
                f"[ImageHandler thread {thread_id}] Shutdown initiated, stopping batch processing prior to final emission.")
            return
        logger.debug(
            f"[ImageHandler thread {thread_id}] sending final emission with image list total {self.data_service.get_image_list_len()}")
        if signal:
            signal.emit()
        logger.info(f"[ImageHandler refresh_image_list_task thread {thread_id}] completed image list refresh.")

    def _process_files_in_directory(self, directory, signal, folders_to_skip, thread_id=""):
        """
        Process image files in the given directory with dynamic batch sizing.

        Walks through the directory, processes images in batches, and adjusts batch size based on processing time.
        Skips directories in `folders_to_skip` and handles a shutdown event if triggered.

        :param str directory: Directory path to process.
        :param signal: Signal object to emit when a batch is processed.
        :param list folders_to_skip: List of directories to skip.
        """
        if not thread_id:
            thread_id = int(QThread.currentThreadId())
        try:
            batch_images = []
            initial_batch_size = 50
            min_batch_size = 10
            max_batch_size = 1000
            batch_size = initial_batch_size
            target_batch_time = 0.1
            logger.info(f"[ImageHandler thread {thread_id}] About to process {directory}.")

            for root, _, files in os.walk(directory):
                if self.is_shutdown():
                    logger.debug(
                        f"[ImageHandler thread {thread_id}] Shutdown initiated, stopping batch processing while about to process {root}.")
                    return
                if os.path.normpath(root) in map(os.path.normpath, folders_to_skip):
                    logger.debug(f"[ImageHandler thread {thread_id}] Skipping directory: {root}")
                    continue

                sorted_files = os_sorted(files)
                i = 0

                while i < len(sorted_files) and not self.is_shutdown():
                    start_time = time.time()
                    batch_images.clear()
                    batch_count = 0

                    while batch_count < batch_size and i < len(sorted_files) and not self.is_shutdown():
                        file = sorted_files[i]
                        i += 1

                        file_path = os.path.join(root, file)
                        if is_image_file(file_path):
                            batch_images.append(file_path)
                            batch_count += 1
                        else:
                            continue
                    with QMutexLocker(self.lock):
                        if self.is_shutdown():
                            logger.debug(f"[ImageHandler thread {thread_id}] Shutdown during image list open condition")
                            return
                        while batch_images and self.start_dirs and directory not in self.start_dirs and not self.is_shutdown():
                            logger.debug(f"[ImageHandler thread {thread_id}] Waiting to add images from {directory}")
                            self.image_list_open_condition.wait(self.lock, 100)  # Wait for 100ms

                    if self.is_shutdown():
                        logger.debug(
                            f"[ImageHandler thread {thread_id}] Shutdown during file processing in {directory}")
                        return
                    with QMutexLocker(self.lock):
                        if batch_images and self.start_dirs[0] == directory:
                            if self.is_shutdown():
                                logger.debug(
                                    f"[ImageHandler thread {thread_id}] Shutdown before extending image list during file processing")
                                return
                            image_list = self.data_service.get_image_list()
                            if not image_list:
                                self.data_service.set_image_list(batch_images.copy())
                                self.data_service.set_current_index(0)
                            else:
                                image_list.extend(batch_images)
                                self.data_service.set_image_list(image_list)

                            if self.is_shutdown():
                                logger.debug(
                                    f"[ImageHandler thread {thread_id}] Shutdown before emitting signal during file processing")
                                return
                    if signal:
                        logger.debug(
                            f"[ImageHandler thread {thread_id}] emitting signal during file processing for {directory}")
                        signal.emit()

                    end_time = time.time()
                    batch_processing_time = end_time - start_time

                    if batch_processing_time < target_batch_time and batch_size < max_batch_size:
                        batch_size = min(batch_size * 2, max_batch_size)
                    elif batch_processing_time > target_batch_time and batch_size > min_batch_size:
                        batch_size = max(batch_size // 2, min_batch_size)

                    logger.debug(f"[ImageHandler thread {thread_id}] Batch size adjusted to: {batch_size}")
                    logger.info(f"[ImageHandler thread {thread_id}] Completed processing {directory}")

        except Exception as e:
            logger.error(f"[ImageHandler thread {thread_id}] Error processing files in directory {directory}: {e}")

    def find_start_directory(self, image_path):
        """
        Find the start directory for the given image.

        :param str image_path: The path to the image.
        :return: The start directory corresponding to the image.
        :rtype: str
        """
        with QMutexLocker(self.lock):
            return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))),
                        None)

    def shutdown(self):
        logger.info("[ImageHandler] Shutdown in progress, lock released")
        self.set_shutdown()
        with QMutexLocker(self.lock):
            logger.debug("[ImageHandler] Notifying all threads waiting on image_list_open_condition condition.")
            self.image_list_open_condition.wakeAll()

        self.data_service.cache_manager.shutdown()

        logger.info("[ImageHandler] Shutdown complete.")

    def set_shutdown(self):
        with QMutexLocker(self.shutdown_mutex):
            self.shutdown_flag = True

    def is_shutdown(self):
        with QMutexLocker(self.shutdown_mutex):
            return self.shutdown_flag
