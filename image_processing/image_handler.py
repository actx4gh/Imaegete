import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock, Event

from natsort import os_sorted
from core import config, logger
from core.exceptions import ImageSorterError
from .file_operations import move_related_files, check_and_remove_empty_dir


class ImageHandler:
    def __init__(self, thread_manager, data_service):
        self.thread_manager = thread_manager
        self.data_service = data_service  # Use the data service for shared state
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs

        self.lock = RLock()
        self.is_refreshing = Event()
        # Initialize the image list in the data service
        self.data_service.set_image_list([])  # Initialize empty image list

    def add_image_to_list(self, image_path, index=None):
        """Add a new image to the image list at the specified index or at the end."""
        image_list = self.data_service.get_image_list()  # Get the image list from the data service
        if self.is_image_file(image_path) and image_path not in image_list:
            with self.lock:
                if index is not None:
                    image_list.insert(index, image_path)
                else:
                    image_list.append(image_path)
            self.data_service.set_image_list(image_list)  # Update the image list in the data service

    def remove_image_from_list(self, image_path):
        """Remove an image from the image list."""
        with self.lock:
            image_list = self.data_service.get_image_list()  # Get the image list from the data service
            if image_path in image_list:
                image_list.remove(image_path)
            self.data_service.set_image_list(image_list)  # Update the image list in the data service

    def delete_image(self, image_path):
        """Move image to the delete folder and remove from the list."""
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

    def move_image(self, image_path, category):
        """Move an image to the specified category folder asynchronously."""
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        logger.info(f"[ImageHandler] Moving image: {image_path}")

        dest_folder = self.dest_folders[start_dir].get(category)
        if not dest_folder:
            logger.error(f"[ImageHandler] Destination folder not found for category {category} in directory {start_dir}")
            return

        self.thread_manager.submit_task(self._move_image_task, image_path, start_dir, dest_folder)

    def _move_image_task(self, image_path, source_dir, dest_dir):
        with self.lock:
            try:
                move_related_files(image_path, source_dir, dest_dir)
                check_and_remove_empty_dir(source_dir)
                logger.info(f"[ImageHandler] Moved {image_path} from {source_dir} to {dest_dir}")
            except Exception as e:
                logger.error(f"[ImageHandler] Error moving image {image_path}: {e}")

    def undo_last_action(self):
        """Undo the last move or delete action."""
        if not self.data_service.sorted_images:
            logger.warning("[ImageHandler] No actions to undo.")
            return

        last_action = self.data_service.sorted_images.pop()
        action_type, image_path, *rest = last_action
        self.thread_manager.submit_task(self._undo_action_task, image_path, action_type, rest)

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

        logger.info("[ImageHandler] Submitting refresh image list task.")

        start_time = time.time()  # Start the timer
        self.thread_manager.submit_task(self._refresh_image_list_task, signal, shutdown_event)
        end_time = time.time()  # End the timer after the task is submitted
        elapsed_time = end_time - start_time
        logger.info(f"[ImageHandler] Time taken to submit the image list refresh task: {elapsed_time:.4f} seconds")

    def _refresh_image_list_task(self, signal=None, shutdown_event=None):
        """Task to refresh the image list with respect to shutdown events and log the time taken."""
        logger.debug("[ImageHandler] Starting image list refresh.")

        all_dirs = os_sorted(self.start_dirs)

        start_time = time.time()  # Start the timer
        with self.lock:
            self.data_service.set_image_list([])  # Clear the image list in the data service

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
                                image_list = self.data_service.get_image_list()  # Get the current image list
                                image_list.extend(image_files)
                                self.data_service.set_image_list(image_list)  # Update the image list in the data service
                    except Exception as e:
                        logger.error(f"[ImageHandler] Error during image list refresh: {e}")

            finally:
                executor.shutdown(wait=False)

        self.is_refreshing.clear()
        signal.emit()
        end_time = time.time()  # End the timer after refreshing the list
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
                        image_list = self.data_service.get_image_list()  # Get the image list
                        image_list.extend(local_files)
                        self.data_service.set_image_list(image_list)  # Update image list in data service
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

    def shutdown(self):
        """Handle shutdown for ImageHandler."""
        logger.info("[ImageHandler] Initiating shutdown.")
        self.thread_manager.shutdown(wait=False)

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def is_image_file(self, filename):
        """Check if the file is a valid image format."""
        valid_extensions = ['.webp', '.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)


