# image_handler.py
import os

from natsort import os_sorted

import config
import logger
from .file_operations import move_related_files, move_related_files_back, check_and_remove_empty_dir


class ImageHandler:
    def __init__(self):
        self.dest_folders = config.dest_folders
        self.delete_folders = config.delete_folders
        self.start_dirs = config.start_dirs

        self.image_list = []
        self.deleted_images = []
        self.refresh_image_list()

    def refresh_image_list(self):
        self.image_list = []
        for start_dir in self.start_dirs:
            for root, dirs, files in os.walk(start_dir):
                root_abs = os.path.abspath(root)
                # Exclude sort directories
                dirs[:] = [d for d in dirs if os.path.join(root_abs, d) not in [os.path.abspath(f) for f in
                                                                                self.dest_folders[start_dir].values()]
                           and os.path.join(root_abs, d) not in [os.path.abspath(self.delete_folders[start_dir])]]

                for file in files:
                    if self.is_image_file(file):
                        file_path = os.path.join(root_abs, file)
                        relative_path = os.path.relpath(file_path, start_dir)
                        self.image_list.append(relative_path)

        self.image_list = os_sorted(self.image_list)
        logger.info(f"Image list count: {len(self.image_list)}")

    def move_image(self, image_name, category):
        image_path = os.path.abspath(image_name)
        logger.debug(f"Moving image: {image_path}")

        # Find the start directory for the image
        start_dir = next((d for d in self.start_dirs if image_path.startswith(os.path.abspath(d))), None)
        if not start_dir:
            logger.error(f"Start directory for image {image_name} not found.")
            return

        corresponding_dest_folder = self.dest_folders[start_dir].get(category)
        if not corresponding_dest_folder:
            logger.error(f"Destination folder not found for category {category} in directory {start_dir}")
            return

        move_related_files(image_path, start_dir, corresponding_dest_folder)
        logger.info(f"Moved image: {image_name} to category {category}")
        self.deleted_images.append(('move', image_name, category))

        self.refresh_image_list()
        check_and_remove_empty_dir(corresponding_dest_folder)

    def delete_image(self, image_name):
        image_path = os.path.abspath(image_name)
        logger.debug(f"Deleting image: {image_path}")

        # Find the start directory for the image
        start_dir = next((d for d in self.start_dirs if image_path.startswith(os.path.abspath(d))), None)
        if not start_dir:
            logger.error(f"Start directory for image {image_name} not found.")
            return

        corresponding_delete_folder = self.delete_folders.get(start_dir)
        if not corresponding_delete_folder:
            logger.error(f"No delete folder found for directory {start_dir}")
            return

        move_related_files(image_path, start_dir, corresponding_delete_folder)
        logger.info(f"Deleted image: {image_name}")
        self.deleted_images.append(('delete', image_name))

        self.refresh_image_list()
        check_and_remove_empty_dir(corresponding_delete_folder)

    def is_image_file(self, filename):
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def undo_last_action(self):
        if self.deleted_images:
            last_action = self.deleted_images.pop()
            image_name = last_action[1]
            image_path = os.path.abspath(image_name)

            # Find the start directory for the image
            start_dir = next((d for d in self.start_dirs if image_path.startswith(os.path.abspath(d))), None)
            if not start_dir:
                logger.error(f"Start directory for image {image_name} not found.")
                return None

            if last_action[0] == 'delete':
                delete_folder = self.delete_folders.get(start_dir)
                if delete_folder:
                    move_related_files_back(image_name, delete_folder, start_dir)
                    check_and_remove_empty_dir(delete_folder)
                    logger.info(f"Undo delete: {image_name} back to source folder {start_dir}")
            elif last_action[0] == 'move':
                category = last_action[2]
                dest_folder = self.dest_folders[start_dir].get(category)
                if dest_folder:
                    move_related_files_back(image_name, dest_folder, start_dir)
                    check_and_remove_empty_dir(dest_folder)
                    logger.info(f"Undo move: {image_name} from {category} back to source folder {start_dir}")

            self.refresh_image_list()
            return last_action
        return None
