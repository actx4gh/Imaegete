from PyQt6.QtCore import QObject
from os.path import dirname
from core import config, logger
from image_processing.data_management.file_operations import find_matching_directory


class ImageHandler(QObject):
    def __init__(self, data_service, thread_manager, image_list_manager, file_task_handler):
        super().__init__()
        self.data_service = data_service
        self.thread_manager = thread_manager
        self.image_list_manager = image_list_manager
        self.file_task_handler = file_task_handler
        self.delete_folders = config.delete_folders
        self.dest_folders = config.dest_folders
        self.start_dirs = config.start_dirs
        pass

    def move_or_delete_image(self, image_path, action_type, original_index=None, category=None):
        """
        Helper function to move or delete an image.
        Determines the correct source and destination directories based on action type.

        :param str image_path: The path to the image.
        :param str action_type: The action type ('move' or 'delete').
        :param int original_index:
        :param str category: The category to move the image to (required for 'move' action).
        """
        start_dir = find_matching_directory(image_path, self.start_dirs)
        if not start_dir:
            logger.error(f"Start directory for image {image_path} not found.")
            return

        image_dir = dirname(image_path)
        if action_type == 'delete':
            if original_index is None:
                dest_dir = image_dir
                source_dir = self.delete_folders.get(start_dir)
            else:
                dest_dir = self.delete_folders.get(start_dir)
                source_dir = image_dir
            if dest_dir:
                self.file_task_handler.delete_image(image_path, source_dir, dest_dir)
            else:
                logger.error(f"Delete folder not configured for start directory {start_dir}")
        elif action_type == 'move' and category:
            category_folder = self.dest_folders.get(start_dir, {}).get(category)
            if original_index is None:
                dest_dir = image_dir
                source_dir = category_folder
            else:
                dest_dir = category_folder
                source_dir = image_dir
            if dest_dir:
                self.file_task_handler.move_image(image_path, source_dir, dest_dir)
            else:
                logger.error(f"Destination folder not found for category {category} in directory {start_dir}")

        if original_index is not None:
            self.data_service.append_sorted_images((action_type, image_path, category, original_index))

    def move_current_image(self, category):
        """
        Move the current image to a category folder.
        """
        current_index, image_path = self.image_list_manager.pop_image()
        if image_path:
            self.move_or_delete_image(image_path, 'move', original_index=current_index, category=category)

    def delete_current_image(self):
        """
        Delete the current image by moving it to the delete folder.
        """
        current_index, image_path = self.image_list_manager.pop_image()
        if image_path:
            self.move_or_delete_image(image_path, 'delete', original_index=current_index)

    def undo_last_action(self):
        """
        Undo the last move or delete action.
        """
        last_action = self.data_service.pop_sorted_images()
        if last_action:
            action_type, image_path, *rest = last_action
            original_index = rest[-1]
            if action_type == 'delete':
                self.move_or_delete_image(image_path, 'delete')
            elif action_type == 'move':
                category = rest[0]
                self.move_or_delete_image(image_path, 'move', category=category)
            self.image_list_manager.add_image_to_list(image_path, original_index)
            self.data_service.set_current_index(original_index)
            return last_action
