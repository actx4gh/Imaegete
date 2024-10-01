from PyQt6.QtCore import QObject, pyqtSignal, QRecursiveMutex
from PyQt6.QtGui import QPixmap

from imaegete.core.logger import logger, config
from glavnaqt.core.event_bus import create_or_get_shared_event_bus


class ImageController(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_list_updated = pyqtSignal()
    image_ready = pyqtSignal(str, object)

    def __init__(self, image_list_manager, image_loader, image_handler):
        super().__init__()
        self.image_list_manager = image_list_manager
        self.image_loader = image_loader
        self.image_handler = image_handler
        self.lock = QRecursiveMutex()
        self.current_displayed_image = None
        self.loading_images = set()  # Track currently loading images
        self.event_bus = create_or_get_shared_event_bus()
        self.image_ready.connect(self.send_image_to_display)
        self.image_list_updated.connect(self.on_image_list_updated)
        self.event_bus.emit('show_busy')
        self.folders_to_skip = self._get_folders_to_skip()
        self.image_list_manager.refresh_image_list(config.start_dirs.copy(), folders_to_skip=self.folders_to_skip,
                                                   signal=self.image_list_updated)

    def show_image(self, image_path=None):
        if image_path in self.loading_images:
            return
        elif not image_path:
            image_path = self.image_list_manager.data_service.get_current_image_path()

        def display_callback(image):
            self.loading_images.discard(image_path)
            if image:
                pixmap = QPixmap.fromImage(image)
                self.image_loaded.emit(image_path, pixmap)  # Emit signal to MainWindow
                self.current_displayed_image = image_path
            else:
                self.image_cleared.emit()

        self.loading_images.add(image_path)
        self.image_loader.load_image_async(image_path, display_callback)

    def next_image(self):
        image_path = self.image_list_manager.set_next_image()
        self.show_image(image_path)

    def previous_image(self):
        image_path = self.image_list_manager.set_previous_image()
        self.show_image(image_path)

    def first_image(self):
        image_path = self.image_list_manager.set_first_image()
        self.show_image(image_path)

    def last_image(self):
        image_path = self.image_list_manager.set_last_image()
        self.show_image(image_path)

    def random_image(self):
        image_path = self.image_list_manager.set_random_image()
        self.show_image(image_path)

    def send_image_to_display(self, image_path, image):
        pixmap = QPixmap.fromImage(image)
        self.image_loaded.emit(image_path, pixmap)
        self.event_bus.emit('hide_busy')

    def move_image(self, category):
        self.image_handler.move_current_image(category)
        self.show_image()

    def delete_image(self):
        self.image_handler.delete_current_image()
        self.show_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            self.show_image()

    def _get_folders_to_skip(self):
        folders_to_skip = []
        for start_dir, subfolders in config.dest_folders.items():
            folders_to_skip.extend(subfolders.values())
        for start_dir, delete_folder in config.delete_folders.items():
            folders_to_skip.append(delete_folder)
        return folders_to_skip



    def on_image_list_updated(self):
        """
        Handle the event when the image list is updated.
        Automatically display the first image from the list.
        """
        self.event_bus.emit("update_image_total")
        if not self.current_displayed_image:
            self.current_displayed_image = 'displaying'
            image_path = self.image_list_manager.data_service.get_current_image_path()
            if image_path:
                self.show_image(image_path)
            else:
                self.current_displayed_image = ''
                logger.error("[ImageController] Could not get current image from data service.")
        else:
            self.event_bus.emit('hide_busy')