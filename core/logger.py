import logging
import os
import inspect
from core import config


# Function to dynamically get or create a logger based on module hierarchy
def get_dynamic_logger():
    # Get the name of the module that called this function
    stack = inspect.stack()
    module = inspect.getmodule(stack[1][0])
    if module:
        module_name = module.__name__
    else:
        module_name = '__main__'

    # Create or retrieve a logger based on the module name
    logger = logging.getLogger(module_name)

    # Check if the logger is already configured to avoid duplicate handlers
    if not logger.hasHandlers():
        configure_logger(logger, module_name)

    return logger


# Configure logger function
def configure_logger(logger, module_name):
    log_dir = config.log_dir
    log_file_path = os.path.join(log_dir, config.LOG_FILE_NAME)
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    logger.setLevel(log_level)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # File handler
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    logger.info(f"Logger configured for module: {module_name}")


# Expose logger dynamically based on module
def __getattr__(name):
    dynamic_logger = get_dynamic_logger()
    return getattr(dynamic_logger, name)


# Ensure the main module logger is set up
logger = get_dynamic_logger()
logger.info(
    f"Logging initialized with log file: {config.LOG_FILE_NAME} and level: {logging.getLevelName(logger.level)}")

# Log initial configuration details
logger.info(f"sort_dir: {config.sort_dir}")
logger.info(f"start_folders: {config.start_dirs}")
logger.info(f"delete_folders: {config.delete_folders}")
logger.info(f"dest_folders: {config.dest_folders}")
