import os
import pickle
from collections import OrderedDict

from PyQt6.QtCore import QMutex, QThread, QMutexLocker
from PyQt6.QtCore import QObject, QCoreApplication, pyqtSignal
from PyQt6.QtCore import QReadWriteLock
from PyQt6.QtGui import QImage
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core import config
from core import logger
from glavnaqt.core.event_bus import create_or_get_shared_event_bus
from image_processing.data_management.file_operations import is_image_file


class CacheManager(QObject):
    """
    A class to manage the caching of images, including loading, refreshing, and handling metadata.
    """
    request_display_update = pyqtSignal(str)

    def __init__(self, cache_dir, thread_manager, data_service, image_directories, max_size=500, debounce_interval=0.5,
                 stability_check_interval=1,
                 stability_check_retries=3):
        super().__init__()
        self.dest_folders = config.dest_folders
        self.event_bus = create_or_get_shared_event_bus()
        self.delete_folders = config.delete_folders
        self.debounce_interval = debounce_interval
        self.stability_check_interval = stability_check_interval
        self.stability_check_retries = stability_check_retries
        self.cache_dir = cache_dir
        self.thread_manager = thread_manager
        self.data_service = data_service
        self.image_directories = image_directories
        self.max_size = max_size
        self.metadata_cache = OrderedDict()
        self.metadata_manager = MetadataManager(self.cache_dir, self.thread_manager)
        self.image_cache = OrderedDict()
        self.cache_lock = QMutex()
        self.debounce_tasks = {}
        self.moveToThread(QCoreApplication.instance().thread())
        self._setup_cache_directory()
        self.shutdown_mutex = QMutex()
        self.shutdown_flag = False
        self.initialize_watchdog()
        self.currently_active_requests = set()
        self.display_requested_once = False

        # Shutdown flag and mutex

    def is_shutting_down(self):
        with QMutexLocker(self.shutdown_mutex):
            return self.shutdown_flag

    def is_cached(self, image_path):
        return image_path in self.image_cache

    def retrieve_image(self, image_path, active_request=False, background=True):
        with QMutexLocker(self.cache_lock):
            if self.is_shutting_down():
                logger.info(f"[CacheManager] Shutdown initiated, not retrieving image {image_path}.")
                return None
            image = self.image_cache.get(image_path)
            if image:
                logger.debug(f"[CacheManager] Image found in cache for {image_path}")
                self.image_cache.move_to_end(image_path)
                return image
            else:
                logger.debug(f"[CacheManager] Image was not found in cache for {image_path}")

            if image_path in self.currently_active_requests and active_request:
                logger.warning(
                    f"[CacheManager] Duplicate request: Image {image_path} is already being loaded, skipping.")
                return None

            logger.debug(f"[CacheManager] Marking image {image_path} as being actively requested.")
            self.currently_active_requests.add(image_path)

        if background:
            if self.thread_manager.is_shutting_down:
                logger.info(f"[CacheManager] Shutdown initiated, not submitting background task for {image_path}.")
                return None
            logger.debug(f"[CacheManager] Submitting image load task in background thread for {image_path}")
            runnable = self.thread_manager.submit_task(self.load_from_disk_and_cache, image_path=image_path)
            if runnable is None:
                logger.info(f"[CacheManager] Task submission failed for image {image_path} due to shutdown.")
                return None
        else:
            logger.debug(f"[CacheManager] Running image load task directly for {image_path}")
            return self.load_from_disk_and_cache(image_path)
        return None

    def load_from_disk_and_cache(self, image_path):
        thread_id = int(QThread.currentThreadId())
        if not image_path:
            logger.debug(f"[CacheManager thread {thread_id}] No image_path provided, returning without loading image")
            return
        if self.is_shutting_down():
            logger.info(f"[CacheManager thread {thread_id}] Shutdown initiated, not loading image {image_path}.")
            return
        image = QImage(image_path)
        if not image.isNull():
            index = self.data_service.get_index_for_image(image_path)
            logger.debug(f"[CacheManager thread {thread_id}] Loaded image from disk: {image_path} index {index}")
            with QMutexLocker(self.cache_lock):
                if self.is_shutting_down():
                    logger.info(
                        f"[CacheManager thread {thread_id}] Shutdown initiated, not caching image {image_path}.")
                    return
                self.image_cache[image_path] = image
                self.image_cache.move_to_end(image_path)

                if len(self.image_cache) > self.max_size:
                    removed_item = self.image_cache.popitem(last=False)
                    logger.debug(
                        f"[CacheManager thread {thread_id}] Cache size exceeded while loading {image_path}, removing oldest item: {removed_item[0]}")
                file_size = os.path.getsize(image_path)
                last_modified = os.path.getmtime(image_path)
                metadata = {
                    'size': image.size(),
                    'file_size': file_size,
                    'last_modified': last_modified
                }
                self.metadata_manager.save_metadata(image_path, metadata)
                self.metadata_cache[image_path] = metadata
                if image_path in self.currently_active_requests and not self.display_requested_once:
                    self.currently_active_requests.discard(image_path)
                return image
        else:
            logger.error(
                f"[CacheManager thread {thread_id}] Failed to load image from disk. Marking invalid: {image_path}")
            self.data_service.remove_image(image_path)
            self.event_bus.emit("update_image_total")
            with QMutexLocker(self.cache_lock):
                self.currently_active_requests.discard(image_path)
            # Optionally, you might want to handle loading another image

    def refresh_cache(self, image_path):
        if self.is_shutting_down():
            logger.info(f"[CacheManager] Shutdown initiated, not refreshing cache for {image_path}.")
            return
        logger.info(f"[CacheManager] Refreshing cache for {image_path}")
        if self.metadata_manager.file_is_ready(image_path):
            if self.thread_manager.is_shutting_down:
                logger.info(f"[CacheManager] Shutdown initiated, not submitting refresh task for {image_path}.")
                return
            self.thread_manager.submit_task(self._refresh_task, image_path=image_path)
        else:
            logger.warning(f"[CacheManager] Skipping cache refresh for {image_path} - file is not ready.")

    def _refresh_task(self, image_path):
        if self.is_shutting_down():
            logger.info(f"[CacheManager] Shutdown initiated, not refreshing cache for {image_path}.")
            return
        with QMutexLocker(self.cache_lock):
            self.image_cache.pop(image_path, None)
            self.currently_active_requests.discard(image_path)
        self.load_from_disk_and_cache(image_path)

    def debounced_cache_refresh(self, image_path):
        if self.is_shutting_down():
            logger.info(f"[CacheManager] Shutdown initiated, not refreshing cache for {image_path}.")
            return

        def debounced_task():
            if self.is_shutting_down():
                logger.info(f"[CacheManager] Shutdown initiated, not running debounced task for {image_path}.")
                return
            if self.debounce_tasks.get(image_path):
                del self.debounce_tasks[image_path]
            self.refresh_cache(image_path)

        if image_path not in self.debounce_tasks:
            if self.thread_manager.is_shutting_down:
                logger.info(f"[CacheManager] Shutdown initiated, not submitting debounced task for {image_path}.")
                return
            runnable = self.thread_manager.submit_task(debounced_task)
            if runnable is not None:
                self.debounce_tasks[image_path] = runnable

    def shutdown(self):
        logger.info("[CacheManager] Initiating shutdown.")
        with QMutexLocker(self.shutdown_mutex):
            self.shutdown_flag = True
        self.shutdown_watchdog()
        with QMutexLocker(self.cache_lock):
            self.currently_active_requests.clear()
        logger.info("[CacheManager] Shutdown complete.")

    def get_cache_path(self, image_path):
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def initialize_watchdog(self):
        """
        Initialize the watchdog observer to monitor changes in the image directories, excluding
        specific subdirectories that match `dest_folders` or `delete_folders`.
        """
        if self.is_shutting_down():
            logger.info("[CacheManager] Shutdown initiated, not initializing watchdog.")
            return
        event_handler = CacheEventHandler(self)
        self.watchdog_observer = Observer()

        directories_to_exclude = set()

        for start_dir in self.image_directories:
            if start_dir in self.dest_folders:
                for dest_subfolder in self.dest_folders[start_dir].values():
                    directories_to_exclude.add(os.path.normpath(dest_subfolder))

            if start_dir in self.delete_folders:
                delete_folder = self.delete_folders[start_dir]
                directories_to_exclude.add(os.path.normpath(delete_folder))

        for directory in self.image_directories:
            normalized_dir = os.path.normpath(directory)
            if normalized_dir not in directories_to_exclude:
                self.watchdog_observer.schedule(event_handler, normalized_dir, recursive=True)

        self.watchdog_observer.start()
        logger.debug(f"[CacheManager] Watchdog started, monitoring directories excluding: {directories_to_exclude}")
        if not self.thread_manager.is_shutting_down:
            self.thread_manager.submit_task(self._monitor_watchdog)
        else:
            logger.info("[CacheManager] Shutdown initiated, not starting watchdog monitor task.")

    def _monitor_watchdog(self):
        while not self.thread_manager.is_shutting_down and not self.is_shutting_down():
            if not self.watchdog_observer.is_alive():
                self.restart_watchdog()
            QThread.sleep(self.stability_check_interval)

    def restart_watchdog(self):
        """
        Restart the watchdog observer if it crashes.
        """
        if self.is_shutting_down():
            logger.info("[CacheManager] Shutdown initiated, not restarting watchdog.")
            return
        logger.warning("[CacheManager] Watchdog observer crashed. Restarting...")
        self.shutdown_watchdog()
        self.initialize_watchdog()

    def shutdown_watchdog(self):
        """
        Stop the watchdog observer and wait for the thread to finish.
        """
        if hasattr(self, 'watchdog_observer') and self.watchdog_observer.is_alive():
            self.watchdog_observer.stop()
            self.watchdog_observer.join()
            logger.info("[CacheManager] Watchdog observer stopped.")

    def _setup_cache_directory(self):
        """
        Set up the cache directory by creating it if it does not exist.
        """
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
                logger.info(f"[CacheManager] Cache directory created: {self.cache_dir}")
            except OSError as e:
                logger.error(f"[CacheManager] Failed to create cache directory: {e}")
        else:
            logger.debug(f"[CacheManager] Cache directory already exists: {self.cache_dir}")

    def _load_metadata_task(self, image_path):
        if self.is_shutting_down():
            logger.info(f"[CacheManager] Shutdown initiated, not loading metadata for {image_path}.")
            return
        metadata = self.metadata_manager.load_metadata(image_path)
        if metadata:
            with QMutexLocker(self.cache_lock):
                if self.is_shutting_down():
                    logger.info(f"[CacheManager] Shutdown initiated, not caching metadata for {image_path}.")
                    return
                self.metadata_cache[image_path] = metadata
                if len(self.metadata_cache) > self.max_size:
                    self.metadata_cache.popitem(last=False)
            logger.debug(f"[CacheManager] Loaded metadata for {image_path} and cached it.")

    def get_metadata(self, image_path):
        """
        Retrieve metadata for an image from the cache or load it asynchronously if not available.
        Uses ThreadManager to load metadata without blocking the main thread.

        :param str image_path: The path of the image to retrieve metadata for.
        :return: The metadata of the image or None if loading.
        :rtype: dict or None
        """
        if self.is_shutting_down():
            logger.info(f"[CacheManager] Shutdown initiated, not retrieving metadata for {image_path}.")
            return None
        if image_path in self.metadata_cache:
            self.metadata_cache.move_to_end(image_path)
            return self.metadata_cache[image_path]

        if self.thread_manager.is_shutting_down:
            logger.info(f"[CacheManager] Shutdown initiated, not submitting metadata load task for {image_path}.")
            return None
        self.thread_manager.submit_task(self._load_metadata_task, image_path=image_path)
        return None


class MetadataManager:
    """
    A class to manage the metadata of images, including saving and loading metadata.
    """

    def __init__(self, cache_dir, thread_manager):
        self.cache_dir = cache_dir
        self.thread_manager = thread_manager
        self.lock = QReadWriteLock()
        self.shutdown_flag = False
        self.shutdown_mutex = QMutex()

    def is_shutting_down(self):
        with QMutexLocker(self.shutdown_mutex):
            return self.shutdown_flag

    def shutdown(self):
        with QMutexLocker(self.shutdown_mutex):
            self.shutdown_flag = True

    def save_metadata(self, image_path, metadata):
        if self.is_shutting_down():
            logger.info(f"[MetadataManager] Shutdown initiated, not saving metadata for {image_path}.")
            return

        def async_save():
            if self.is_shutting_down():
                logger.info(f"[MetadataManager] Shutdown initiated, not saving metadata for {image_path}.")
                return
            cache_path = self.get_cache_path(image_path)
            current_metadata = self.load_metadata(image_path)

            if current_metadata != metadata:
                self.lock.lockForWrite()
                try:
                    with open(cache_path, 'wb') as f:
                        pickle.dump(metadata, f)
                    logger.debug(f"[MetadataManager] Metadata saved for {image_path}.")
                finally:
                    self.lock.unlock()

        if self.thread_manager.is_shutting_down:
            logger.info(f"[MetadataManager] Shutdown initiated, not submitting save metadata task for {image_path}.")
            return
        self.thread_manager.submit_task(async_save)

    def load_metadata(self, image_path):
        if self.is_shutting_down():
            logger.info(f"[MetadataManager] Shutdown initiated, not loading metadata for {image_path}.")
            return None
        cache_path = self.get_cache_path(image_path)
        if os.path.exists(cache_path):
            self.lock.lockForRead()
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"[MetadataManager] Failed to load metadata for {image_path}: {e}")
                return None
            finally:
                self.lock.unlock()
        return None

    def get_cache_path(self, image_path):
        filename = os.path.basename(image_path)
        return os.path.join(self.cache_dir, f"{filename}.cache")

    def file_is_ready(self, image_path):
        return True


class CacheEventHandler(FileSystemEventHandler):
    """
    A class to handle filesystem events related to the image cache, such as file creation, modification, and deletion.
    """

    def __init__(self, cache_manager):
        """Initialize event handler with reference to CacheManager."""
        super().__init__()
        self.cache_manager = cache_manager
        self.excluded_paths = set()

        for start_dir in self.cache_manager.image_directories:
            if start_dir in self.cache_manager.dest_folders:
                for dest_subfolder in self.cache_manager.dest_folders[start_dir].values():
                    self.excluded_paths.add(os.path.normpath(dest_subfolder))

            if start_dir in self.cache_manager.delete_folders:
                delete_folder = self.cache_manager.delete_folders[start_dir]
                self.excluded_paths.add(os.path.normpath(delete_folder))

    def _is_excluded(self, path):
        """
        Check if the event path is in an excluded folder.
        """
        normalized_path = os.path.normpath(path)
        for excluded_path in self.excluded_paths:
            if normalized_path.startswith(excluded_path):
                return True
        return False

    def on_modified(self, event):
        """
        Handle file modification events and refresh the cache only if the modification time has changed.
        """
        if self.cache_manager.is_shutting_down():
            logger.info(f"[CacheEventHandler] Shutdown initiated, ignoring modified event for {event.src_path}.")
            return
        if not event.is_directory and not self._is_excluded(event.src_path):
            self.handle_modified(event)

    def handle_modified(self, event):
        """Handle modification logic separately to keep `on_modified` clean."""
        if not is_image_file(event.src_path):
            return
        if event.src_path in self.cache_manager.currently_active_requests:
            logger.debug(
                f'[CacheEventHandler] Returning without further processing {event.src_path}. Already active in the cache.')
            return None
        self.__refresh_cache_if_needed(event)

    def on_created(self, event):
        """
        Handle file creation events to refresh the cache.
        """
        if self.cache_manager.is_shutting_down():
            logger.info(f"[CacheEventHandler] Shutdown initiated, ignoring created event for {event.src_path}.")
            return
        if not any((event.is_directory, self._is_excluded(event.src_path))) and is_image_file(event.src_path):
            logger.debug(
                f'[CacheEventHandler] File creation event triggered for {event.src_path}, adding to image list and refreshing cache')
            self.cache_manager.data_service.insert_sorted_image(event.src_path)
            self.cache_manager.event_bus.emit("update_image_total")
            self.__refresh_cache_if_needed(event)

    def on_deleted(self, event):
        """
        Handle file deletion events by removing the image from the cache.
        """
        if self.cache_manager.is_shutting_down():
            logger.info(f"[CacheEventHandler] Shutdown initiated, ignoring deleted event for {event.src_path}.")
            return
        if not event.is_directory and not self._is_excluded(
                event.src_path) and event.src_path in self.cache_manager.data_service.get_image_list():
            logger.debug(
                f'[CacheEventHandler] File deletion event triggered for {event.src_path}, removing from image list')
            self.cache_manager.data_service.remove_image(event.src_path)
            self.cache_manager.event_bus.emit("update_image_total")
            self.cache_manager.request_display_update.emit(self.cache_manager.data_service.get_current_image_path())

    def __refresh_cache_if_needed(self, event):
        if self.cache_manager.is_shutting_down():
            logger.info(f"[CacheEventHandler] Shutdown initiated, not refreshing cache for {event.src_path}.")
            return
        try:
            current_mod_time = os.path.getmtime(event.src_path)
            cached_metadata = self.cache_manager.metadata_cache.get(event.src_path)

            if cached_metadata:
                cached_mod_time = cached_metadata.get('last_modified')
                if cached_mod_time != current_mod_time:
                    logger.debug(
                        f'[CacheEventHandler] Modification time changed for {event.src_path}. Refreshing cache.')
                    self.cache_manager.debounced_cache_refresh(event.src_path)
                else:
                    logger.debug(
                        f'[CacheEventHandler] Modification time unchanged for {event.src_path}. No refresh needed.')

            else:
                logger.debug(f'[CacheEventHandler] No metadata cached for {event.src_path}. Refreshing cache.')
                self.cache_manager.debounced_cache_refresh(event.src_path)
        except Exception as e:
            logger.error(f'[CacheEventHandler] Error while handling {event.event_type} event for {event.src_path}: {e}')
