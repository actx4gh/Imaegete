from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QAction, QMenu
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QFontMetrics
import os
from .logging_setup import setup_logging
from .ui_initializer import UIInitializer
from .event_handling import setup_event_handling, handle_resize_event
from .status_bar_manager import StatusBarManager
from .image_controller import ImageController

class ResizeSignal(QObject):
    resized = pyqtSignal()

class ImageSorterGUI(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.logger = setup_logging()
        self.logger.info("[ImageSorterGUI] Initializing ImageSorterGUI")
        self.setWindowTitle("Image Sorter")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(100, 100)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        resize_signal = ResizeSignal()
        setup_event_handling(self, resize_signal)

        self.status_bar_manager = StatusBarManager(self, None)  # Placeholder for image_manager
        self.ui_initializer = UIInitializer(self, config, self.logger)
        self.ui_initializer.init_ui()

        self.image_controller = ImageController(self, config, self.logger)
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
        self.logger.info(f"[ImageSorterGUI] Window resized to {self.width()}x{self.height()}")

    def update_zoom_percentage(self):
        current_image_path = self.image_controller.image_manager.get_current_image_path()
        self.status_bar_manager.update_status_bar(current_image_path)

    def adjust_layout(self):
        self.adjust_font_size()
        self.adjust_top_bar_height()
        self.adjust_status_bar_height()

    def adjust_font_size(self):
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
        new_size = max(1, min(int(width / (text_length / 1.5)), 12))

        if width < max_text_width:
            scale_factor = width / max_text_width
            new_size = max(1, int(scale_factor * new_size))

        # Apply the new font size
        self.category_label.setFont(QFont("Helvetica", new_size))
        self.status_bar_manager.status_label.setFont(QFont("Helvetica", new_size))

    def adjust_top_bar_height(self):
        font_metrics = self.category_label.fontMetrics()
        text_height = font_metrics.height()
        self.top_bar.setFixedHeight(text_height + 10)

    def adjust_status_bar_height(self):
        font_metrics = self.status_bar_manager.status_label.fontMetrics()
        text_height = font_metrics.height()
        self.status_bar_manager.status_bar.setFixedHeight(text_height + 10)

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
