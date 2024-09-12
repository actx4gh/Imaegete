import os

from PyQt6.QtGui import QPixmap

from core import logger


def load_image_with_qpixmap(image_path):
    """
    Load an image using QPixmap and return the pixmap object.

    Args:
        image_path (str): The path of the image to load.

    Returns:
        QPixmap: The loaded pixmap object, or None if loading fails.
    """
    
    if not os.path.exists(image_path):
        logger.error(f"[ImageUtils] Image file does not exist: {image_path}")
        return None

    
    pixmap = QPixmap(image_path)

    
    if pixmap.isNull():
        logger.error(f"[ImageUtils] Failed to load image (unsupported format or corrupted file): {image_path}")
        return None

    return pixmap
