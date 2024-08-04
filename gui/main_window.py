import logging
import os
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QFrame, QWidget, QLabel, QStatusBar, QAction, QMenu

from image_processing.image_manager import ImageManager
from key_binding.key_binder import bind_keys
from .collapsible_splitter import CollapsibleSplitter
from .image_display import ImageDisplay


class ResizeSignal(QObject):
    resized = pyqtSignal()


class ImageSorterGUI(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.logger = logging.getLogger('image_sorter')
        self.logger.info("[ImageSorterGUI] Initializing ImageSorterGUI")
        self.setWindowTitle("Image Sorter")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(100, 100)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.main_layout.setSpacing(0)  # Remove spacing

        self.resize_signal = ResizeSignal()
        self.resize_signal.resized.connect(self.on_resize_timeout)

        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.log_resize_event)  # Connect timer to logging method

        self.logger.info("[ImageSorterGUI] Calling initUI")
        self.initUI(config)
        self.logger.info("[ImageSorterGUI] UI initialized")

        self.image_manager = ImageManager(config)
        self.image_manager.image_loaded.connect(self.on_image_loaded)
        self.image_manager.image_cleared.connect(self.image_display.clear_image)
        self.image_manager.load_image()  # Ensure the first image is loaded at startup

        self.show()

        self.logger.info("[ImageSorterGUI] Binding keys")
        bind_keys(self, config['categories'], self.image_manager)

        self.image_display.image_changed.connect(self.update_status_bar)
        self.resize_signal.resized.connect(self.update_zoom_percentage)
        self.logger.info("[ImageSorterGUI] Keys bound")

    def initUI(self, config):
        self.logger.info("[ImageSorterGUI] Initializing UI components")

        self.top_bar = QFrame(self)
        self.top_bar.setFrameShape(QFrame.NoFrame)
        self.top_bar_layout = QVBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(0)
        self.top_bar_layout.setAlignment(Qt.AlignCenter)

        self.category_label = QLabel(self.format_category_keys(config['categories']), self)
        self.category_label.setFont(QFont("Helvetica", 8))
        self.category_label.setStyleSheet("color: black;")
        self.top_bar_layout.addWidget(self.category_label)

        self.top_splitter = CollapsibleSplitter(Qt.Vertical, 3)
        self.top_splitter.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.top_splitter.addWidget(self.top_bar)

        self.image_display = ImageDisplay(self.logger)
        self.image_display.image_changed.connect(self.update_status_bar)  # Connect signal to update status bar
        self.top_splitter.addWidget(self.image_display.get_widget())
        self.main_layout.addWidget(self.top_splitter)

        self.status_bar = QStatusBar(self)
        self.status_label = QLabel("Status: Ready", self)
        self.status_label.setFont(QFont("Helvetica", 8))
        self.status_label.setStyleSheet("color: black;")
        self.status_bar.addWidget(self.status_label)

        self.bottom_splitter = CollapsibleSplitter(Qt.Vertical, 3)
        self.bottom_splitter.setBottomSplitter(True)
        self.bottom_splitter.setContentsMargins(0, 0, 0, 0)
        self.bottom_splitter.addWidget(self.top_splitter)
        self.bottom_splitter.addWidget(self.status_bar)
        self.main_layout.addWidget(self.bottom_splitter)

        self.top_splitter.setCollapsible(0, True)
        self.top_splitter.setCollapsible(1, False)
        self.bottom_splitter.setCollapsible(0, False)
        self.bottom_splitter.setCollapsible(1, True)

        self.adjust_layout()
        self.logger.info("[ImageSorterGUI] Finished initializing UI components")

    def on_image_loaded(self, file_path, pixmap):
        self.image_display.display_image(file_path, pixmap)
        self.update_status_bar(file_path)

    def update_status_bar(self, file_path=None):
        if not file_path:
            file_path = self.image_manager.get_current_image_path()
            if not file_path:
                self.status_label.setText("No image loaded")
                self.status_label.setToolTip("No image loaded")
                return

        filename = self.get_filename(file_path)
        zoom_percentage = self.get_zoom_percentage()
        dimensions = self.get_image_dimensions(file_path)
        file_size = self.get_file_size(file_path)
        modification_date = self.get_modification_date(file_path)
        image_index = self.image_manager.get_current_image_index()
        total_images = len(self.image_manager.image_handler.image_list)

        status_text = f"📁 {image_index + 1}/{total_images} • 🔍 {zoom_percentage}% • 📏 {dimensions} • 💾 {file_size} • 📅 {modification_date}"
        self.status_label.setText(status_text)

        self.status_label.setToolTip(f"Filename: {filename}\nZoom: {zoom_percentage}%\nDimensions: {dimensions}\n"
                                     f"File Size: {file_size}\nModification Date: {modification_date}\n"
                                     f"Image: {image_index + 1}/{total_images}")

    def get_filename(self, file_path):
        return os.path.basename(file_path)

    def get_zoom_percentage(self):
        return self.image_display.get_zoom_percentage()

    def get_image_dimensions(self, file_path):
        image = self.image_manager.image_cache.load_image(file_path)
        return f"{image.width} x {image.height} px"

    def get_file_size(self, file_path):
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def get_modification_date(self, file_path):
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')

    def resizeEvent(self, event):
        self.resize_signal.resized.emit()
        if self.resize_timer.isActive():
            self.resize_timer.stop()
        self.resize_timer.start(300)
        super().resizeEvent(event)

        self.update_status_bar()

    def setup_interactive_status_bar(self):
        # Clickable segments with actions
        self.status_label.mousePressEvent = self.status_bar_clicked
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
        # Dummy implementation for segment identification
        return "filename" if pos.x() < 100 else "zoom" if pos.x() < 200 else "date"

    def open_file_location(self):
        current_image_path = self.image_manager.get_current_image_path()
        if current_image_path:
            folder_path = os.path.dirname(current_image_path)
            os.startfile(folder_path)

    def adjust_zoom_level(self):
        # Implement zoom adjustment
        pass

    def open_file_properties(self):
        current_image_path = self.image_manager.get_current_image_path()
        if current_image_path:
            os.system(f'explorer /select,"{current_image_path}"')

    def format_category_keys(self, categories):
        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def adjust_layout(self):
        self.adjust_font_size()
        self.adjust_top_bar_height()
        self.adjust_status_bar_height()

    def adjust_font_size(self):
        width = self.width()
        text_length = len(self.category_label.text())
        new_size = max(1, min(int(width / (text_length / 1.5)), 12))
        self.category_label.setFont(QFont("Helvetica", new_size))
        self.status_label.setFont(QFont("Helvetica", new_size))  # Ensure the status bar font scales similarly

    def adjust_top_bar_height(self):
        font_metrics = self.category_label.fontMetrics()
        text_height = font_metrics.height()
        self.top_bar.setFixedHeight(text_height + 10)

    def adjust_status_bar_height(self):
        font_metrics = self.status_label.fontMetrics()
        text_height = font_metrics.height()
        self.status_bar.setFixedHeight(text_height + 10)

    def log_resize_event(self):
        self.logger.info(f"[ImageSorterGUI] Window resized to {self.width()}x{self.height()}")

    def finalize_resize(self):
        self.image_display.update_image_label()

    def on_resize_timeout(self):
        self.adjust_layout()
        self.image_display.update_image_label()

    def update_zoom_percentage(self):
        current_image_path = self.image_manager.get_current_image_path()
        self.update_status_bar(current_image_path)

    def closeEvent(self, event):
        self.logger.info("[ImageSorterGUI] closeEvent triggered")
        self.image_manager.stop_threads()
        event.accept()

    def cleanup(self):
        self.logger.info("[ImageSorterGUI] cleanup called")
        if self.image_manager is not None:
            self.image_manager.stop_threads()
        self.logger.info("[ImageSorterGUI] Threads stopped")
