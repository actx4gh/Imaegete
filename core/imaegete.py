import sys

from PyQt6.QtWidgets import QApplication

from core import config, logger
from glavnaqt.core.thread_manager import ThreadManager
from gui.image_display import ImageDisplay
from gui.main_window import ImaegeteGUI
from gui.status_bar_manager import ImaegeteStatusBarManager
from image_processing.data_management.cache_manager import CacheManager
from image_processing.data_management.image_cache_handler import ImageCacheHandler
from image_processing.data_management.data_service import ImageDataService
from image_processing.data_management.file_task_handler import FileTaskHandler
from image_processing.new_image_handler import ImageHandler
from image_processing.data_management.image_list_manager import ImageListManager
from image_processing.image_loader import ImageLoader
from image_processing.image_controller import ImageController


def main():
    """
    Main entry point for the Imaegete application. Initializes the GUI and manages application shutdown.
    """
    logger.info("[Main] Starting application.")
    app = QApplication(sys.argv)
    thread_manager = ThreadManager()

    data_service = ImageDataService()
    _ = ImaegeteStatusBarManager(thread_manager=thread_manager, data_service=data_service)
    cache_manager = CacheManager(config.cache_dir, thread_manager, data_service, image_directories=config.start_dirs,
                                 max_size=config.IMAGE_CACHE_MAX_SIZE_KB)

    data_service.set_cache_manager(cache_manager)
    image_list_manager = ImageListManager(data_service=data_service, thread_manager=thread_manager)
    file_task_handler = FileTaskHandler(thread_manager=thread_manager)
    image_handler = ImageHandler(data_service, thread_manager, image_list_manager, file_task_handler)
    image_cache_handler = ImageCacheHandler(cache_manager=cache_manager)
    image_loader = ImageLoader(cache_handler=image_cache_handler, thread_manager=thread_manager)
    image_controller = ImageController(image_list_manager, image_loader, image_handler)

    image_display = ImageDisplay()
    sorter_gui = ImaegeteGUI(image_display=image_display, image_controller=image_controller, data_service=data_service)

    sorter_gui.show()

    def on_exit():
        logger.info("[Main] Application exit triggered")

    app.aboutToQuit.connect(on_exit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
