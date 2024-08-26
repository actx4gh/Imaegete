import os
from datetime import datetime

import logger
from glavnaqt.ui.status_bar_manager import StatusBarManager as BaseStatusBarManager


class ImageSorterStatusBarManager(BaseStatusBarManager):
    def __init__(self, image_manager):
        logger.debug("Initializing ImageSorterStatusBarManager.")
        super().__init__()  # Initialize the base StatusBarManager
        self.image_manager = image_manager
        self.main_window = None

    def set_main_window(self, main_window):
        logger.debug("Configuring StatusBarManager with main window.")
        self.main_window = main_window
        super().set_main_window(main_window)

    def connect_signals(self, image_controller):
        logger.debug("Connecting signals for StatusBarManager.")
        image_controller.image_loaded_signal.connect(self.update_status_bar)
        logger.debug("Connected image_loaded_signal to update_status_bar.")
        image_controller.image_cleared_signal.connect(lambda: self.update_status_bar("No image loaded"))
        logger.debug("Connected image_cleared_signal to update_status_bar with 'No image loaded'.")
        self.image_manager.image_list_changed.connect(self.update_status_bar)
        logger.debug("Connected image_list_changed to update_status_bar.")

    def update_status_bar(self, file_path=None):
        logger.debug(f"update_status_bar called with file_path: {file_path}")
        if not self.main_window or not self.status_label:
            logger.error("Main window or status label is not initialized.")
            return
        logger.debug(f"update_status_bar called with file_path: {file_path}")
        if not file_path:
            file_path = self.image_manager.get_current_image_path()
            logger.debug(f"Retrieved file_path from image_manager: {file_path}")
            if not file_path:
                super().update_status_bar("No image loaded")
                return

        # Use the in-memory metadata if available
        metadata = self.image_manager.current_metadata
        logger.debug(f"Retrieved metadata: {metadata}")
        if not metadata:
            logger.warning(f"Metadata not found for {file_path}. Status bar information may be incomplete.")
            super().update_status_bar("No metadata available")
            return

        filename = self.get_filename(file_path)
        zoom_percentage = self.main_window.image_display.get_zoom_percentage()
        dimensions = self.get_image_dimensions(metadata)
        file_size = self.get_file_size(metadata)
        modification_date = self.get_modification_date(metadata)
        image_index = self.image_manager.get_current_image_index()
        total_images = len(self.image_manager.image_handler.image_list)

        status_text = (f"📁 {image_index + 1}/{total_images} • 🔍 {zoom_percentage}% • "
                       f"📏 {dimensions} • 💾 {file_size} • 📅 {modification_date}")

        if self.status_label.text() == status_text:
            logger.debug("Status bar text is already up-to-date, skipping update.")
            return

        logger.debug(f"Setting status_text with text: {status_text}")
        super().update_status_bar(status_text)

        tooltip_text = (
            f"Filename: {filename}\nZoom: {zoom_percentage}%\nDimensions: {dimensions}\n"
            f"File Size: {file_size}\nModification Date: {modification_date}\n"
            f"Image: {image_index + 1}/{total_images}"
        )
        logger.debug(f"Setting tooltip with text: {tooltip_text}")
        self.status_label.setToolTip(tooltip_text)

    def get_filename(self, file_path):
        return os.path.basename(file_path)

    def get_image_dimensions(self, metadata):
        if 'size' in metadata:
            size = metadata['size']
            logger.info(f"Using cached dimensions: {size.width()} x {size.height()} px")
            return f"{size.width()} x {size.height()} px"
        logger.warning("Unknown dimensions")
        return "Unknown dimensions"

    def get_file_size(self, metadata):
        if 'file_size' in metadata:
            size = metadata['file_size']
            logger.info(f"File size: {size} bytes")
            return self._format_file_size(size)
        logger.warning("Unknown size")
        return "Unknown size"

    def get_modification_date(self, metadata):
        if 'last_modified' in metadata:
            mod_date = datetime.fromtimestamp(metadata['last_modified']).strftime('%Y-%m-%d %H:%M')
            logger.info(f"Modification date: {mod_date}")
            return mod_date
        logger.warning("Unknown modification date")
        return "Unknown date"

    def _format_file_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
