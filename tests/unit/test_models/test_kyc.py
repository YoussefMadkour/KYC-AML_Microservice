"""
Unit tests for KYC models.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User, UserRole
from app.models.kyc import KYCCheck, KYCStatus, Document, DocumentType


# Test database setup
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        hashed_password="hashed_password_123"
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestKYCCheck:
    """Test cases for KYCCheck model."""
    
    def test_create_kyc_check(self, db_session, test_user):
        """Test creating a KYC check."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.PENDING,
            provider="mock_provider_1",
            provider_reference="ref_123456",
            verification_result={"score": 85, "status": "pass"},
            risk_score="low",
            notes="Initial KYC check"
        )
        
        db_session.add(kyc_check)
        db_session.commit()
        
        # Verify KYC check was created
        assert kyc_check.id is not None
        assert kyc_check.user_id == test_user.id
        assert kyc_check.status == KYCStatus.PENDING
        assert kyc_check.provider == "mock_provider_1"
        assert kyc_check.provider_reference == "ref_123456"
        assert kyc_check.verification_result["score"] == 85
        assert kyc_check.risk_score == "low"
        assert kyc_check.submitted_at is not None
        assert kyc_check.created_at is not None
        assert kyc_check.updated_at is not None
    
    def test_kyc_check_repr(self, db_session, test_user):
        """Test KYC check string representation."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.IN_PROGRESS,
            provider="mock_provider_1"
        )
        
        db_session.add(kyc_check)
        db_session.commit()
        
        repr_str = repr(kyc_check)
        assert "KYCCheck" in repr_str
        assert str(kyc_check.id) in repr_str
        assert str(test_user.id) in repr_str
        assert "IN_PROGRESS" in repr_str
    
    def test_is_completed_property(self, db_session, test_user):
        """Test is_completed property."""
        # Test pending check (not completed)
        pending_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.PENDING,
            provider="mock_provider_1"
        )
        assert pending_check.is_completed is False
        
        # Test approved check (completed)
        approved_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.APPROVED,
            provider="mock_provider_1"
        )
        assert approved_check.is_completed is True
        
        # Test rejected check (completed)
        rejected_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.REJECTED,
            provider="mock_provider_1"
        )
        assert rejected_check.is_completed is True
        
        # Test expired check (completed)
        expired_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.EXPIRED,
            provider="mock_provider_1"
        )
        assert expired_check.is_completed is True
    
    def test_is_pending_review_property(self, db_session, test_user):
        """Test is_pending_review property."""
        manual_review_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.MANUAL_REVIEW,
            provider="mock_provider_1"
        )
        assert manual_review_check.is_pending_review is True
        
        approved_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.APPROVED,
            provider="mock_provider_1"
        )
        assert approved_check.is_pending_review is False
    
    def test_processing_time_seconds_property(self, db_session, test_user):
        """Test processing_time_seconds property."""
        now = datetime.utcnow()
        submitted_time = now - timedelta(minutes=5)  # 5 minutes ago
        
        # Test with completed check
        completed_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.APPROVED,
            provider="mock_provider_1",
            submitted_at=submitted_time,
            completed_at=now
        )
        
        processing_time = completed_check.processing_time_seconds
        assert processing_time == 300  # 5 minutes = 300 seconds
        
        # Test with incomplete check
        incomplete_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.PENDING,
            provider="mock_provider_1",
            submitted_at=submitted_time
        )
        
        assert incomplete_check.processing_time_seconds is None
    
    def test_can_transition_to_method(self, db_session, test_user):
        """Test can_transition_to method."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.PENDING,
            provider="mock_provider_1"
        )
        
        # Valid transitions from PENDING
        assert kyc_check.can_transition_to(KYCStatus.IN_PROGRESS) is True
        assert kyc_check.can_transition_to(KYCStatus.REJECTED) is True
        
        # Invalid transitions from PENDING
        assert kyc_check.can_transition_to(KYCStatus.APPROVED) is False
        assert kyc_check.can_transition_to(KYCStatus.MANUAL_REVIEW) is False
        
        # Test transitions from IN_PROGRESS
        kyc_check.status = KYCStatus.IN_PROGRESS
        assert kyc_check.can_transition_to(KYCStatus.APPROVED) is True
        assert kyc_check.can_transition_to(KYCStatus.REJECTED) is True
        assert kyc_check.can_transition_to(KYCStatus.MANUAL_REVIEW) is True
        assert kyc_check.can_transition_to(KYCStatus.PENDING) is False
        
        # Test final states (no valid transitions)
        kyc_check.status = KYCStatus.REJECTED
        assert kyc_check.can_transition_to(KYCStatus.APPROVED) is False
        assert kyc_check.can_transition_to(KYCStatus.IN_PROGRESS) is False
    
    def test_update_status_method(self, db_session, test_user):
        """Test update_status method."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.PENDING,
            provider="mock_provider_1"
        )
        
        # Valid status update
        result = kyc_check.update_status(KYCStatus.IN_PROGRESS, "Processing started")
        assert result is True
        assert kyc_check.status == KYCStatus.IN_PROGRESS
        assert kyc_check.notes == "Processing started"
        
        # Invalid status update
        result = kyc_check.update_status(KYCStatus.PENDING, "Cannot go back")
        assert result is False
        assert kyc_check.status == KYCStatus.IN_PROGRESS  # Should remain unchanged
        
        # Test completion timestamp setting
        original_completed_at = kyc_check.completed_at
        result = kyc_check.update_status(KYCStatus.APPROVED, "Verification passed")
        assert result is True
        assert kyc_check.status == KYCStatus.APPROVED
        assert kyc_check.completed_at is not None
        assert kyc_check.completed_at != original_completed_at
    
    def test_kyc_status_enum(self):
        """Test KYCStatus enum values."""
        assert KYCStatus.PENDING == "pending"
        assert KYCStatus.IN_PROGRESS == "in_progress"
        assert KYCStatus.APPROVED == "approved"
        assert KYCStatus.REJECTED == "rejected"
        assert KYCStatus.MANUAL_REVIEW == "manual_review"
        assert KYCStatus.EXPIRED == "expired"
    
    def test_default_values(self, db_session, test_user):
        """Test default values for KYC check fields."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        
        db_session.add(kyc_check)
        db_session.commit()
        
        # Check default values
        assert kyc_check.status == KYCStatus.PENDING
        assert kyc_check.submitted_at is not None


class TestDocument:
    """Test cases for Document model."""
    
    def test_create_document(self, db_session, test_user):
        """Test creating a document."""
        # First create a KYC check
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        db_session.add(kyc_check)
        db_session.commit()
        
        # Create document
        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/passport_123.jpg",
            file_name="passport_123.jpg",
            file_size="2048576",
            file_hash="abc123def456",
            mime_type="image/jpeg",
            document_number="P123456789",
            issuing_country="US",
            issue_date=datetime(2020, 1, 1),
            expiry_date=datetime(2030, 1, 1),
            is_verified="verified",
            verification_notes="Document verified successfully"
        )
        
        db_session.add(document)
        db_session.commit()
        
        # Verify document was created
        assert document.id is not None
        assert document.kyc_check_id == kyc_check.id
        assert document.document_type == DocumentType.PASSPORT
        assert document.file_path == "/uploads/passport_123.jpg"
        assert document.file_name == "passport_123.jpg"
        assert document.file_hash == "abc123def456"
        assert document.document_number == "P123456789"
        assert document.issuing_country == "US"
        assert document.is_verified == "verified"
        assert document.created_at is not None
        assert document.updated_at is not None
    
    def test_document_repr(self, db_session, test_user):
        """Test document string representation."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        db_session.add(kyc_check)
        db_session.commit()
        
        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.DRIVER_LICENSE,
            file_path="/uploads/license.jpg",
            file_name="license.jpg",
            file_hash="hash123"
        )
        
        db_session.add(document)
        db_session.commit()
        
        repr_str = repr(document)
        assert "Document" in repr_str
        assert str(document.id) in repr_str
        assert "DRIVER_LICENSE" in repr_str
        assert str(kyc_check.id) in repr_str
    
    def test_is_expired_property(self, db_session, test_user):
        """Test is_expired property."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        db_session.add(kyc_check)
        db_session.commit()
        
        # Test expired document
        expired_document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/expired.jpg",
            file_name="expired.jpg",
            file_hash="hash123",
            expiry_date=datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        )
        assert expired_document.is_expired is True
        
        # Test valid document
        valid_document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/valid.jpg",
            file_name="valid.jpg",
            file_hash="hash456",
            expiry_date=datetime.utcnow() + timedelta(days=365)  # Expires in a year
        )
        assert valid_document.is_expired is False
        
        # Test document without expiry date
        no_expiry_document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.UTILITY_BILL,
            file_path="/uploads/bill.pdf",
            file_name="bill.pdf",
            file_hash="hash789"
        )
        assert no_expiry_document.is_expired is False
    
    def test_days_until_expiry_property(self, db_session, test_user):
        """Test days_until_expiry property."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        db_session.add(kyc_check)
        db_session.commit()
        
        # Test document expiring in 30 days
        future_expiry = datetime.utcnow() + timedelta(days=30)
        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/passport.jpg",
            file_name="passport.jpg",
            file_hash="hash123",
            expiry_date=future_expiry
        )
        
        days_until_expiry = document.days_until_expiry
        # Allow for slight timing differences (29 or 30 days)
        assert days_until_expiry in [29, 30]
        
        # Test document without expiry date
        no_expiry_document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.UTILITY_BILL,
            file_path="/uploads/bill.pdf",
            file_name="bill.pdf",
            file_hash="hash456"
        )
        assert no_expiry_document.days_until_expiry is None
    
    def test_document_type_enum(self):
        """Test DocumentType enum values."""
        assert DocumentType.PASSPORT == "passport"
        assert DocumentType.DRIVER_LICENSE == "driver_license"
        assert DocumentType.NATIONAL_ID == "national_id"
        assert DocumentType.UTILITY_BILL == "utility_bill"
        assert DocumentType.BANK_STATEMENT == "bank_statement"
        assert DocumentType.PROOF_OF_ADDRESS == "proof_of_address"
    
    def test_default_values(self, db_session, test_user):
        """Test default values for document fields."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            provider="mock_provider_1"
        )
        db_session.add(kyc_check)
        db_session.commit()
        
        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/test.jpg",
            file_name="test.jpg",
            file_hash="hash123"
        )
        
        db_session.add(document)
        db_session.commit()
        
        # Check default values
        assert document.is_verified == "pending"