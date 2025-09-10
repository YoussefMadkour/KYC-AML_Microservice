"""
Unit tests for KYC service.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from app.core.exceptions import BusinessLogicError, ValidationError
from app.models.kyc import DocumentType, KYCStatus
from app.models.user import User, UserRole
from app.schemas.kyc import DocumentCreate, KYCCheckCreate, KYCStatusUpdate
from app.services.kyc_service import KYCService


class TestKYCService:
    """Test cases for KYC service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository."""
        return Mock()
    
    @pytest.fixture
    def mock_kyc_repo(self):
        """Mock KYC repository."""
        return Mock()
    
    @pytest.fixture
    def mock_doc_repo(self):
        """Mock document repository."""
        return Mock()
    
    @pytest.fixture
    def kyc_service(self, mock_db, mock_user_repo, mock_kyc_repo, mock_doc_repo):
        """KYC service with mocked dependencies."""
        service = KYCService(mock_db)
        service.user_repository = mock_user_repo
        service.kyc_repository = mock_kyc_repo
        service.document_repository = mock_doc_repo
        return service
    
    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = Mock(spec=User)
        user.id = uuid4()
        user.email = "test@example.com"
        user.is_active = True
        user.role = UserRole.USER
        return user
    
    @pytest.fixture
    def sample_document_create(self):
        """Sample document creation data."""
        return DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport.jpg",
            file_path="/uploads/passport.jpg",
            file_hash="a" * 64,  # Valid SHA-256 hash length
            mime_type="image/jpeg",
            document_number="P123456789",
            issuing_country="US",
            expiry_date=datetime.utcnow() + timedelta(days=365)
        )
    
    @pytest.fixture
    def sample_kyc_create(self, sample_document_create):
        """Sample KYC check creation data."""
        return KYCCheckCreate(
            provider="mock_provider",
            documents=[sample_document_create],
            notes="Test KYC check"
        )
    
    def test_create_kyc_check_success(self, kyc_service, sample_user, sample_kyc_create):
        """Test successful KYC check creation."""
        # Setup mocks
        kyc_service.user_repository.get.return_value = sample_user
        kyc_service.kyc_repository.get_by_user_id.return_value = []  # No existing checks
        
        mock_kyc_check = Mock()
        mock_kyc_check.id = uuid4()
        mock_kyc_check.user_id = sample_user.id
        mock_kyc_check.status = KYCStatus.PENDING
        mock_kyc_check.provider = "mock_provider"
        mock_kyc_check.documents = []
        mock_kyc_check.created_at = datetime.utcnow()
        mock_kyc_check.updated_at = datetime.utcnow()
        
        kyc_service.kyc_repository.create_from_dict.return_value = mock_kyc_check
        
        mock_document = Mock()
        mock_document.id = uuid4()
        mock_document.document_type = DocumentType.PASSPORT
        kyc_service.document_repository.create_from_dict.return_value = mock_document
        
        # Execute
        with patch.object(kyc_service, '_get_active_check', return_value=None):
            with patch.object(kyc_service, '_to_response') as mock_to_response:
                mock_response = Mock()
                mock_to_response.return_value = mock_response
                
                result = kyc_service.create_kyc_check(sample_user.id, sample_kyc_create)
        
        # Verify
        assert result == mock_response
        kyc_service.user_repository.get.assert_called_once_with(sample_user.id)
        kyc_service.kyc_repository.create_from_dict.assert_called_once()
        kyc_service.document_repository.create_from_dict.assert_called_once()
    
    def test_create_kyc_check_user_not_found(self, kyc_service, sample_kyc_create):
        """Test KYC check creation with non-existent user."""
        user_id = uuid4()
        kyc_service.user_repository.get.return_value = None
        
        with pytest.raises(ValidationError, match="User not found"):
            kyc_service.create_kyc_check(user_id, sample_kyc_create)
    
    def test_create_kyc_check_inactive_user(self, kyc_service, sample_user, sample_kyc_create):
        """Test KYC check creation with inactive user."""
        sample_user.is_active = False
        kyc_service.user_repository.get.return_value = sample_user
        
        with pytest.raises(BusinessLogicError, match="Cannot create KYC check for inactive user"):
            kyc_service.create_kyc_check(sample_user.id, sample_kyc_create)
    
    def test_create_kyc_check_existing_active_check(self, kyc_service, sample_user, sample_kyc_create):
        """Test KYC check creation when user already has active check."""
        kyc_service.user_repository.get.return_value = sample_user
        
        existing_check = Mock()
        existing_check.status = KYCStatus.PENDING
        
        with patch.object(kyc_service, '_get_active_check', return_value=existing_check):
            with pytest.raises(BusinessLogicError, match="User already has an active KYC check"):
                kyc_service.create_kyc_check(sample_user.id, sample_kyc_create)
    
    def test_validate_documents_no_documents(self, kyc_service):
        """Test document validation with no documents."""
        with pytest.raises(ValidationError, match="At least one document is required"):
            kyc_service._validate_documents([])
    
    def test_validate_documents_no_identity_document(self, kyc_service):
        """Test document validation without identity document."""
        doc = DocumentCreate(
            document_type=DocumentType.UTILITY_BILL,
            file_name="bill.pdf",
            file_path="/uploads/bill.pdf",
            file_hash="a" * 64,
            mime_type="application/pdf"
        )
        
        with pytest.raises(ValidationError, match="At least one identity document"):
            kyc_service._validate_documents([doc])
    
    def test_validate_documents_duplicate_types(self, kyc_service):
        """Test document validation with duplicate types."""
        doc1 = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport1.jpg",
            file_path="/uploads/passport1.jpg",
            file_hash="a" * 64,
            expiry_date=datetime.utcnow() + timedelta(days=365)
        )
        doc2 = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport2.jpg",
            file_path="/uploads/passport2.jpg",
            file_hash="b" * 64,
            expiry_date=datetime.utcnow() + timedelta(days=365)
        )
        
        with pytest.raises(ValidationError, match="Duplicate document types are not allowed"):
            kyc_service._validate_documents([doc1, doc2])
    
    def test_validate_document_invalid_hash(self, kyc_service):
        """Test document validation with invalid hash."""
        doc = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport.jpg",
            file_path="/uploads/passport.jpg",
            file_hash="invalid_hash",  # Too short
            expiry_date=datetime.utcnow() + timedelta(days=365)
        )
        
        with pytest.raises(ValidationError, match="File hash must be a valid SHA-256 hash"):
            kyc_service._validate_document(doc)
    
    def test_validate_document_missing_expiry(self, kyc_service):
        """Test document validation with missing expiry date for passport."""
        doc = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport.jpg",
            file_path="/uploads/passport.jpg",
            file_hash="a" * 64,
            # Missing expiry_date
        )
        
        with pytest.raises(ValidationError, match="passport must have an expiry date"):
            kyc_service._validate_document(doc)
    
    def test_validate_document_expired(self, kyc_service):
        """Test document validation with expired document."""
        doc = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport.jpg",
            file_path="/uploads/passport.jpg",
            file_hash="a" * 64,
            expiry_date=datetime.utcnow() - timedelta(days=1)  # Expired
        )
        
        with pytest.raises(ValidationError, match="passport is expired"):
            kyc_service._validate_document(doc)
    
    def test_get_kyc_check_success(self, kyc_service):
        """Test successful KYC check retrieval."""
        kyc_check_id = uuid4()
        user_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.id = kyc_check_id
        mock_kyc_check.user_id = user_id
        
        kyc_service.kyc_repository.get_with_documents.return_value = mock_kyc_check
        
        with patch.object(kyc_service, '_to_response') as mock_to_response:
            mock_response = Mock()
            mock_to_response.return_value = mock_response
            
            result = kyc_service.get_kyc_check(kyc_check_id, user_id)
        
        assert result == mock_response
        kyc_service.kyc_repository.get_with_documents.assert_called_once_with(kyc_check_id)
    
    def test_get_kyc_check_not_found(self, kyc_service):
        """Test KYC check retrieval when not found."""
        kyc_check_id = uuid4()
        kyc_service.kyc_repository.get_with_documents.return_value = None
        
        result = kyc_service.get_kyc_check(kyc_check_id)
        
        assert result is None
    
    def test_get_kyc_check_unauthorized_user(self, kyc_service):
        """Test KYC check retrieval with unauthorized user."""
        kyc_check_id = uuid4()
        user_id = uuid4()
        other_user_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.user_id = other_user_id  # Different user
        
        kyc_service.kyc_repository.get_with_documents.return_value = mock_kyc_check
        
        result = kyc_service.get_kyc_check(kyc_check_id, user_id)
        
        assert result is None
    
    def test_update_kyc_status_success(self, kyc_service):
        """Test successful KYC status update."""
        kyc_check_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.id = kyc_check_id
        mock_kyc_check.status = KYCStatus.PENDING
        mock_kyc_check.can_transition_to.return_value = True
        
        kyc_service.kyc_repository.get.return_value = mock_kyc_check
        kyc_service.kyc_repository.update_status.return_value = mock_kyc_check
        
        status_update = KYCStatusUpdate(
            status=KYCStatus.IN_PROGRESS,
            notes="Processing started"
        )
        
        with patch.object(kyc_service, '_to_response') as mock_to_response:
            with patch.object(kyc_service, '_log_status_change'):
                mock_response = Mock()
                mock_to_response.return_value = mock_response
                
                result = kyc_service.update_kyc_status(kyc_check_id, status_update)
        
        assert result == mock_response
        mock_kyc_check.can_transition_to.assert_called_once_with(KYCStatus.IN_PROGRESS)
        kyc_service.kyc_repository.update_status.assert_called_once()
    
    def test_update_kyc_status_invalid_transition(self, kyc_service):
        """Test KYC status update with invalid transition."""
        kyc_check_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.status = KYCStatus.APPROVED
        mock_kyc_check.can_transition_to.return_value = False
        
        kyc_service.kyc_repository.get.return_value = mock_kyc_check
        
        status_update = KYCStatusUpdate(
            status=KYCStatus.PENDING,
            notes="Invalid transition"
        )
        
        with pytest.raises(ValidationError, match="Invalid status transition"):
            kyc_service.update_kyc_status(kyc_check_id, status_update)
    
    def test_update_kyc_status_not_found(self, kyc_service):
        """Test KYC status update when check not found."""
        kyc_check_id = uuid4()
        kyc_service.kyc_repository.get.return_value = None
        
        status_update = KYCStatusUpdate(
            status=KYCStatus.IN_PROGRESS,
            notes="Processing started"
        )
        
        result = kyc_service.update_kyc_status(kyc_check_id, status_update)
        
        assert result is None
    
    def test_get_active_check_pending(self, kyc_service):
        """Test getting active check with pending status."""
        user_id = uuid4()
        
        mock_check = Mock()
        mock_check.status = KYCStatus.PENDING
        
        kyc_service.kyc_repository.get_by_user_id.side_effect = [
            [mock_check],  # Found pending check
            [],  # No in_progress checks
            []   # No manual_review checks
        ]
        
        result = kyc_service._get_active_check(user_id)
        
        assert result == mock_check
    
    def test_get_active_check_none(self, kyc_service):
        """Test getting active check when none exists."""
        user_id = uuid4()
        
        kyc_service.kyc_repository.get_by_user_id.return_value = []
        
        result = kyc_service._get_active_check(user_id)
        
        assert result is None
    
    def test_get_user_kyc_checks(self, kyc_service):
        """Test getting user's KYC checks."""
        user_id = uuid4()
        
        mock_checks = [Mock(), Mock()]
        kyc_service.kyc_repository.get_by_user_id.return_value = mock_checks
        
        with patch.object(kyc_service, '_to_response') as mock_to_response:
            mock_responses = [Mock(), Mock()]
            mock_to_response.side_effect = mock_responses
            
            result = kyc_service.get_user_kyc_checks(user_id)
        
        assert result == mock_responses
        kyc_service.kyc_repository.get_by_user_id.assert_called_once_with(user_id, 0, 100, None)
    
    def test_get_pending_checks(self, kyc_service):
        """Test getting pending KYC checks."""
        mock_checks = [Mock(), Mock()]
        kyc_service.kyc_repository.get_pending_checks.return_value = mock_checks
        
        with patch.object(kyc_service, '_to_response') as mock_to_response:
            mock_responses = [Mock(), Mock()]
            mock_to_response.side_effect = mock_responses
            
            result = kyc_service.get_pending_checks()
        
        assert result == mock_responses
        kyc_service.kyc_repository.get_pending_checks.assert_called_once_with(100)
    
    def test_get_kyc_statistics(self, kyc_service):
        """Test getting KYC statistics."""
        mock_stats = {
            "total": 100,
            "by_status": {"pending": 10, "approved": 80, "rejected": 10},
            "completion_rate": 90.0
        }
        
        kyc_service.kyc_repository.get_statistics.return_value = mock_stats
        
        result = kyc_service.get_kyc_statistics()
        
        assert result == mock_stats
        kyc_service.kyc_repository.get_statistics.assert_called_once()
    
    @patch('app.services.kyc_service.encrypt_field')
    def test_create_document_with_encryption(self, mock_encrypt, kyc_service):
        """Test document creation with field encryption."""
        kyc_check_id = uuid4()
        
        doc_data = DocumentCreate(
            document_type=DocumentType.PASSPORT,
            file_name="passport.jpg",
            file_path="/uploads/passport.jpg",
            file_hash="a" * 64,
            document_number="P123456789"
        )
        
        mock_encrypt.return_value = "encrypted_doc_number"
        
        mock_document = Mock()
        kyc_service.document_repository.create_from_dict.return_value = mock_document
        
        result = kyc_service._create_document(kyc_check_id, doc_data)
        
        assert result == mock_document
        mock_encrypt.assert_called_once_with("P123456789")
        kyc_service.document_repository.create_from_dict.assert_called_once()
        
        # Verify the document data passed to repository
        call_args = kyc_service.document_repository.create_from_dict.call_args[0][0]
        assert call_args["document_number"] == "encrypted_doc_number"
        assert call_args["kyc_check_id"] == kyc_check_id
    
    def test_get_kyc_history(self, kyc_service):
        """Test getting KYC check history."""
        kyc_check_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.created_at = datetime.utcnow()
        mock_kyc_check.completed_at = None
        
        kyc_service.kyc_repository.get.return_value = mock_kyc_check
        
        result = kyc_service.get_kyc_history(kyc_check_id)
        
        assert len(result) == 1
        assert result[0]["new_status"] == KYCStatus.PENDING
        assert result[0]["notes"] == "KYC check created"
    
    def test_get_kyc_history_with_completion(self, kyc_service):
        """Test getting KYC check history with completion."""
        kyc_check_id = uuid4()
        
        mock_kyc_check = Mock()
        mock_kyc_check.created_at = datetime.utcnow()
        mock_kyc_check.completed_at = datetime.utcnow()
        mock_kyc_check.status = KYCStatus.APPROVED
        mock_kyc_check.notes = "Verification completed"
        
        kyc_service.kyc_repository.get.return_value = mock_kyc_check
        
        result = kyc_service.get_kyc_history(kyc_check_id)
        
        assert len(result) == 2
        assert result[1]["new_status"] == KYCStatus.APPROVED
        assert result[1]["notes"] == "Verification completed"