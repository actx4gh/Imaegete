import os
import traceback

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
        self.refresh_image_list()  # Initial full scan

    def add_image_to_list(self, image_path):
        """Add a new image to the image list."""
        if self.is_image_file(image_path) and image_path not in self.image_list:
            self.image_list.append(image_path)
            self.image_list.sort()  # Ensure the list remains sorted

    def remove_image_from_list(self, image_path):
        """Remove an image from the image list."""
        if image_path in self.image_list:
            self.image_list.remove(image_path)

    def refresh_image_list(self):
        """Initial full scan to build the list of images from all start directories."""
        logger.debug("Starting refresh_image_list")
        logger.debug('refresh_image_list called. Call stack:\n{}'.format(traceback.format_stack()))

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

        # Directly remove the image from the list
        self.image_list.remove(image_path)
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

        move_related_files(image_path, os.path.dirname(image_path), delete_folder)
        logger.info(f"Deleted image: {image_path}")
        self.deleted_images.append(('delete', image_path))

        # Directly remove the image from the list
        self.image_list.remove(image_path)
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
                    # Restore to the original path using the full original path
                    original_path = image_path.replace(delete_folder, start_dir)
                    move_related_files(image_path, delete_folder, os.path.dirname(original_path))
                    check_and_remove_empty_dir(delete_folder)
                    logger.info(f"Undo delete: {image_path} back to original location {original_path}")

                    # Directly add the image back to the image list
                    if original_path not in self.image_list:
                        self.add_image_to_list(original_path)  # Add image back to list without refresh
            elif last_action[0] == 'move':
                category = last_action[2]
                dest_folder = self.dest_folders[start_dir].get(category)
                if dest_folder:
                    # Restore to the original path using the full original path
                    original_path = image_path.replace(dest_folder, start_dir)
                    move_related_files(image_path, dest_folder, os.path.dirname(original_path))
                    check_and_remove_empty_dir(dest_folder)
                    logger.info(f"Undo move: {image_path} from {category} back to original location {original_path}")

                    # Directly add the image back to the image list
                    if original_path not in self.image_list:
                        self.add_image_to_list(original_path)  # Add image back to list without refresh

            # No need to call refresh_image_list here
            return last_action
        return None

    #    def move_image(self, image_path, category):
    #        """Move image to the specified category folder."""
    #        start_dir = self.find_start_directory(image_path)
    #        if not start_dir:
    #            logger.error(f"Start directory for image {image_path} not found.")
    #            return
    #
    #        logger.debug(f"Moving image: {image_path}")
    #
    #        dest_folder = self.dest_folders[start_dir].get(category)
    #        if not dest_folder:
    #            logger.error(f"Destination folder not found for category {category} in directory {start_dir}")
    #            return
    #
    #        move_related_files(image_path, os.path.dirname(image_path), dest_folder)
    #        logger.info(f"Moved image: {image_path} to category {category}")
    #        self.deleted_images.append(('move', image_path, category))
    #
    #        # Update image list directly instead of refreshing
    #        self.image_list.remove(image_path)
    #        check_and_remove_empty_dir(dest_folder)
    #
    #    def delete_image(self, image_path):
    #        """Move image to the delete folder."""
    #        start_dir = self.find_start_directory(image_path)
    #        if not start_dir:
    #            logger.error(f"Start directory for image {image_path} not found.")
    #            return
    #
    #        logger.debug(f"Deleting image: {image_path}")
    #
    #        delete_folder = self.delete_folders.get(start_dir)
    #        if not delete_folder:
    #            logger.error(f"No delete folder found for directory {start_dir}")
    #            return
    #
    #        move_related_files(image_path, os.path.dirname(image_path), delete_folder)
    #        logger.info(f"Deleted image: {image_path}")
    #        self.deleted_images.append(('delete', image_path))
    #
    #        # Update image list directly instead of refreshing
    #        self.image_list.remove(image_path)
    #        check_and_remove_empty_dir(delete_folder)
    #
    #    def undo_last_action(self):
    #        """Undo the last move or delete action."""
    #        if self.deleted_images:
    #            last_action = self.deleted_images.pop()
    #            image_path = last_action[1]
    #
    #            start_dir = self.find_start_directory(image_path)
    #            if not start_dir:
    #                logger.error(f"Start directory for image {image_path} not found.")
    #                return None
    #
    #            if last_action[0] == 'delete':
    #                delete_folder = self.delete_folders.get(start_dir)
    #                if delete_folder:
    #                    move_related_files(image_path, delete_folder, start_dir)
    #                    check_and_remove_empty_dir(delete_folder)
    #                    logger.info(f"Undo delete: {image_path} back to source folder {start_dir}")
    #                    self.add_image_to_list(image_path)  # Add image back to list
    #            elif last_action[0] == 'move':
    #                category = last_action[2]
    #                dest_folder = self.dest_folders[start_dir].get(category)
    #                if dest_folder:
    #                    move_related_files(image_path, dest_folder, start_dir)
    #                    check_and_remove_empty_dir(dest_folder)
    #                    logger.info(f"Undo move: {image_path} from {category} back to source folder {start_dir}")
    #                    self.add_image_to_list(image_path)  # Add image back to list
    #
    #            # No call to refresh_image_list
    #            return last_action
    #        return None

    def find_start_directory(self, image_path):
        """Find the start directory corresponding to the image path."""
        return next((d for d in self.start_dirs if os.path.abspath(image_path).startswith(os.path.abspath(d))), None)
