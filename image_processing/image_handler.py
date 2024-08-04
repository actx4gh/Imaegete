# image_handler.py
import logging
import os
from natsort import os_sorted
from .file_operations import move_related_files, move_related_files_back, check_and_remove_empty_dir

class ImageHandler:
    def __init__(self, source_folder, dest_folders, delete_folder):
        self.source_folder = source_folder
        self.dest_folders = dest_folders
        self.delete_folder = delete_folder
        self.image_list = []
        self.deleted_images = []
        self.logger = logging.getLogger('image_sorter')
        self.refresh_image_list()

    def refresh_image_list(self):
        self.image_list = [f for f in os.listdir(self.source_folder) if os.path.isfile(os.path.join(self.source_folder, f)) and self.is_image_file(f)]
        self.image_list = os_sorted(self.image_list)  # Sort files using os_sorted for natural sort order
        self.logger.info(f"Image list count: {len(self.image_list)}")

    def is_image_file(self, filename):
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

    def move_image(self, image_name, category):
        if category in self.dest_folders:
            move_related_files(image_name, self.source_folder, self.dest_folders[category])
            self.logger.info(f"Moved image: {image_name} to category {category}")
            self.deleted_images.append(('move', image_name, category))
        self.refresh_image_list()
        check_and_remove_empty_dir(self.dest_folders[category])

    def delete_image(self, image_name):
        move_related_files(image_name, self.source_folder, self.delete_folder)
        self.logger.info(f"Deleted image: {image_name}")
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
                self.logger.info(f"Undo delete: {image_name} back to source folder")
            elif last_action[0] == 'move':
                image_name, category = last_action[1], last_action[2]
                move_related_files_back(image_name, self.source_folder, self.dest_folders[category])
                check_and_remove_empty_dir(self.dest_folders[category])
                self.logger.info(f"Undo move: {image_name} from {category} back to source folder")
            self.refresh_image_list()
            return last_action
        return None
