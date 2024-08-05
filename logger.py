import logging

# Configure the logger
logger = logging.getLogger('image_sorter')
logger.setLevel(logging.INFO)

if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    handler = logging.FileHandler('image_sorter.log', encoding='utf-8')
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

logger.info("Logging set up with log file: image_sorter.log")

# Expose the logger attributes as part of the module's namespace
def __getattr__(name):
    return getattr(logger, name)
