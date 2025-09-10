"""
Integration tests for field-level encryption in models.
"""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.models.user import User, UserRole
from app.utils.encryption import field_encryption
from tests.conftest import TestingSessionLocal


class TestModelEncryption:
    """Integration tests for model field encryption."""

    @pytest.fixture
    def db_session(self):
        """Database session for testing."""
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def test_user_phone_number_encryption(self, db_session: Session):
        """Test that user phone numbers are encrypted in database."""
        # Create user with phone number
        original_phone = "555-123-4567"
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone_number=original_phone,
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )

        # Save to database
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Verify phone number is accessible (decrypted automatically)
        assert user.phone_number == original_phone

        # Check raw database value is encrypted
        raw_result = db_session.execute(
            "SELECT phone_number FROM users WHERE id = :user_id", {"user_id": user.id}
        ).fetchone()

        raw_phone = raw_result[0] if raw_result else None

        # Raw value should be different from original (encrypted)
        if raw_phone:  # Only test if phone number was stored
            assert raw_phone != original_phone

            # Should be able to decrypt manually
            decrypted = field_encryption.decrypt(raw_phone)
            assert decrypted == original_phone

    def test_document_number_encryption(self, db_session: Session):
        """Test that document numbers are encrypted in database."""
        # Create user first
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Create KYC check
        kyc_check = KYCCheck(
            user_id=user.id, status=KYCStatus.PENDING, provider="test_provider"
        )
        db_session.add(kyc_check)
        db_session.commit()

        # Create document with sensitive document number
        original_doc_number = "P123456789"
        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/test.pdf",
            file_name="passport.pdf",
            file_size="1024",
            file_hash="abc123",
            document_number=original_doc_number,
            issuing_country="US",
            is_verified="pending",
        )

        # Save to database
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)

        # Verify document number is accessible (decrypted automatically)
        assert document.document_number == original_doc_number

        # Check raw database value is encrypted
        raw_result = db_session.execute(
            "SELECT document_number FROM documents WHERE id = :doc_id",
            {"doc_id": document.id},
        ).fetchone()

        raw_doc_number = raw_result[0] if raw_result else None

        # Raw value should be different from original (encrypted)
        if raw_doc_number:  # Only test if document number was stored
            assert raw_doc_number != original_doc_number

            # Should be able to decrypt manually
            decrypted = field_encryption.decrypt(raw_doc_number)
            assert decrypted == original_doc_number

    def test_encryption_with_none_values(self, db_session: Session):
        """Test encryption handling of None values."""
        # Create user without phone number
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone_number=None,  # Explicitly None
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )

        # Save to database
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Verify None is handled correctly
        assert user.phone_number is None

        # Check raw database value
        raw_result = db_session.execute(
            "SELECT phone_number FROM users WHERE id = :user_id", {"user_id": user.id}
        ).fetchone()

        raw_phone = raw_result[0] if raw_result else None
        assert raw_phone is None

    def test_encryption_with_empty_string(self, db_session: Session):
        """Test encryption handling of empty strings."""
        # Create user with empty phone number
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone_number="",  # Empty string
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )

        # Save to database
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Verify empty string is handled correctly
        assert user.phone_number == ""

    def test_encryption_roundtrip_with_special_characters(self, db_session: Session):
        """Test encryption with special characters in data."""
        special_phone = "+1 (555) 123-4567 ext. 890"
        special_doc_number = "P-123/456@789#"

        # Create user
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            phone_number=special_phone,
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Create KYC and document
        kyc_check = KYCCheck(
            user_id=user.id, status=KYCStatus.PENDING, provider="test_provider"
        )
        db_session.add(kyc_check)
        db_session.commit()

        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/test.pdf",
            file_name="passport.pdf",
            file_size="1024",
            file_hash="abc123",
            document_number=special_doc_number,
            issuing_country="US",
            is_verified="pending",
        )
        db_session.add(document)
        db_session.commit()

        # Refresh from database
        db_session.refresh(user)
        db_session.refresh(document)

        # Verify special characters are preserved
        assert user.phone_number == special_phone
        assert document.document_number == special_doc_number

    def test_encryption_performance_with_large_data(self, db_session: Session):
        """Test encryption performance with larger data sets."""
        import time

        # Create multiple users with encrypted phone numbers
        users = []
        start_time = time.time()

        for i in range(10):  # Small batch for testing
            user = User(
                email=f"user{i}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                phone_number=f"555-123-{i:04d}",
                hashed_password="hashed_password",
                role=UserRole.USER,
                is_active=True,
            )
            users.append(user)
            db_session.add(user)

        db_session.commit()
        creation_time = time.time() - start_time

        # Query all users back
        start_time = time.time()
        queried_users = (
            db_session.query(User).filter(User.email.like("user%@example.com")).all()
        )
        query_time = time.time() - start_time

        # Verify all phone numbers are correctly decrypted
        assert len(queried_users) == 10
        for i, user in enumerate(queried_users):
            expected_phone = f"555-123-{i:04d}"
            # Note: Order might not be preserved, so check if any user has this phone
            phone_numbers = [u.phone_number for u in queried_users]
            assert expected_phone in phone_numbers

        # Performance should be reasonable
        assert creation_time < 5.0, f"Creation too slow: {creation_time}s"
        assert query_time < 2.0, f"Query too slow: {query_time}s"

    def test_encryption_consistency_across_sessions(self, db_session: Session):
        """Test that encryption is consistent across different database sessions."""
        original_phone = "555-987-6543"

        # Create user in first session
        user = User(
            email="consistency@example.com",
            first_name="Consistency",
            last_name="Test",
            phone_number=original_phone,
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        user_id = user.id

        # Close first session
        db_session.close()

        # Open new session and query user
        new_session = TestingSessionLocal()
        try:
            queried_user = new_session.query(User).filter(User.id == user_id).first()

            # Verify phone number is still correctly decrypted
            assert queried_user is not None
            assert queried_user.phone_number == original_phone

        finally:
            new_session.close()

    def test_encryption_with_unicode_characters(self, db_session: Session):
        """Test encryption with unicode characters."""
        unicode_phone = "📞 +1-555-123-4567"
        unicode_doc = "🛂 P123456789"

        # Create user
        user = User(
            email="unicode@example.com",
            first_name="Unicode",
            last_name="Test",
            phone_number=unicode_phone,
            hashed_password="hashed_password",
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        # Create document
        kyc_check = KYCCheck(
            user_id=user.id, status=KYCStatus.PENDING, provider="test_provider"
        )
        db_session.add(kyc_check)
        db_session.commit()

        document = Document(
            kyc_check_id=kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/test.pdf",
            file_name="passport.pdf",
            file_size="1024",
            file_hash="abc123",
            document_number=unicode_doc,
            issuing_country="US",
            is_verified="pending",
        )
        db_session.add(document)
        db_session.commit()

        # Refresh and verify
        db_session.refresh(user)
        db_session.refresh(document)

        assert user.phone_number == unicode_phone
        assert document.document_number == unicode_doc
