from PyQt6.QtGui import QPixmap


class ImageDisplayManager:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.current_image = None

    def update_image_display(self, image):
        pixmap = QPixmap.fromImage(image)
        self.current_image = pixmap
        self._update_ui()

    def _update_ui(self):
        self.event_bus.emit("update_image_display", self.current_image)
