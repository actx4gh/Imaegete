from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QFrame, QLabel

import config
import logger
from .collapsible_splitter import CollapsibleSplitter
from .image_display import ImageDisplay

class UIInitializer:
    def __init__(self, main_window):
        self.main_window = main_window

    def init_ui(self):
        logger.info("[ImageSorterGUI] Initializing UI components")

        self.main_window.top_bar = QFrame(self.main_window)
        self.main_window.top_bar.setFrameShape(QFrame.Shape.NoFrame)
        self.main_window.top_bar_layout = QVBoxLayout(self.main_window.top_bar)
        self.main_window.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.main_window.top_bar_layout.setSpacing(0)
        self.main_window.top_bar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.main_window.category_label = QLabel(self.format_category_keys(config.categories), self.main_window)
        self.main_window.category_label.setFont(QFont("Helvetica", 8))
        self.main_window.category_label.setStyleSheet("color: black;")
        self.main_window.top_bar_layout.addWidget(self.main_window.category_label)

        self.main_window.top_splitter = CollapsibleSplitter(Qt.Orientation.Vertical, 3)
        self.main_window.top_splitter.setContentsMargins(0, 0, 0, 0)
        self.main_window.top_splitter.addWidget(self.main_window.top_bar)

        self.main_window.image_display = ImageDisplay()
        self.main_window.image_display.image_changed.connect(self.main_window.status_bar_manager.update_status_bar)
        self.main_window.top_splitter.addWidget(self.main_window.image_display.get_widget())
        self.main_window.main_layout.addWidget(self.main_window.top_splitter)

        self.main_window.bottom_splitter = CollapsibleSplitter(Qt.Orientation.Vertical, 3)
        self.main_window.bottom_splitter.setBottomSplitter(True)
        self.main_window.bottom_splitter.setContentsMargins(0, 0, 0, 0)
        self.main_window.bottom_splitter.addWidget(self.main_window.top_splitter)
        self.main_window.bottom_splitter.addWidget(self.main_window.status_bar_manager.status_bar)
        self.main_window.main_layout.addWidget(self.main_window.bottom_splitter)

        self.main_window.top_splitter.setCollapsible(0, True)
        self.main_window.top_splitter.setCollapsible(1, False)
        self.main_window.bottom_splitter.setCollapsible(0, False)
        self.main_window.bottom_splitter.setCollapsible(1, True)

        self.main_window.adjust_layout()
        logger.info("[ImageSorterGUI] Finished initializing UI components")

    def format_category_keys(self, categories):
        key_mapping = {str(i + 1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])
