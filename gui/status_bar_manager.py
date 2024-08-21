import os
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QStatusBar


class StatusBarManager:
    def __init__(self, main_window, image_manager):
        self.main_window = main_window
        self.image_manager = image_manager
        self.status_bar = QStatusBar(main_window)

        self.status_label = QLabel("Status: Ready", main_window)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)  # Ensure text is left-aligned

        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.setSizeGripEnabled(False)
        self.main_window.setStatusBar(self.status_bar)

    def update_status_bar(self, file_path=None):
        if not file_path:
            file_path = self.image_manager.get_current_image_path()
            if not file_path:
                self.status_label.setText("No image loaded")
                self.status_label.setToolTip("No image loaded")
                return

        filename = self.get_filename(file_path)
        zoom_percentage = self.main_window.image_display.get_zoom_percentage()
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
