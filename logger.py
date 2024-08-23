import logging
import os

import config
log_dir = config.log_dir
log_file_path = os.path.join(log_dir, 'image_sorter.log')
logger = logging.getLogger('image_sorter')
log_level = getattr(logging, config.log_level.upper(), logging.INFO)
logger.setLevel(log_level)

if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    handler = logging.FileHandler(log_file_path, encoding='utf-8')
    handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

logger.info(f"Logging set up with log file: image_sorter.log and level: {logging.getLevelName(logger.level)}")


# Expose the logger attributes as part of the module's namespace
def __getattr__(name):
    return getattr(logger, name)
