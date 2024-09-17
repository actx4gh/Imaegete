import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from core import logger


def move_file(src, dest):
    """
    Move a file from the source to the destination directory.

    :param str src: The source file path.
    :param str dest: The destination file path.
    """
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        logger.info(f"[FileOperations] Moved file from {src} to {dest}")
    except Exception as e:
        logger.error(f"[FileOperations] Failed to move file from {src} to {dest}: {e}")


def move_image_and_cleanup(image_path, source_dir, dest_dir):
    """
    Move related image files from source to destination and remove the source directory if empty.

    :param str image_path: The path of the image file to move.
    :param str source_dir: The source directory.
    :param str dest_dir: The destination directory.
    """
    move_related_files(image_path, source_dir, dest_dir)
    check_and_remove_empty_dir(source_dir)


def move_related_files(filename, src_folder, dest_folder):
    """
    Move all related files (with the same basename) from the source to the destination directory.

    :param str filename: The name of the file to move related files for.
    :param str src_folder: The source folder.
    :param str dest_folder: The destination folder.
    """
    base, _ = os.path.splitext(os.path.basename(filename))

    src_files = os.listdir(src_folder)
    related_files = []

    for f in src_files:
        if os.path.splitext(f)[0] == base:
            related_files.append(f)

    for f in related_files:
        src_path = os.path.join(src_folder, f)
        dest_path = os.path.join(dest_folder, f)
        move_file(src_path, dest_path)


def check_and_remove_empty_dir(dir_path):
    """
    Check if a directory is empty and remove it if it is.

    :param str dir_path: The directory path to check.
    """
    if os.path.isdir(dir_path) and not os.listdir(dir_path):
        try:
            os.rmdir(dir_path)
            logger.info(f"[FileOperations] Removed empty directory: {dir_path}")
        except Exception as e:
            logger.error(f"[FileOperations] Failed to remove directory {dir_path}: {e}")


def scan_directory(directory):
    """
    List all subdirectories within a given directory.

    :param str directory: The directory to scan.
    :return: A list of subdirectories.
    :rtype: list
    """
    subdirs = [directory]
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(entry.path)
    except PermissionError:
        pass
    return subdirs


def list_all_directories_concurrent(start_dir):
    """
    List all directories recursively using concurrent threads.

    :param list start_dir: The starting directory or list of directories to scan.
    :return: A list of all directories found.
    :rtype: list
    """
    directories = []
    seen_directories = set()

    if isinstance(start_dir, str):
        dirs_to_process = [start_dir]
    else:
        dirs_to_process = list(start_dir)

    with ThreadPoolExecutor() as executor:
        while dirs_to_process:

            future_to_dir = {}
            for d in dirs_to_process:
                if not executor._shutdown:
                    future = executor.submit(scan_directory, d)
                    future_to_dir[future] = d
                else:
                    logger.warning("[FileOperations] Attempted to submit task after executor shutdown.")
                    break

            dirs_to_process = []

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
