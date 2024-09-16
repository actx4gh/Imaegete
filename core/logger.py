import inspect
import logging
import os

from core import config


def get_dynamic_logger():
    """
    Retrieve a dynamic logger for the calling module. If the logger does not have handlers, it configures a new logger.

    :return: A logger instance for the calling module.
    :rtype: logging.Logger
    """
    stack = inspect.stack()
    module = inspect.getmodule(stack[1][0])
    if module:
        module_name = module.__name__
    else:
        module_name = '__main__'

    logger = logging.getLogger(module_name)

    if not logger.hasHandlers():
        configure_logger(logger, module_name)

    return logger


def configure_logger(logger, module_name):
    """
    Configure a logger with both file and console handlers.

    :param logger: The logger instance to configure.
    :type logger: logging.Logger
    :param module_name: The name of the module for which the logger is being configured.
    :type module_name: str
    """
    log_dir = config.log_dir
    log_file_path = os.path.join(log_dir, config.LOG_FILE_NAME)
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    logger.setLevel(log_level)

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    logger.info(f"Logger configured for module: {module_name}")


def __getattr__(name):
    """
    Dynamically retrieve attributes from the logger instance.

    :param name: The name of the attribute to retrieve.
    :type name: str
    :return: The attribute of the logger.
    :rtype: Any
    """
    dynamic_logger = get_dynamic_logger()
    return getattr(dynamic_logger, name)


logger = get_dynamic_logger()
logger.info(
    f"Logging initialized with log file: {config.LOG_FILE_NAME} and level: {logging.getLevelName(logger.level)}")
