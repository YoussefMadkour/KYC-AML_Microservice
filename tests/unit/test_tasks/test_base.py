"""
Unit tests for base task classes and utilities.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from celery.exceptions import Retry

from app.tasks.base import (
    BaseTask,
    KYCTask,
    TaskResult,
    WebhookTask,
    get_task_status,
    revoke_task,
)


class TestTaskResult:
    """Test TaskResult class."""

    def test_success_result_creation(self):
        """Test creating a success result."""
        data = {"key": "value"}
        metadata = {"task_id": "123"}

        result = TaskResult.success_result(data=data, metadata=metadata)

        assert result.success is True
        assert result.data == data
        assert result.error is None
        assert result.metadata == metadata

    def test_error_result_creation(self):
        """Test creating an error result."""
        error = "Something went wrong"
        data = {"key": "value"}
        metadata = {"task_id": "123"}

        result = TaskResult.error_result(error=error, data=data, metadata=metadata)

        assert result.success is False
        assert result.data == data
        assert result.error == error
        assert result.metadata == metadata

    def test_to_dict_conversion(self):
        """Test converting result to dictionary."""
        result = TaskResult(
            success=True, data={"key": "value"}, error=None, metadata={"task_id": "123"}
        )

        result_dict = result.to_dict()

        expected = {
            "success": True,
            "data": {"key": "value"},
            "error": None,
            "metadata": {"task_id": "123"},
        }
        assert result_dict == expected


class TestBaseTask:
    """Test BaseTask class."""

    def test_base_task_configuration(self):
        """Test BaseTask has correct configuration."""
        task = BaseTask()

        assert task.autoretry_for == (Exception,)
        assert task.retry_kwargs["max_retries"] == 3
        assert task.retry_kwargs["countdown"] == 60
        assert task.retry_backoff is True
        assert task.retry_backoff_max == 600
        assert task.retry_jitter is True

    @patch("app.tasks.base.logger")
    def test_on_success_logging(self, mock_logger):
        """Test success logging."""
        task = BaseTask()
        task.name = "test_task"

        task.on_success("result", "task_123", ("arg1",), {"kwarg1": "value1"})

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Task succeeded" in call_args[0][0]
        assert call_args[1]["extra"]["task_id"] == "task_123"
        assert call_args[1]["extra"]["task_name"] == "test_task"

    @patch("app.tasks.base.logger")
    def test_on_failure_logging(self, mock_logger):
        """Test failure logging."""
        task = BaseTask()
        task.name = "test_task"

        exc = Exception("Test error")
        task.on_failure(exc, "task_123", ("arg1",), {"kwarg1": "value1"}, None)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Task failed permanently" in call_args[0][0]
        assert call_args[1]["extra"]["task_id"] == "task_123"
        assert call_args[1]["extra"]["error"] == "Test error"

    @patch("app.tasks.base.logger")
    def test_on_retry_logging(self, mock_logger):
        """Test retry logging."""
        task = BaseTask()
        task.name = "test_task"
        task.max_retries = 3

        exc = Exception("Test error")
        task.on_retry(exc, "task_123", ("arg1",), {"kwarg1": "value1"}, None)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Task retry" in call_args[0][0]
        assert (
            call_args[1]["extra"]["retry_count"] == 0
        )  # Will be 0 since no request object
        assert call_args[1]["extra"]["max_retries"] == 3


class TestKYCTask:
    """Test KYCTask class."""

    def test_kyc_task_configuration(self):
        """Test KYCTask has correct configuration."""
        task = KYCTask()

        assert task.retry_kwargs["max_retries"] == 5
        assert task.retry_kwargs["countdown"] == 30
        assert task.retry_backoff_max == 300

    def test_apply_async_sets_queue(self):
        """Test that apply_async sets the correct queue."""
        task = KYCTask()

        # Mock the parent apply_async method
        with patch.object(BaseTask, "apply_async") as mock_apply_async:
            mock_apply_async.return_value = Mock()

            # Call apply_async
            task.apply_async(args=("arg1",), kwargs={"key": "value"})

            # Verify the queue was set
            call_args = mock_apply_async.call_args
            assert call_args[1]["queue"] == "kyc_queue"


class TestWebhookTask:
    """Test WebhookTask class."""

    def test_webhook_task_configuration(self):
        """Test WebhookTask has correct configuration."""
        task = WebhookTask()

        assert task.retry_kwargs["max_retries"] == 3
        assert task.retry_kwargs["countdown"] == 10
        assert task.retry_backoff_max == 120

    def test_apply_async_sets_queue(self):
        """Test that apply_async sets the correct queue."""
        task = WebhookTask()

        # Mock the parent apply_async method
        with patch.object(BaseTask, "apply_async") as mock_apply_async:
            mock_apply_async.return_value = Mock()

            # Call apply_async
            task.apply_async(args=("arg1",), kwargs={"key": "value"})

            # Verify the queue was set
            call_args = mock_apply_async.call_args
            assert call_args[1]["queue"] == "webhook_queue"


class TestTaskUtilities:
    """Test task utility functions."""

    @patch("app.tasks.base.celery_app")
    def test_get_task_status_success(self, mock_celery_app):
        """Test getting task status successfully."""
        # Mock AsyncResult
        mock_result = Mock()
        mock_result.status = "SUCCESS"
        mock_result.result = {"data": "test"}
        mock_result.ready.return_value = True
        mock_result.failed.return_value = False
        mock_result.traceback = None
        mock_result.date_done = "2023-01-01T00:00:00"

        mock_celery_app.AsyncResult.return_value = mock_result

        status = get_task_status("task_123")

        assert status["task_id"] == "task_123"
        assert status["status"] == "SUCCESS"
        assert status["result"] == {"data": "test"}
        assert status["traceback"] is None
        assert status["date_done"] == "2023-01-01T00:00:00"

    @patch("app.tasks.base.celery_app")
    @patch("app.tasks.base.logger")
    def test_get_task_status_error(self, mock_logger, mock_celery_app):
        """Test getting task status with error."""
        mock_celery_app.AsyncResult.side_effect = Exception("Connection error")

        status = get_task_status("task_123")

        assert status is None
        mock_logger.error.assert_called_once()

    @patch("app.tasks.base.celery_app")
    @patch("app.tasks.base.logger")
    def test_revoke_task_success(self, mock_logger, mock_celery_app):
        """Test revoking task successfully."""
        mock_control = Mock()
        mock_celery_app.control = mock_control

        result = revoke_task("task_123", terminate=True)

        assert result is True
        mock_control.revoke.assert_called_once_with("task_123", terminate=True)
        mock_logger.info.assert_called_once()

    @patch("app.tasks.base.celery_app")
    @patch("app.tasks.base.logger")
    def test_revoke_task_error(self, mock_logger, mock_celery_app):
        """Test revoking task with error."""
        mock_control = Mock()
        mock_control.revoke.side_effect = Exception("Revoke error")
        mock_celery_app.control = mock_control

        result = revoke_task("task_123")

        assert result is False
        mock_logger.error.assert_called_once()


class TestTaskRetryMechanisms:
    """Test task retry mechanisms."""

    def test_exponential_backoff_calculation(self):
        """Test that retry backoff is configured correctly."""
        task = BaseTask()

        # Verify backoff settings
        assert task.retry_backoff is True
        assert task.retry_backoff_max == 600
        assert task.retry_jitter is True

    def test_kyc_task_retry_limits(self):
        """Test KYC task retry limits."""
        task = KYCTask()

        assert task.retry_kwargs["max_retries"] == 5
        assert task.retry_backoff_max == 300  # 5 minutes max

    def test_webhook_task_retry_limits(self):
        """Test webhook task retry limits."""
        task = WebhookTask()

        assert task.retry_kwargs["max_retries"] == 3
        assert task.retry_backoff_max == 120  # 2 minutes max
