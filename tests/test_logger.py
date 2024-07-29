import os
import time
from logger import setup_logging
from pytest import mark

@mark.logging
def test_setup_logging():
    log_file_path = 'image_sorter.log'
    print(f"Testing log file creation in: {os.getcwd()}")

    if os.path.exists(log_file_path):
        os.remove(log_file_path)  # Ensure the log file doesn't already exist

    logger = setup_logging()
    logger.info('Test log entry')  # Add a log entry to trigger log file creation
    logger.handlers[0].flush()  # Ensure log entry is written

    # Add a delay to ensure the log file is written
    time.sleep(1)

    try:
        assert os.path.isfile(log_file_path)
        print(f"Log file found: {log_file_path}")
    finally:
        # Properly close the log file handler before attempting to delete the file
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

        # Clean up the log file if the test passes
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
            print(f"Log file {log_file_path} removed after test.")
