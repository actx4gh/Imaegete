# main.py
import sys
from PyQt5.QtWidgets import QApplication
from config import get_configuration
from logger import setup_logging
from gui.image_sorter_gui import ImageSorterGUI
import logging

def main():
    config = get_configuration()
    setup_logging('image_sorter.log')

    app = QApplication(sys.argv)
    sorter_gui = ImageSorterGUI(config)
    sorter_gui.show()

    def on_exit():
        logging.getLogger('image_sorter').info("[main] Application exit triggered")
        sorter_gui.cleanup()  # Ensure GUI cleanup
        logging.getLogger('image_sorter').info("[main] GUI cleanup done")

    app.aboutToQuit.connect(on_exit)

    logging.getLogger('image_sorter').info("[main] Application starting")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
