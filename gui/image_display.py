from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QLabel, QSizePolicy, QMessageBox, QVBoxLayout, QWidget


class ImageDisplay:
    def __init__(self, logger):
        self.logger = logger
        self.widget = QWidget()
        self.layout = QVBoxLayout(self.widget)

        # Remove margins and paddings
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.image_label = QLabel(self.widget)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(1, 1)

        # Remove margins from the label
        self.image_label.setContentsMargins(0, 0, 0, 0)

        self.layout.addWidget(self.image_label)
        self.current_pixmap = None

    def get_widget(self):
        return self.widget

    def display_image(self, image_path, image):
        if image:
            self.logger.info(f"[ImageDisplay] Displaying image: {image_path}")
            qimage = self.pil_to_qimage(image)
            self.current_pixmap = QPixmap.fromImage(qimage)
            self.update_image_label()
        else:
            self.logger.error("[ImageDisplay] Error: No image to display")
            QMessageBox.critical(self.widget, "Error", "No image to display!")

    def clear_image(self):
        self.logger.info("[ImageDisplay] Clearing image")
        self.current_pixmap = None
        self.image_label.clear()

    def schedule_update_image_label(self):
        if self.update_timer.isActive():
            self.update_timer.stop()
        self.update_timer.start(300)  # Adjust the debounce period as needed

    def update_image_label(self):
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio,
                                                       Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.clear_image()

    def pil_to_qimage(self, pil_image):
        pil_image = pil_image.convert("RGBA")
        data = pil_image.tobytes("raw", "RGBA")
        qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
        return qimage
