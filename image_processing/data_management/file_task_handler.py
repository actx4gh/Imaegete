import os

from image_processing.data_management.file_operations import move_image_and_cleanup


# FileOperationHandler (file_task_handler.py)
class FileTaskHandler:
    def __init__(self, thread_manager):
        self.thread_manager = thread_manager

    def move_image(self, image_path, source_dir, dest_dir):
        def task():
            move_image_and_cleanup(image_path, source_dir, dest_dir)

        self.thread_manager.submit_task(task)

    def delete_image(self, image_path, delete_dir):
        # Deleting an image is treated as moving it to the delete folder
        self.move_image(image_path, os.path.dirname(image_path), delete_dir)
