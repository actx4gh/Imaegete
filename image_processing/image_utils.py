from PyQt6.QtGui import QPixmap

import logger


def load_image_with_qpixmap(image_path):
    """
    Load an image using QPixmap and return the pixmap object.

    Args:
        image_path (str): The path of the image to load.

    Returns:
        QPixmap: The loaded pixmap object, or None if loading fails.
    """
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        logger.error(f"Failed to load image: {image_path}")
        return None
    return pixmap
