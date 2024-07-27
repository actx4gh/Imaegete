import os
from tkinter import Tk
from gui import ImageSorterGUI
from config import get_configuration, ensure_directories_exist

def main():
    config = get_configuration()
    ensure_directories_exist(config['dest_folders'], config['delete_folder'])

    root = Tk()
    sorter_gui = ImageSorterGUI(root, config)
    root.mainloop()

if __name__ == "__main__":
    main()

