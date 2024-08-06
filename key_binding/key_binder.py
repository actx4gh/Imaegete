from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

import config


def bind_keys(gui, image_manager):
    key_mapping = {str(i + 1): cat for i, cat in enumerate(config.categories)}
    for key, category in key_mapping.items():
        shortcut = QShortcut(QKeySequence(key), gui)
        shortcut.activated.connect(lambda c=category: image_manager.move_image(c))
    delete_shortcut = QShortcut(QKeySequence('Delete'), gui)
    delete_shortcut.activated.connect(image_manager.delete_image)
    next_shortcut = QShortcut(QKeySequence('Right'), gui)
    next_shortcut.activated.connect(image_manager.next_image)
    prev_shortcut = QShortcut(QKeySequence('Left'), gui)
    prev_shortcut.activated.connect(image_manager.previous_image)
    first_shortcut = QShortcut(QKeySequence('Home'), gui)
    first_shortcut.activated.connect(image_manager.first_image)
    last_shortcut = QShortcut(QKeySequence('End'), gui)
    last_shortcut.activated.connect(image_manager.last_image)
    undo_shortcut = QShortcut(QKeySequence('u'), gui)
    undo_shortcut.activated.connect(image_manager.undo_last_action)
