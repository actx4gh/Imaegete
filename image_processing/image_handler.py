# image_handler.py
import os
from typing import List

from natsort import os_sorted

import config
import logger
from .file_operations import move_related_files, move_related_files_back, check_and_remove_empty_dir


class ImageHandler:
    def __init__(self):
        self.source_folder = config.source_folder
        self.dest_folders = config.dest_folders
        self.delete_folder = config.delete_folder

        self.image_list = []
        self.deleted_images = []
        self.refresh_image_list()

    def refresh_image_list(self):
        self.image_list: List[str] = []
        for root, _, files in os.walk(self.source_folder):
            for file in files:
                if self.is_image_file(file):
                    # Ensure all parts are strings
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.source_folder)
                    self.image_list.append(relative_path)
        self.image_list = os_sorted(self.image_list)  # Sort files using os_sorted for natural sort order
        logger.info(f"Image list count: {len(self.image_list)}")

    def is_image_file(self, filename):
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def move_image(self, image_name, category):
        if category in self.dest_folders:
            move_related_files(image_name, self.source_folder, self.dest_folders[category])
            logger.info(f"Moved image: {image_name} to category {category}")
            self.deleted_images.append(('move', image_name, category))
        self.refresh_image_list()
        check_and_remove_empty_dir(self.dest_folders[category])

    def delete_image(self, image_name):
        move_related_files(image_name, self.source_folder, self.delete_folder)
        logger.info(f"Deleted image: {image_name}")
        self.deleted_images.append(('delete', image_name))
        self.refresh_image_list()
        check_and_remove_empty_dir(self.delete_folder)

    def undo_last_action(self):
        if self.deleted_images:
            last_action = self.deleted_images.pop()
            if last_action[0] == 'delete':
                image_name = last_action[1]
                move_related_files_back(image_name, self.source_folder, self.delete_folder)
                check_and_remove_empty_dir(self.delete_folder)
                logger.info(f"Undo delete: {image_name} back to source folder")
            elif last_action[0] == 'move':
                image_name, category = last_action[1], last_action[2]
                move_related_files_back(image_name, self.source_folder, self.dest_folders[category])
                check_and_remove_empty_dir(self.dest_folders[category])
                logger.info(f"Undo move: {image_name} from {category} back to source folder")
            self.refresh_image_list()
            return last_action
        return None
