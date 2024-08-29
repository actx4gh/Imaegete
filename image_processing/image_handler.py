import os
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

from PyQt6.QtCore import pyqtBoundSignal
from natsort import os_sorted

import config
import logger
from .file_operations import move_related_files, check_and_remove_empty_dir, list_all_directories_concurrent


class ImageHandler:
    def __init__(self):
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs
        self.image_list = []
        self.first_image = None
        self.deleted_images = []
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

    def move_image(self, image_path, category):
        """Move image to the specified category folder."""
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"Start directory for image {image_path} not found.")
            return

        logger.debug(f"Moving image: {image_path}")

        dest_folder = self.dest_folders[start_dir].get(category)
        if not dest_folder:
            logger.error(f"Destination folder not found for category {category} in directory {start_dir}")
            return

        original_index = self.image_list.index(image_path)
        move_related_files(image_path, os.path.dirname(image_path), dest_folder)
        logger.info(f"Moved image: {image_path} to category {category}")

        with self.lock:
            self.deleted_images.append(('move', image_path, category, original_index))
            self.image_list.pop(original_index)
        check_and_remove_empty_dir(dest_folder)

    def delete_image(self, image_path):
        """Move image to the delete folder."""
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"Start directory for image {image_path} not found.")
            return

        logger.debug(f"Deleting image: {image_path}")

        delete_folder = self.delete_folders.get(start_dir)
        if not delete_folder:
            logger.error(f"No delete folder found for directory {start_dir}")
            return

        original_index = self.image_list.index(image_path)
        move_related_files(image_path, os.path.dirname(image_path), delete_folder)
        logger.info(f"Deleted image: {image_path}")

        with self.lock:
            self.deleted_images.append(('delete', image_path, original_index))
            self.image_list.pop(original_index)
        check_and_remove_empty_dir(delete_folder)

    def undo_last_action(self):
        """Undo the last move or delete action."""
        if self.deleted_images:
            last_action = self.deleted_images.pop()
            action_type = last_action[0]
            image_path = last_action[1]
            original_index = last_action[-1]  # Get the stored original index

            start_dir = self.find_start_directory(image_path)
            if not start_dir:
                logger.error(f"Start directory for image {image_path} not found.")
                return None

            if action_type == 'delete':
                delete_folder = self.delete_folders.get(start_dir)
                if delete_folder:
                    original_path = image_path.replace(delete_folder, start_dir)
                    move_related_files(image_path, delete_folder, os.path.dirname(original_path))
                    check_and_remove_empty_dir(delete_folder)
                    logger.info(f"Undo delete: {image_path} back to original location {original_path}")

                    # Restore image at its original index
                    self.add_image_to_list(original_path, original_index)

            elif action_type == 'move':
                category = last_action[2]
                dest_folder = self.dest_folders[start_dir].get(category)
                if dest_folder:
                    original_path = image_path.replace(dest_folder, start_dir)
                    move_related_files(image_path, dest_folder, os.path.dirname(original_path))
                    check_and_remove_empty_dir(dest_folder)
                    logger.info(f"Undo move: {image_path} from {category} back to original location {original_path}")

                    # Restore image at its original index
                    self.add_image_to_list(original_path, original_index)

            return last_action
        return None

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)

    def refresh_image_list(self, signal=None):
        """Initial full scan to build the list of images from all start directories."""
        logger.debug("Starting refresh_image_list")

        # Step 1: List all directories concurrently
        all_dirs = list_all_directories_concurrent(self.start_dirs)

        # Step 2: Sort all directories using os_sorted
        sorted_dirs = os_sorted(all_dirs)

        # Step 3: Prepare for concurrent processing
        with self.lock:
            self.image_list.clear()
        first_image_found = False  # To track if first image is set

        def process_files_in_directory(directory):
            """Helper function to process files in a directory and add image files."""
            image_files = []
            for root, _, files in os.walk(directory):
                sorted_files = os_sorted(files)  # Sort files using os_sorted
                for file in sorted_files:
                    if self.is_image_file(file):
                        file_path = os.path.join(root, file)
                        image_files.append(file_path)
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
                        if not first_image_found:
                            self.first_image = image_files[0]
                            first_image_found = True
                            logger.debug(f'First image found: {self.first_image}')
                        if signal and isinstance(signal, pyqtBoundSignal):
                            logger.debug(
                                f'Emitting signal image population with image list count {len(self.image_list)}')
                            signal.emit()

        with self.lock:
            self.image_list = os_sorted(self.image_list)
        logger.debug(f"Completed refresh_image_list with {len(self.image_list)} images.")

    def is_image_file(self, filename):
        """Check if the file is a valid image format."""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)
