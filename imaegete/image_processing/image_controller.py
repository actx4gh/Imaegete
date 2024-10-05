from PyQt6.QtCore import QObject, QRecursiveMutex, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QPixmap

from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from imaegete.core.logger import logger


class ImageController(QObject):
    image_loaded = pyqtSignal(str, object)
    image_cleared = pyqtSignal()
    image_ready = pyqtSignal(str, object)

    def __init__(self, image_list_manager, image_loader, image_handler):
        super().__init__()
        self.image_list_manager = image_list_manager
        self.image_loader = image_loader
        self.image_handler = image_handler
        self.lock = QRecursiveMutex()
        self.current_displayed_image = None
        self.loading_images = set()  # Track currently loading images
        self.event_bus = create_or_get_shared_event_bus()
        self.image_ready.connect(self.send_image_to_display)
        self.image_list_manager.image_list_updated.connect(self.on_image_list_updated)
        self.last_cycle_type = 'next'  # Default cycle type is next
        self.cycle_interval = 3000  # Default cycle interval in milliseconds
        self.tap_times = []
        self.last_manual_cycle_type = None  # Track the last manual cycle type
        self.manual_cycle_timeout = 60000  # Timeout for manual taps (1 minute = 60000ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.cycle_images)
        self.timer_running = False  # Initialize the timer as not running
        self.tap_timer = QTimer(self)  # Timer to reset tap times after 1 minute of inactivity
        self.tap_timer.setSingleShot(True)
        self.tap_timer.timeout.connect(self.reset_tap_times)

    def cycle_images(self):
        """Automatically cycle through images based on the last cycle type."""
        if self.last_cycle_type == 'next':
            self.next_image(manual=False)  # Indicate this is automatic cycling
        elif self.last_cycle_type == 'previous':
            self.previous_image(manual=False)  # Indicate this is automatic cycling
        elif self.last_cycle_type == 'random':
            self.random_image(manual=False)  # Indicate this is automatic cycling

    def next_image(self, manual=True):
        """Handle the next image cycle."""
        if manual:
            self.handle_manual_cycle('next')  # Handle manual cycle and set rate
        self.last_cycle_type = 'next'
        image_path = self.image_list_manager.set_next_image()
        self.show_image(image_path)

    def previous_image(self, manual=True):
        """Handle the previous image cycle."""
        if manual:
            self.handle_manual_cycle('previous')  # Handle manual cycle and set rate
        self.last_cycle_type = 'previous'
        image_path = self.image_list_manager.set_previous_image()
        self.show_image(image_path)

    def random_image(self, manual=True):
        """Handle the random image cycle."""
        if manual:
            self.handle_manual_cycle('random')  # Handle manual cycle and set rate
        self.last_cycle_type = 'random'
        image_path = self.image_list_manager.set_random_image()
        self.show_image(image_path)

    def handle_manual_cycle(self, current_cycle_type):
        """Handle manual cycle and update the rate if the same cycle type is pressed twice in a row."""
        now = QTime.currentTime()

        # If the user switches cycle types, reset the rate and tap times
        if current_cycle_type != self.last_manual_cycle_type:
            self.tap_times.clear()
            self.last_manual_cycle_type = current_cycle_type
            self.tap_timer.start(self.manual_cycle_timeout)  # Start timeout countdown
            return  # No rate setting on first cycle type switch

        # If the same cycle type is pressed consecutively, calculate the rate
        self.tap_times.append(now)
        if len(self.tap_times) >= 2:
            interval = self.tap_times[-2].msecsTo(self.tap_times[-1])
            self.update_cycle_rate(interval)  # Set new cycle rate
            self.tap_times = self.tap_times[-2:]  # Keep the last two times for tracking
            self.tap_timer.start(self.manual_cycle_timeout)  # Restart the timeout timer

    def reset_tap_times(self):
        """Reset tap times after the timeout (1 minute of inactivity)."""
        self.tap_times.clear()
        self.last_manual_cycle_type = None

    def update_cycle_rate(self, interval):
        """Update the cycling interval based on key press interval."""
        self.cycle_interval = interval
        self.timer.setInterval(interval)  # Update the slideshow interval, but don't reset the timer

    def start_slideshow(self):
        """Start the timer for automatic cycling."""
        if not self.timer_running:
            self.timer.start(self.cycle_interval)
            self.timer_running = True

    def stop_slideshow(self):
        """Stop the timer, pause the slideshow, and reset the cycling rate to the default."""
        if self.timer_running:
            self.timer.stop()
            self.timer_running = False
            self.reset_cycle_rate()  # Reset to default rate when stopping the slideshow

    def reset_cycle_rate(self):
        """Reset the cycling interval to the default value."""
        self.cycle_interval = 3000  # Default cycle interval (3 seconds)
        self.timer.setInterval(self.cycle_interval)  # Ensure the timer is updated with the default interval

    def toggle_slideshow(self):
        """Toggle between start and stop for the slideshow."""
        if self.timer_running:
            self.stop_slideshow()
        else:
            self.start_slideshow()

    def track_key_press_and_set_rate(self):
        """Track key presses and adjust cycle rate."""
        now = QTime.currentTime()
        self.tap_times.append(now)

        # If the user presses a key twice in a row, calculate the time interval and set the rate
        if len(self.tap_times) >= 2:
            interval = self.tap_times[-2].msecsTo(self.tap_times[-1])
            self.update_cycle_rate(interval)  # Set new cycle rate
            self.tap_times = self.tap_times[-2:]  # Keep only the last two times to track

    def show_image(self, image_path=None):
        if image_path in self.loading_images:
            return
        elif not image_path:
            image_path = self.image_list_manager.data_service.get_current_image_path()

        def display_callback(image):
            self.loading_images.discard(image_path)
            if image:
                self.image_loaded.emit(image_path, image)
                self.current_displayed_image = image_path
            else:
                self.image_cleared.emit()

        self.loading_images.add(image_path)
        self.image_loader.load_image_async(image_path, display_callback)

    def first_image(self):
        image_path = self.image_list_manager.set_first_image()
        self.show_image(image_path)

    def last_image(self):
        image_path = self.image_list_manager.set_last_image()
        self.show_image(image_path)

    def send_image_to_display(self, image_path, image):
        pixmap = QPixmap.fromImage(image)
        self.image_loaded.emit(image_path, pixmap)
        self._hide_busy_indicator()

    def move_image(self, category):
        self.image_handler.move_current_image(category)
        self.show_image()

    def delete_image(self):
        self.image_handler.delete_current_image()
        self.show_image()

    def undo_last_action(self):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            self.show_image()

    def on_image_list_updated(self):
        """
        Handle the event when the image list is updated.
        Automatically display the first image from the list.
        """
        self.event_bus.emit("update_image_total")
        if not self.current_displayed_image:
            self.current_displayed_image = 'displaying'
            image_path = self.image_list_manager.data_service.get_current_image_path()
            if image_path:
                self.show_image(image_path)
            else:
                self.current_displayed_image = ''
                logger.error("[ImageController] Could not get current image from data service.")
        else:
            self._hide_busy_indicator()

    def _hide_busy_indicator(self):
        if not self.image_list_manager.refreshing:
            self.event_bus.emit('hide_busy')

    def shutdown(self):
        """
        Shutdown the ImageController safely.
        """
        self.image_list_manager.image_list_open_condition.wakeAll()
        self.image_list_manager.data_service.cache_manager.shutdown()
