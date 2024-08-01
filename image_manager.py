from image_handler import ImageHandler
from image_loader import NonGPUImageLoader, GPUImageLoader
import logging

class ImageManager:
    def __init__(self, gui, config, use_gpu=False):
        self.gui = gui
        self.config = config
        self.image_handler = ImageHandler(config['source_folder'], config['dest_folders'], config['delete_folder'])
        self.current_index = 0
        self.image_loader = None
        self.use_gpu = use_gpu

    def load_image(self):
        if self.image_loader is not None and self.image_loader.isRunning():
            self.image_loader.stop()
            self.image_loader.wait()
        if 0 <= self.current_index < len(self.image_handler.image_list):
            if self.use_gpu:
                self.image_loader = GPUImageLoader(self.image_handler, self.current_index)
            else:
                self.image_loader = NonGPUImageLoader(self.image_handler, self.current_index)
            self.image_loader.image_loaded.connect(self.gui.display_image)
            self.image_loader.finished_loading.connect(self.on_image_loaded)
            self.image_loader.start()
        else:
            logging.info("No current image to load")

    def on_image_loaded(self):
        logging.info("Image loaded and thread finished")

    def next_image(self):
        if self.current_index < len(self.image_handler.image_list) - 1:
            self.current_index += 1
            self.load_image()

    def previous_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()

    def move_image(self, category):
        self.image_handler.move_image(category)
        self.load_image()

    def delete_image(self):
        self.image_handler.delete_image()
        self.load_image()

    def undo_last_action(self):
        self.image_handler.undo_last_action()
        self.load_image()

    def first_image(self):
        self.current_index = 0
        self.load_image()

    def last_image(self):
        self.current_index = len(self.image_handler.image_list) - 1
        self.load_image()

    def stop_threads(self):
        if self.image_loader is not None and self.image_loader.isRunning():
            self.image_loader.stop()
            self.image_loader.wait()
