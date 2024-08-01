from PyQt5.QtWidgets import QApplication
import sys
from config import get_configuration, ensure_directories_exist
from gui import ImageSorterGUI
import logging

def setup_logging(log_file_path):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        handlers=[logging.FileHandler(log_file_path),
                                  logging.StreamHandler()])
    logging.info(f"Logging set up with log file: {log_file_path}")

def main():
    config = get_configuration()
    ensure_directories_exist(config['dest_folders'], config['delete_folder'])
    setup_logging('image_sorter.log')

    app = QApplication(sys.argv)
    sorter_gui = ImageSorterGUI(config)
    sorter_gui.show()

    def on_exit():
        logging.info("[main] Application exit triggered")

    app.aboutToQuit.connect(on_exit)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
