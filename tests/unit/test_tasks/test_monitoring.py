"""
Unit tests for task monitoring utilities.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.utils.task_monitoring import TaskLogger, TaskMonitor


class TestTaskMonitor:
    """Test TaskMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_celery_app = Mock()
        self.monitor = TaskMonitor(self.mock_celery_app)

    def test_get_active_tasks_success(self):
        """Test getting active tasks successfully."""
        # Mock inspect and active tasks
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        mock_active_tasks = {
            "worker1": [
                {
                    "id": "task_123",
                    "name": "app.tasks.kyc_tasks.process_kyc_verification",
                    "args": ["kyc_123"],
                    "kwargs": {"correlation_id": "corr_123"},
                    "time_start": 1234567890.0,
                }
            ]
        }
        mock_inspect.active.return_value = mock_active_tasks

        result = self.monitor.get_active_tasks()

        assert "worker1" in result
        assert len(result["worker1"]) == 1
        task = result["worker1"][0]
        assert task["task_id"] == "task_123"
        assert task["task_name"] == "app.tasks.kyc_tasks.process_kyc_verification"
        assert task["args"] == ["kyc_123"]
        assert task["worker"] == "worker1"

    @patch("app.utils.task_monitoring.logger")
    def test_get_active_tasks_error(self, mock_logger):
        """Test getting active tasks with error."""
        self.mock_celery_app.control.inspect.side_effect = Exception("Connection error")

        result = self.monitor.get_active_tasks()

        assert result == {}
        mock_logger.error.assert_called_once()

    def test_get_scheduled_tasks_success(self):
        """Test getting scheduled tasks successfully."""
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        mock_scheduled_tasks = {
            "worker1": [
                {
                    "request": {
                        "id": "task_456",
                        "task": "app.tasks.webhook_tasks.process_webhook_event",
                        "args": ["webhook_123"],
                        "kwargs": {"idempotency_key": "idem_123"},
                    },
                    "eta": "2023-01-01T12:00:00",
                    "priority": 6,
                }
            ]
        }
        mock_inspect.scheduled.return_value = mock_scheduled_tasks

        result = self.monitor.get_scheduled_tasks()

        assert "worker1" in result
        assert len(result["worker1"]) == 1
        task = result["worker1"][0]
        assert task["task_id"] == "task_456"
        assert task["task_name"] == "app.tasks.webhook_tasks.process_webhook_event"
        assert task["eta"] == "2023-01-01T12:00:00"
        assert task["priority"] == 6

    def test_get_worker_stats_success(self):
        """Test getting worker stats successfully."""
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        mock_stats = {
            "worker1": {
                "pool": {"max-concurrency": 4, "processes": [1234, 1235]},
                "total": {"tasks.kyc": 10, "tasks.webhook": 5},
                "rusage": {"utime": 1.5, "stime": 0.5},
                "clock": "123456789",
                "pid": 1234,
                "broker": {"transport": "pyamqp", "hostname": "localhost"},
            }
        }
        mock_inspect.stats.return_value = mock_stats

        result = self.monitor.get_worker_stats()

        assert "worker1" in result
        worker_stats = result["worker1"]
        assert worker_stats["status"] == "online"
        assert worker_stats["pool"]["max-concurrency"] == 4
        assert worker_stats["total_tasks"]["tasks.kyc"] == 10
        assert worker_stats["pid"] == 1234

    def test_health_check_healthy(self):
        """Test health check when system is healthy."""
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        # Mock successful stats call
        mock_inspect.stats.return_value = {"worker1": {"pid": 1234}}

        # Mock successful ping
        mock_inspect.ping.return_value = {"worker1": "pong"}

        # Mock AsyncResult for result backend check
        mock_result = Mock()
        self.mock_celery_app.AsyncResult.return_value = mock_result

        result = self.monitor.health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert result["checks"]["workers"]["status"] == "healthy"
        assert result["checks"]["workers"]["worker_count"] == 1
        assert result["checks"]["broker"]["status"] == "healthy"
        assert result["checks"]["result_backend"]["status"] == "healthy"

    def test_health_check_unhealthy_no_workers(self):
        """Test health check when no workers are available."""
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        # Mock no workers available
        mock_inspect.stats.return_value = None

        result = self.monitor.health_check()

        assert result["status"] == "unhealthy"
        assert result["checks"]["workers"]["status"] == "unhealthy"
        assert "No workers available" in result["checks"]["workers"]["error"]

    def test_health_check_broker_error(self):
        """Test health check when broker is unavailable."""
        mock_inspect = Mock()
        self.mock_celery_app.control.inspect.return_value = mock_inspect

        # Mock successful stats but failed ping
        mock_inspect.stats.return_value = {"worker1": {"pid": 1234}}
        mock_inspect.ping.side_effect = Exception("Broker connection failed")

        result = self.monitor.health_check()

        assert result["status"] == "unhealthy"
        assert result["checks"]["broker"]["status"] == "unhealthy"
        assert "Broker connection failed" in result["checks"]["broker"]["error"]


class TestTaskLogger:
    """Test TaskLogger class."""

    @patch("app.utils.task_monitoring.logging.getLogger")
    @patch("app.utils.task_monitoring.time.time")
    def test_task_logger_initialization(self, mock_time, mock_get_logger):
        """Test TaskLogger initialization."""
        mock_time.return_value = 1234567890.0
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        task_logger = TaskLogger("test_task", "task_123")

        assert task_logger.task_name == "test_task"
        assert task_logger.task_id == "task_123"
        assert task_logger.start_time == 1234567890.0
        mock_get_logger.assert_called_once_with("tasks.test_task")

    @patch("app.utils.task_monitoring.logging.getLogger")
    @patch("app.utils.task_monitoring.time.time")
    def test_info_logging(self, mock_time, mock_get_logger):
        """Test info logging with task context."""
        mock_time.side_effect = [1234567890.0, 1234567895.0]  # start_time, current_time
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        task_logger = TaskLogger("test_task", "task_123")
        task_logger.info("Test message", custom_field="custom_value")

        mock_logger.info.assert_called_once_with(
            "Test message",
            extra={
                "task_name": "test_task",
                "task_id": "task_123",
                "duration": 5.0,
                "custom_field": "custom_value",
            },
        )

    @patch("app.utils.task_monitoring.logging.getLogger")
    @patch("app.utils.task_monitoring.time.time")
    def test_error_logging(self, mock_time, mock_get_logger):
        """Test error logging with task context."""
        mock_time.side_effect = [1234567890.0, 1234567900.0]
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        task_logger = TaskLogger("test_task", "task_123")
        task_logger.error("Error message", error_code="E001")

        mock_logger.error.assert_called_once_with(
            "Error message",
            extra={
                "task_name": "test_task",
                "task_id": "task_123",
                "duration": 10.0,
                "error_code": "E001",
            },
        )

    @patch("app.utils.task_monitoring.logging.getLogger")
    @patch("app.utils.task_monitoring.time.time")
    def test_warning_logging(self, mock_time, mock_get_logger):
        """Test warning logging with task context."""
        mock_time.side_effect = [1234567890.0, 1234567892.0]
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        task_logger = TaskLogger("test_task", "task_123")
        task_logger.warning("Warning message", warning_type="RETRY")

        mock_logger.warning.assert_called_once_with(
            "Warning message",
            extra={
                "task_name": "test_task",
                "task_id": "task_123",
                "duration": 2.0,
                "warning_type": "RETRY",
            },
        )

    @patch("app.utils.task_monitoring.logging.getLogger")
    @patch("app.utils.task_monitoring.time.time")
    def test_debug_logging(self, mock_time, mock_get_logger):
        """Test debug logging with task context."""
        mock_time.side_effect = [1234567890.0, 1234567891.0]
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        task_logger = TaskLogger("test_task", "task_123")
        task_logger.debug("Debug message", debug_info="details")

        mock_logger.debug.assert_called_once_with(
            "Debug message",
            extra={
                "task_name": "test_task",
                "task_id": "task_123",
                "duration": 1.0,
                "debug_info": "details",
            },
        )
