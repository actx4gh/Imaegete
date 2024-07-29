import os
import pytest
from tkinter import Tk
from unittest.mock import patch
import tempfile
import logging
from image_handler import ImageHandler
from gui import ImageSorterGUI
from PIL import Image

@pytest.fixture
def gui():
    """Fixture to set up the ImageSorterGUI with mocked configuration."""
    with tempfile.TemporaryDirectory() as temp_source_dir, tempfile.TemporaryDirectory() as temp_dest_dir, tempfile.TemporaryDirectory() as temp_delete_dir:
        log_file_path = os.path.join(temp_source_dir, 'image_sorter.log')

        mock_config = {
            'source_folder': temp_source_dir,
            'dest_folders': {'cat1': temp_dest_dir},
            'delete_folder': temp_delete_dir,
            'categories': ['Cat1', 'Cat2']
        }

        with patch('config.get_configuration', return_value=mock_config):
            with patch('config.ensure_directories_exist'):
                root = Tk()
                gui_instance = ImageSorterGUI(root, mock_config, log_file_path=log_file_path)
                yield gui_instance, log_file_path
                root.destroy()

        # Ensure the log file handlers are properly closed before removal
        logger = logging.getLogger('image_sorter')
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

@pytest.fixture
def image_handler():
    """Fixture to set up an ImageHandler with temporary directories."""
    with tempfile.TemporaryDirectory() as source_folder, tempfile.TemporaryDirectory() as dest_folder, tempfile.TemporaryDirectory() as delete_folder:
        handler = ImageHandler(source_folder, {'cat1': dest_folder}, delete_folder)
        yield handler

@pytest.fixture
def test_jpg():
    """Fixture to create a simple JPEG file."""
    def _create_test_jpg(path):
        image = Image.new('RGB', (100, 100), color='red')
        image.save(path, 'JPEG')
    return _create_test_jpg
