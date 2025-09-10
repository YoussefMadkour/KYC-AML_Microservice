"""
Unit tests for GDPR service.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.models.user import User, UserRole
from app.services.gdpr_service import GDPRService


class TestGDPRService:
    """Test cases for GDPR service."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository."""
        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        repo.update = AsyncMock()
        repo.delete = AsyncMock()
        return repo

    @pytest.fixture
    def mock_kyc_repo(self):
        """Mock KYC repository."""
        repo = MagicMock()
        repo.get_by_user_id = AsyncMock()
        repo.get_documents_by_kyc_id = AsyncMock()
        repo.update = AsyncMock()
        repo.delete = AsyncMock()
        repo.delete_document = AsyncMock()
        repo.update_document = AsyncMock()
        return repo

    @pytest.fixture
    def mock_webhook_repo(self):
        """Mock webhook repository."""
        repo = MagicMock()
        repo.get_by_user_id = AsyncMock()
        repo.delete = AsyncMock()
        return repo

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            phone_number="1234567890",
            address_line1="123 Main St",
            city="Anytown",
            state_province="State",
            postal_code="12345",
            country="US",
            role=UserRole.USER,
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        return user

    @pytest.fixture
    def sample_kyc_check(self, sample_user):
        """Sample KYC check for testing."""
        return KYCCheck(
            id=uuid4(),
            user_id=sample_user.id,
            status=KYCStatus.APPROVED,
            provider="mock_provider",
            provider_reference="ref123",
            verification_result={"status": "approved"},
            risk_score="low",
            submitted_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

    @pytest.fixture
    def sample_document(self, sample_kyc_check):
        """Sample document for testing."""
        return Document(
            id=uuid4(),
            kyc_check_id=sample_kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/doc.pdf",
            file_name="passport.pdf",
            file_size="1024",
            file_hash="abc123",
            document_number="P123456789",
            issuing_country="US",
            is_verified="verified",
            created_at=datetime.utcnow(),
        )

    @pytest.fixture
    def gdpr_service(self, mock_db, mock_user_repo, mock_kyc_repo, mock_webhook_repo):
        """GDPR service instance with mocked dependencies."""
        return GDPRService(
            db=mock_db,
            user_repo=mock_user_repo,
            kyc_repo=mock_kyc_repo,
            webhook_repo=mock_webhook_repo,
        )

    @pytest.mark.asyncio
    async def test_export_user_data_success(
        self,
        gdpr_service,
        mock_user_repo,
        mock_kyc_repo,
        mock_webhook_repo,
        sample_user,
        sample_kyc_check,
        sample_document,
    ):
        """Test successful user data export."""
        # Setup mocks
        mock_user_repo.get_by_id.return_value = sample_user
        mock_kyc_repo.get_by_user_id.return_value = [sample_kyc_check]
        mock_kyc_repo.get_documents_by_kyc_id.return_value = [sample_document]
        mock_webhook_repo.get_by_user_id.return_value = []

        # Execute
        result = await gdpr_service.export_user_data(sample_user.id)

        # Verify
        assert result["export_metadata"]["user_id"] == str(sample_user.id)
        assert result["export_metadata"]["export_type"] == "gdpr_data_export"
        assert result["user_profile"]["email"] == sample_user.email
        assert result["user_profile"]["first_name"] == sample_user.first_name
        assert len(result["kyc_checks"]) == 1
        assert result["kyc_checks"][0]["id"] == str(sample_kyc_check.id)
        assert len(result["kyc_checks"][0]["documents"]) == 1

        # Verify repository calls
        mock_user_repo.get_by_id.assert_called_once_with(sample_user.id)
        mock_kyc_repo.get_by_user_id.assert_called_once_with(sample_user.id)
        mock_webhook_repo.get_by_user_id.assert_called_once_with(sample_user.id)

    @pytest.mark.asyncio
    async def test_export_user_data_user_not_found(self, gdpr_service, mock_user_repo):
        """Test user data export when user not found."""
        # Setup mocks
        user_id = uuid4()
        mock_user_repo.get_by_id.return_value = None

        # Execute and verify
        with pytest.raises(ValueError, match=f"User {user_id} not found"):
            await gdpr_service.export_user_data(user_id)

    @pytest.mark.asyncio
    async def test_delete_user_data_soft_delete(
        self,
        gdpr_service,
        mock_db,
        mock_user_repo,
        mock_kyc_repo,
        mock_webhook_repo,
        sample_user,
        sample_kyc_check,
        sample_document,
    ):
        """Test soft deletion of user data."""
        # Setup mocks
        mock_user_repo.get_by_id.return_value = sample_user
        mock_kyc_repo.get_by_user_id.return_value = [sample_kyc_check]
        mock_kyc_repo.get_documents_by_kyc_id.return_value = [sample_document]
        mock_webhook_repo.get_by_user_id.return_value = []

        # Execute
        result = await gdpr_service.delete_user_data(sample_user.id, soft_delete=True)

        # Verify
        assert result["user_id"] == str(sample_user.id)
        assert result["soft_delete"] is True
        assert result["deleted_items"]["user_profile"] is True
        assert result["deleted_items"]["kyc_checks"] == 1
        assert result["deleted_items"]["documents"] == 1

        # Verify database commit was called
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_data_hard_delete(
        self,
        gdpr_service,
        mock_db,
        mock_user_repo,
        mock_kyc_repo,
        mock_webhook_repo,
        sample_user,
        sample_kyc_check,
        sample_document,
    ):
        """Test hard deletion of user data."""
        # Setup mocks
        mock_user_repo.get_by_id.return_value = sample_user
        mock_kyc_repo.get_by_user_id.return_value = [sample_kyc_check]
        mock_kyc_repo.get_documents_by_kyc_id.return_value = [sample_document]
        mock_webhook_repo.get_by_user_id.return_value = []

        # Execute
        result = await gdpr_service.delete_user_data(sample_user.id, soft_delete=False)

        # Verify
        assert result["user_id"] == str(sample_user.id)
        assert result["soft_delete"] is False
        assert result["deleted_items"]["user_profile"] is True
        assert result["deleted_items"]["kyc_checks"] == 1
        assert result["deleted_items"]["documents"] == 1

        # Verify delete methods were called
        mock_kyc_repo.delete_document.assert_called_once_with(sample_document.id)
        mock_kyc_repo.delete.assert_called_once_with(sample_kyc_check.id)
        mock_user_repo.delete.assert_called_once_with(sample_user.id)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_processing_info(
        self, gdpr_service, mock_user_repo, mock_kyc_repo, sample_user, sample_kyc_check
    ):
        """Test getting data processing information."""
        # Setup mocks
        mock_user_repo.get_by_id.return_value = sample_user
        mock_kyc_repo.get_by_user_id.return_value = [sample_kyc_check]

        # Execute
        result = await gdpr_service.get_data_processing_info(sample_user.id)

        # Verify
        assert result["user_id"] == str(sample_user.id)
        assert "data_categories" in result
        assert "personal_data" in result["data_categories"]
        assert "kyc_data" in result["data_categories"]
        assert result["data_categories"]["kyc_data"]["collected"] is True
        assert "user_rights" in result
        assert "access" in result["user_rights"]

    @pytest.mark.asyncio
    async def test_anonymize_user_data(self, gdpr_service, mock_user_repo, sample_user):
        """Test user data anonymization."""
        # Execute
        await gdpr_service._anonymize_user_data(sample_user)

        # Verify anonymization
        assert sample_user.email.startswith("deleted_user_")
        assert sample_user.first_name == "DELETED"
        assert sample_user.last_name == "USER"
        assert sample_user.phone_number is None
        assert sample_user.date_of_birth is None
        assert sample_user.is_active is False

        # Verify update was called
        mock_user_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_anonymize_kyc_data(
        self, gdpr_service, mock_kyc_repo, sample_kyc_check
    ):
        """Test KYC data anonymization."""
        # Execute
        await gdpr_service._anonymize_kyc_data(sample_kyc_check)

        # Verify anonymization
        assert sample_kyc_check.notes == "Data anonymized for GDPR compliance"
        assert sample_kyc_check.verification_result == {"anonymized": True}
        assert sample_kyc_check.rejection_reason is None

        # Verify update was called
        mock_kyc_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_anonymize_document_data(
        self, gdpr_service, mock_kyc_repo, sample_document
    ):
        """Test document data anonymization."""
        # Execute
        await gdpr_service._anonymize_document_data(sample_document)

        # Verify anonymization
        assert sample_document.document_number is None
        assert sample_document.file_name == "anonymized_document"
        assert (
            sample_document.verification_notes == "Data anonymized for GDPR compliance"
        )

        # Verify update was called
        mock_kyc_repo.update_document.assert_called_once()
