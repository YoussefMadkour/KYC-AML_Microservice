"""
Integration tests for KYC processing tasks.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.kyc import DocumentType, KYCStatus
from app.models.user import User, UserRole
from app.repositories.kyc_repository import KYCRepository
from app.repositories.user_repository import UserRepository
from app.schemas.kyc import DocumentCreate, KYCCheckCreate
from app.services.kyc_service import KYCService
from app.services.mock_provider import RiskLevel, VerificationOutcome
from app.tasks.kyc_tasks import (
    process_kyc_batch,
    process_kyc_verification,
    track_kyc_progress,
    update_kyc_status,
)
from app.worker import celery_app


@pytest.fixture
def db_session():
    """Get database session for testing."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user_repo = UserRepository(db_session)
    user_data = {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "date_of_birth": datetime(1990, 1, 1).date(),
        "phone_number": "+1234567890",
        "hashed_password": "hashed_password_here",
        "address_line1": "123 Test St",
        "city": "Test City",
        "state_province": "Test State",
        "postal_code": "12345",
        "country": "US",
        "is_active": True,
        "role": UserRole.USER,
    }
    user = user_repo.create_from_dict(user_data)
    db_session.commit()
    return user


@pytest.fixture
def test_kyc_check(db_session: Session, test_user: User):
    """Create a test KYC check."""
    kyc_service = KYCService(db_session)

    # Create KYC check with documents
    kyc_data = KYCCheckCreate(
        provider="jumio",
        documents=[
            DocumentCreate(
                document_type=DocumentType.PASSPORT,
                file_path="/tmp/passport.jpg",
                file_name="passport.jpg",
                file_size=1024000,
                file_hash="a" * 64,
                mime_type="image/jpeg",
                document_number="P123456789",
                issuing_country="US",
                issue_date=datetime(2020, 1, 1).date(),
                expiry_date=datetime(2030, 1, 1).date(),
            )
        ],
        notes="Test KYC check",
    )

    kyc_check = kyc_service.create_kyc_check(test_user.id, kyc_data)
    return kyc_check


class TestKYCVerificationTask:
    """Test KYC verification processing task."""

    def test_process_kyc_verification_success(
        self, db_session: Session, test_kyc_check
    ):
        """Test successful KYC verification processing."""
        kyc_check_id = str(test_kyc_check.id)

        # Mock the async provider call
        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            # Create mock provider response
            mock_response = MagicMock()
            mock_response.overall_status = VerificationOutcome.APPROVED
            mock_response.risk_level = RiskLevel.LOW
            mock_response.confidence_score = 0.95
            mock_response.processing_time_ms = 2000
            mock_response.provider_reference = "JUM_TEST123456"
            mock_response.document_results = []
            mock_response.biometric_result = None
            mock_response.dict.return_value = {
                "provider_reference": "JUM_TEST123456",
                "overall_status": "approved",
                "confidence_score": 0.95,
            }

            # Mock the service
            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.return_value = mock_response

            # Execute task
            result = process_kyc_verification.apply(args=[kyc_check_id, "jumio"])

            # Verify result
            assert result.successful()
            result_data = result.result
            assert result_data["success"] is True
            assert result_data["data"]["kyc_check_id"] == kyc_check_id
            assert result_data["data"]["status"] == KYCStatus.APPROVED.value
            assert result_data["data"]["provider"] == "jumio"
            assert result_data["data"]["confidence_score"] == 0.95

            # Verify database was updated
            kyc_service = KYCService(db_session)
            updated_check = kyc_service.get_kyc_check(test_kyc_check.id)
            assert updated_check.status == KYCStatus.APPROVED
            assert updated_check.provider_reference == "JUM_TEST123456"
            assert updated_check.verification_result is not None

    def test_process_kyc_verification_rejected(
        self, db_session: Session, test_kyc_check
    ):
        """Test KYC verification with rejection outcome."""
        kyc_check_id = str(test_kyc_check.id)

        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            # Create mock provider response for rejection
            mock_response = MagicMock()
            mock_response.overall_status = VerificationOutcome.REJECTED
            mock_response.risk_level = RiskLevel.HIGH
            mock_response.confidence_score = 0.25
            mock_response.processing_time_ms = 1500
            mock_response.provider_reference = "JUM_REJECT123"
            mock_response.document_results = [
                MagicMock(issues=["Document quality poor", "Potential tampering"])
            ]
            mock_response.biometric_result = None
            mock_response.dict.return_value = {
                "provider_reference": "JUM_REJECT123",
                "overall_status": "rejected",
                "confidence_score": 0.25,
            }

            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.return_value = mock_response

            # Execute task
            result = process_kyc_verification.apply(args=[kyc_check_id, "jumio"])

            # Verify result
            assert result.successful()
            result_data = result.result
            assert result_data["success"] is True
            assert result_data["data"]["status"] == KYCStatus.REJECTED.value

            # Verify database was updated
            kyc_service = KYCService(db_session)
            updated_check = kyc_service.get_kyc_check(test_kyc_check.id)
            assert updated_check.status == KYCStatus.REJECTED
            assert updated_check.rejection_reason is not None
            assert "Document quality poor" in updated_check.rejection_reason

    def test_process_kyc_verification_manual_review(
        self, db_session: Session, test_kyc_check
    ):
        """Test KYC verification requiring manual review."""
        kyc_check_id = str(test_kyc_check.id)

        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            # Create mock provider response for manual review
            mock_response = MagicMock()
            mock_response.overall_status = VerificationOutcome.MANUAL_REVIEW
            mock_response.risk_level = RiskLevel.MEDIUM
            mock_response.confidence_score = 0.65
            mock_response.processing_time_ms = 3000
            mock_response.provider_reference = "JUM_REVIEW123"
            mock_response.document_results = []
            mock_response.biometric_result = None
            mock_response.dict.return_value = {
                "provider_reference": "JUM_REVIEW123",
                "overall_status": "manual_review",
                "confidence_score": 0.65,
            }

            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.return_value = mock_response

            # Execute task
            result = process_kyc_verification.apply(args=[kyc_check_id, "jumio"])

            # Verify result
            assert result.successful()
            result_data = result.result
            assert result_data["data"]["status"] == KYCStatus.MANUAL_REVIEW.value

            # Verify database was updated
            kyc_service = KYCService(db_session)
            updated_check = kyc_service.get_kyc_check(test_kyc_check.id)
            assert updated_check.status == KYCStatus.MANUAL_REVIEW

    def test_process_kyc_verification_not_found(self, db_session: Session):
        """Test KYC verification with non-existent check ID."""
        non_existent_id = str(uuid4())

        # Execute task
        result = process_kyc_verification.apply(args=[non_existent_id, "jumio"])

        # Verify task failed
        assert result.failed()
        # The task should retry and eventually fail

    def test_process_kyc_verification_provider_error(
        self, db_session: Session, test_kyc_check
    ):
        """Test KYC verification with provider error."""
        kyc_check_id = str(test_kyc_check.id)

        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            # Mock provider to raise exception
            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.side_effect = Exception(
                "Provider unavailable"
            )

            # Execute task
            result = process_kyc_verification.apply(args=[kyc_check_id, "jumio"])

            # Verify task failed and will retry
            assert result.failed()

            # Verify KYC check status was updated to rejected
            kyc_service = KYCService(db_session)
            updated_check = kyc_service.get_kyc_check(test_kyc_check.id)
            assert updated_check.status == KYCStatus.REJECTED
            assert "Provider unavailable" in updated_check.rejection_reason


class TestKYCStatusUpdateTask:
    """Test KYC status update task."""

    def test_update_kyc_status_success(self, db_session: Session, test_kyc_check):
        """Test successful KYC status update."""
        kyc_check_id = str(test_kyc_check.id)
        new_status = KYCStatus.APPROVED.value
        details = {"notes": "Manual approval", "updated_by": "admin"}

        # Execute task
        result = update_kyc_status.apply(args=[kyc_check_id, new_status, details])

        # Verify result
        assert result.successful()
        result_data = result.result
        assert result_data["success"] is True
        assert result_data["data"]["kyc_check_id"] == kyc_check_id
        assert result_data["data"]["status"] == new_status

        # Verify database was updated
        kyc_service = KYCService(db_session)
        updated_check = kyc_service.get_kyc_check(test_kyc_check.id)
        assert updated_check.status == KYCStatus.APPROVED
        assert "Manual approval" in updated_check.notes

    def test_update_kyc_status_invalid_status(
        self, db_session: Session, test_kyc_check
    ):
        """Test KYC status update with invalid status."""
        kyc_check_id = str(test_kyc_check.id)
        invalid_status = "invalid_status"

        # Execute task
        result = update_kyc_status.apply(args=[kyc_check_id, invalid_status])

        # Verify task failed
        assert result.failed()

    def test_update_kyc_status_not_found(self, db_session: Session):
        """Test KYC status update with non-existent check ID."""
        non_existent_id = str(uuid4())
        new_status = KYCStatus.APPROVED.value

        # Execute task
        result = update_kyc_status.apply(args=[non_existent_id, new_status])

        # Verify task failed
        assert result.failed()


class TestKYCBatchProcessingTask:
    """Test KYC batch processing task."""

    def test_process_kyc_batch_success(self, db_session: Session, test_user: User):
        """Test successful batch KYC processing."""
        # Create multiple KYC checks
        kyc_service = KYCService(db_session)
        kyc_checks = []

        for i in range(3):
            kyc_data = KYCCheckCreate(
                provider="jumio",
                documents=[
                    DocumentCreate(
                        document_type=DocumentType.PASSPORT,
                        file_path=f"/tmp/passport_{i}.jpg",
                        file_name=f"passport_{i}.jpg",
                        file_size=1024000,
                        file_hash="a" * 64,
                        mime_type="image/jpeg",
                        document_number=f"P12345678{i}",
                        issuing_country="US",
                        issue_date=datetime(2020, 1, 1).date(),
                        expiry_date=datetime(2030, 1, 1).date(),
                    )
                ],
                notes=f"Test KYC check {i}",
            )
            kyc_check = kyc_service.create_kyc_check(test_user.id, kyc_data)
            kyc_checks.append(str(kyc_check.id))

        # Execute batch task
        result = process_kyc_batch.apply(args=[kyc_checks, "jumio"])

        # Verify result
        assert result.successful()
        result_data = result.result
        assert result_data["success"] is True
        assert result_data["data"]["total"] == 3
        assert result_data["data"]["success_count"] == 3
        assert result_data["data"]["failure_count"] == 0
        assert len(result_data["data"]["successful"]) == 3

    def test_process_kyc_batch_empty_list(self, db_session: Session):
        """Test batch processing with empty list."""
        # Execute batch task with empty list
        result = process_kyc_batch.apply(args=[[], "jumio"])

        # Verify result
        assert result.successful()
        result_data = result.result
        assert result_data["data"]["total"] == 0
        assert result_data["data"]["success_count"] == 0


class TestKYCProgressTrackingTask:
    """Test KYC progress tracking task."""

    def test_track_kyc_progress_pending(self, db_session: Session, test_kyc_check):
        """Test tracking progress for pending KYC check."""
        kyc_check_id = str(test_kyc_check.id)

        # Execute task
        result = track_kyc_progress.apply(args=[kyc_check_id])

        # Verify result
        assert result.successful()
        result_data = result.result
        assert result_data["success"] is True

        progress_info = result_data["data"]
        assert progress_info["kyc_check_id"] == kyc_check_id
        assert progress_info["current_status"] == KYCStatus.PENDING.value
        assert progress_info["is_completed"] is False
        assert progress_info["progress_percentage"] == 10
        assert progress_info["documents_count"] == 1

    def test_track_kyc_progress_completed(self, db_session: Session, test_kyc_check):
        """Test tracking progress for completed KYC check."""
        kyc_check_id = str(test_kyc_check.id)

        # Update KYC check to approved status
        kyc_service = KYCService(db_session)
        kyc_service.update_kyc_status(
            test_kyc_check.id,
            status_update=type(
                "StatusUpdate",
                (),
                {
                    "status": KYCStatus.APPROVED,
                    "notes": "Test approval",
                    "rejection_reason": None,
                },
            )(),
            updated_by="test",
        )

        # Execute task
        result = track_kyc_progress.apply(args=[kyc_check_id])

        # Verify result
        assert result.successful()
        result_data = result.result

        progress_info = result_data["data"]
        assert progress_info["current_status"] == KYCStatus.APPROVED.value
        assert progress_info["is_completed"] is True
        assert progress_info["progress_percentage"] == 100

    def test_track_kyc_progress_not_found(self, db_session: Session):
        """Test tracking progress for non-existent KYC check."""
        non_existent_id = str(uuid4())

        # Execute task
        result = track_kyc_progress.apply(args=[non_existent_id])

        # Verify task failed
        assert result.failed()


class TestKYCTaskRetryLogic:
    """Test retry logic for KYC tasks."""

    def test_process_kyc_verification_retry_on_failure(
        self, db_session: Session, test_kyc_check
    ):
        """Test that KYC verification task retries on failure."""
        kyc_check_id = str(test_kyc_check.id)

        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            # Mock provider to raise exception on first call, succeed on second
            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.side_effect = [
                Exception("Temporary failure"),
                Exception("Still failing"),  # Will keep failing for this test
            ]

            # Execute task - it should fail and retry
            result = process_kyc_verification.apply(args=[kyc_check_id, "jumio"])

            # Verify task failed after retries
            assert result.failed()

            # Verify the provider was called multiple times (due to retries)
            assert mock_service_instance.submit_kyc_verification.call_count >= 1

    def test_update_kyc_status_retry_on_database_error(
        self, db_session: Session, test_kyc_check
    ):
        """Test that status update task retries on database errors."""
        kyc_check_id = str(test_kyc_check.id)
        new_status = KYCStatus.APPROVED.value

        with patch("app.tasks.kyc_tasks.KYCService") as mock_service:
            # Mock service to raise exception
            mock_service_instance = mock_service.return_value
            mock_service_instance.update_kyc_status.side_effect = Exception(
                "Database error"
            )

            # Execute task
            result = update_kyc_status.apply(args=[kyc_check_id, new_status])

            # Verify task failed
            assert result.failed()


class TestKYCTaskIntegration:
    """Integration tests for KYC task workflows."""

    def test_complete_kyc_workflow(self, db_session: Session, test_user: User):
        """Test complete KYC workflow from creation to completion."""
        # Create KYC check
        kyc_service = KYCService(db_session)
        kyc_data = KYCCheckCreate(
            provider="jumio",
            documents=[
                DocumentCreate(
                    document_type=DocumentType.PASSPORT,
                    file_path="/tmp/passport.jpg",
                    file_name="passport.jpg",
                    file_size=1024000,
                    file_hash="a" * 64,
                    mime_type="image/jpeg",
                    document_number="P123456789",
                    issuing_country="US",
                    issue_date=datetime(2020, 1, 1).date(),
                    expiry_date=datetime(2030, 1, 1).date(),
                )
            ],
            notes="Integration test KYC check",
        )

        kyc_check = kyc_service.create_kyc_check(test_user.id, kyc_data)
        kyc_check_id = str(kyc_check.id)

        # Step 1: Track initial progress
        progress_result = track_kyc_progress.apply(args=[kyc_check_id])
        assert progress_result.successful()
        assert (
            progress_result.result["data"]["current_status"] == KYCStatus.PENDING.value
        )

        # Step 2: Process KYC verification
        with patch("app.tasks.kyc_tasks.MockProviderService") as mock_service:
            mock_response = MagicMock()
            mock_response.overall_status = VerificationOutcome.APPROVED
            mock_response.risk_level = RiskLevel.LOW
            mock_response.confidence_score = 0.95
            mock_response.processing_time_ms = 2000
            mock_response.provider_reference = "JUM_INTEGRATION123"
            mock_response.document_results = []
            mock_response.biometric_result = None
            mock_response.dict.return_value = {
                "provider_reference": "JUM_INTEGRATION123",
                "overall_status": "approved",
                "confidence_score": 0.95,
            }

            mock_service_instance = mock_service.return_value
            mock_service_instance.submit_kyc_verification.return_value = mock_response

            # Process verification
            verification_result = process_kyc_verification.apply(
                args=[kyc_check_id, "jumio"]
            )
            assert verification_result.successful()
            assert (
                verification_result.result["data"]["status"] == KYCStatus.APPROVED.value
            )

        # Step 3: Track final progress
        final_progress_result = track_kyc_progress.apply(args=[kyc_check_id])
        assert final_progress_result.successful()
        final_progress = final_progress_result.result["data"]
        assert final_progress["current_status"] == KYCStatus.APPROVED.value
        assert final_progress["is_completed"] is True
        assert final_progress["progress_percentage"] == 100
        assert final_progress["provider_reference"] == "JUM_INTEGRATION123"

        # Verify final database state
        final_check = kyc_service.get_kyc_check(kyc_check.id)
        assert final_check.status == KYCStatus.APPROVED
        assert final_check.provider_reference == "JUM_INTEGRATION123"
        assert final_check.verification_result is not None
        assert final_check.completed_at is not None
