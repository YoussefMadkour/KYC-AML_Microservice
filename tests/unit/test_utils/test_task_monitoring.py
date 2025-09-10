"""
Unit tests for task monitoring utilities.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.models.kyc import KYCStatus
from app.utils.task_monitoring import TaskMonitor, get_task_monitor


class TestTaskMonitor:
    """Test TaskMonitor class."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_kyc_repository(self):
        """Mock KYC repository."""
        return Mock()

    @pytest.fixture
    def task_monitor(self, mock_db, mock_kyc_repository):
        """Create TaskMonitor instance with mocked dependencies."""
        with patch("app.utils.task_monitoring.KYCRepository") as mock_repo_class:
            mock_repo_class.return_value = mock_kyc_repository
            monitor = TaskMonitor(mock_db)
            monitor.kyc_repository = mock_kyc_repository
            return monitor

    def test_get_task_status_success(self, task_monitor):
        """Test successful task status retrieval."""
        task_id = "test-task-123"

        with patch("app.utils.task_monitoring.celery_app") as mock_celery:
            # Mock AsyncResult
            mock_result = Mock()
            mock_result.status = "SUCCESS"
            mock_result.ready.return_value = True
            mock_result.successful.return_value = True
            mock_result.failed.return_value = False
            mock_result.result = {"success": True, "data": {"test": "data"}}
            mock_result.traceback = None
            mock_result.date_done = datetime.utcnow()

            mock_celery.AsyncResult.return_value = mock_result

            # Test
            status = task_monitor.get_task_status(task_id)

            # Verify
            assert status is not None
            assert status["task_id"] == task_id
            assert status["status"] == "SUCCESS"
            assert status["ready"] is True
            assert status["successful"] is True
            assert status["failed"] is False
            assert status["result"] == {"success": True, "data": {"test": "data"}}
            assert status["date_done"] is not None

    def test_get_task_status_not_found(self, task_monitor):
        """Test task status retrieval for non-existent task."""
        task_id = "non-existent-task"

        with patch("app.utils.task_monitoring.celery_app") as mock_celery:
            mock_celery.AsyncResult.side_effect = Exception("Task not found")

            # Test
            status = task_monitor.get_task_status(task_id)

            # Verify
            assert status is None

    def test_get_kyc_processing_status_success(self, task_monitor, mock_kyc_repository):
        """Test successful KYC processing status retrieval."""
        kyc_check_id = uuid4()

        # Mock KYC check
        mock_kyc_check = Mock()
        mock_kyc_check.id = kyc_check_id
        mock_kyc_check.status = KYCStatus.IN_PROGRESS
        mock_kyc_check.is_completed = False
        mock_kyc_check.is_pending_review = False
        mock_kyc_check.provider = "jumio"
        mock_kyc_check.provider_reference = "JUM_123456"
        mock_kyc_check.submitted_at = datetime.utcnow() - timedelta(minutes=2)
        mock_kyc_check.completed_at = None
        mock_kyc_check.processing_time_seconds = 120
        mock_kyc_check.documents = [Mock(), Mock()]  # 2 documents
        mock_kyc_check.risk_score = "low"
        mock_kyc_check.notes = "Processing in progress"
        mock_kyc_check.rejection_reason = None
        mock_kyc_check.verification_result = {
            "overall_outcome": "pending",
            "confidence_score": 0.8,
            "processing_time_ms": 2000,
        }

        mock_kyc_repository.get_with_documents.return_value = mock_kyc_check

        # Test
        status = task_monitor.get_kyc_processing_status(kyc_check_id)

        # Verify
        assert status["kyc_check_id"] == str(kyc_check_id)
        assert status["status"] == KYCStatus.IN_PROGRESS.value
        assert status["is_completed"] is False
        assert status["progress_percentage"] == 50
        assert status["provider"] == "jumio"
        assert status["documents_count"] == 2
        assert status["estimated_completion_seconds"] > 0
        assert "verification_summary" in status

    def test_get_kyc_processing_status_not_found(
        self, task_monitor, mock_kyc_repository
    ):
        """Test KYC processing status for non-existent check."""
        kyc_check_id = uuid4()
        mock_kyc_repository.get_with_documents.return_value = None

        # Test
        status = task_monitor.get_kyc_processing_status(kyc_check_id)

        # Verify
        assert "error" in status
        assert status["error"] == "KYC check not found"

    def test_get_active_tasks_for_kyc(self, task_monitor):
        """Test getting active tasks for KYC check."""
        kyc_check_id = uuid4()

        with patch("app.utils.task_monitoring.celery_app") as mock_celery:
            # Mock inspect
            mock_inspect = Mock()
            mock_active_tasks = {
                "worker1": [
                    {
                        "id": "task-1",
                        "name": "app.tasks.kyc_tasks.process_kyc_verification",
                        "args": [str(kyc_check_id)],
                        "kwargs": {},
                        "time_start": 1234567890,
                        "acknowledged": True,
                    },
                    {
                        "id": "task-2",
                        "name": "app.tasks.other_tasks.some_task",
                        "args": ["other-id"],
                        "kwargs": {},
                        "time_start": 1234567891,
                        "acknowledged": True,
                    },
                ]
            }
            mock_inspect.active.return_value = mock_active_tasks
            mock_celery.control.inspect.return_value = mock_inspect

            # Test
            active_tasks = task_monitor.get_active_tasks_for_kyc(kyc_check_id)

            # Verify - should only return KYC-related task
            assert len(active_tasks) == 1
            assert active_tasks[0]["task_id"] == "task-1"
            assert (
                active_tasks[0]["task_name"]
                == "app.tasks.kyc_tasks.process_kyc_verification"
            )
            assert active_tasks[0]["worker"] == "worker1"

    def test_get_task_history_for_kyc(self, task_monitor, mock_kyc_repository):
        """Test getting task history for KYC check."""
        kyc_check_id = uuid4()

        # Mock KYC check
        mock_kyc_check = Mock()
        mock_kyc_check.created_at = datetime.utcnow() - timedelta(hours=1)
        mock_kyc_check.updated_at = datetime.utcnow() - timedelta(minutes=30)
        mock_kyc_check.completed_at = datetime.utcnow() - timedelta(minutes=10)
        mock_kyc_check.status = KYCStatus.APPROVED

        mock_kyc_repository.get.return_value = mock_kyc_check

        # Test
        history = task_monitor.get_task_history_for_kyc(kyc_check_id)

        # Verify
        assert len(history) >= 2  # At least creation and completion events
        assert any(event["event"] == "kyc_check_created" for event in history)
        assert any(event["event"] == "processing_completed" for event in history)

    def test_get_system_task_statistics(self, task_monitor):
        """Test getting system task statistics."""
        with patch("app.utils.task_monitoring.celery_app") as mock_celery:
            # Mock inspect
            mock_inspect = Mock()
            mock_inspect.active.return_value = {
                "worker1": [
                    {"name": "app.tasks.kyc_tasks.process_kyc_verification"},
                    {"name": "app.tasks.kyc_tasks.update_kyc_status"},
                ],
                "worker2": [{"name": "app.tasks.webhook_tasks.process_webhook"}],
            }
            mock_inspect.scheduled.return_value = {
                "worker1": [{"name": "scheduled_task"}]
            }
            mock_inspect.reserved.return_value = {
                "worker1": [{"name": "reserved_task"}]
            }
            mock_inspect.active_queues.return_value = {
                "worker1": [
                    {
                        "name": "kyc_queue",
                        "routing_key": "kyc_queue",
                        "exchange": {"name": "default"},
                    }
                ]
            }

            mock_celery.control.inspect.return_value = mock_inspect

            # Test
            stats = task_monitor.get_system_task_statistics()

            # Verify
            assert stats["active_tasks"] == 3
            assert stats["scheduled_tasks"] == 1
            assert stats["reserved_tasks"] == 1
            assert len(stats["workers"]) == 2
            assert "kyc_queue" in stats["queues"]
            assert "app.tasks.kyc_tasks.process_kyc_verification" in stats["task_types"]

    def test_cancel_kyc_processing_success(self, task_monitor, mock_kyc_repository):
        """Test successful KYC processing cancellation."""
        kyc_check_id = uuid4()

        # Mock active tasks
        with patch.object(task_monitor, "get_active_tasks_for_kyc") as mock_get_tasks:
            mock_get_tasks.return_value = [
                {"task_id": "task-1", "task_name": "process_kyc_verification"},
                {"task_id": "task-2", "task_name": "update_kyc_status"},
            ]

            with patch("app.utils.task_monitoring.celery_app") as mock_celery:
                # Mock KYC check
                mock_kyc_check = Mock()
                mock_kyc_check.status = KYCStatus.IN_PROGRESS
                mock_kyc_repository.get.return_value = mock_kyc_check

                # Test
                result = task_monitor.cancel_kyc_processing(
                    kyc_check_id, "User requested cancellation"
                )

                # Verify
                assert result is True
                assert mock_celery.control.revoke.call_count == 2
                mock_kyc_repository.update_status.assert_called_once()

    def test_cancel_kyc_processing_no_active_tasks(self, task_monitor):
        """Test KYC processing cancellation with no active tasks."""
        kyc_check_id = uuid4()

        with patch.object(task_monitor, "get_active_tasks_for_kyc") as mock_get_tasks:
            mock_get_tasks.return_value = []

            # Test
            result = task_monitor.cancel_kyc_processing(kyc_check_id)

            # Verify
            assert result is False

    def test_extract_verification_summary(self, task_monitor):
        """Test verification result summary extraction."""
        verification_result = {
            "overall_outcome": "approved",
            "confidence_score": 0.95,
            "risk_level": "low",
            "processing_time_ms": 3000,
            "document_results": [
                {"status": "approved", "document_type": "passport"},
                {"status": "approved", "document_type": "utility_bill"},
            ],
            "biometric_result": {
                "face_match_score": 0.92,
                "liveness_score": 0.88,
                "quality_score": 0.85,
            },
        }

        # Test
        summary = task_monitor._extract_verification_summary(verification_result)

        # Verify
        assert summary["outcome"] == "approved"
        assert summary["confidence"] == 0.95
        assert summary["risk_level"] == "low"
        assert summary["processing_time_ms"] == 3000
        assert summary["documents_processed"] == 2
        assert summary["documents_approved"] == 2
        assert summary["biometric_match"] == 0.92
        assert summary["liveness_score"] == 0.88

    def test_is_kyc_related_task_true(self, task_monitor):
        """Test KYC task identification - positive case."""
        kyc_check_id = str(uuid4())
        task_info = {
            "name": "app.tasks.kyc_tasks.process_kyc_verification",
            "args": [kyc_check_id, "jumio"],
            "kwargs": {},
        }

        # Test
        result = task_monitor._is_kyc_related_task(task_info, kyc_check_id)

        # Verify
        assert result is True

    def test_is_kyc_related_task_false(self, task_monitor):
        """Test KYC task identification - negative case."""
        kyc_check_id = str(uuid4())
        task_info = {
            "name": "app.tasks.other_tasks.some_task",
            "args": ["other-id"],
            "kwargs": {},
        }

        # Test
        result = task_monitor._is_kyc_related_task(task_info, kyc_check_id)

        # Verify
        assert result is False

    def test_is_kyc_related_task_kwargs_match(self, task_monitor):
        """Test KYC task identification with kwargs match."""
        kyc_check_id = str(uuid4())
        task_info = {
            "name": "app.tasks.kyc_tasks.update_kyc_status",
            "args": [],
            "kwargs": {"kyc_check_id": kyc_check_id},
        }

        # Test
        result = task_monitor._is_kyc_related_task(task_info, kyc_check_id)

        # Verify
        assert result is True


class TestGetTaskMonitor:
    """Test get_task_monitor function."""

    def test_get_task_monitor_with_db(self):
        """Test getting task monitor with provided database session."""
        mock_db = Mock()

        with patch("app.utils.task_monitoring.KYCRepository"):
            monitor = get_task_monitor(mock_db)

            assert isinstance(monitor, TaskMonitor)
            assert monitor.db == mock_db

    def test_get_task_monitor_without_db(self):
        """Test getting task monitor without database session."""
        with patch("app.utils.task_monitoring.get_db") as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])

            with patch("app.utils.task_monitoring.KYCRepository"):
                monitor = get_task_monitor()

                assert isinstance(monitor, TaskMonitor)
                assert monitor.db == mock_db
