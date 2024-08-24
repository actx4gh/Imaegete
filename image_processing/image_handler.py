import os

from natsort import os_sorted

import config
import logger
from .file_operations import move_related_files, check_and_remove_empty_dir


class ImageHandler:
    def __init__(self):
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs

        self.image_list = []
        self.deleted_images = []
        self.refresh_image_list()

    def refresh_image_list(self):
        """Refresh the list of images from all start directories."""
        logger.debug("Starting refresh_image_list")

        temp_image_list = []  # Temporary list to check for duplicates
        for start_dir in self.start_dirs:
            logger.debug(f"Processing start directory: {start_dir}")
            for root, dirs, files in os.walk(start_dir):
                root_abs = os.path.abspath(root)

                # Exclude sort and delete directories
                dirs[:] = [d for d in dirs if os.path.join(root_abs, d) not in
                           [os.path.abspath(f) for f in self.dest_folders[start_dir].values()] and
                           os.path.join(root_abs, d) != os.path.abspath(self.delete_folders[start_dir])]

                for file in files:
                    if self.is_image_file(file):
                        file_path = os.path.join(root_abs, file)
                        temp_image_list.append(file_path)  # Add to temporary list

        # Remove duplicates by converting to set and back to list
        self.image_list = os_sorted(list(set(temp_image_list)))
        logger.debug(f"Completed refresh_image_list with {len(self.image_list)} images.")

    def is_image_file(self, filename):
        """Check if the file is a valid image format."""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def move_image(self, image_path, category):
        """Move image to the specified category folder."""
        # Use image_path directly as it's now the full path
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"Start directory for image {image_path} not found.")
            return

        logger.debug(f"Moving image: {image_path}")

        dest_folder = self.dest_folders[start_dir].get(category)
        if not dest_folder:
            logger.error(f"Destination folder not found for category {category} in directory {start_dir}")
            return

        move_related_files(image_path, os.path.dirname(image_path), dest_folder)
        logger.info(f"Moved image: {image_path} to category {category}")
        self.deleted_images.append(('move', image_path, category))

        self.refresh_image_list()
        check_and_remove_empty_dir(dest_folder)

    def delete_image(self, image_path):
        """Move image to the delete folder."""
        # Use image_path directly as it's now the full path
        start_dir = self.find_start_directory(image_path)
        if not start_dir:
            logger.error(f"Start directory for image {image_path} not found.")
            return

        logger.debug(f"Deleting image: {image_path}")

        delete_folder = self.delete_folders.get(start_dir)
        if not delete_folder:
            logger.error(f"No delete folder found for directory {start_dir}")
            return

        move_related_files(image_path, os.path.dirname(image_path), delete_folder)
        logger.info(f"Deleted image: {image_path}")
        self.deleted_images.append(('delete', image_path))

        self.refresh_image_list()
        check_and_remove_empty_dir(delete_folder)

    def undo_last_action(self):
        """Undo the last move or delete action."""
        if self.deleted_images:
            last_action = self.deleted_images.pop()
            image_path = last_action[1]

            start_dir = self.find_start_directory(image_path)
            if not start_dir:
                logger.error(f"Start directory for image {image_path} not found.")
                return None

            if last_action[0] == 'delete':
                delete_folder = self.delete_folders.get(start_dir)
                if delete_folder:
                    move_related_files(image_path, delete_folder, start_dir)
                    check_and_remove_empty_dir(delete_folder)
                    logger.info(f"Undo delete: {image_path} back to source folder {start_dir}")
            elif last_action[0] == 'move':
                category = last_action[2]
                dest_folder = self.dest_folders[start_dir].get(category)
                if dest_folder:
                    move_related_files(image_path, dest_folder, start_dir)
                    check_and_remove_empty_dir(dest_folder)
                    logger.info(f"Undo move: {image_path} from {category} back to source folder {start_dir}")

            self.refresh_image_list()
            return last_action
        return None

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)
