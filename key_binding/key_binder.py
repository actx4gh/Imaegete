from PyQt6.QtGui import QKeySequence, QShortcut

from core import config
from core.config import NEXT_KEY, PREV_KEY, FIRST_KEY, LAST_KEY, UNDO_KEY, DELETE_KEY, RANDOM_KEY, FULLSCREEN_KEY


def bind_keys(gui, image_manager):
    """
    Bind keyboard shortcuts to actions in the GUI.

    This function creates QShortcuts for various key sequences, such as navigation between images,
    deletion of images, toggling fullscreen, and other image management functions. The shortcuts are
    connected to methods within the image_manager and gui.

    :param gui: The main GUI window where shortcuts will be applied.
    :param image_manager: The image manager responsible for handling image-related operations.
    """

    if config.categories:
        key_mapping = {str(i + 1): cat for i, cat in enumerate(config.categories)}
        for key, category in key_mapping.items():
            shortcut = QShortcut(QKeySequence(key), gui)
            shortcut.activated.connect(lambda c=category: image_manager.move_image(c))
    delete_shortcut = QShortcut(QKeySequence(DELETE_KEY), gui)
    delete_shortcut.activated.connect(image_manager.delete_image)
    next_shortcut = QShortcut(QKeySequence(NEXT_KEY), gui)
    next_shortcut.activated.connect(image_manager.next_image)
    prev_shortcut = QShortcut(QKeySequence(PREV_KEY), gui)
    prev_shortcut.activated.connect(image_manager.previous_image)
    first_shortcut = QShortcut(QKeySequence(FIRST_KEY), gui)
    first_shortcut.activated.connect(image_manager.first_image)
    last_shortcut = QShortcut(QKeySequence(LAST_KEY), gui)
    last_shortcut.activated.connect(image_manager.last_image)
    undo_shortcut = QShortcut(QKeySequence(UNDO_KEY), gui)
    undo_shortcut.activated.connect(image_manager.undo_last_action)
    undo_shortcut = QShortcut(QKeySequence(RANDOM_KEY), gui)
    undo_shortcut.activated.connect(image_manager.random_image)
    fullscreen_shortcut = QShortcut(QKeySequence(FULLSCREEN_KEY), gui)
    fullscreen_shortcut.activated.connect(lambda: gui.image_display.toggle_fullscreen(gui))
