from tkinter import Tk, Canvas, BOTH, Label, TOP, Frame, X, RIGHT, LEFT, Y
from PIL import Image, ImageTk
import logging
from image_handler import ImageHandler
from logger import setup_logging
from config import get_configuration, ensure_directories_exist

class ImageSorterGUI:
    def __init__(self, master, config):
        self.master = master
        self.image_handler = ImageHandler(config['source_folder'], config['dest_folders'], config['delete_folder'])
        setup_logging()
        self.master.title("Image Sorter")
        self.master.geometry("800x600")
        self.master.resizable(True, True)

        # Create a frame for the top bar
        self.top_bar = Frame(master)
        self.top_bar.pack(side=TOP, fill=X)

        # Create a label to display the categories and their corresponding keys
        self.category_label = Label(self.top_bar, text=self.format_category_keys(config['categories']), font=("Helvetica", 8))
        self.category_label.pack(side=TOP, pady=1, padx=5, fill=BOTH)

        # Create a frame to act as the splitter handle for the top bar
        self.splitter_handle = Frame(master, height=3, bg="grey", cursor="hand2")
        self.splitter_handle.pack(side=TOP, fill=X)
        self.splitter_handle.bind("<Button-1>", self.toggle_top_bar)

        # Create a frame for the sidebar
        self.sidebar = Frame(master, width=200)
        self.sidebar.pack(side=RIGHT, fill=Y)

        # Create a frame to act as the splitter handle for the sidebar
        self.sidebar_splitter_handle = Frame(master, width=3, bg="grey", cursor="hand2")
        self.sidebar_splitter_handle.pack(side=RIGHT, fill=Y)
        self.sidebar_splitter_handle.bind("<Button-1>", self.toggle_sidebar)

        # Create the main canvas
        self.canvas = Canvas(master, bg='white')
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.canvas.bind('<Configure>', self.resize_image)

        self.load_image()
        self.bind_keys(config['categories'])

        self.master.bind('<Configure>', self.adjust_layout)

    def format_category_keys(self, categories):
        key_mapping = {str(i+1): cat for i, cat in enumerate(categories)}
        return " | ".join([f"{key}: {cat}" for key, cat in key_mapping.items()])

    def adjust_layout(self, event=None):
        self.adjust_font_size()
        self.adjust_sidebar_width()

    def adjust_font_size(self, event=None):
        width = self.master.winfo_width()
        text_length = len(self.category_label.cget("text"))
        new_size = max(1, min(int(width / (text_length / 1.5)), 12))
        self.category_label.config(font=("Helvetica", new_size))

    def adjust_sidebar_width(self, event=None):
        total_width = self.master.winfo_width()
        min_total_width = 400
        max_total_width = 800

        if total_width < min_total_width:
            sidebar_ratio = 1 / 10
        elif total_width > max_total_width:
            sidebar_ratio = 1 / 4
        else:
            # Linear interpolation for ratio between min and max widths
            sidebar_ratio = 1 / 4 - (1 / 4 - 1 / 10) * (max_total_width - total_width) / (max_total_width - min_total_width)
        
        sidebar_width = min(200, total_width * sidebar_ratio)
        self.sidebar.config(width=sidebar_width)

    def bind_keys(self, categories):
        key_mapping = {str(i+1): cat for i, cat in enumerate(categories)}
        for key, category in key_mapping.items():
            self.master.bind(key, lambda event, cat=category: self.move_image(cat))
            self.master.bind(f'<KP_{key}>', lambda event, cat=category: self.move_image(cat))
        self.master.bind('<Delete>', self.delete_image)
        self.master.bind('<KP_Delete>', self.delete_image)
        self.master.bind('<Right>', self.next_image)
        self.master.bind('<Left>', self.previous_image)
        self.master.bind('<Home>', self.first_image)
        self.master.bind('<End>', self.last_image)
        self.master.bind('u', self.undo_last_action)

    def toggle_top_bar(self, event):
        if self.top_bar.winfo_ismapped():
            self.top_bar.pack_forget()
            self.splitter_handle.config(bg="lightgrey")
        else:
            self.top_bar.pack(side=TOP, fill=X, before=self.splitter_handle)
            self.splitter_handle.config(bg="grey")

    def toggle_sidebar(self, event):
        if self.sidebar.winfo_ismapped():
            self.sidebar.pack_forget()
            self.sidebar_splitter_handle.config(bg="lightgrey")
        else:
            self.sidebar.pack(side=RIGHT, fill=Y, before=self.sidebar_splitter_handle)
            self.sidebar_splitter_handle.config(bg="grey")

    def load_image(self):
        self.current_image = self.image_handler.load_image()
        if self.current_image:
            self.display_image()
            logging.info(f"Loaded image: {self.image_handler.image_list[self.image_handler.image_index]}")
        else:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2,
                text="All images sorted!",
                font=("Helvetica", 24)
            )
            logging.info("All images sorted!")

    def display_image(self):
        canvas_width, canvas_height = self.canvas.winfo_width(), self.canvas.winfo_height()
        image = self.current_image.copy()
        image.thumbnail((canvas_width, canvas_height))
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(canvas_width / 2, canvas_height / 2, anchor='center', image=self.photo)

    def resize_image(self, event):
        self.display_image()

    def move_image(self, category):
        self.image_handler.move_image(category)
        self.load_image()

    def delete_image(self, event):
        self.image_handler.delete_image()
        self.load_image()

    def next_image(self, event):
        if self.image_handler.image_index < len(self.image_handler.image_list) - 1:
            self.image_handler.image_index += 1
            self.load_image()
            logging.info(f"Moved to next image: {self.image_handler.image_list[self.image_handler.image_index]}")
        else:
            logging.info("No more images to display.")

    def previous_image(self, event):
        if self.image_handler.image_index > 0:
            self.image_handler.image_index -= 1
            self.load_image()
            logging.info(f"Moved to previous image: {self.image_handler.image_list[self.image_handler.image_index]}")
        else:
            logging.info("No previous images to display.")

    def first_image(self, event):
        self.image_handler.image_index = 0
        self.load_image()
        logging.info(f"Moved to first image: {self.image_handler.image_list[self.image_handler.image_index]}")

    def last_image(self, event):
        self.image_handler.image_index = len(self.image_handler.image_list) - 1
        self.load_image()
        logging.info(f"Moved to last image: {self.image_handler.image_list[self.image_handler.image_index]}")

    def undo_last_action(self, event):
        last_action = self.image_handler.undo_last_action()
        if last_action:
            action_type = last_action[0]
            if action_type == 'move':
                category, filename = last_action[1], last_action[2]
                self.image_handler.image_index = self.image_handler.image_list.index(filename)
            elif action_type == 'delete':
                filename = last_action[1]
                self.image_handler.image_index = self.image_handler.image_list.index(filename)
        self.load_image()

def main():
    config = get_configuration()
    ensure_directories_exist(config['dest_folders'], config['delete_folder'])

    root = Tk()
    sorter_gui = ImageSorterGUI(root, config)
    root.mainloop()

if __name__ == "__main__":
    main()

