import sys
import os
from tkinter import Tk
from gui import ImageSorterGUI
from config import get_configuration, ensure_directories_exist

def main():
    # Ensure the script can find the other modules
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)

    config = get_configuration()
    ensure_directories_exist(config['dest_folders'], config['delete_folder'])

    root = Tk()
    sorter_gui = ImageSorterGUI(root, config)
    root.mainloop()

if __name__ == "__main__":
    main()

