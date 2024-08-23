from PyQt6.QtCore import QObject, pyqtSignal

from image_processing.new_image_manager import ImageManager
from key_binding.key_binder import bind_keys


class ImageController(QObject):
    image_loaded_signal = pyqtSignal(str)
    image_cleared_signal = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.image_manager = ImageManager()
        self.image_manager.image_loaded.connect(self.on_image_loaded)
        self.image_manager.image_cleared.connect(self.image_cleared_signal.emit)
        self.image_manager.load_image()

        bind_keys(main_window, self.image_manager)

    def on_image_loaded(self, file_path, pixmap):
        self.main_window.image_display.display_image(file_path, pixmap)
        self.image_loaded_signal.emit(file_path)
