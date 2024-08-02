import logging


def setup_logging(log_file_path=None):
    logger = logging.getLogger('image_sorter')
    logger.setLevel(logging.INFO)

    if not logger.hasHandlers():
        handler = logging.FileHandler(log_file_path if log_file_path else 'image_sorter.log', encoding='utf-8')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        logger.info(f"Logging set up with log file: {log_file_path if log_file_path else 'image_sorter.log'}")
