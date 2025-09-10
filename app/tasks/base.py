"""
Base task classes with retry logic and error handling.
"""

import logging
import traceback
from typing import Any, Dict, Optional

from celery import Task
from celery.exceptions import Retry

from app.core.config import settings
from app.worker import celery_app

logger = logging.getLogger(__name__)


class BaseTask(Task):
    """
    Base task class with common retry logic and error handling.
    """

    # Default retry settings
    autoretry_for = (Exception,)
    retry_kwargs = {
        "max_retries": 3,
        "countdown": 60,  # Initial delay in seconds
    }
    retry_backoff = True
    retry_backoff_max = 600  # Max delay of 10 minutes
    retry_jitter = True

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """
        Success handler called when task succeeds.
        """
        logger.info(
            "Task succeeded",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "result": retval,
            },
        )

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """
        Failure handler called when task fails permanently.
        """
        logger.error(
            "Task failed permanently",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "error": str(exc),
                "traceback": traceback.format_exception(
                    type(exc), exc, exc.__traceback__
                ),
            },
        )

    def on_retry(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """
        Retry handler called when task is retried.
        """
        logger.warning(
            "Task retry",
            extra={
                "task_id": task_id,
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
                "error": str(exc),
                "retry_count": (
                    getattr(self.request, "retries", 0)
                    if hasattr(self, "request")
                    else 0
                ),
                "max_retries": self.max_retries,
            },
        )


class KYCTask(BaseTask):
    """
    Base class for KYC-related tasks with specific retry logic.
    """

    # KYC-specific retry settings
    retry_kwargs = {
        "max_retries": 5,
        "countdown": 30,
    }
    retry_backoff_max = 300  # Max delay of 5 minutes for KYC tasks

    def apply_async(self, args=None, kwargs=None, **options):
        """
        Override apply_async to add KYC-specific options.
        """
        # Set default queue for KYC tasks
        options.setdefault("queue", "kyc_queue")

        # Add correlation ID for tracking
        if kwargs and "correlation_id" not in kwargs:
            kwargs["correlation_id"] = (
                self.request.id if hasattr(self, "request") else None
            )

        return super().apply_async(args, kwargs, **options)


class WebhookTask(BaseTask):
    """
    Base class for webhook-related tasks with specific retry logic.
    """

    # Webhook-specific retry settings
    retry_kwargs = {
        "max_retries": 3,
        "countdown": 10,
    }
    retry_backoff_max = 120  # Max delay of 2 minutes for webhooks

    def apply_async(self, args=None, kwargs=None, **options):
        """
        Override apply_async to add webhook-specific options.
        """
        # Set default queue for webhook tasks
        options.setdefault("queue", "webhook_queue")

        # Add idempotency key for webhook processing
        if kwargs and "idempotency_key" not in kwargs:
            kwargs["idempotency_key"] = (
                f"webhook_{self.request.id}" if hasattr(self, "request") else None
            )

        return super().apply_async(args, kwargs, **options)


class TaskResult:
    """
    Standardized task result wrapper.
    """

    def __init__(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def success_result(
        cls,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "TaskResult":
        """Create a success result."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def error_result(
        cls,
        error: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "TaskResult":
        """Create an error result."""
        return cls(success=False, data=data, error=error, metadata=metadata)


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get task status and result from Celery.

    Args:
        task_id: The task ID to check

    Returns:
        Dictionary with task status information or None if not found
    """
    try:
        result = celery_app.AsyncResult(task_id)

        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None,
            "date_done": result.date_done,
        }
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}")
        return None


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """
    Revoke a task.

    Args:
        task_id: The task ID to revoke
        terminate: Whether to terminate the task if it's running

    Returns:
        True if task was revoked successfully
    """
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} revoked successfully")
        return True
    except Exception as e:
        logger.error(f"Error revoking task {task_id}: {e}")
        return False
