import os
import threading
from datetime import datetime

from core import logger
from glavnaqt.ui.status_bar_manager import StatusBarManager as BaseStatusBarManager


class ImaegeteStatusBarManager(BaseStatusBarManager):

    def __init__(self, thread_manager, data_service):
        """
        Initialize the ImaegeteStatusBarManager class.

        Sets up the event bus subscriptions and initializes the thread manager and data service.

        :param thread_manager: Manages background threads for tasks.
        :param data_service: Manages data related to images and metadata.
        """

        super().__init__()
        self.thread_manager = thread_manager
        self.data_service = data_service
        self.bar_data = {}

        self.event_bus.subscribe('image_loaded', self.update_status_bar)
        self.event_bus.subscribe('metadata_changed', self.update_status_bar)
        self.event_bus.subscribe('update_image_total', self.update_image_total)
        self.event_bus.subscribe('show_busy', self.start_busy_indicator)
        self.event_bus.subscribe('hide_busy', self.stop_busy_indicator)

    def update_status_bar(self, file_path=None, zoom_percentage=None):
        """
        Update the status bar with image file path and zoom percentage.

        :param file_path: Path of the image file.
        :param zoom_percentage: Zoom percentage of the displayed image.
        """

        if self.status_label.isVisible():
            if file_path is None:
                file_path = self.data_service.get_current_image_path()

            if not file_path:
                self.update_status_for_no_image()
                return

            self.start_worker(file_path=file_path, zoom_percentage=zoom_percentage)

    def update_image_total(self):
        """
        Update the status bar to show the total number of images.

        This method overrides the base class's update method and focuses on updating metadata.
        """

        self.bar_data['image_index'] = self.data_service.get_current_index()
        self.bar_data['total_images'] = len(self.data_service.get_image_list())

        self.start_worker(file_path=None, zoom_percentage=None)

    def update_status_for_no_image(self):
        """
        Update the status bar when no image is loaded.

        Clears the status bar data and resets the status text.
        """

        self.bar_data.clear()
        self.status_label.setText("No image loaded")
        self.status_label.setToolTip("")

    def start_worker(self, *args, **kwargs):

        """
        Start a worker thread to process the status update.

        This method prevents starting a new worker if the current one is still running.
        """

        if self.worker and self.worker.isRunning():
            return

        self.thread_manager.submit_task(self._process_status_update, *args, **kwargs)

    def _process_status_update(self, file_path=None, zoom_percentage=None):
        """
        Process the status update task, fetching data and updating the status bar.

        :param file_path: Path of the image file.
        :param zoom_percentage: Zoom percentage of the displayed image.
        """
        thread_id = threading.get_ident()
        f"[StatusBarManager thread {thread_id}] processing status bar update"
        if zoom_percentage is not None:
            self.bar_data['zoom_percentage'] = zoom_percentage

        if file_path:
            metadata = self.data_service.cache_manager.get_metadata(file_path)
            if not metadata:
                logger.warning(
                    f"[StatusBarManager thread {thread_id}] Metadata not found for {file_path}. Status bar information may be incomplete."
                )
                super().update_status_bar("No metadata available")
                return

            self.bar_data['filename'] = self.get_filename(file_path)
            self.bar_data['dimensions'] = self.get_image_dimensions(metadata)
            self.bar_data['file_size'] = self.get_file_size(metadata)
            self.bar_data['modification_date'] = self.get_modification_date(metadata)
            self.bar_data['image_index'] = self.data_service.get_current_index()
            self.bar_data['total_images'] = len(self.data_service.get_image_list())

        self.status_label.setText(self.status_text)
        self.status_label.setToolTip(self.tooltip_text)

    def get_bar_data_value(self, key, default):
        """
        Retrieve a value from the status bar data with a default fallback.

        :param key: The key to search for in the bar data.
        :param default: The default value to return if the key is not found.
        :return: The value corresponding to the key or the default value.
        """

        value = self.bar_data.get(key, default)
        return value if value is not None else default

    @property
    def status_text(self):
        """
        Property that constructs the status bar text using the current bar data.

        :return: The constructed status bar text.
        """

        image_index = self.get_bar_data_value('image_index', 0)
        total_images = self.get_bar_data_value('total_images', 0)
        zoom_percentage = self.get_bar_data_value('zoom_percentage', 'Unknown')
        dimensions = self.get_bar_data_value('dimensions', 'Unknown dimensions')
        file_size = self.get_bar_data_value('file_size', 'Unknown size')
        modification_date = self.get_bar_data_value('modification_date', 'Unknown date')

        return (
            f"📁 {image_index + 1}/{total_images} • 🔍 {zoom_percentage}% • "
            f"📏 {dimensions} • 💾 {file_size} • 📅 {modification_date}"
        )

    @property
    def tooltip_text(self):
        """
        Property that constructs the status bar tooltip using the current bar data.

        :return: The constructed tooltip text.
        """

        image_index = self.get_bar_data_value('image_index', 0)
        total_images = self.get_bar_data_value('total_images', 0)
        zoom_percentage = self.get_bar_data_value('zoom_percentage', 'Unknown')
        dimensions = self.get_bar_data_value('dimensions', 'Unknown dimensions')
        file_size = self.get_bar_data_value('file_size', 'Unknown size')
        modification_date = self.get_bar_data_value('modification_date', 'Unknown date')
        filename = self.get_bar_data_value('filename', 'Unknown file')

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
