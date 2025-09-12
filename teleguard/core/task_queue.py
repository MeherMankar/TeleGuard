"""Background task queue with retry mechanisms"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class Task:
    def __init__(
        self,
        task_id: str,
        func: Callable,
        args: tuple,
        kwargs: dict,
        max_retries: int = 3,
        retry_delay: int = 60,
    ):
        self.task_id = task_id
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.attempts = 0
        self.created_at = datetime.now(timezone.utc)
        self.next_run = datetime.now(timezone.utc)


class TaskQueue:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running = False
        self.worker_task = None

    async def add_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        max_retries: int = 3,
        retry_delay: int = 60,
        **kwargs,
    ):
        """Add task to queue"""
        task = Task(task_id, func, args, kwargs, max_retries, retry_delay)
        self.tasks[task_id] = task

        logger.info("Task added to queue", task_id=task_id, func=func.__name__)

        if not self.running:
            await self.start()

    async def start(self):
        """Start task worker"""
        if self.running:
            return

        self.running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Task queue started")

    async def stop(self):
        """Stop task worker"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
        logger.info("Task queue stopped")

    async def _worker(self):
        """Background worker to process tasks"""
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                ready_tasks = [
                    task
                    for task in self.tasks.values()
                    if task.next_run <= current_time
                ]

                for task in ready_tasks:
                    await self._execute_task(task)

                await asyncio.sleep(10)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Task worker error", error=str(e))
                await asyncio.sleep(30)

    async def _execute_task(self, task: Task):
        """Execute a single task"""
        try:
            task.attempts += 1
            logger.info("Executing task", task_id=task.task_id, attempt=task.attempts)

            if asyncio.iscoroutinefunction(task.func):
                await task.func(*task.args, **task.kwargs)
            else:
                task.func(*task.args, **task.kwargs)

            # Task completed successfully
            del self.tasks[task.task_id]
            logger.info("Task completed", task_id=task.task_id)

        except Exception as e:
            logger.error(
                "Task execution failed",
                task_id=task.task_id,
                attempt=task.attempts,
                error=str(e),
            )

            if task.attempts >= task.max_retries:
                # Max retries reached, remove task
                del self.tasks[task.task_id]
                logger.error("Task failed permanently", task_id=task.task_id)
            else:
                # Schedule retry
                task.next_run = datetime.now(timezone.utc) + timedelta(
                    seconds=task.retry_delay
                )
                logger.info(
                    "Task scheduled for retry",
                    task_id=task.task_id,
                    next_run=task.next_run.isoformat(),
                )


# Global task queue
task_queue = TaskQueue()
