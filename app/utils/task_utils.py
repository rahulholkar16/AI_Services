import asyncio
import logging

logger = logging.getLogger(__name__)

def log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task failed: %r", exc)
