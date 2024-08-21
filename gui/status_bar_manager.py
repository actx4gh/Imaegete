# image_sorter/status_bar_manager.py

import os
from datetime import datetime

from glavnaqt.ui.status_bar_manager import StatusBarManager as BaseStatusBarManager


class ImageSorterStatusBarManager(BaseStatusBarManager):
    def __init__(self, main_window, image_manager):
        super().__init__(main_window)  # Initialize the base StatusBarManager
        self.image_manager = image_manager

    def connect_signals(self, image_controller):
        image_controller.image_loaded_signal.connect(self.update_status_bar)
        image_controller.image_cleared_signal.connect(lambda: self.update_status_bar("No image loaded"))

    def update_status_bar(self, file_path=None):
        """Updates the status bar with custom image information."""
        if not file_path:
            file_path = self.image_manager.get_current_image_path()
            if not file_path:
                super().update_status_bar("No image loaded")
                return

        filename = self.get_filename(file_path)
        zoom_percentage = self.main_window.image_display.get_zoom_percentage()
        dimensions = self.get_image_dimensions(file_path)
        file_size = self.get_file_size(file_path)
        modification_date = self.get_modification_date(file_path)
        image_index = self.image_manager.get_current_image_index()
        total_images = len(self.image_manager.image_handler.image_list)

        status_text = (f"📁 {image_index + 1}/{total_images} • 🔍 {zoom_percentage}% • "
                       f"📏 {dimensions} • 💾 {file_size} • 📅 {modification_date}")
        super().update_status_bar(status_text)

        self.status_label.setToolTip(
            f"Filename: {filename}\nZoom: {zoom_percentage}%\nDimensions: {dimensions}\n"
            f"File Size: {file_size}\nModification Date: {modification_date}\n"
            f"Image: {image_index + 1}/{total_images}"
        )

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
