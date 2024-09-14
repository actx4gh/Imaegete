from PyQt6.QtCore import Qt, QObject
from PyQt6.QtWidgets import QLabel, QSizePolicy

from core import logger


class ImageDisplay(QObject):

    def __init__(self):
        super().__init__()
        self.image_label = QLabel()
        self.image_label.setObjectName("image_display_label")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(1, 1)

        self.image_label.setContentsMargins(0, 0, 0, 0)
        self.current_pixmap = None
        self.is_fullscreen = False

    def display_image(self, image_path, pixmap):
        logger.debug(f"[ImageDisplay] Attempting to display image: {image_path}")
        if pixmap and self.current_pixmap != pixmap:
            logger.info(f"[ImageDisplay] Displaying image: {image_path}")
            self.current_pixmap = pixmap
            self.update_image_label()
            logger.debug(f"[ImageDisplay] Image displayed: {image_path}")
        else:
            self.image_label.setText("No image to display.")
            self.clear_image()

    def update_image_label(self):
        logger.debug("[ImageDisplay] Updating image label.")
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.FastTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            logger.debug(f"[ImageDisplay] Updated image label size: {self.image_label.size()}")
        else:
            logger.debug("[ImageDisplay] No pixmap found, clearing image.")
            self.clear_image()

    def clear_image(self):
        logger.info("[ImageDisplay] Clearing image")
        self.current_pixmap = None
        self.image_label.clear()

    def get_zoom_percentage(self):
        if not self.current_pixmap:
            return 100
        pixmap_size = self.current_pixmap.size()
        label_size = self.image_label.size()
        width_ratio = label_size.width() / pixmap_size.width()
        height_ratio = label_size.height() / pixmap_size.height()
        zoom_percentage = min(width_ratio, height_ratio) * 100
        return round(zoom_percentage)

    def toggle_fullscreen(self, main):
        """Toggle full-screen display of the current image."""
        if self.is_fullscreen:
            main.toggle_fullscreen_layout()
            main.showNormal()
        else:
            main.toggle_fullscreen_layout()
            main.showFullScreen()

        self.image_label.resize(main.size())
        self.update_image_label()
        self.is_fullscreen = not self.is_fullscreen
        logger.debug(f"[ImageDisplay] Full-screen mode toggled: {self.is_fullscreen}")
