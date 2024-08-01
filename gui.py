from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QSplitter, QSizePolicy, QFrame, QWidget, QLabel, QSplitterHandle
from PyQt5.QtGui import QFont, QPixmap, QColor, QPainter, QImage
from logger import setup_logging
from image_manager import ImageManager
from key_binder import bind_keys
import logging

class ResizeSignal(QObject):
    resized = pyqtSignal()

class CollapsibleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(5)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(100, 100, 100)
        painter.fillRect(self.rect(), color)

    def mousePressEvent(self, event):
        splitter = self.splitter()
        if splitter.widget(0).isVisible():
            splitter.widget(0).setVisible(False)
            splitter.setSizes([0, 1])
        else:
            splitter.widget(0).setVisible(True)
            splitter.setSizes([1, 1])
        self.update()
        super().mousePressEvent(event)

    def hideEvent(self, event):
        self.show()
        super().hideEvent(event)

class CollapsibleSplitter(QSplitter):
    def createHandle(self):
        return CollapsibleSplitterHandle(self.orientation(), self)

class ImageSorterGUI(QMainWindow):
    def __init__(self, config, log_file_path='image_sorter.log'):
        super().__init__()
        logging.info("[ImageSorterGUI] Initializing ImageSorterGUI")
        self.image_manager = None
        self.logger = setup_logging(log_file_path)
        self.logger.info(f"[ImageSorterGUI] Logging set up with log file: {log_file_path}")
        self.setWindowTitle("Image Sorter")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(100, 100)

        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.resize_signal = ResizeSignal()
        self.resize_signal.resized.connect(self.on_resize_timeout)

        self.current_pixmap = None
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.finalize_resize)

        logging.info("[ImageSorterGUI] Calling initUI")
        self.initUI(config)
        logging.info("[ImageSorterGUI] UI initialized")
        self.image_manager = ImageManager(self, config, use_gpu=False)
        self.show()

        logging.info("[ImageSorterGUI] Binding keys")
        bind_keys(self, config['categories'], self.image_manager)
        logging.info("[ImageSorterGUI] Keys bound")

    def initUI(self, config):
        logging.info("[ImageSorterGUI] Initializing UI components")
        self.top_bar = QFrame(self)
        self.top_bar.setFrameShape(QFrame.NoFrame)
        self.top_bar_layout = QVBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setAlignment(Qt.AlignCenter)
        self.category_label = QLabel(self.format_category_keys(config['categories']), self)
        self.category_label.setFont(QFont("Helvetica", 8))
        self.top_bar_layout.addWidget(self.category_label)

        self.top_splitter = CollapsibleSplitter(Qt.Vertical)
        self.top_splitter.setHandleWidth(5)
        self.top_splitter.addWidget(self.top_bar)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(1, 1)
        self.image_label.setContentsMargins(0, 0, 0, 0)

        self.top_splitter.addWidget(self.image_label)
        self.main_layout.addWidget(self.top_splitter)

        self.top_splitter.setCollapsible(0, True)
        self.top_splitter.setCollapsible(1, False)

        self.adjust_layout()
        logging.info("[ImageSorterGUI] Finished initializing UI components")

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

    def display_image(self, qimage):
        if qimage:
            logging.info("[ImageSorterGUI] Displaying image")
            self.current_pixmap = QPixmap.fromImage(qimage)
            self.update_image_label()
        else:
            logging.error("[ImageSorterGUI] Error: No image to display")

    def update_image_label(self):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        self.resize_signal.resized.emit()
        self.update_image_label()
        self.resize_timer.start(100)  # Adjust this value as needed
        super().resizeEvent(event)

    def finalize_resize(self):
        self.update_image_label()

    def on_resize_timeout(self):
        self.image_manager.load_image()
        self.adjust_layout()

    def closeEvent(self, event):
        logging.info("[ImageSorterGUI] closeEvent triggered")
        self.image_manager.stop_threads()
        event.accept()
