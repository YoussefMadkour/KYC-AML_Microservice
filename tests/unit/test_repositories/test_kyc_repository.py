"""
Unit tests for KYC repository.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.repositories.kyc_repository import DocumentRepository, KYCRepository


class TestKYCRepository:
    """Test cases for KYC repository."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        db.query.return_value = Mock()
        return db

    @pytest.fixture
    def kyc_repository(self, mock_db):
        """KYC repository with mocked database."""
        return KYCRepository(mock_db)

    @pytest.fixture
    def sample_kyc_check(self):
        """Sample KYC check for testing."""
        check = Mock(spec=KYCCheck)
        check.id = uuid4()
        check.user_id = uuid4()
        check.status = KYCStatus.PENDING
        check.provider = "mock_provider"
        check.created_at = datetime.utcnow()
        return check

    def test_get_by_user_id(self, kyc_repository, mock_db, sample_kyc_check):
        """Test getting KYC checks by user ID."""
        user_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_kyc_check]

        result = kyc_repository.get_by_user_id(user_id, skip=0, limit=10)

        assert result == [sample_kyc_check]
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.offset.assert_called_with(0)
        mock_query.limit.assert_called_with(10)

    def test_get_by_user_id_with_status_filter(self, kyc_repository, mock_db):
        """Test getting KYC checks by user ID with status filter."""
        user_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        kyc_repository.get_by_user_id(user_id, status=KYCStatus.APPROVED)

        # Should be called twice - once for user_id, once for status
        assert mock_query.filter.call_count == 2

    def test_get_with_documents(self, kyc_repository, mock_db, sample_kyc_check):
        """Test getting KYC check with documents."""
        kyc_check_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_kyc_check

        result = kyc_repository.get_with_documents(kyc_check_id)

        assert result == sample_kyc_check
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.first.assert_called_once()

    def test_get_by_provider_reference(self, kyc_repository, mock_db, sample_kyc_check):
        """Test getting KYC check by provider reference."""
        provider_ref = "PROV123456"

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_kyc_check

        result = kyc_repository.get_by_provider_reference(provider_ref)

        assert result == sample_kyc_check
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.first.assert_called_once()

    def test_get_pending_checks(self, kyc_repository, mock_db):
        """Test getting pending KYC checks."""
        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = kyc_repository.get_pending_checks(limit=50)

        assert result == []
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.limit.assert_called_with(50)

    def test_get_checks_by_status(self, kyc_repository, mock_db):
        """Test getting KYC checks by status."""
        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = kyc_repository.get_checks_by_status(
            KYCStatus.APPROVED, skip=10, limit=20
        )

        assert result == []
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.offset.assert_called_with(10)
        mock_query.limit.assert_called_with(20)

    def test_count_by_user_id(self, kyc_repository, mock_db):
        """Test counting KYC checks by user ID."""
        user_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5

        result = kyc_repository.count_by_user_id(user_id)

        assert result == 5
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.count.assert_called_once()

    def test_count_by_user_id_with_status(self, kyc_repository, mock_db):
        """Test counting KYC checks by user ID with status filter."""
        user_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2

        result = kyc_repository.count_by_user_id(user_id, status=KYCStatus.APPROVED)

        assert result == 2
        # Should be called twice - once for user_id, once for status
        assert mock_query.filter.call_count == 2

    def test_get_user_latest_check(self, kyc_repository, mock_db, sample_kyc_check):
        """Test getting user's latest KYC check."""
        user_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = sample_kyc_check

        result = kyc_repository.get_user_latest_check(user_id)

        assert result == sample_kyc_check
        mock_db.query.assert_called_once_with(KYCCheck)
        mock_query.filter.assert_called()
        mock_query.order_by.assert_called()
        mock_query.first.assert_called_once()

    def test_update_status_success(self, kyc_repository, mock_db, sample_kyc_check):
        """Test successful status update."""
        kyc_check_id = uuid4()

        # Mock the get method to return our sample check
        kyc_repository.get = Mock(return_value=sample_kyc_check)
        sample_kyc_check.can_transition_to.return_value = True

        result = kyc_repository.update_status(
            kyc_check_id=kyc_check_id,
            new_status=KYCStatus.APPROVED,
            provider_reference="PROV123",
            verification_result={"score": 0.95},
            risk_score="low",
            notes="Verification completed",
        )

        assert result == sample_kyc_check
        assert sample_kyc_check.status == KYCStatus.APPROVED
        assert sample_kyc_check.provider_reference == "PROV123"
        assert sample_kyc_check.verification_result == {"score": 0.95}
        assert sample_kyc_check.risk_score == "low"
        assert sample_kyc_check.notes == "Verification completed"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_kyc_check)

    def test_update_status_invalid_transition(self, kyc_repository, sample_kyc_check):
        """Test status update with invalid transition."""
        kyc_check_id = uuid4()

        # Mock the get method to return our sample check
        kyc_repository.get = Mock(return_value=sample_kyc_check)
        sample_kyc_check.can_transition_to.return_value = False

        with pytest.raises(ValueError, match="Invalid status transition"):
            kyc_repository.update_status(
                kyc_check_id=kyc_check_id, new_status=KYCStatus.PENDING
            )

    def test_update_status_not_found(self, kyc_repository):
        """Test status update when check not found."""
        kyc_check_id = uuid4()

        # Mock the get method to return None
        kyc_repository.get = Mock(return_value=None)

        result = kyc_repository.update_status(
            kyc_check_id=kyc_check_id, new_status=KYCStatus.APPROVED
        )

        assert result is None

    def test_get_statistics(self, kyc_repository, mock_db):
        """Test getting KYC statistics."""
        # Setup mock for total count
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.count.return_value = 100

        # Setup mock for status counts
        status_counts = [
            (KYCStatus.PENDING, 10),
            (KYCStatus.APPROVED, 80),
            (KYCStatus.REJECTED, 10),
        ]
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = status_counts

        result = kyc_repository.get_statistics()

        assert result["total"] == 100
        assert result["by_status"]["pending"] == 10
        assert result["by_status"]["approved"] == 80
        assert result["by_status"]["rejected"] == 10
        assert result["completion_rate"] == 90.0


class TestDocumentRepository:
    """Test cases for Document repository."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        db.query.return_value = Mock()
        return db

    @pytest.fixture
    def document_repository(self, mock_db):
        """Document repository with mocked database."""
        return DocumentRepository(mock_db)

    @pytest.fixture
    def sample_document(self):
        """Sample document for testing."""
        doc = Mock(spec=Document)
        doc.id = uuid4()
        doc.kyc_check_id = uuid4()
        doc.document_type = DocumentType.PASSPORT
        doc.file_name = "passport.jpg"
        doc.is_verified = "pending"
        return doc

    def test_get_by_kyc_check_id(self, document_repository, mock_db, sample_document):
        """Test getting documents by KYC check ID."""
        kyc_check_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [sample_document]

        result = document_repository.get_by_kyc_check_id(kyc_check_id)

        assert result == [sample_document]
        mock_db.query.assert_called_once_with(Document)
        mock_query.filter.assert_called()
        mock_query.order_by.assert_called()
        mock_query.all.assert_called_once()

    def test_get_by_type_and_check(self, document_repository, mock_db, sample_document):
        """Test getting document by type and check ID."""
        kyc_check_id = uuid4()

        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_document

        result = document_repository.get_by_type_and_check(
            kyc_check_id, DocumentType.PASSPORT
        )

        assert result == sample_document
        mock_db.query.assert_called_once_with(Document)
        mock_query.filter.assert_called()
        mock_query.first.assert_called_once()

    def test_get_expired_documents(self, document_repository, mock_db):
        """Test getting expired documents."""
        # Setup mock query chain
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = document_repository.get_expired_documents(limit=50)

        assert result == []
        mock_db.query.assert_called_once_with(Document)
        mock_query.filter.assert_called()
        mock_query.limit.assert_called_with(50)

    def test_update_verification_status_success(
        self, document_repository, mock_db, sample_document
    ):
        """Test successful verification status update."""
        document_id = uuid4()

        # Mock the get method to return our sample document
        document_repository.get = Mock(return_value=sample_document)

        result = document_repository.update_verification_status(
            document_id=document_id,
            is_verified="verified",
            verification_notes="Document verified successfully",
        )

        assert result == sample_document
        assert sample_document.is_verified == "verified"
        assert sample_document.verification_notes == "Document verified successfully"
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_document)

    def test_update_verification_status_not_found(self, document_repository):
        """Test verification status update when document not found."""
        document_id = uuid4()

        # Mock the get method to return None
        document_repository.get = Mock(return_value=None)

        result = document_repository.update_verification_status(
            document_id=document_id, is_verified="verified"
        )

        assert result is None
