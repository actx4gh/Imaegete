import sys

from PyQt6.QtWidgets import QApplication

import logger
from gui.main_window import ImageSorterGUI


def main():
    app = QApplication(sys.argv)
    sorter_gui = ImageSorterGUI()
    sorter_gui.show()

    def on_exit():
        logger.info("[main] Application exit triggered")

    app.aboutToQuit.connect(on_exit)

    logger.info("[main] Application starting")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
