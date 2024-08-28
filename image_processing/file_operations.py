# file_operations.py
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

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


def scan_directory(directory):
    """Helper function to list all directories within a given directory."""
    subdirs = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry.path)
    except PermissionError:
        pass  # Skip directories for which we don't have permissions
    return subdirs


def list_all_directories_concurrent(start_dirs):
    """List all directories recursively using concurrent threads from multiple start directories."""
    directories = []
    dirs_to_process = start_dirs.copy()  # Initialize with all start directories

    with ThreadPoolExecutor() as executor:
        while dirs_to_process:
            # Submit tasks for each directory to be processed
            future_to_dir = {executor.submit(scan_directory, d): d for d in dirs_to_process}
            dirs_to_process = []  # Reset for the next batch of directories

            # Collect results as they are completed
            for future in future_to_dir:
                subdirs = future.result()
                directories.extend(subdirs)
                dirs_to_process.extend(subdirs)

    return directories
