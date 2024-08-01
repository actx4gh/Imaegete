import os
import shutil
import logging
from PIL import Image
from natsort import os_sorted


class ImageHandler:
    def __init__(self, source_folder, dest_folders, delete_folder):
        self.source_folder = source_folder
        self.dest_folders = dest_folders
        self.delete_folder = delete_folder
        self.supported_extensions = ('.jpg', '.jpeg', '.png')
        self.image_list = self.get_image_list()
        self.image_index = 0
        self.undo_stack = []
        self.image_cache = {}
        logging.info(f"Initialized ImageHandler with source folder: {source_folder}")

    def get_image_list(self):
        image_files = [f for f in os.listdir(self.source_folder) if f.lower().endswith(self.supported_extensions)]
        image_files = os_sorted(image_files)  # Sort files using os_sorted for natural sort order
        logging.info(f"Image list: {image_files}")
        return image_files

    def load_image(self, index=None):
        if index is None:
            index = self.image_index
        if index < len(self.image_list):
            image_path = os.path.join(self.source_folder, self.image_list[index])
            logging.info(f"Loading image: {image_path}")
            try:
                if image_path in self.image_cache:
                    logging.info(f"Using cached image for {image_path}")
                    return self.image_cache[image_path]
                image = Image.open(image_path)
                self.image_cache[image_path] = image
                logging.info(f"Loaded image: {image_path}")
                return image
            except Exception as e:
                logging.error(f"Failed to load image {image_path}: {e}")
        return None

    def move_file(self, src, dest):
        try:
            shutil.move(src, dest)
            logging.info(f"Moved file from {src} to {dest}")
        except Exception as e:
            logging.error(f"Failed to move file from {src} to {dest}: {e}")

    def move_related_files(self, filename, dest_folder):
        self._move_files(filename, self.source_folder, dest_folder)

    def move_related_files_back(self, filename, src_folder, dest_folder):
        self._move_files(filename, dest_folder, src_folder)

    def _move_files(self, filename, src_folder, dest_folder):
        base, _ = os.path.splitext(filename)
        related_files = [f for f in os.listdir(src_folder) if os.path.splitext(f)[0] == base]
        for f in related_files:
            src_path = os.path.join(src_folder, f)
            dest_path = os.path.join(dest_folder, f)
            self.move_file(src_path, dest_path)

    def move_image(self, category):
        current_image = self.image_list[self.image_index]
        self.move_related_files(current_image, self.dest_folders[category])
        self.undo_stack.append(('move', category, current_image))
        self.image_list.pop(self.image_index)
        if self.image_index >= len(self.image_list):
            self.image_index = max(0, len(self.image_list) - 1)  # Adjust index if it exceeds the list length
        logging.info(f"Image moved to {category}: {current_image}")

    def delete_image(self):
        current_image = self.image_list[self.image_index]
        self.move_related_files(current_image, self.delete_folder)
        self.undo_stack.append(('delete', current_image))
        self.image_list.pop(self.image_index)
        if self.image_index >= len(self.image_list):
            self.image_index = max(0, len(self.image_list) - 1)  # Adjust index if it exceeds the list length
        logging.info(f"Image deleted: {current_image}")

    def undo_last_action(self):
        if not self.undo_stack:
            logging.info("No actions to undo")
            return None

        last_action = self.undo_stack.pop()
        action_type = last_action[0]

        if action_type == 'move':
            category = last_action[1]
            filename = last_action[2]
            self.move_related_files_back(filename, self.source_folder, self.dest_folders[category])
            self.image_list.insert(self.image_index, filename)
            logging.info(f"Undo move: {filename} from {category} back to source folder")

        elif action_type == 'delete':
            filename = last_action[1]
            self.move_related_files_back(filename, self.source_folder, self.delete_folder)
            self.image_list.insert(self.image_index, filename)
            logging.info(f"Undo delete: {filename} back to source folder")

        # Reload the image list to ensure consistency
        self.image_list = self.get_image_list()
        if self.image_index >= len(self.image_list):
            self.image_index = max(0, len(self.image_list) - 1)

        return last_action
