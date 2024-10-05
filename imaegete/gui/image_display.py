from threading import Event

from PyQt6.QtCore import Qt, QTimer, QSize, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter, QMovie
from PyQt6.QtWidgets import QLabel, QSizePolicy

from imaegete.core import logger


class ImageDisplay(QLabel):

    def __init__(self):
        """
        Initialize the ImageDisplay class.

        Sets up the QLabel for image display and initializes necessary attributes like
        current_pixmap, fullscreen status, and label properties.
        """

        super().__init__()
        self.setObjectName("image_display_label")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        self.setContentsMargins(0, 0, 0, 0)
        self.fullscreen_toggling = Event()
        self.current_pixmap = None
        self.current_movie = None
        self._movie_size = QSize()
        self._min_size = QSize()
        self.current_frame_delay_offset = 0
        self.is_fullscreen = False
        self.timer = QTimer(self)
        self.image_label = self

    def minimumSizeHint(self):
        """Provide the minimum size hint based on the movie or pixmap size."""
        return self._min_size if self._min_size.isValid() else super().minimumSizeHint()

    def setMovie(self, movie):
        """
        Override the default setMovie method to handle movie size and state.
        This ensures the movie is scaled and plays properly.
        """
        if self.current_movie == movie:
            return

        super().setMovie(movie)

        if not isinstance(movie, QMovie) or not movie.isValid():
            self._movie_size = QSize()
            self._min_size = QSize()
            self.updateGeometry()
            return

        # Save the current frame and state of the movie
        current_frame = movie.currentFrameNumber()
        movie_state = movie.state()

        # Calculate the full size of the movie by iterating over the frames
        movie.jumpToFrame(0)
        rect = QRect()
        for _ in range(movie.frameCount()):
            movie.jumpToNextFrame()
            rect |= movie.frameRect()

        self._movie_size = QSize(rect.width(), rect.height())
        self._min_size = self.calculate_min_size(self._movie_size)

        # Restore the movie to the original frame and state
        movie.jumpToFrame(current_frame)
        if movie_state == QMovie.MovieState.Running:
            movie.setPaused(False)

        self.updateGeometry()

    def calculate_min_size(self, movie_size):
        """Calculate a reasonable minimum size based on the movie aspect ratio."""
        width = movie_size.width()
        height = movie_size.height()

        if width == height:
            base_size = 4 if width < 4 else width
            return QSize(base_size, base_size)
        else:
            minimum = min(width, height)
            maximum = max(width, height)
            ratio = maximum / minimum
            base = min(4, minimum)
            return QSize(base, round(base * ratio))

    def paintEvent(self, event):
        """
        Custom paint event to handle the scaling of QMovie frames while preserving aspect ratio.
        """
        movie = self.current_movie
        if movie and movie.isValid():
            painter = QPainter(self)
            content_rect = self.contentsRect()

            # Get the current movie frame as a pixmap
            frame_pixmap = movie.currentPixmap()

            if not frame_pixmap.isNull():
                # Scale the frame to fit within the content rect while preserving aspect ratio
                scaled_frame = frame_pixmap.scaled(
                    content_rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                # Center the scaled frame within the content rect
                x_offset = (content_rect.width() - scaled_frame.width()) // 2
                y_offset = (content_rect.height() - scaled_frame.height()) // 2

                # Draw the pixmap at the calculated position
                target_rect = QRect(x_offset, y_offset, scaled_frame.width(), scaled_frame.height())
                painter.drawPixmap(target_rect, scaled_frame)
            else:
                logger.debug("[ImageDisplay] No valid pixmap for the current frame.")
        else:
            super().paintEvent(event)

    def clear(self):
        """Clear the current movie or pixmap from the QLabel."""
        self.current_pixmap = None
        self.current_movie = None
        super().clear()

    def display_image(self, image):
        if isinstance(image, QImage):
            pixmap = QPixmap(image)
            self.display_pixmap(pixmap)
        elif isinstance(image, QMovie):
            movie = image
            self.display_movie(movie)

    def display_pixmap(self, pixmap):
        """
        Display the given image on the QLabel.

        :param pixmap: The QPixmap object representing the image.
        """

        if pixmap and self.current_pixmap != pixmap:
            self.current_pixmap = pixmap

            # Properly clean up the movie before switching to a pixmap
            if self.current_movie:
                logger.info("[ImageDisplay] Cleaning up movie before displaying pixmap.")
                self.current_movie.frameChanged.disconnect(self.on_frame_changed)
                self.current_movie = None

                # Stop and clear the timer
                if self.timer.isActive():
                    self.timer.stop()

            self.scale_and_apply_pixmap_to_label()
        elif not self.current_movie:
            self.image_label.setText("No image to display.")
            self.clear_image()

    def update_image_label(self):
        if self.current_pixmap:
            QTimer.singleShot(100, self.scale_and_apply_pixmap_to_label)
        elif self.current_movie:
            pass

    def display_movie(self, movie):
        """
        Display a QMovie (animated GIF) and ensure it plays the animation.
        """
        if movie and self.current_movie != movie:
            logger.info(f"[ImageDisplay] Displaying animated GIF.")
            if self.timer and self.timer.isActive():
                self.timer.stop()
                self.timer.timeout.disconnect()
            self.current_movie = movie
            self.current_pixmap = None

            self.setMovie(self.current_movie)

            # Ensure frameChanged is connected
            self.current_movie.frameChanged.connect(self.on_frame_changed)
            self.timer.timeout.connect(lambda: self.current_movie.jumpToNextFrame())
            self.timer.start(self.current_movie.nextFrameDelay())  # Use the actual frame delay

        elif not self.current_pixmap:
            self.image_label.setText("No image to display.")
            self.clear_image()

    def set_speed_offset(self, offset):
        """
        Set the frame delay offset for controlling animation speed.
        Positive values slow down the animation, negative values speed it up.
        """
        self.current_frame_delay_offset = offset
        logger.debug(f"[ImageDisplay] Animation speed adjusted with offset: {self.current_frame_delay_offset}")

    def normal_speed(self):
        """ Increase the animation speed by decreasing the delay. """
        self.set_speed_offset(0)

    def increase_speed(self, increment=10):
        """ Increase the animation speed by decreasing the delay. """
        self.set_speed_offset(self.current_frame_delay_offset - increment)

    def decrease_speed(self, decrement=10):
        """ Decrease the animation speed by increasing the delay. """
        self.set_speed_offset(self.current_frame_delay_offset + decrement)

    def on_frame_changed(self, frame_number):
        """
        Slot that handles frame changes in the QMovie.
        Ensures the movie animation progresses smoothly and applies the delay offset.
        """

        # Repaint the current frame
        self.repaint()

        # Stop the current timer before setting the new delay
        if self.timer.isActive():
            self.timer.stop()

        # Calculate the adjusted delay with the offset
        base_delay = self.current_movie.nextFrameDelay()
        adjusted_delay = max(1, base_delay + self.current_frame_delay_offset)  # Ensure delay is at least 1 ms

        # Start the timer with the adjusted delay
        self.timer.start(adjusted_delay)

    def scale_and_apply_pixmap_to_label(self):
        """
        Update the QLabel to display the current pixmap, scaling it to fit the label size.
        """

        logger.debug("[ImageDisplay] Updating image label.")
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            logger.debug(f"[ImageDisplay] Updated image label size: {self.image_label.size()}")
        elif self.current_movie:
            pass
        else:
            logger.debug("[ImageDisplay] No pixmap or movie found, clearing image.")
            self.clear_image()

    def clear_image(self):
        """
        Clear the image currently displayed on the QLabel.
        """

        logger.info("[ImageDisplay] Clearing image")
        self.current_pixmap = None
        self.current_movie = None
        self.image_label.clear()

    def get_zoom_percentage(self):
        """
        Calculate the zoom percentage based on the QLabel and pixmap sizes.

        :return: The zoom percentage as an integer.
        """

        if self.current_movie:
            pixmap_size = self.current_movie.currentPixmap().size()
        elif self.current_pixmap:
            pixmap_size = self.current_pixmap.size()
        else:
            return 100
        label_size = self.image_label.size()
        width_ratio = label_size.width() / pixmap_size.width()
        height_ratio = label_size.height() / pixmap_size.height()
        zoom_percentage = min(width_ratio, height_ratio) * 100
        return round(zoom_percentage)

    def toggle_fullscreen(self, main):
        """
        Toggle between full-screen and normal window mode.

        :param main: The main window object.
        """
        if self.fullscreen_toggling.is_set():
            return
        self.fullscreen_toggling.set()
        self.image_label.setUpdatesEnabled(False)
        if self.is_fullscreen:
            main.toggle_fullscreen_layout()
            main.showNormal()
        else:
            main.toggle_fullscreen_layout()
            main.showFullScreen()

        self.is_fullscreen = not self.is_fullscreen
        self._resize_and_update_label()

    def _resize_and_update_label(self):
        self.update_image_label()
        self.image_label.setUpdatesEnabled(True)
        self.fullscreen_toggling.clear()
        logger.debug(f"[ImageDisplay] Full-screen mode toggled: {self.is_fullscreen}")
