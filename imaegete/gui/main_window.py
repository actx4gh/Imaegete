import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from imaegete.core import config, logger
from glavnaqt.core import config as ui_config
from glavnaqt.ui.main_window import MainWindow
from imaegete.key_binding.key_binder import bind_keys


class ImaegeteGUI(MainWindow):
    def __init__(self, image_display, image_controller, data_service, app_name=config.APP_NAME, *args, **kwargs):
        """
        Initialize the ImaegeteGUI class with the provided parameters.

        :param image_display: Object responsible for displaying images.
        :param image_controller: Manager handling image operations like loading and clearing.
        :param data_service: Service managing data related to images.
        :param app_name: The name of the application (default: config.APP_NAME).
        :param args: Additional arguments passed to the parent class.
        :param kwargs: Keyword arguments passed to the parent class.
        """

        logger.debug("[ImaegeteGUI] Initializing ImaegeteGUI.")
        self.signals_connected = False
        self.ui_config = ui_config
        self.cleanup_thread = None
        self.image_display = image_display
        self.image_display.image_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.app_name = app_name
        self.image_controller = image_controller
        self.data_service = data_service

        logger.debug(f"[ImaegeteGUI] Creating main GUI window {config.WINDOW_TITLE_SUFFIX}.")
        self._initialize_ui_components()
        super().__init__(*args, **kwargs)
        self.setWindowTitle(f"{self.app_name} - No image loaded")
        self._connect_signals()
        self.setup_interactive_status_bar()
        logger.debug("[ImaegeteGUI] UI configuration set up.")

        bind_keys(self, self.image_controller)

        self.show()
        logger.debug("[ImaegeteGUI] Main window shown.")

    def _initialize_ui_components(self):

        """
        Initialize the UI components and apply necessary configuration settings.

        This method sets up various aspects of the user interface, including
        fonts, splitter handle width, status bar configuration, and collapsible sections.
        """

        logger.debug("[ImaegeteGUI] UI configuration set up.")
        self.ui_config.font_size = "Helvetica"
        self.ui_config.font_size = 13
        self.ui_config.splitter_handle_width = 3
        self.ui_config.enable_status_bar_manager = True
        if config.categories:
            self.ui_config.update_collapsible_section('top', self.format_category_keys(config.categories),
                                                              self.ui_config.ALIGN_CENTER)
        self.ui_config.update_collapsible_section('main_content', 'test main content',
                                                          alignment=self.ui_config.ALIGN_CENTER,
                                                          widget=self.image_display.image_label)
        self.ui_config.update_collapsible_section('bottom', 'test status bar',
                                                          alignment=self.ui_config.ALIGN_CENTER)

    def resizeEvent(self, event):

        """
        Handle the window resize event and apply custom behavior for the ImaegeteGUI.

        :param event: The resize event containing information about the new window size.
        """

        if self.data_service.get_current_image_path():
            self.image_display.update_image_label()
            self.resize_emission_args['zoom_percentage'] = self.image_display.get_zoom_percentage()
        super().resizeEvent(event)

    def _connect_signals(self):
        """
        Connect signals to their respective slots. Ensures signals are connected only once.
        """

        self.image_controller.image_loaded.connect(self.update_ui_on_image_loaded)
        self.image_controller.image_cleared.connect(self.update_ui_on_image_cleared)
        self.image_display.image_label.customContextMenuRequested.connect(self.show_context_menu)
        self.signals_connected = True
        logger.debug("[ImaegeteGUI] Signals connected for image display.")

    def _disconnect_signals(self):

        """
        Disconnect signals to avoid memory leaks when the window is closed or signals need to be reset.
        """

        try:
            self.image_controller.image_cleared.disconnect(self.update_ui_on_image_cleared)
            self.image_display.image_label.customContextMenuRequested.disconnect(self.show_context_menu)
            self.image_controller.image_loaded.disconnect(self.update_ui_on_image_loaded)
            logger.debug("[ImaegeteGUI] Signals disconnected.")
        except TypeError:
            logger.debug("[ImaegeteGUI] No signals were connected or already disconnected.")

    def update_ui_on_image_loaded(self, file_path, pixmap):
        """
        Update the UI when a new image is loaded.

        :param file_path: The path to the loaded image file.
        :param pixmap: The QPixmap representation of the loaded image.
        """
        if self.image_display:
            self.image_display.display_image(file_path, pixmap)
        if self.status_bar:
            self.event_bus.emit('status_update', file_path, self.image_display.get_zoom_percentage())
        self.setWindowTitle(f"{self.app_name} - {os.path.basename(file_path)}")
        logger.debug(f'[ImaegeteGUI] UI updated for loaded image {file_path}')

    def update_ui_on_image_cleared(self):
        """
        Update the UI when the currently displayed image is cleared from the screen.
        """

        if self.image_display:
            self.image_display.clear_image()

    def on_resize(self):
        """
        Log and handle the resize event. Triggered when the window size changes.
        """

        self.log_resize_event()

    def setup_interactive_status_bar(self):
        """
        Setup the status bar to allow interaction with the user, such as clicking events.
        """

        if self.status_label:
            self.status_label.mousePressEvent = self.status_bar_clicked
        self.status_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def log_resize_event(self):
        """
        Log information about the window resize event, including the new width and height.
        """

        logger.debug(f"[ImaegeteGUI] Window resized to {self.width()}x{self.height()}")

    def format_category_keys(self, categories):
        """
        Format the category keys for display in the UI.

        :param categories: A list of category names.
        :return: A formatted string representing the category keys.
        """

        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def status_bar_clicked(self, event):
        """
        Handle clicks on the status bar to trigger actions like opening file location or adjusting zoom.

        :param event: The mouse click event with position information.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            segment = self.identify_segment(event.pos())
            if segment == "filename":
                self.open_file_location()
            elif segment == "zoom":
                self.adjust_zoom_level()
            elif segment == "date":
                self.open_file_properties()

    def show_context_menu(self, pos):
        """
        Display a context menu based on the user's right-click position in the UI.

        :param pos: The position where the context menu should be shown.
        """

        context_menu = QMenu(self)
        if self.identify_segment(pos) == "filename":
            context_menu.addAction(QAction("Open File Location", self, triggered=self.open_file_location))
        elif self.identify_segment(pos) == "zoom":
            context_menu.addAction(QAction("Adjust Zoom", self, triggered=self.adjust_zoom_level))
        elif self.identify_segment(pos) == "date":
            context_menu.addAction(QAction("File Properties", self, triggered=self.open_file_properties))
        context_menu.exec(self.mapToGlobal(pos))

    def identify_segment(self, pos):
        """
        Identify the UI segment (filename, zoom, or date) based on the mouse click position.

        :param pos: The position of the mouse click.
        :return: The identified segment ("filename", "zoom", or "date").
        """

        return "filename" if pos.x() < 100 else "zoom" if pos.x() < 200 else "date"

    def open_file_location(self):
        """
        Open the file explorer at the location of the currently loaded image.
        """

        current_image_path = self.data_service.get_current_image_path()
        if current_image_path:
            folder_path = os.path.dirname(current_image_path)
            os.startfile(folder_path)

    def adjust_zoom_level(self):
        """
        Adjust the zoom level of the displayed image. (Functionality not yet implemented)
        """
        pass

    def open_file_properties(self):
        """
        Open the file properties for the currently loaded image.
        """

        current_image_path = self.data_service.get_current_image_path()
        if current_image_path:
            os.system(f'explorer /select,\"{current_image_path}\"')

    def closeEvent(self, event):
        """
        Handle the window close event. This method ensures that signals are disconnected
        and any necessary cleanup is performed before the application exits.

        :param event: The close event triggering the shutdown.
        """
        logger.debug("[CustomMainWindow] Closing CustomMainWindow...")

        # Perform custom cleanup
        self._disconnect_signals()
        self.image_controller.shutdown()

        # Ensure that MainWindow shutdown logic is executed
        super().closeEvent(event)  # Calls the parent MainWindow's closeEvent to handle ThreadManager shutdown

        logger.debug("[CustomMainWindow] Exiting application.")
        event.accept()
