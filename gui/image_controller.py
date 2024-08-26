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
        self.image_manager.image_cleared.connect(self.image_cleared_signal.emit)
        logger.debug("Signals connected: image_loaded and image_cleared.")

    def set_main_window(self, main_window):
        self.main_window = main_window
        logger.debug("Main window set in ImageController.")
        bind_keys(main_window, self.image_manager)
        # Load image after main window is set to ensure everything is ready
        self.image_manager.load_image()

    def on_image_loaded(self, file_path, pixmap):
        logger.debug(f"on_image_loaded triggered with file_path: {file_path}.")
        if self.main_window:
            self.main_window.image_display.display_image(file_path, pixmap)
            logger.debug(f"Emitting image_loaded_signal for {file_path}.")
            self.image_loaded_signal.emit(file_path)
        else:
            logger.error("Main window is not set in ImageController.")
