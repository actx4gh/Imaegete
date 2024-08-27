from PyQt6.QtCore import QObject, pyqtSignal

import logger
from key_binding.key_binder import bind_keys


class ImageController(QObject):
    image_loaded_signal = pyqtSignal(str)
    image_cleared_signal = pyqtSignal()

    def __init__(self, image_manager):
        super().__init__()
        self.main_window = None
        self.image_manager = image_manager
        logger.debug("Connecting image_manager signals to ImageController.")
        self.image_manager.image_loaded.connect(self.on_image_loaded)
        self.image_manager.image_cleared.connect(
            lambda: self.main_window.image_display.clear_image() if self.main_window else None)
        logger.debug("Signals connected: image_loaded and image_cleared.")

    def set_main_window(self, main_window):
        self.main_window = main_window
        logger.debug("Main window set in ImageController.")
        bind_keys(main_window, self.image_manager)

        # Connect the image_list_populated signal
        self.image_manager.image_list_populated.connect(self.on_image_list_populated)

    def on_image_list_populated(self):
        """Load the first image when the image list is populated."""
        logger.debug("Image list populated signal received.")
        if self.image_manager.image_handler.image_list:
            self.image_manager.current_index = 0  # Start from the first image
            self.image_manager.load_image()  # Trigger loading of the first image

    def on_image_loaded(self, file_path, pixmap):
        logger.debug(f"on_image_loaded triggered with file_path: {file_path}.")
        if self.main_window:
            self.main_window.image_display.display_image(file_path, pixmap)
            logger.info(f"Image displayed: {file_path}")
        else:
            logger.error("Main window is not set in ImageController.")
