import os

from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QAction, QMenu

import logger
from .event_handling import setup_event_handling, handle_resize_event
from .image_controller import ImageController
from .status_bar_manager import StatusBarManager
from .collapsible_splitter import CollapsibleSplitter
from .ui_initializer import UIInitializer


class ResizeSignal(QObject):
    resized = pyqtSignal()


class ImageSorterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("[ImageSorterGUI] Initializing ImageSorterGUI")
        self.setWindowTitle("Image Sorter")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(100, 100)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # Ensure no margins
        self.main_layout.setSpacing(0)

        resize_signal = ResizeSignal()
        setup_event_handling(self, resize_signal)

        self.status_bar_manager = StatusBarManager(self, None)  # Placeholder for image_manager
        self.ui_initializer = UIInitializer(self)
        self.ui_initializer.init_ui()

        self.image_controller = ImageController(self)
        self.status_bar_manager.image_manager = self.image_controller.image_manager  # Now set the actual image manager

        self.image_display.image_changed.connect(self.status_bar_manager.update_status_bar)
        self.resize_signal.resized.connect(self.status_bar_manager.update_status_bar)

        self.show()

    def resizeEvent(self, event):
        handle_resize_event(self, event, self.status_bar_manager.update_status_bar)
        super().resizeEvent(event)

    def on_image_loaded(self, file_path, pixmap):
        self.image_controller.on_image_loaded(file_path, pixmap)

    def on_resize_timeout(self):
        self.adjust_layout()
        self.image_display.update_image_label()

    def log_resize_event(self):
        logger.info(f"[ImageSorterGUI] Window resized to {self.width()}x{self.height()}")

    def update_zoom_percentage(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        self.status_bar_manager.update_status_bar(current_image_path)

    def adjust_layout(self):
        self.adjust_font_size()
        self.adjust_top_bar_height()
        self.adjust_status_bar_height()
        self.log_widget_geometries()  # Log widget geometries after layout adjustments

    def adjust_font_size(self):
        max_font_size = 12
        min_font_size = 5
        width = self.width()

        # Calculate the text widths for both the top bar and status bar
        top_bar_font_metrics = QFontMetrics(self.category_label.font())
        top_bar_text_width = top_bar_font_metrics.width(self.category_label.text())

        status_bar_font_metrics = QFontMetrics(self.status_bar_manager.status_label.font())
        status_bar_text_width = status_bar_font_metrics.width(self.status_bar_manager.status_label.text())

        # Determine the larger of the two widths
        max_text_width = max(top_bar_text_width, status_bar_text_width)

        # Adjust font size based on the larger text width and the current window width
        text_length = max(len(self.category_label.text()), len(self.status_bar_manager.status_label.text()))
        new_size = max(min_font_size, min(int(width / (text_length / 1.5)), max_font_size))

        if width < max_text_width:
            scale_factor = width / max_text_width
            new_size = max(min_font_size, int(scale_factor * new_size))

        # Apply the new font size using pixel size
        category_font = QFont("Helvetica")
        category_font.setPixelSize(new_size)
        self.category_label.setFont(category_font)

        status_font = QFont("Helvetica")
        status_font.setPixelSize(new_size)
        self.status_bar_manager.status_label.setFont(status_font)


    def adjust_top_bar_height(self):
        font_metrics = self.category_label.fontMetrics()
        text_height = font_metrics.height()
        padding = max(2, int(text_height * 0.2))  # Dynamic padding based on the font height
        self.top_bar.setFixedHeight(text_height + padding)  # Adjust the height based on the font height
        logger.debug(f"[ImageSorterGUI] Top bar height: {self.top_bar.height()}")

    def adjust_status_bar_height(self):
        font_metrics = self.status_bar_manager.status_label.fontMetrics()
        text_height = font_metrics.height()
        padding = max(2, int(text_height * 0.2))  # Dynamic padding based on the font height
        self.status_bar_manager.status_bar.setFixedHeight(
            text_height + padding)  # Adjust the height based on the font height
        logger.debug(
            f"[ImageSorterGUI] Status bar height: {self.status_bar_manager.status_bar.height()}")

    def log_widget_geometries(self):
        logger.debug(f"[ImageSorterGUI] Top splitter geometry: {self.top_splitter.geometry()}")
        logger.debug(f"[ImageSorterGUI] Image display geometry: {self.image_display.get_widget().geometry()}")
        logger.debug(f"[ImageSorterGUI] Status bar geometry: {self.status_bar_manager.status_bar.geometry()}")
        for i in range(self.top_splitter.count()):
            widget = self.top_splitter.widget(i)
            logger.debug(f"[ImageSorterGUI] Top splitter widget {i} geometry: {widget.geometry()}")
        logger.debug(f"[ImageSorterGUI] Splitter handle size: {self.top_splitter.handleWidth()}")

    # Interactive status bar methods
    def setup_interactive_status_bar(self):
        self.status_bar_manager.status_label.mousePressEvent = self.status_bar_clicked
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def status_bar_clicked(self, event):
        if event.button() == Qt.LeftButton:
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
        context_menu.exec_(self.mapToGlobal(pos))

    def identify_segment(self, pos):
        return "filename" if pos.x() < 100 else "zoom" if pos.x() < 200 else "date"

    def open_file_location(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        if current_image_path:
            folder_path = os.path.dirname(current_image_path)
            os.startfile(folder_path)

    def adjust_zoom_level(self):
        pass  # Implement zoom adjustment

    def open_file_properties(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        if current_image_path:
            os.system(f'explorer /select,"{current_image_path}"')

    def cleanup(self):
        # Implement necessary cleanup operations here
        logger.info("[ImageSorterGUI] Performing cleanup operations")
        # Add any other necessary cleanup steps here
