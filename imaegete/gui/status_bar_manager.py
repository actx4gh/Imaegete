import os
from datetime import datetime

from PyQt6.QtCore import pyqtSlot, QMutex, QMutexLocker, QThread

from imaegete.core import logger
from glavnaqt.ui.status_bar_manager import StatusBarManager as BaseStatusBarManager


class ImaegeteStatusBarManager(BaseStatusBarManager):
    def __init__(self, thread_manager, data_service):
        super().__init__(thread_manager)
        self.data_service = data_service
        self.bar_data = {}
        self.bar_data_mutex = QMutex()  # Mutex for thread-safe access to bar_data

        # Subscribe to events
        self.event_bus.subscribe('image_loaded', self.update_status_bar_event)
        self.event_bus.subscribe('metadata_changed', self.update_status_bar_event)
        self.event_bus.subscribe('update_image_total', self.update_image_total_event)

    def update_status_bar_event(self, file_path=None, zoom_percentage=None):
        """
        Event handler for status bar updates.

        :param file_path: Path to the image file.
        :param zoom_percentage: Zoom percentage of the displayed image.
        """
        if self.status_label and self.status_label.isVisible():
            if file_path is None:
                file_path = self.data_service.get_current_image_path()

            if not file_path:
                self.update_status_for_no_image()
                return

            self.start_worker(file_path=file_path, zoom_percentage=zoom_percentage)

    def update_image_total_event(self):
        """
        Event handler to update the total number of images.
        """
        with QMutexLocker(self.bar_data_mutex):
            self.bar_data['image_index'] = self.data_service.get_current_index()
            self.bar_data['total_images'] = len(self.data_service.get_image_list())

        self.start_worker()

    def update_status_for_no_image(self):
        """
        Update the status bar when no image is loaded.
        """
        with QMutexLocker(self.bar_data_mutex):
            self.bar_data.clear()
        self.status_label.setText("No image loaded")
        self.status_label.setToolTip("")

    def _process_status_update(self, file_path=None, zoom_percentage=None, **kwargs):
        """
        Background task to process the status update.

        :param file_path: Path to the image file.
        :param zoom_percentage: Zoom percentage of the displayed image.
        """
        thread_id = int(QThread.currentThreadId())
        logger.debug(f"[ImaegeteStatusBarManager thread {thread_id}] processing status bar update")

        # Create a local copy of bar_data to avoid threading issues
        with QMutexLocker(self.bar_data_mutex):
            bar_data = self.bar_data.copy()

        if zoom_percentage is not None:
            bar_data['zoom_percentage'] = zoom_percentage

        if file_path:
            metadata = self.data_service.cache_manager.get_metadata(file_path)
            if not metadata:
                logger.warning(
                    f"[ImaegeteStatusBarManager thread {thread_id}] Metadata not found for {file_path}. Status bar information may be incomplete."
                )
                status_text = "No metadata available"
                tooltip_text = ""
                self.status_updated.emit(status_text, tooltip_text)
                return

            bar_data['filename'] = self.get_filename(file_path)
            bar_data['dimensions'] = self.get_image_dimensions(metadata)
            bar_data['file_size'] = self.get_file_size(metadata)
            bar_data['modification_date'] = self.get_modification_date(metadata)
            bar_data['image_index'] = self.data_service.get_current_index()
            bar_data['total_images'] = len(self.data_service.get_image_list())

        # Construct status text and tooltip
        status_text = self.construct_status_text(bar_data)
        tooltip_text = self.construct_tooltip_text(bar_data)

        # Update bar_data in the main thread
        self._pending_bar_data = bar_data

        # Emit the signal to update the GUI
        self.status_updated.emit(status_text, tooltip_text)

    @pyqtSlot(str, str)
    def update_status_bar(self, status_text, tooltip_text):
        """
        Slot to update the status bar GUI elements in the main thread.

        :param status_text: Text to display in the status bar.
        :param tooltip_text: Tooltip text for the status bar.
        """
        if self.status_label:
            self.status_label.setText(status_text)
            self.status_label.setToolTip(tooltip_text)

        # Update bar_data safely
        if hasattr(self, '_pending_bar_data'):
            with QMutexLocker(self.bar_data_mutex):
                self.bar_data.update(self._pending_bar_data)
            del self._pending_bar_data

    def construct_status_text(self, bar_data):
        """
        Construct the status bar text using the provided bar data.

        :param bar_data: Dictionary containing bar data.
        :return: The constructed status bar text.
        """
        image_index = bar_data.get('image_index', 0)
        total_images = bar_data.get('total_images', 0)
        zoom_percentage = bar_data.get('zoom_percentage', 'Unknown')
        dimensions = bar_data.get('dimensions', 'Unknown dimensions')
        file_size = bar_data.get('file_size', 'Unknown size')
        modification_date = bar_data.get('modification_date', 'Unknown date')

        return (
            f"📁 {image_index + 1}/{total_images} • 🔍 {zoom_percentage}% • "
            f"📏 {dimensions} • 💾 {file_size} • 📅 {modification_date}"
        )

    def construct_tooltip_text(self, bar_data):
        """
        Construct the status bar tooltip using the provided bar data.

        :param bar_data: Dictionary containing bar data.
        :return: The constructed tooltip text.
        """
        image_index = bar_data.get('image_index', 0)
        total_images = bar_data.get('total_images', 0)
        zoom_percentage = bar_data.get('zoom_percentage', 'Unknown')
        dimensions = bar_data.get('dimensions', 'Unknown dimensions')
        file_size = bar_data.get('file_size', 'Unknown size')
        modification_date = bar_data.get('modification_date', 'Unknown date')
        filename = bar_data.get('filename', 'Unknown file')

        return (
            f"Filename: {filename}\nZoom: {zoom_percentage}%\nDimensions: {dimensions}\n"
            f"File Size: {file_size}\nModification Date: {modification_date}\n"
            f"Image: {image_index + 1}/{total_images}"
        )

    def get_filename(self, file_path):
        """
        Get the filename from the given file path.

        :param file_path: Path of the image file.
        :return: The filename extracted from the path.
        """
        return os.path.basename(file_path)

    def get_image_dimensions(self, metadata):
        """
        Get the dimensions of the image from its metadata.

        :param metadata: Metadata dictionary containing image information.
        :return: The dimensions of the image as a string.
        """
        if 'size' in metadata:
            size = metadata['size']
            return f"{size.width()} x {size.height()} px"
        return "Unknown dimensions"

    def get_file_size(self, metadata):
        """
        Get the file size from the image metadata.

        :param metadata: Metadata dictionary containing file information.
        :return: The file size as a string.
        """
        if 'file_size' in metadata:
            size = metadata['file_size']
            return self._format_file_size(size)
        return "Unknown size"

    def get_modification_date(self, metadata):
        """
        Get the modification date of the image from its metadata.

        :param metadata: Metadata dictionary containing file information.
        :return: The modification date as a formatted string.
        """
        if 'last_modified' in metadata:
            return datetime.fromtimestamp(metadata['last_modified']).strftime('%Y-%m-%d %H:%M')
        return "Unknown date"

    def _format_file_size(self, size):
        """
        Format the file size into a human-readable format (e.g., KB, MB, GB).

        :param size: File size in bytes.
        :return: The formatted file size as a string.
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
