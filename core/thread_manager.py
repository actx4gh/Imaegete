from concurrent.futures import ThreadPoolExecutor

from core import logger


class ThreadManager:
    def __init__(self, max_workers=4):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.is_shutting_down = False
        self.tasks = []

    def submit_task(self, task, *args, **kwargs):
        """Submit a task to the thread pool, unless shutting down."""
        if not self.is_shutting_down:
            try:
                future = self.thread_pool.submit(task, *args, **kwargs)
                self.tasks.append(future)
                return future
            except Exception as e:
                logger.error(f"Error submitting task to thread pool: {e}")
                return None
        else:
            logger.warning("[ThreadManager] Cannot submit new tasks, shutting down.")
            return None

    def shutdown(self, wait=False):
        """Gracefully shut down the thread pool, allowing ongoing tasks to complete, unless wait=False."""
        self.is_shutting_down = True
        logger.info("[ThreadManager] Initiating shutdown of thread pool.")

        if not wait:
            logger.info("[ThreadManager] Forcing cancellation of ongoing tasks.")
            for task in self.tasks:
                if not task.done():
                    task.cancel()  

        try:
            self.thread_pool.shutdown(wait=wait)
            logger.info("[ThreadManager] Thread pool shutdown complete.")
        except Exception as e:
            logger.error(f"[ThreadManager] Error during thread pool shutdown: {e}")
