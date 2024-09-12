import traceback
import logging

class ImageSorterError(Exception):
    def __init__(self, message, context=None):
        super().__init__(message)
        self.context = context or self._get_context()

    def _get_context(self):
        
        return traceback.format_stack()

    def log(self, logger=None):
        """Log the error with its context using the provided logger."""
        logger = logger or logging.getLogger(__name__)
        logger.error(f"Error: {self}, Context: {self.context}")