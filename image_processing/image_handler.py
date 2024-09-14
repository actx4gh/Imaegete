import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock, Event

import numpy as np
from natsort import os_sorted

from core import config, logger
from core.exceptions import ImageSorterError
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from image_processing.data_management.file_operations import move_image_and_cleanup


class ImageHandler:

    def __init__(self, thread_manager, data_service):
        self.thread_manager = thread_manager
        self.event_bus = create_or_get_shared_event_bus()
        self.data_service = data_service
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs
        self.shuffled_indices = []
        self.data_service.set_current_index(0)
        self.data_service.set_current_image_path(None)

        self.lock = RLock()
        self.is_refreshing = Event()

        self.data_service.set_image_list([])
        self.data_service.set_sorted_images([])

    def add_image_to_list(self, image_path, index=None):
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
        """Remove an image from the image list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if image_path in image_list:
                image_list.remove(image_path)
            self.data_service.set_image_list(image_list)

    def set_first_image(self):
        """Navigate to the first image (index 0) and update the data service."""
        with self.lock:
            if len(self.data_service.get_image_list()) > 0:
                self.set_current_image_by_index(0)

    def set_last_image(self):
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
        """Set the index to the next image in the list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                next_index = (self.data_service.get_current_index() + 1) % len(image_list)
                self.set_current_image_by_index(next_index)

    def set_previous_image(self):
        """Set the index to the previous image in the list."""
        with self.lock:
            image_list = self.data_service.get_image_list()
            if len(image_list) > 0:
                previous_index = (self.data_service.get_current_index() - 1) % len(image_list)
                self.set_current_image_by_index(previous_index)

    def set_current_image_by_index(self, index=None):
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
        """Check if a valid current image exists."""
        return bool(self.data_service.get_current_image_path())

    def prefetch_images(self, depth=3, max_prefetch=10):
        """Handle prefetching of images."""
        total_images = len(self.data_service.get_image_list())
        if total_images == 0:
            return

        prev_index = (self.data_service.get_current_index() + -1) % total_images
        next_index = (self.data_service.get_current_index() + 1) % total_images
        behind = np.arange(prev_index, prev_index - depth, -1) % total_images
        ahead = np.arange(next_index, next_index + depth) % total_images

        logger.debug(
            f"[ImageManager] Starting prefetch of indexes {list(behind)} and {list(ahead)} from index {self.data_service.get_current_index()} with a total of {total_images} images")

        prefetch_indices = [item for pair in zip(ahead, behind) for item in pair]

        if len(prefetch_indices) > max_prefetch:
            prefetch_indices = prefetch_indices[:max_prefetch]
            logger.warn(f"[ImageManager] Reduced number of prefetch items to max_prefetch {max_prefetch}")

        for index in prefetch_indices:
            image_path = self.data_service.get_image_path(index)
            if image_path:
                image = self.data_service.cache_manager.retrieve_image(image_path)
                if image:
                    logger.debug(f"[ImageManager] Skipping already cached image: {image_path}")
                else:
                    logger.info(f"[ImageManager] Prefetching uncached image: {image_path}")
                    # No need to set active_request=True here
                    self.data_service.cache_manager.retrieve_image(image_path)
                    self.data_service.cache_manager.get_metadata(image_path)

    def load_image_from_cache(self, image_path):
        logger.debug(f"Loading image from cache or disk: {image_path}")
        image = self.data_service.cache_manager.retrieve_image(image_path, active_request=True)
        return image

    def prefetch_images_if_needed(self):
        """Check if prefetching is needed and perform prefetching."""
        if not self.is_refreshing.is_set():
            self.prefetch_images()

    def delete_current_image(self):
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
            raise ImageSorterError(f"Action type {action_type} unrecognized")

        self._move_image_task(image_path, source_dir, dest_dir)

    def refresh_image_list(self, signal=None, shutdown_event=None):
        """Submit task to refresh the image list asynchronously and log the time taken."""
        if shutdown_event and shutdown_event.is_set():
            logger.info("[ImageHandler] Shutdown initiated, not starting new refresh task.")
            return

        logger.debug("[ImageHandler] Submitting refresh image list task.")

        start_time = time.time()
        self.thread_manager.submit_task(self._refresh_image_list_task, signal, shutdown_event)
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.debug(f"[ImageHandler] Time taken to submit the image list refresh task: {elapsed_time:.4f} seconds")

    def _refresh_image_list_task(self, signal=None, shutdown_event=None):
        """Task to refresh the image list with respect to shutdown events and log the time taken."""
        logger.debug("[ImageHandler] Starting image list refresh.")

        all_dirs = os_sorted(self.start_dirs)

        start_time = time.time()
        with self.lock:
            self.data_service.set_image_list([])

        def process_files_in_directory(directory):
            return self._process_files_in_directory(directory, shutdown_event, signal)

        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(process_files_in_directory, d): d for d in all_dirs}

            try:
                for future in as_completed(futures):
                    try:
                        image_files = future.result()
                        if image_files:
                            with self.lock:
                                image_list = self.data_service.get_image_list()
                                image_list.extend(image_files)
                                self.data_service.set_image_list(
                                    image_list)
                    except Exception as e:
                        logger.error(f"[ImageHandler] Error during image list refresh: {e}")

            finally:
                executor.shutdown(wait=False)

        self.is_refreshing.clear()
        signal.emit()
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"[ImageHandler] Time taken to refresh image list: {elapsed_time:.4f} seconds")

    def _process_files_in_directory(self, directory, shutdown_event, signal):
        """Process image files in the directory and return the list of image paths."""
        image_files = []
        local_files = []
        files_processed = 0
        batch_size = 5

        for root, _, files in os.walk(directory):
            for file in os_sorted(files):
                if self.is_image_file(file):
                    file_path = os.path.join(root, file)
                    local_files.append(file_path)
                    files_processed += 1

                if files_processed % 100 == 0:
                    batch_size = min(batch_size + 10, 100)

                if len(local_files) >= batch_size:
                    with self.lock:
                        image_list = self.data_service.get_image_list()
                        image_list.extend(local_files)
                        self.data_service.set_image_list(image_list)
                    local_files = []

                if shutdown_event.is_set():
                    logger.debug("[ImageHandler] Shutdown initiated, stopping after file processing.")
                    return image_files

                if files_processed % batch_size == 0 and signal:
                    signal.emit()

        if local_files:
            with self.lock:
                image_list = self.data_service.get_image_list()
                image_list.extend(local_files)
                self.data_service.set_image_list(image_list)

        if signal:
            signal.emit()

        return image_files

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def is_image_file(self, filename):
        """Check if the file is a valid image format."""
        valid_extensions = ['.webp', '.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def shutdown(self):
        self.data_service.cache_manager.shutdown()
