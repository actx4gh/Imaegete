# file_operations.py
import os
import shutil

import logger


def move_file(src, dest):
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        logger.info(f"Moved file from {src} to {dest}")
    except Exception as e:
        logger.error(f"Failed to move file from {src} to {dest}: {e}")


9


def move_related_files(filename, src_folder, dest_folder):
    # Extract only the filename part
    base, _ = os.path.splitext(os.path.basename(filename))

    # Prepare paths
    src_files = os.listdir(src_folder)
    related_files = []

    # Find related files based on base name
    for f in src_files:
        if os.path.splitext(f)[0] == base:
            related_files.append(f)

    # Move related files
    for f in related_files:
        src_path = os.path.join(src_folder, f)
        dest_path = os.path.join(dest_folder, f)
        move_file(src_path, dest_path)


def check_and_remove_empty_dir(dir_path):
    if os.path.isdir(dir_path) and not os.listdir(dir_path):
        try:
            os.rmdir(dir_path)
            logger.info(f"Removed empty directory: {dir_path}")
        except Exception as e:
            logger.error(f"Failed to remove directory {dir_path}: {e}")
