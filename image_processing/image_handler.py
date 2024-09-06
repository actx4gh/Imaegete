import os
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtBoundSignal
from natsort import os_sorted

import config
import logger
from exceptions import ImageSorterError
from .file_operations import move_related_files, check_and_remove_empty_dir, list_all_directories_concurrent


class MoveFileWorker(QThread):
    def __init__(self, image_path, source_dir, dest_dir, callback=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.source_dir = source_dir
        self.dest_dir = dest_dir
        self.callback = callback  # Optional callback function to call after work is done
        self.thread_id = QThread.currentThreadId()
        # self.thread_memory_address = id(QThread.currentThread())

    # Inside MoveFileWorker class in image_handler.py

    def run(self):
        logger.info(
            f"[MoveFileWorker {self.thread_id}] thread started for moving from {self.source_dir} to {self.dest_dir}")
        try:
            move_related_files(self.image_path, self.source_dir, self.dest_dir)
            logger.info(f"[MoveFileWorker {self.thread_id}]Finished moving files for {self.image_path}")
            check_and_remove_empty_dir(self.dest_dir)
            logger.info(
                f"[MoveFileWorker {self.thread_id}] Checked and removed empty directory if necessary: {self.dest_dir}")
            logger.info(f"[MoveFileWorker {self.thread_id}] Moved file from {self.source_dir} to {self.dest_dir}")
        except Exception as e:
            logger.error(f"[MoveFileWorker {self.thread_id}] Error in MoveFileWorker: {e}")

        if self.callback:
            try:
                self.callback()  # Execute callback if provided
                logger.debug(f"[MoveFileWorker {self.thread_id}] Callback executed successfully.")
            except Exception as e:
                logger.error(f"[MoveFileWorker {self.thread_id}] Error executing callback in MoveFileWorker: {e}")


class ImageHandler:
    def __init__(self):
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs
        self.image_list = []
        self.sorted_images = []
        self.lock = RLock()

    def add_image_to_list(self, image_path, index=None):
        """Add a new image to the image list at the specified index or at the end."""
        if self.is_image_file(image_path) and image_path not in self.image_list:
            with self.lock:
                if index is not None:
                    self.image_list.insert(index, image_path)
                else:
                    self.image_list.append(image_path)

    def remove_image_from_list(self, image_path):
        """Remove an image from the image list."""
        if image_path in self.image_list:
            with self.lock:
                self.image_list.remove(image_path)

    # In image_handler.py

    def delete_image(self, image_path, original_index):
        """Move image to the delete folder without removing it from the cache."""
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return

        logger.info(f"[ImageHandler] Deleting image: {image_path}")

        delete_folder = self.delete_folders.get(start_dir)
        if not delete_folder:
            logger.error(f"[ImageHandler] No delete folder found for directory {start_dir}")
            return

        with self.lock:
            self.sorted_images.append(('delete', image_path, original_index))
            self.image_list.pop(original_index)

        # Start delete operation in a background thread
        self.worker = MoveFileWorker(image_path, os.path.dirname(image_path), delete_folder)
        self.worker.start()

        logger.info(f"[ImageHandler] Deleted image: {image_path}")

    def move_image(self, image_path, category, original_index):
        """Move image to the specified category folder without removing it from the cache."""
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

        with self.lock:
            self.sorted_images.append(('move', image_path, category, original_index))
            self.image_list.pop(original_index)

        # Start move operation in a background thread
        self.worker = MoveFileWorker(image_path, os.path.dirname(image_path), dest_folder)
        self.worker.start()

        logger.info(f"[ImageHandler] Moved image: {image_path} to category {category}")

    def undo_last_action(self):
        if not self.sorted_images:
            logger.warning("[ImageHandler] No actions to undo.")
            return None

        last_action = self.sorted_images.pop()
        action_type, image_path, *rest = last_action
        original_index = rest[-1]  # Get the stored original index

        logger.info(f"[ImageHandler] Undoing action: {action_type} on {image_path} at index {original_index}")
        with self.lock:
            if image_path not in self.image_list:
                # Insert the image back at its original index
                self.image_list.insert(original_index, image_path)
            logger.info(f"[ImageHandler] Restored image: {image_path} to index: {original_index}")

        return last_action

    def complete_undo_last_action(self, image_path, action_type, rest):
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"[ImageHandler] Start directory for image {image_path} not found.")
            return None

        if action_type == 'delete':
            source_dir = self.delete_folders.get(start_dir)
            dest_dir = start_dir
        elif action_type == 'move':
            category = rest[0]
            source_dir = self.dest_folders[start_dir].get(category)
            dest_dir = start_dir
        else:
            raise ImageSorterError(f"Action type {action_type} unrecognized")

        logger.debug(
            f"[ImageHandler] Creating MoveFileWorker thread for undo_last_action with source: {source_dir}, dest: {dest_dir}")
        self.worker = MoveFileWorker(
            image_path,
            source_dir,
            dest_dir)
        self.worker.start()
        logger.debug("[ImageHandler] MoveFileWorker thread started for undo_last_action")

    def restore_image(self, image_path, original_index):
        """Restore image to its original index in the image list."""

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def refresh_image_list(self, signal=None):
        """Initial full scan to build the list of images from all start directories."""
        logger.info("[ImageHandler] Starting image list refresh")

        # Step 1: List all directories concurrently
        all_dirs = list_all_directories_concurrent(self.start_dirs)

        # Step 2: Sort all directories using os_sorted
        sorted_dirs = os_sorted(all_dirs)

        # Step 3: Prepare for concurrent processing
        with self.lock:
            self.image_list.clear()

        def process_files_in_directory(directory):
            """Helper function to process files in a directory and add image files."""
            image_files = []
            for root, _, files in os.walk(directory):
                sorted_files = os_sorted(files)  # Sort files using os_sorted
                for file in sorted_files:
                    if self.is_image_file(file):
                        file_path = os.path.join(root, file)
                        image_files.append(file_path)
                    else:
                        logger.debug(f'[ImageHandler] Refresh thread: Skipping non-image file {file}')
                break  # Only process the first level of files
            return image_files

        # Use ThreadPoolExecutor to maximize concurrency
        with ThreadPoolExecutor() as executor:
            # List of futures to process in sorted directory order
            futures = [executor.submit(process_files_in_directory, d) for d in sorted_dirs]

            # Collect results in the order of directory submission
            for future in futures:
                image_files = future.result()
                if image_files:
                    with self.lock:
                        self.image_list.extend(image_files)
                        if signal and isinstance(signal, pyqtBoundSignal):
                            logger.debug(
                                f'[ImageHandler] Emitting signal image population with image list count {len(self.image_list)}')
                            signal.emit()

        with self.lock:
            self.image_list = os_sorted(self.image_list)
        logger.debug(f"[ImageHandler] Completed refresh_image_list with {len(self.image_list)} images.")

    def is_image_file(self, filename):
        """Check if the file is a valid image format."""
        valid_extensions = ['.webp', '.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)
