from image_processing.image_manager import ImageManager
from key_binding.key_binder import bind_keys

class ImageController:
    def __init__(self, main_window, config, logger):
        self.main_window = main_window
        self.logger = logger
        self.image_manager = ImageManager(config)
        self.image_manager.image_loaded.connect(self.on_image_loaded)
        self.image_manager.image_cleared.connect(self.main_window.image_display.clear_image)
        self.image_manager.load_image()

        bind_keys(main_window, config['categories'], self.image_manager)
        self.main_window.image_display.image_changed.connect(lambda: self.main_window.status_bar_manager.update_status_bar())

    def on_image_loaded(self, file_path, pixmap):
        self.main_window.image_display.display_image(file_path, pixmap)
        self.main_window.status_bar_manager.update_status_bar(file_path)
