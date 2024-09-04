import os
from datetime import datetime

import logger
from glavnaqt.ui.status_bar_manager import StatusBarManager as BaseStatusBarManager


class ImageSorterStatusBarManager(BaseStatusBarManager):

    def __init__(self, image_manager):
        super().__init__()  # Initializes the event bus in the parent class
        self.image_manager = image_manager
        self.bar_data = {}

        # Use the event bus from the parent class
        self.event_bus.subscribe('image_loaded', self.update_status_bar)
        self.event_bus.subscribe('metadata_changed', self.update_status_bar)

    def update_status_bar(self, file_path=None, zoom_percentage=None):
        """Override and augment the update_status_bar method from the base class."""
        if file_path is None:
            file_path = self.image_manager.get_current_image_path()

        if not file_path:
            self.update_status_for_no_image()
            return

        self.start_worker(file_path=file_path, zoom_percentage=zoom_percentage)

    def update_status_for_no_image(self):
        """Update the status bar when there is no image loaded."""
        self.bar_data.clear()
        self.status_label.setText("No image loaded")
        self.status_label.setToolTip("")

    def start_worker(self, *args, **kwargs):
        """Override start_worker to initialize StatusBarUpdateWorker with custom logic."""

        # Custom logic to avoid redundant worker starts
        if self.worker and self.worker.isRunning():
            # If a worker is already running, avoid starting a new one
            # logger.debug("Worker already running; skipping start_worker.")
            return

        # Start the worker with necessary parameters
        super().start_worker(*args, **kwargs)

        # Adjust the signal handling for the worker
        self.worker.status_updated.disconnect()
        self.worker.status_updated.connect(
            lambda text, tooltip: self._process_status_update(file_path=kwargs.get('file_path'),
                                                              zoom_percentage=kwargs.get('zoom_percentage'))
        )

        self.worker.start()

    def _process_status_update(self, file_path=None, zoom_percentage=None):
        """Fetch data and perform status update in the main thread after worker processing."""
        # Ensure updates are made appropriately
        if zoom_percentage is not None:
            self.bar_data['zoom_percentage'] = zoom_percentage

        if file_path:
            metadata = self.image_manager.current_metadata or self.image_manager.image_cache.get_metadata(file_path)
            if not metadata:
                logger.warning(f"Metadata not found for {file_path}. Status bar information may be incomplete.")
                super().update_status_bar("No metadata available")
                return

            self.bar_data['filename'] = self.get_filename(file_path)
            self.bar_data['dimensions'] = self.get_image_dimensions(metadata)
            self.bar_data['file_size'] = self.get_file_size(metadata)
            self.bar_data['modification_date'] = self.get_modification_date(metadata)
            self.bar_data['image_index'] = self.image_manager.get_current_image_index()
            self.bar_data['total_images'] = len(self.image_manager.image_handler.image_list)

        self.status_label.setText(self.status_text)
        self.status_label.setToolTip(self.tooltip_text)

    def get_bar_data_value(self, key, default):
        """Helper method to retrieve bar data values with default fallback."""
        value = self.bar_data.get(key, default)
        return value if value is not None else default

    @property
    def status_text(self):
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
        return os.path.basename(file_path)

    def get_image_dimensions(self, metadata):
        if 'size' in metadata:
            size = metadata['size']
            return f"{size.width()} x {size.height()} px"
        return "Unknown dimensions"

    def get_file_size(self, metadata):
        if 'file_size' in metadata:
            size = metadata['file_size']
            return self._format_file_size(size)
        return "Unknown size"

    def get_modification_date(self, metadata):
        if 'last_modified' in metadata:
            return datetime.fromtimestamp(metadata['last_modified']).strftime('%Y-%m-%d %H:%M')
        return "Unknown date"

    def _format_file_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
