import os
import random
import time
from PyQt6.QtCore import QThread, QWaitCondition, QMutex
from natsort import os_sorted

from imaegete.core.logger import logger, config
from imaegete.image_processing.data_management.file_operations import is_image_file


class ImageListManager:
    def __init__(self, data_service, thread_manager):
        self.data_service = data_service
        self.thread_manager = thread_manager
        self._start_dirs = []
        self._shuffled_indices = []
        self.lock = QMutex()
        self.image_list_open_condition = QWaitCondition()

    @property
    def start_dirs(self):
        """
        Get the list of start directories, sorted if not already cached.

        :return: A sorted list of start directories.
        :rtype: list
        """
        if not self._start_dirs:
            self._start_dirs = os_sorted(config.start_dirs)
        return self._start_dirs

    def refresh_image_list(self, directories_to_process, folders_to_skip=None, signal=None):
        """
        Refresh the image list by scanning directories asynchronously.
        Emit signal when images are added in batches.
        """
        self._start_dirs = directories_to_process
        for directory in self._start_dirs:
            self.thread_manager.submit_task(self.process_files_in_directory, directory=directory, signal=signal,
                                            folders_to_skip=folders_to_skip, tag="refresh_image_list",
                                            on_finished=self.thread_manager.task_finished_callback)

    def process_files_in_directory(self, directory, folders_to_skip, signal):
        """
        Process image files in a given directory, updating the image list in batches.
        Emit signal after each batch of images is processed.
        """
        thread_id = int(QThread.currentThreadId())
        logger.debug(f"[ImageListManager thread {thread_id}] Starting processing {directory}.")

        image_list = []
        initial_batch_size = 50
        min_batch_size = 10
        max_batch_size = 1000
        batch_size = initial_batch_size
        target_batch_time = 0.1

        for root, _, files in os.walk(directory):
            if os.path.normpath(root) in folders_to_skip:
                continue

            sorted_files = os_sorted(files)
            i = 0

            while i < len(sorted_files):
                start_time = time.time()
                batch_images = []

                while len(batch_images) < batch_size and i < len(sorted_files):
                    file = sorted_files[i]
                    file_path = os.path.join(root, file)
                    if is_image_file(file_path):
                        batch_images.append(file_path)
                    i += 1

                image_list.extend(batch_images)
                if directory == self.start_dirs[0]:
                    if image_list and not self.data_service.get_image_list():
                        self.data_service.set_current_image_path(image_list[0])
                        self.data_service.set_current_index(0)
                    self.data_service.extend_image_list(image_list)
                    image_list = []
                    if signal:
                        signal.emit()

                # Adjust batch size based on processing time
                batch_processing_time = time.time() - start_time
                if batch_processing_time < target_batch_time and batch_size < max_batch_size:
                    batch_size = min(batch_size * 2, max_batch_size)
                elif batch_processing_time > target_batch_time and batch_size > min_batch_size:
                    batch_size = max(batch_size // 2, min_batch_size)

        if image_list:
            while directory != self.start_dirs[0]:
                logger.debug(f"[ImageHandler thread {thread_id}] Waiting to add images from {directory}")
                self.image_list_open_condition.wait(self.lock, 100)
            self.data_service.extend_image_list(image_list)
            if signal:
                signal.emit()
        self.start_dirs.remove(directory)
        self.image_list_open_condition.wakeAll()

    def add_image_to_list(self, image_path, index=None):
        """
        Add a new image to the image list at the specified index or at the end.
        """
        image_list = self.data_service.get_image_list()
        if is_image_file(image_path) and image_path not in image_list:
            if index is not None:
                image_list.insert(index, image_path)
            else:
                image_list.append(image_path)
            self.data_service.set_image_list(image_list)

    def remove_image_from_list(self, image_path):
        """
        Remove an image from the image list.
        """
        image_list = self.data_service.get_image_list()
        if image_path in image_list:
            image_list.remove(image_path)
        self.data_service.set_image_list(image_list)

    def pop_image(self):
        """
        Pop an image from the current index in the image list.
        """
        image_list = self.data_service.get_image_list()
        original_index = self.data_service.get_current_index()
        image_path = self.data_service.pop_image_list(original_index)
        if original_index == len(image_list):
            self.data_service.set_current_index(len(image_list) - 1)
        else:
            self.data_service.set_current_image_to_current_index()
        return original_index, image_path

    def set_current_image_by_index(self, index=None):
        if index is not None:
            self.data_service.set_current_index(index)
        elif self.data_service.get_current_index() is None:
            self.data_service.set_current_index(0)

        image_path = self.data_service.get_current_image_path()
        if image_path:
            self.data_service.set_current_image_path(image_path)
            return image_path
        return None

    def set_first_image(self):
        if len(self.data_service.get_image_list()) > 0:
            return self.set_current_image_by_index(0)

    def set_last_image(self):
        image_list = self.data_service.get_image_list()
        if len(image_list) > 0:
            last_index = len(image_list) - 1
            return self.set_current_image_by_index(last_index)

    def set_next_image(self):
        image_list = self.data_service.get_image_list()
        if len(image_list) > 0:
            next_index = (self.data_service.get_current_index() + 1) % len(image_list)
            return self.set_current_image_by_index(next_index)

    def set_previous_image(self):
        image_list = self.data_service.get_image_list()
        if len(image_list) > 0:
            previous_index = (self.data_service.get_current_index() - 1) % len(image_list)
            return self.set_current_image_by_index(previous_index)

    def set_random_image(self):
        image_list = self.data_service.get_image_list()
        if len(image_list) > 0:
            if not self._shuffled_indices:
                self._shuffled_indices = list(range(len(image_list)))
                random.shuffle(self._shuffled_indices)
            random_index = self._shuffled_indices.pop(0)
            return self.set_current_image_by_index(random_index)

    def has_current_image(self):
        return bool(self.data_service.get_current_image_path())
