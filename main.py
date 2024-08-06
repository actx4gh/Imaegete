import sys

from PyQt5.QtWidgets import QApplication

import logger
from gui.main_window import ImageSorterGUI


def main():
    app = QApplication(sys.argv)
    sorter_gui = ImageSorterGUI()
    sorter_gui.show()

    def on_exit():
        logger.info("[main] Application exit triggered")
        sorter_gui.cleanup()  # Ensure GUI cleanup
        logger.info("[main] GUI cleanup done")

    app.aboutToQuit.connect(on_exit)

    logger.info("[main] Application starting")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
