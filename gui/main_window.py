import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

import config
import logger
from glavnaqt.core.config import UIConfiguration
from glavnaqt.ui.main_window import MainWindow
from .image_controller import ImageController  # Preserved
from .image_display import ImageDisplay  # Preserved
from .status_bar_manager import ImageSorterStatusBarManager


class ImageSorterGUI(MainWindow):

    def __init__(self, *args, **kwargs):
        # Initialize ImageDisplay first
        self.image_display = ImageDisplay()

        # Define the UI configuration
        ui_config = UIConfiguration(
            font_face="Helvetica",
            font_size=13,
            splitter_handle_width=4,
            window_size=(800, 600),
            window_position=(150, 150),
            enable_status_bar_manager=True,
            collapsible_sections={
                'top': {
                    'text': self.format_category_keys(config.categories),
                    'alignment': UIConfiguration.ALIGN_CENTER,
                },
                'main_content': {
                    'alignment': UIConfiguration.ALIGN_CENTER,
                    'widget': self.image_display.get_widget()
                },
                'bottom': {
                    'alignment': UIConfiguration.ALIGN_CENTER
                }
            }
        )

        # Call the parent constructor first
        super().__init__(ui_config, *args, **kwargs)

        # Initialize the ImageController with a reference to this window
        self.image_controller = ImageController(self)

        # Now that everything is initialized, connect the signals
        self.status_bar_manager.connect_signals(self.image_controller)
        self.image_display.image_changed.connect(self._status_bar_manager.update_status_bar)
        self.event_bus.subscribe('resize', lambda event: self.on_resize())

        self.show()

    @property
    def status_bar_manager(self):
        if self._status_bar_manager is None:
            # Initialize status bar manager now that everything else is set up
            self._status_bar_manager = ImageSorterStatusBarManager(self, self.image_controller.image_manager)
        return self._status_bar_manager

    def _initialize_ui(self, collapsible_sections):
        """Ensure status_bar_manager is initialized before parent UI setup."""
        # Call the parent method
        super()._initialize_ui(collapsible_sections)

    def on_resize(self):
        # Handle the resize event specific to ImageSorter
        self.update_zoom_percentage()
        self.image_display.update_image_label()  # Ensure the image label is updated on resize
        self.log_resize_event()
        self.status_bar_manager.update_status_bar()

    def update_zoom_percentage(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        self.status_bar_manager.update_status_bar(current_image_path)

    def log_resize_event(self):
        logger.info(f"[ImageSorterGUI] Window resized to {self.width()}x{self.height()}")

    def format_category_keys(self, categories):
        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def on_image_loaded(self, file_path, pixmap):
        self.image_controller.on_image_loaded(file_path, pixmap)

    # Interactive status bar methods
    def setup_interactive_status_bar(self):
        self.status_bar_manager.status_label.mousePressEvent = self.status_bar_clicked
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def status_bar_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            segment = self.identify_segment(event.pos())
            if segment == "filename":
                self.open_file_location()
            elif segment == "zoom":
                self.adjust_zoom_level()
            elif segment == "date":
                self.open_file_properties()

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        if self.identify_segment(pos) == "filename":
            context_menu.addAction(QAction("Open File Location", self, triggered=self.open_file_location))
        elif self.identify_segment(pos) == "zoom":
            context_menu.addAction(QAction("Adjust Zoom", self, triggered=self.adjust_zoom_level))
        elif self.identify_segment(pos) == "date":
            context_menu.addAction(QAction("File Properties", self, triggered=self.open_file_properties))
        context_menu.exec(self.mapToGlobal(pos))

    def identify_segment(self, pos):
        return "filename" if pos.x() < 100 else "zoom" if pos.x() < 200 else "date"

    def open_file_location(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        if current_image_path:
            folder_path = os.path.dirname(current_image_path)
            os.startfile(folder_path)

    def adjust_zoom_level(self):
        # Implement zoom adjustment logic specific to image sorting
        pass

    def open_file_properties(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        if current_image_path:
            os.system(f'explorer /select,\"{current_image_path}\"')
