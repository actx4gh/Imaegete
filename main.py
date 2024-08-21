import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QWidget, QSplitter, QLabel

import logger
from gui.main_window import ImageSorterGUI


def log_widget_hierarchy(widget, level=0, visited=None):
    """
    Logs the hierarchy and properties of widgets starting from the given widget.

    Args:
        widget (QWidget): The root widget to start logging from.
        level (int, optional): The indentation level for nested widgets. Defaults to 0.
        visited (set, optional): Set of widget IDs that have already been logged. Defaults to None.
    """
    if visited is None:
        visited = set()

    widget_id = id(widget)

    if widget_id in visited:
        return  # Skip already logged widgets

    visited.add(widget_id)

    indent = "    " * level
    width = widget.geometry().width()
    height = widget.geometry().height()
    size_policy = widget.sizePolicy()
    size_hint = widget.sizeHint()

    # Log the widget with its Python object ID
    logger.debug(f"{indent}Widget: {widget.objectName() or 'Unnamed'}, Type: {type(widget).__name__}, "
                 f"Width: {width}px, Height: {height}px, ID: {hex(widget_id)}")
    logger.debug(f"{indent}    SizePolicy: Horizontal: {size_policy.horizontalPolicy()}, "
                 f"Vertical: {size_policy.verticalPolicy()}")
    logger.debug(f"{indent}    SizeHint: {size_hint.width()}px x {size_hint.height()}px")

    # Log margins if available
    if hasattr(widget, 'getContentsMargins'):
        left_margin, top_margin, right_margin, bottom_margin = widget.getContentsMargins()
        logger.debug(f"{indent}    Margins: Left: {left_margin}px, Right: {right_margin}px, "
                     f"Top: {top_margin}px, Bottom: {bottom_margin}px")
    else:
        logger.debug(f"{indent}    Margins: Not available for {type(widget).__name__}")

    # Log padding if available (example method, assuming there is a method to get padding)
    if hasattr(widget, 'getContentsPadding'):
        left_padding, top_padding, right_padding, bottom_padding = widget.getContentsPadding()
        logger.debug(f"{indent}    Padding: Left: {left_padding}px, Right: {right_padding}px, "
                     f"Top: {top_padding}px, Bottom: {bottom_padding}px")
    else:
        logger.debug(f"{indent}    Padding: Not available for {type(widget).__name__}")

    # Check for alignment
    if isinstance(widget, QLabel) or hasattr(widget, 'alignment'):
        alignment = widget.alignment()
        alignment_str = alignment_to_string(alignment)
        logger.debug(f"{indent}    Alignment: {alignment_str}")

    # Log text if widget is a QLabel
    if isinstance(widget, QLabel):
        logger.debug(f"{indent}    Text: {widget.text()}")

    # Check for layout information
    if widget.layout() is not None:
        layout = widget.layout()
        margins = layout.contentsMargins()
        logger.debug(f"{indent}    Layout: {type(layout).__name__}, Spacing: {layout.spacing()}, "
                     f"ContentsMargins: Left: {margins.left()}px, Right: {margins.right()}px, "
                     f"Top: {margins.top()}px, Bottom: {margins.bottom()}px")

    # Check for splitters
    if isinstance(widget, QSplitter):
        orientation = "Horizontal" if widget.orientation() == Qt.Orientation.Horizontal else "Vertical"
        logger.debug(f"{indent}    Splitter Orientation: {orientation}")

    # Recursively log child widgets
    for child in widget.findChildren(QWidget):
        log_widget_hierarchy(child, level + 1, visited)


def alignment_to_string(alignment):
    """
    Converts the alignment flag to a human-readable string.
    """
    alignments = []
    if alignment & Qt.AlignmentFlag.AlignLeft:
        alignments.append("AlignLeft")
    if alignment & Qt.AlignmentFlag.AlignRight:
        alignments.append("AlignRight")
    if alignment & Qt.AlignmentFlag.AlignHCenter:
        alignments.append("AlignHCenter")
    if alignment & Qt.AlignmentFlag.AlignTop:
        alignments.append("AlignTop")
    if alignment & Qt.AlignmentFlag.AlignBottom:
        alignments.append("AlignBottom")
    if alignment & Qt.AlignmentFlag.AlignVCenter:
        alignments.append("AlignVCenter")
    if alignment & Qt.AlignmentFlag.AlignCenter:
        alignments.append("AlignCenter")

    return " | ".join(alignments) if alignments else "AlignNone"


def main():
    app = QApplication(sys.argv)
    sorter_gui = ImageSorterGUI()
    log_widget_hierarchy(sorter_gui)
    sorter_gui.show()

    def on_exit():
        logger.info("[main] Application exit triggered")

    app.aboutToQuit.connect(on_exit)

    logger.info("[main] Application starting")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
