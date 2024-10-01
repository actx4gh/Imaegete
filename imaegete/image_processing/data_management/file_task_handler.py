from PyQt6.QtCore import QThread

from imaegete.image_processing.data_management.file_operations import move_image_and_cleanup


# FileOperationHandler (file_task_handler.py)
class FileTaskHandler:
    def __init__(self, thread_manager, data_service):
        self.thread_manager = thread_manager
        self.data_service = data_service

    def move_image(self, image_path, source_dir, dest_dir):
        def task():
            move_image_and_cleanup(image_path, source_dir, dest_dir)
            self.data_service.cache_manager.initialize_watchdog()
            QThread.sleep(1)
            self.data_service.remove_file_task(image_path)

        self.data_service.cache_manager.shutdown_watchdog()
        self.data_service.append_ongoing_file_tasks(image_path)
        self.thread_manager.submit_task(task)

    def delete_image(self, image_path, source_dir, dest_dir):
        # Deleting an image is treated as moving it to the delete folder
        self.move_image(image_path, source_dir, dest_dir)
