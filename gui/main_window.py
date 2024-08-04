import logging

from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QFrame, QWidget, QLabel

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
        self.image_manager.image_loaded.connect(self.image_display.display_image)
        self.image_manager.image_cleared.connect(self.image_display.clear_image)
        self.image_manager.load_image()  # Ensure the first image is loaded at startup

        self.show()

        self.logger.info("[ImageSorterGUI] Binding keys")
        bind_keys(self, config['categories'], self.image_manager)
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
        self.top_bar_layout.addWidget(self.category_label)

        self.top_splitter = CollapsibleSplitter(Qt.Vertical)
        self.top_splitter.setHandleWidth(5)
        self.top_splitter.setContentsMargins(0, 0, 0, 0)  # Remove margins
        self.top_splitter.addWidget(self.top_bar)

        self.image_display = ImageDisplay(self.logger)
        self.top_splitter.addWidget(self.image_display.get_widget())
        self.main_layout.addWidget(self.top_splitter)

        self.top_splitter.setCollapsible(0, True)
        self.top_splitter.setCollapsible(1, False)

        self.adjust_layout()
        self.logger.info("[ImageSorterGUI] Finished initializing UI components")

    def format_category_keys(self, categories):
        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def adjust_layout(self):
        self.adjust_font_size()
        self.adjust_top_bar_height()

    def adjust_font_size(self):
        width = self.width()
        text_length = len(self.category_label.text())
        new_size = max(1, min(int(width / (text_length / 1.5)), 12))
        self.category_label.setFont(QFont("Helvetica", new_size))

    def adjust_top_bar_height(self):
        font_metrics = self.category_label.fontMetrics()
        text_height = font_metrics.height()
        self.top_bar.setFixedHeight(text_height + 10)

    def log_resize_event(self):
        self.logger.info(f"[ImageSorterGUI] Window resized to {self.width()}x{self.height()}")

    def resizeEvent(self, event):
        self.resize_signal.resized.emit()
        if self.resize_timer.isActive():
            self.resize_timer.stop()
        self.resize_timer.start(300)  # Adjust the debounce period as needed
        super().resizeEvent(event)

    def finalize_resize(self):
        self.image_display.update_image_label()

    def on_resize_timeout(self):
        self.adjust_layout()
        self.image_display.update_image_label()

    def closeEvent(self, event):
        self.logger.info("[ImageSorterGUI] closeEvent triggered")
        self.image_manager.stop_threads()
        event.accept()

    def cleanup(self):
        self.logger.info("[ImageSorterGUI] cleanup called")
        if self.image_manager is not None:
            self.image_manager.stop_threads()
        self.logger.info("[ImageSorterGUI] Threads stopped")
