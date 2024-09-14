import os

import pytest


@pytest.mark.not_logging
def test_format_category_keys(gui):
    gui_instance, log_file_path = gui
    formatted_keys = gui_instance.format_category_keys(['Cat1', 'Cat2'])
    assert '1: Cat1' in formatted_keys
    assert '2: Cat2' in formatted_keys

    logger = gui_instance.logger
    for handler in logger.handlers:
        handler.flush()

    print(f"Reading log file from: {log_file_path}")
    if not os.path.exists(log_file_path):
        print(f"Log file does not exist: {log_file_path}")
        assert False, "Log file was not created"
    with open(log_file_path, 'r') as f:
        log_contents = f.read()
    print(f"Log contents: {log_contents}")
    assert "All images sorted!" in log_contents
