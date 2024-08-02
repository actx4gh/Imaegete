from image_processing.image_handler import ImageHandler
from PyQt5.QtCore import pyqtSignal, QObject
import logging
import os

class ImageManager(QObject):
    image_loaded = pyqtSignal(str)

    def __init__(self, gui, config):
        super().__init__()
        self.gui = gui
        self.config = config
        self.logger = logging.getLogger('image_sorter')
        self.image_handler = ImageHandler(config['source_folder'], config['dest_folders'], config['delete_folder'])
        self.current_index = 0

    def load_image(self):
        self.logger.info(f"Loading image at index {self.current_index} of {len(self.image_handler.image_list)}")
        if 0 <= self.current_index < len(self.image_handler.image_list):
            image_path = os.path.join(self.image_handler.source_folder, self.image_handler.image_list[self.current_index])
            self.logger.info(f"Displaying image: {image_path}")
            self.gui.display_image(image_path)
            self.image_loaded.emit(image_path)
        else:
            self.logger.info("No current image to load")
            self.gui.clear_image()

    def next_image(self):
        if self.current_index < len(self.image_handler.image_list) - 1:
            self.current_index += 1
            self.logger.info(f"Moving to next image: index {self.current_index}")
            self.load_image()
        else:
            self.logger.info("No next image available")

    def previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.logger.info(f"Moving to previous image: index {self.current_index}")
            self.load_image()
        else:
            self.logger.info("No previous image available")

    def move_image(self, category):
        self.image_handler.move_image(category)
        self.refresh_image_list()
        self.ensure_valid_index()
        self.load_image()

    def delete_image(self):
        self.logger.info(f"Deleting image at index {self.current_index}")
        self.image_handler.delete_image()
        self.refresh_image_list()
        self.ensure_valid_index()
        self.load_image()

    def undo_last_action(self):
        self.image_handler.undo_last_action()
        self.refresh_image_list()
        self.load_image()

    def first_image(self):
        self.current_index = 0
        self.load_image()

    def last_image(self):
        self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()

    def ensure_valid_index(self):
        if self.current_index >= len(self.image_handler.image_list):
            self.current_index = len(self.image_handler.image_list) - 1
        if self.current_index < 0:
            self.current_index = 0
        self.logger.info(f"Ensuring valid index: {self.current_index}")

    def refresh_image_list(self):
        self.image_handler.refresh_image_list()
        self.logger.info(f"Image list refreshed: {self.image_handler.image_list}")

    def stop_threads(self):
        # Assuming we have threading to handle; otherwise, we can leave this empty
        pass
