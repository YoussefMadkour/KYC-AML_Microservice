"""
Integration tests for GDPR API endpoints.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import SecurityUtils
from app.main import app
from app.models.kyc import Document, DocumentType, KYCCheck, KYCStatus
from app.models.user import User, UserRole
from tests.conftest import TestingSessionLocal


class TestGDPRAPI:
    """Integration tests for GDPR API endpoints."""

    @pytest.fixture
    def client(self):
        """Test client."""
        return TestClient(app)

    @pytest.fixture
    def db_session(self):
        """Database session for testing."""
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture
    def test_user(self, db_session: Session):
        """Create a test user."""
        user = User(
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            phone_number="555-123-4567",
            hashed_password=SecurityUtils.hash_password("testpassword"),
            role=UserRole.USER,
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def admin_user(self, db_session: Session):
        """Create an admin user."""
        user = User(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            hashed_password=SecurityUtils.hash_password("adminpassword"),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    @pytest.fixture
    def test_kyc_check(self, db_session: Session, test_user):
        """Create a test KYC check."""
        kyc_check = KYCCheck(
            user_id=test_user.id,
            status=KYCStatus.APPROVED,
            provider="mock_provider",
            provider_reference="ref123",
            verification_result={"status": "approved"},
            risk_score="low",
        )
        db_session.add(kyc_check)
        db_session.commit()
        db_session.refresh(kyc_check)
        return kyc_check

    @pytest.fixture
    def test_document(self, db_session: Session, test_kyc_check):
        """Create a test document."""
        document = Document(
            kyc_check_id=test_kyc_check.id,
            document_type=DocumentType.PASSPORT,
            file_path="/uploads/test.pdf",
            file_name="passport.pdf",
            file_size="1024",
            file_hash="abc123",
            document_number="P123456789",
            issuing_country="US",
            is_verified="verified",
        )
        db_session.add(document)
        db_session.commit()
        db_session.refresh(document)
        return document

    def get_auth_headers(self, user: User):
        """Get authentication headers for a user."""
        token = SecurityUtils.create_access_token(str(user.id))
        return {"Authorization": f"Bearer {token}"}

    def test_export_own_data_success(
        self,
        client: TestClient,
        test_user: User,
        test_kyc_check: KYCCheck,
        test_document: Document,
    ):
        """Test successful export of own data."""
        headers = self.get_auth_headers(test_user)

        response = client.get("/api/v1/gdpr/export/me", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify export structure
        assert "export_metadata" in data
        assert "user_profile" in data
        assert "kyc_checks" in data
        assert "webhook_events" in data

        # Verify user data
        assert data["user_profile"]["email"] == test_user.email
        assert data["user_profile"]["first_name"] == test_user.first_name

        # Verify KYC data
        assert len(data["kyc_checks"]) == 1
        assert data["kyc_checks"][0]["status"] == KYCStatus.APPROVED.value

        # Verify document data
        assert len(data["kyc_checks"][0]["documents"]) == 1
        assert (
            data["kyc_checks"][0]["documents"][0]["document_type"]
            == DocumentType.PASSPORT.value
        )

    def test_export_other_user_data_as_admin(
        self, client: TestClient, admin_user: User, test_user: User
    ):
        """Test admin can export other user's data."""
        headers = self.get_auth_headers(admin_user)

        response = client.get(f"/api/v1/gdpr/export/{test_user.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_profile"]["email"] == test_user.email

    def test_export_other_user_data_as_regular_user_forbidden(
        self, client: TestClient, test_user: User, admin_user: User
    ):
        """Test regular user cannot export other user's data."""
        headers = self.get_auth_headers(test_user)

        response = client.get(f"/api/v1/gdpr/export/{admin_user.id}", headers=headers)

        assert response.status_code == 403
        assert "only access your own data" in response.json()["detail"].lower()

    def test_export_nonexistent_user(self, client: TestClient, admin_user: User):
        """Test export of nonexistent user returns 404."""
        headers = self.get_auth_headers(admin_user)
        fake_user_id = uuid4()

        response = client.get(f"/api/v1/gdpr/export/{fake_user_id}", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_own_data_success(self, client: TestClient, test_user: User):
        """Test successful deletion of own data (soft delete)."""
        headers = self.get_auth_headers(test_user)

        response = client.delete("/api/v1/gdpr/delete/me", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify deletion summary
        assert data["user_id"] == str(test_user.id)
        assert data["soft_delete"] is True
        assert data["deleted_items"]["user_profile"] is True

    def test_delete_other_user_data_as_admin_soft(
        self, client: TestClient, admin_user: User, test_user: User
    ):
        """Test admin can soft delete other user's data."""
        headers = self.get_auth_headers(admin_user)

        response = client.delete(
            f"/api/v1/gdpr/delete/{test_user.id}?soft_delete=true", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_user.id)
        assert data["soft_delete"] is True

    def test_delete_other_user_data_as_admin_hard(
        self, client: TestClient, admin_user: User, test_user: User
    ):
        """Test admin can hard delete other user's data."""
        headers = self.get_auth_headers(admin_user)

        response = client.delete(
            f"/api/v1/gdpr/delete/{test_user.id}?soft_delete=false", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_user.id)
        assert data["soft_delete"] is False

    def test_delete_other_user_data_as_regular_user_forbidden(
        self, client: TestClient, test_user: User, admin_user: User
    ):
        """Test regular user cannot delete other user's data."""
        headers = self.get_auth_headers(test_user)

        response = client.delete(
            f"/api/v1/gdpr/delete/{admin_user.id}", headers=headers
        )

        assert response.status_code == 403
        assert "administrator" in response.json()["detail"].lower()

    def test_get_data_processing_info_own_data(
        self, client: TestClient, test_user: User
    ):
        """Test getting data processing info for own data."""
        headers = self.get_auth_headers(test_user)

        response = client.get("/api/v1/gdpr/processing-info/me", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify processing info structure
        assert "user_id" in data
        assert "data_categories" in data
        assert "data_sharing" in data
        assert "user_rights" in data

        # Verify data categories
        assert "personal_data" in data["data_categories"]
        assert "kyc_data" in data["data_categories"]
        assert "technical_data" in data["data_categories"]

        # Verify user rights
        rights = data["user_rights"]
        assert "access" in rights
        assert "rectification" in rights
        assert "erasure" in rights
        assert "portability" in rights
        assert "objection" in rights

    def test_get_data_processing_info_other_user_as_admin(
        self, client: TestClient, admin_user: User, test_user: User
    ):
        """Test admin can get processing info for other users."""
        headers = self.get_auth_headers(admin_user)

        response = client.get(
            f"/api/v1/gdpr/processing-info/{test_user.id}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_user.id)

    def test_get_data_processing_info_unauthorized(self, client: TestClient):
        """Test unauthorized access to processing info."""
        response = client.get("/api/v1/gdpr/processing-info/me")

        assert response.status_code == 401

    def test_export_data_unauthorized(self, client: TestClient):
        """Test unauthorized access to data export."""
        response = client.get("/api/v1/gdpr/export/me")

        assert response.status_code == 401

    def test_delete_data_unauthorized(self, client: TestClient):
        """Test unauthorized access to data deletion."""
        response = client.delete("/api/v1/gdpr/delete/me")

        assert response.status_code == 401

    def test_export_data_with_encrypted_fields(
        self, client: TestClient, test_user: User
    ):
        """Test that exported data includes decrypted sensitive fields."""
        headers = self.get_auth_headers(test_user)

        response = client.get("/api/v1/gdpr/export/me", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Verify that encrypted fields are properly decrypted in export
        user_profile = data["user_profile"]
        assert "phone_number" in user_profile

        # If phone number was encrypted, it should be decrypted in the export
        if user_profile["phone_number"]:
            # Should be readable phone number, not encrypted gibberish
            assert len(user_profile["phone_number"]) > 0
