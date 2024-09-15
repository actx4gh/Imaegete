

Imaegeon is a desktop application designed for efficiently organizing and managing large collections of images. The project uses PyQt6 for the GUI and leverages multithreading for performing file operations, caching, and image handling to ensure a responsive user experience.



- **Image Sorting**: Move images between different categories or delete them with customizable key bindings.
- **Multithreaded Operations**: Asynchronous image loading, caching, and processing to keep the UI responsive.
- **Image Caching**: A cache system to store images and metadata, minimizing disk reads.
- **Prefetching**: Prefetch images ahead of time for smoother navigation between images.
- **Key Bindings**: Customizable keyboard shortcuts for quick image navigation and sorting.
- **Full-Screen Viewing**: Toggle full-screen image viewing for a better experience.
- **Status Bar Information**: Displays detailed information about the currently selected image, including file size, dimensions, and more.



- **`main.py`**: Entry point for the application, responsible for initializing and launching the UI and managing resources.
- **`config.py`**: Centralized configuration handling, supporting platform-specific settings and YAML configuration.
- **`logger.py`**: Custom logger for logging application events to both the console and log files.
- **`image_manager.py`**: Manages the current image, handles navigation between images, and triggers image loading.
- **`image_handler.py`**: Handles the core image operations such as moving, deleting, and shuffling images.
- **`cache_manager.py`**: Manages caching of images and metadata to optimize image loading performance.
- **`data_service.py`**: A service layer that provides access to image-related data and maintains the image list and indices.
- **`file_operations.py`**: Handles low-level file operations like moving and cleaning up images.
- **`image_display.py`**: Provides the GUI component for displaying images, with support for resizing and full-screen modes.
- **`status_bar_manager.py`**: Manages the status bar, displaying real-time information about the currently loaded image.
- **`thread_manager.py`**: Manages a pool of threads for running tasks asynchronously without blocking the main UI thread.
- **`exceptions.py`**: Defines custom exceptions for error handling throughout the application.
- **`key_binder.py`**: Maps keyboard shortcuts to actions for quick image sorting, navigation, and manipulation.



1. Clone the repository:

    ```bash
    git clone https://github.com/actx4gh/imaegeon.git
    ```

2. Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3. Run the application:

    ```bash
    python main.py
    ```



- **Next Image**: Right Arrow
- **Previous Image**: Left Arrow
- **First Image**: Home
- **Last Image**: End
- **Delete Image**: Delete
- **Random Image**: R
- **Undo Last Action**: U
- **Toggle Full-Screen**: F



- **Not Ready for Production**: This project is still under active development and is not yet ready for wide consumption. Some features may not function as expected, and additional testing and error handling are needed.



- Improved error handling and logging.
- Enhanced UI elements and customization options.
- Support for more image formats and larger datasets.
- Comprehensive unit testing and documentation.



Contributions are welcome. Please feel free to submit a pull request or file an issue.



[MIT License](LICENSE)
