import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from core import logger


def move_file(src, dest):
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        logger.info(f"[FileOperations] Moved file from {src} to {dest}")
    except Exception as e:
        logger.error(f"[FileOperations] Failed to move file from {src} to {dest}: {e}")


def move_image_and_cleanup(image_path, source_dir, dest_dir):
    move_related_files(image_path, source_dir, dest_dir)
    check_and_remove_empty_dir(source_dir)


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
            logger.info(f"[FileOperations] Removed empty directory: {dir_path}")
        except Exception as e:
            logger.error(f"[FileOperations] Failed to remove directory {dir_path}: {e}")


def scan_directory(directory):
    """Helper function to list all directories within a given directory."""
    subdirs = [directory]
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry.path)
    except PermissionError:
        pass  # Skip directories for which we don't have permissions
    return subdirs


def list_all_directories_concurrent(start_dir):
    """List all directories recursively using concurrent threads."""
    directories = []
    seen_directories = set()

    if isinstance(start_dir, str):
        dirs_to_process = [start_dir]
    else:
        dirs_to_process = list(start_dir)

    with ThreadPoolExecutor() as executor:
        while dirs_to_process:
            # Submit tasks for each new directory to be processed
            future_to_dir = {}
            for d in dirs_to_process:
                if not executor._shutdown:  # Check if executor is not shut down
                    future = executor.submit(scan_directory, d)
                    future_to_dir[future] = d
                else:
                    logger.warning("[FileOperations] Attempted to submit task after executor shutdown.")
                    break

            dirs_to_process = []  # Reset for the next batch of directories

            # Collect results as they are completed
            for future in future_to_dir:
                try:
                    subdirs = future.result()
                except Exception as e:
                    logger.error(f"[FileOperations] Exception while scanning directory: {e}")
                    continue

                for subdir in subdirs:
                    if subdir not in seen_directories:
                        seen_directories.add(subdir)
                        directories.append(subdir)
                        dirs_to_process.append(subdir)

    return directories
# def list_all_directories_concurrent(start_dir):
#    """List all directories recursively using concurrent threads."""
#    directories = []
#    seen_directories = set()
#
#    if isinstance(start_dir, str):
#        dirs_to_process = [start_dir]
#    else:
#        dirs_to_process = list(start_dir)
#
#    with ThreadPoolExecutor() as executor:
#        while dirs_to_process:
#            # Submit tasks for each new directory to be processed
#            future_to_dir = {executor.submit(scan_directory, d): d for d in dirs_to_process}
#            dirs_to_process = []  # Reset for the next batch of directories
#
#            # Collect results as they are completed
#            for future in future_to_dir:
#                subdirs = future.result()
#                for subdir in subdirs:
#                    if subdir not in seen_directories:
#                        seen_directories.add(subdir)
#                        directories.append(subdir)
#                        dirs_to_process.append(subdir)
#
#    return directories
#
