# file_operations.py
import os
import shutil
import logging

def move_file(src, dest):
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        logging.getLogger('image_sorter').info(f"Moved file from {src} to {dest}")
    except Exception as e:
        logging.getLogger('image_sorter').error(f"Failed to move file from {src} to {dest}: {e}")

def move_related_files(filename, src_folder, dest_folder):
    base, _ = os.path.splitext(filename)
    related_files = [f for f in os.listdir(src_folder) if os.path.splitext(f)[0] == base]
    for f in related_files:
        src_path = os.path.join(src_folder, f)
        dest_path = os.path.join(dest_folder, f)
        move_file(src_path, dest_path)

def move_related_files_back(filename, src_folder, dest_folder):
    move_related_files(filename, dest_folder, src_folder)

def check_and_remove_empty_dir(dir_path):
    if os.path.isdir(dir_path) and not os.listdir(dir_path):
        try:
            os.rmdir(dir_path)
            logging.getLogger('image_sorter').info(f"Removed empty directory: {dir_path}")
        except Exception as e:
            logging.getLogger('image_sorter').error(f"Failed to remove directory {dir_path}: {e}")
