import logging

def setup_logging(log_file_path=None):
    logger = logging.getLogger('image_sorter')
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a file handler with utf-8 encoding
    handler = logging.FileHandler(log_file_path if log_file_path else 'image_sorter.log', encoding='utf-8')
    handler.setLevel(logging.INFO)

    # Create a logging format
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(handler)

    logger.info(f"Logging set up with log file: {log_file_path if log_file_path else 'image_sorter.log'}")

    return logger
