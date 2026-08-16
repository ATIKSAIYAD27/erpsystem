import threading
import queue
import logging
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Lightweight background task queue using ThreadPoolExecutor."""

    def __init__(self, max_workers=4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks = {}
        self._task_counter = 0
        self._lock = threading.Lock()

    def submit(self, func, *args, task_name="task", **kwargs):
        with self._lock:
            self._task_counter += 1
            task_id = self._task_counter

        future = self._executor.submit(self._run_task, task_id, func, *args, **kwargs)
        with self._lock:
            self._tasks[task_id] = {
                'id': task_id,
                'name': task_name,
                'status': 'running',
                'submitted': time.time(),
                'future': future
            }
        logger.info("Background task %d (%s) submitted", task_id, task_name)
        return task_id

    def _run_task(self, task_id, func, *args, **kwargs):
        try:
            result = func(*args, **kwargs)
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]['status'] = 'completed'
                    self._tasks[task_id]['result'] = result
                    self._tasks[task_id]['completed'] = time.time()
            logger.info("Background task %d completed", task_id)
            return result
        except Exception as e:
            with self._lock:
                if task_id in self._tasks:
                    self._tasks[task_id]['status'] = 'failed'
                    self._tasks[task_id]['error'] = str(e)
                    self._tasks[task_id]['completed'] = time.time()
            logger.error("Background task %d failed: %s\n%s", task_id, e, traceback.format_exc())
            return None

    def get_status(self, task_id):
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self):
        with self._lock:
            return {k: {kk: vv for kk, vv in v.items() if kk != 'future'} 
                    for k, v in self._tasks.items()}

    def cleanup_old_tasks(self, max_age=3600):
        with self._lock:
            now = time.time()
            to_delete = []
            for task_id, task in self._tasks.items():
                if now - task.get('submitted', now) > max_age:
                    to_delete.append(task_id)
            for tid in to_delete:
                del self._tasks[tid]


task_manager = BackgroundTaskManager(max_workers=4)


def run_in_background(task_name="background_task"):
    """Decorator to run a function in the background."""
    def decorator(f):
        def wrapper(*args, **kwargs):
            return task_manager.submit(f, *args, task_name=task_name, **kwargs)
        wrapper.__name__ = f.__name__
        wrapper.__doc__ = f.__doc__
        return wrapper
    return decorator
