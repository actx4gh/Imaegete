import logging
import traceback


class ImaegeteError(Exception):
    """
    A custom exception class for handling errors within the Imaegete application.

    :param message: The error message to display.
    :type message: str
    :param context: Optional context information, such as stack trace details.
    :type context: list or None
    """

    def __init__(self, message, context=None):
        """
        Initialize the ImaegeteError with a message and optional context.

        :param message: The error message.
        :type message: str
        :param context: Optional context for additional error details.
        :type context: list or None
        """
        super().__init__(message)
        self.context = context or self._get_context()

    def _get_context(self):
        """
        Retrieve the stack trace to provide additional context for the error.

        :return: The stack trace as a list of strings.
        :rtype: list
        """
        return traceback.format_stack()

    def log(self, logger=None):
        """
        Log the error message along with its context using the specified logger.

        :param logger: The logger instance to use for logging the error. If None, a default logger is used.
        :type logger: logging.Logger or None
        """
        """Log the error with its context using the provided logger."""
        logger = logger or logging.getLogger(__name__)
        logger.error(f"Error: {self}, Context: {self.context}")
