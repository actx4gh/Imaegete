import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from core import config, logger
from glavnaqt.core import config as glavnaqt_config
from glavnaqt.ui.main_window import MainWindow
from key_binding.key_binder import bind_keys


class ImaegeteGUI(MainWindow):
    def __init__(self, image_display, image_manager, data_service, app_name=config.APP_NAME, *args, **kwargs):
        logger.debug("[ImaegeteGUI] Initializing ImaegeteGUI.")
        self.signals_connected = False
        self.cleanup_thread = None
        self.image_display = image_display
        self.app_name = app_name
        self.image_manager = image_manager
        self.data_service = data_service

        logger.debug(f"[ImaegeteGUI] Creating main GUI window {config.WINDOW_TITLE_SUFFIX}.")
        self._initialize_ui_components()
        super().__init__(*args, **kwargs)
        self.setWindowTitle(f"{self.app_name} - No image loaded")
        self.setup_interactive_status_bar()
        logger.debug("[ImaegeteGUI] UI configuration set up.")

        self._connect_signals()
        bind_keys(self, self.image_manager)
        self.image_manager.refresh_image_list()

        logger.debug("[ImaegeteGUI] Status bar manager configured and signals connected.")
        self.show()
        logger.debug("[ImaegeteGUI] Main window shown.")
        logger.debug("[ImaegeteGUI] Initial image load triggered.")

    def _initialize_ui_components(self):
        """Initialize UI components and configure settings."""
        logger.debug("[ImaegeteGUI] UI configuration set up.")
        glavnaqt_config.config.font_size = "Helvetica"
        glavnaqt_config.config.font_size = 13
        glavnaqt_config.config.splitter_handle_width = 3
        glavnaqt_config.config.enable_status_bar_manager = True
        glavnaqt_config.config.update_collapsible_section('top', self.format_category_keys(config.categories),
                                                          glavnaqt_config.ALIGN_CENTER)
        glavnaqt_config.config.update_collapsible_section('main_content', 'test main content',
                                                          alignment=glavnaqt_config.ALIGN_CENTER,
                                                          widget=self.image_display.image_label)
        glavnaqt_config.config.update_collapsible_section('bottom', 'test status bar',
                                                          alignment=glavnaqt_config.ALIGN_CENTER)

    def resizeEvent(self, event):
        """Override resizeEvent to add additional behavior while preserving base functionality."""
        if self.data_service.get_current_image_path():
            self.image_display.update_image_label()
            self.resize_emission_args['zoom_percentage'] = self.image_display.get_zoom_percentage()
        super().resizeEvent(event)

    def _connect_signals(self):
        """Connect signals. Ensures signals are connected only once."""
        self.image_manager.image_loaded.connect(self.update_ui_on_image_loaded)
        self.image_manager.image_cleared.connect(self.update_ui_on_image_cleared)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.signals_connected = True
        logger.debug("[ImaegeteGUI] Signals connected for image display.")

    def _disconnect_signals(self):
        """Disconnect signals to avoid memory leaks."""
        try:
            self.image_manager.image_cleared.disconnect(self.update_ui_on_image_cleared)
            self.customContextMenuRequested.disconnect(self.show_context_menu)
            self.image_manager.image_loaded.disconnect(self.update_ui_on_image_loaded)
            logger.debug("[ImaegeteGUI] Signals disconnected.")
        except TypeError:
            logger.debug("[ImaegeteGUI] No signals were connected or already disconnected.")

    def update_ui_on_image_loaded(self, file_path, pixmap):
        """UI update after image is loaded."""
        if self.image_display:
            self.image_display.display_image(file_path, pixmap)
        if self.status_bar:
            self.event_bus.emit('status_update', file_path, self.image_display.get_zoom_percentage())
        self.setWindowTitle(f"{self.app_name} - {os.path.basename(file_path)}")

    def update_ui_on_image_cleared(self):
        """Update the UI when the image is cleared."""
        if self.image_display:
            self.image_display.clear_image()

    def on_resize(self):
        self.log_resize_event()

    def setup_interactive_status_bar(self):
        """Setup status bar interaction after it is fully configured."""
        if self.status_label:
            self.status_label.mousePressEvent = self.status_bar_clicked
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _initialize_ui(self, collapsible_sections):
        """Ensure status_bar_manager is initialized before parent UI setup."""
        super()._initialize_ui(collapsible_sections)

    def log_resize_event(self):
        logger.info(f"[ImaegeteGUI] Window resized to {self.width()}x{self.height()}")

    def format_category_keys(self, categories):
        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def status_bar_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            segment = self.identify_segment(event.pos())
            if segment == "filename":
                self.open_file_location()
            elif segment == "zoom":
                self.adjust_zoom_level()
            elif segment == "date":
                self.open_file_properties()

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        if self.identify_segment(pos) == "filename":
            context_menu.addAction(QAction("Open File Location", self, triggered=self.open_file_location))
        elif self.identify_segment(pos) == "zoom":
            context_menu.addAction(QAction("Adjust Zoom", self, triggered=self.adjust_zoom_level))
        elif self.identify_segment(pos) == "date":
            context_menu.addAction(QAction("File Properties", self, triggered=self.open_file_properties))
        context_menu.exec(self.mapToGlobal(pos))

    def identify_segment(self, pos):
        return "filename" if pos.x() < 100 else "zoom" if pos.x() < 200 else "date"

    def open_file_location(self):
        current_image_path = self.data_service.get_current_image_path()
        if current_image_path:
            folder_path = os.path.dirname(current_image_path)
            os.startfile(folder_path)

    def adjust_zoom_level(self):

        pass

    def open_file_properties(self):
        current_image_path = self.data_service.get_current_image_path()
        if current_image_path:
            os.system(f'explorer /select,\"{current_image_path}\"')

    def closeEvent(self, event):
        """Handle the window close event to disconnect signals and perform cleanup."""
        logger.debug("[ImaegeteGUI] Closing ImaegeteGUI...")

        self._disconnect_signals()

        self.image_manager.shutdown()

        logger.debug("[ImaegeteGUI] Exiting application.")
        event.accept()
