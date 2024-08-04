import logging
import os

from PyQt5.QtCore import pyqtSignal, QObject

from .image_cache import ImageCache
from .image_handler import ImageHandler
from .image_loader import ThreadedImageLoader


class ImageManager(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.logger = logging.getLogger('image_sorter')
        self.image_handler = ImageHandler(config['source_folder'], config['dest_folders'], config['delete_folder'])
        self.image_cache = ImageCache()
        self.current_index = 0
        self.loader_thread = None

    def load_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            image_path = os.path.join(self.image_handler.source_folder,
                                      self.image_handler.image_list[self.current_index])
            self.logger.info(
                f"Loading image at index {self.current_index} of {len(self.image_handler.image_list)}: {image_path}")
            if image_path in self.image_cache.cache:
                image = self.image_cache.cache[image_path]
                self.image_loaded.emit(image_path, image)
            else:
                if self.loader_thread is not None:
                    self.loader_thread.quit()
                    self.loader_thread.wait()
                self.loader_thread = ThreadedImageLoader(image_path)
                self.loader_thread.image_loaded.connect(self.on_image_loaded)
                self.loader_thread.start()
        else:
            self.logger.info("No current image to load")
            self.image_cleared.emit()

    def on_image_loaded(self, image_path, image):
        if image is not None:
            self.image_cache.cache[image_path] = image
            self.image_loaded.emit(image_path, image)
        else:
            self.logger.error(f"Failed to load image: {image_path}")

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
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            self.logger.info(f"Moving image: {current_image} to category {category}")
            self.image_handler.move_image(current_image, category)
            self.refresh_image_list()
            self.ensure_valid_index_after_delete()
            self.load_image()

    def delete_image(self):
        if 0 <= self.current_index < len(self.image_handler.image_list):
            current_image = self.image_handler.image_list[self.current_index]
            self.logger.info(f"Deleting image at index {self.current_index}: {current_image}")
            self.image_handler.delete_image(current_image)
            self.refresh_image_list()
            self.ensure_valid_index_after_delete()
            self.load_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            self.logger.info(f"Undo last action: {last_action}")
            self.refresh_image_list()
            if last_action[0] == 'delete':
                self.current_index = self.image_handler.image_list.index(last_action[1])
            elif last_action[0] == 'move':
                self.current_index = self.image_handler.image_list.index(last_action[1])
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

    def ensure_valid_index_after_delete(self):
        if self.current_index >= len(self.image_handler.image_list):
            self.current_index = len(self.image_handler.image_list) - 1
        self.logger.info(f"Ensuring valid index after delete: {self.current_index}")

    def refresh_image_list(self):
        self.image_handler.refresh_image_list()
        self.logger.info(f"Image list refreshed: {self.image_handler.image_list}")

    def stop_threads(self):
        if self.loader_thread is not None:
            self.loader_thread.quit()
            self.loader_thread.wait()
