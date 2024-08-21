from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QLabel, QSizePolicy, QMessageBox, QVBoxLayout, QWidget

import logger


class ImageDisplay(QObject):
    image_changed = pyqtSignal(str)  # Signal to emit the current file path

    def __init__(self):
        super().__init__()
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)

        # Remove margins and paddings
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.image_label = QLabel(self.widget)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(1, 1)

        # Remove margins from the label
        self.image_label.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.image_label)
        self.current_pixmap = None

    def get_widget(self):
        return self.widget

    def display_image(self, image_path, image):
        if image:
            logger.info(f"[ImageDisplay] Displaying image: {image_path}")
            qimage = self.pil_to_qimage(image)
            self.current_pixmap = QPixmap.fromImage(qimage)
            self.update_image_label()
            self.image_changed.emit(image_path)  # Emit signal with the current file path
        else:
            logger.error("[ImageDisplay] Error: No image to display")
            QMessageBox.critical(self.widget, "Error", "No image to display!")

    def clear_image(self):
        logger.info("[ImageDisplay] Clearing image")
        self.current_pixmap = None
        self.image_label.clear()

    def update_image_label(self):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            logger.debug(f"[ImageDisplay] Updated image label size: {self.image_label.size()}")  # Debug print
        else:
            self.clear_image()

    def pil_to_qimage(self, pil_image):
        pil_image = pil_image.convert("RGBA")
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGBA8888)
        return qimage

    def get_zoom_percentage(self):
        if not self.current_pixmap:
            return 100
        pixmap_size = self.current_pixmap.size()
        label_size = self.image_label.size()
        width_ratio = label_size.width() / pixmap_size.width()
        height_ratio = label_size.height() / pixmap_size.height()
        zoom_percentage = min(width_ratio, height_ratio) * 100
        return round(zoom_percentage)
