from PyQt6.QtGui import QKeySequence, QShortcut

from imaegete.core import config
from imaegete.core.config import NEXT_KEY, PREV_KEY, FIRST_KEY, LAST_KEY, UNDO_KEY, DELETE_KEY, RANDOM_KEY, FULLSCREEN_KEY, \
    QUIT_KEY, SLIDE_SHOW_KEY, SPEED_UP_KEY, SPEED_DOWN_KEY


def bind_keys(gui, image_controller, image_display):
    """
    Bind keyboard shortcuts to actions in the GUI.

    This function creates QShortcuts for various key sequences, such as navigation between images,
    deletion of images, toggling fullscreen, and other image management functions. The shortcuts are
    connected to methods within the image_controller and gui.

    :param image_display:
    :param gui: The main GUI window where shortcuts will be applied.
    :param image_controller: The image controller responsible for handling image-related operations.
    """

    if config.categories:
        key_mapping = {str(i + 1): cat for i, cat in enumerate(config.categories)}
        for key, category in key_mapping.items():
            shortcut = QShortcut(QKeySequence(key), gui)
            shortcut.activated.connect(lambda c=category: image_controller.move_image(c))
    delete_shortcut = QShortcut(QKeySequence(DELETE_KEY), gui)
    delete_shortcut.activated.connect(image_controller.delete_image)
    next_shortcut = QShortcut(QKeySequence(NEXT_KEY), gui)
    next_shortcut.activated.connect(image_controller.next_image)
    prev_shortcut = QShortcut(QKeySequence(PREV_KEY), gui)
    prev_shortcut.activated.connect(image_controller.previous_image)
    first_shortcut = QShortcut(QKeySequence(FIRST_KEY), gui)
    first_shortcut.activated.connect(image_controller.first_image)
    last_shortcut = QShortcut(QKeySequence(LAST_KEY), gui)
    last_shortcut.activated.connect(image_controller.last_image)
    undo_shortcut = QShortcut(QKeySequence(UNDO_KEY), gui)
    undo_shortcut.activated.connect(image_controller.undo_last_action)
    undo_shortcut = QShortcut(QKeySequence(RANDOM_KEY), gui)
    undo_shortcut.activated.connect(image_controller.random_image)
    fullscreen_shortcut = QShortcut(QKeySequence(FULLSCREEN_KEY), gui)
    fullscreen_shortcut.activated.connect(lambda: gui.image_display.toggle_fullscreen(gui))
    quit_shortcut = QShortcut(QKeySequence(QUIT_KEY), gui)
    quit_shortcut.activated.connect(gui.close)
    slide_show_shortcut = QShortcut(QKeySequence(SLIDE_SHOW_KEY), gui)
    slide_show_shortcut.activated.connect(image_controller.toggle_slideshow)
    speed_up_shortcut = QShortcut(QKeySequence(SPEED_UP_KEY), gui)
    speed_up_shortcut.activated.connect(image_display.increase_speed)
    speed_down_shortcut = QShortcut(QKeySequence(SPEED_DOWN_KEY), gui)
    speed_down_shortcut.activated.connect(image_display.decrease_speed)