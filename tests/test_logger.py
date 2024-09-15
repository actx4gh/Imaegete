import os
import time

from pytest import mark

from core.logger import setup_logging


@mark.logging
def test_setup_logging():
    log_file_path = 'imaegete.log'
    print(f"Testing log file creation in: {os.getcwd()}")

    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    logger = setup_logging()
    logger.info('Test log entry')
    logger.handlers[0].flush()

    time.sleep(1)

    try:
        assert os.path.isfile(log_file_path)
        print(f"Log file found: {log_file_path}")
    finally:

        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

        if os.path.exists(log_file_path):
            os.remove(log_file_path)
            print(f"Log file {log_file_path} removed after test.")
