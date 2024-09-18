import threading
from concurrent.futures import ThreadPoolExecutor

from core import logger


def log_active_threads():
    active_threads = threading.enumerate()
    logger.debug(f"[ThreadManager] Active threads: {active_threads}")


class ThreadManager:
    """
    A class to manage the submission and execution of tasks using a thread pool.

    :param int max_workers: The maximum number of worker threads to use in the pool.
    """

    def __init__(self, max_workers=16):
        """
        Initialize the ThreadManager with a thread pool and setup task tracking.

        :param int max_workers: Maximum number of worker threads.
        """
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.is_shutting_down = False
        self.tasks = []

    def submit_task(self, task, *args, **kwargs):
        """
        Submit a task to the thread pool for execution.

        :param callable task: The task function to execute.
        :param args: Positional arguments for the task function.
        :param kwargs: Keyword arguments for the task function.
        :return: A future representing the task execution or None if the task could not be submitted.
        :rtype: Future or None
        """
        if not self.is_shutting_down:
            try:
                future = self.thread_pool.submit(task, *args, **kwargs)

                return future
            except Exception as e:
                logger.error(f"Error submitting task to thread pool: {e}")
                return None
        else:
            logger.warning("[ThreadManager] Cannot submit new tasks, shutting down.")
            return None

    def shutdown(self):
        """
        Shuts down the thread pool and cancels all ongoing tasks.
        """
        logger.info("[ThreadManager] Initiating shutdown of thread pool.")
        self.is_shutting_down = True

        for task in self.tasks:
            if not task.done():
                task.cancel()

        logger.info("[ThreadManager] Forcing cancellation of ongoing tasks.")
        self.thread_pool.shutdown(wait=False)

        logger.info("[ThreadManager] Thread pool shutdown complete.")
