"""
Integration tests for KYC verification API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.kyc import KYCCheck, KYCStatus, Document, DocumentType
from app.core.security import SecurityUtils


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_kyc.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_db():
    """Create test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def create_test_user(test_db):
    """Create a test user in the database."""
    db = TestingSessionLocal()
    
    hashed_password = SecurityUtils.get_password_hash("TestPassword123")
    user = User(
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        hashed_password=hashed_password,
        role=UserRole.USER,
        is_active=True,
        is_verified=False,
        phone_number="1234567890",
        address_line1="123 Test St",
        city="Test City",
        state_province="Test State",
        postal_code="12345",
        country="US"
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    return user


@pytest.fixture
def create_admin_user(test_db):
    """Create an admin user in the database."""
    db = TestingSessionLocal()
    
    hashed_password = SecurityUtils.get_password_hash("AdminPassword123")
    user = User(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        hashed_password=hashed_password,
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    return user


@pytest.fixture
def create_compliance_user(test_db):
    """Create a compliance officer user in the database."""
    db = TestingSessionLocal()
    
    hashed_password = SecurityUtils.get_password_hash("CompliancePassword123")
    user = User(
        email="compliance@example.com",
        first_name="Compliance",
        last_name="Officer",
        hashed_password=hashed_password,
        role=UserRole.COMPLIANCE_OFFICER,
        is_active=True,
        is_verified=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    return user


@pytest.fixture
def create_second_user(test_db):
    """Create a second test user in the database."""
    db = TestingSessionLocal()
    
    hashed_password = SecurityUtils.get_password_hash("TestPassword123")
    user = User(
        email="user2@example.com",
        first_name="Second",
        last_name="User",
        hashed_password=hashed_password,
        role=UserRole.USER,
        is_active=True,
        is_verified=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    return user


@pytest.fixture
def create_kyc_check(test_db, create_test_user):
    """Create a test KYC check in the database."""
    db = TestingSessionLocal()
    
    kyc_check = KYCCheck(
        user_id=create_test_user.id,
        provider="mock_provider",
        status=KYCStatus.PENDING,
        submitted_at=datetime.utcnow(),
        notes="Test KYC check"
    )
    
    db.add(kyc_check)
    db.commit()
    db.refresh(kyc_check)
    
    # Add a test document
    document = Document(
        kyc_check_id=kyc_check.id,
        document_type=DocumentType.PASSPORT,
        file_path="/test/path/passport.jpg",
        file_name="passport.jpg",
        file_hash="a" * 64,  # Mock SHA-256 hash
        document_number="encrypted_passport_number",
        expiry_date=datetime.utcnow() + timedelta(days=365),
        is_verified="pending"
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    # Store the IDs to avoid detached instance issues
    kyc_check_id = kyc_check.id
    user_id = kyc_check.user_id
    
    db.close()
    
    # Return a simple object with the IDs
    class MockKYCCheck:
        def __init__(self, id, user_id):
            self.id = id
            self.user_id = user_id
    
    return MockKYCCheck(kyc_check_id, user_id)


def get_auth_headers(client, email: str, password: str):
    """Helper function to get authentication headers."""
    login_data = {"email": email, "password": password}
    response = client.post("/api/v1/auth/login", json=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def get_sample_kyc_data():
    """Get sample KYC check creation data."""
    return {
        "provider": "mock_provider",
        "documents": [
            {
                "document_type": "passport",
                "file_name": "passport.jpg",
                "file_path": "/uploads/passport.jpg",
                "file_hash": "a" * 64,  # Mock SHA-256 hash
                "file_size": "1024",
                "mime_type": "image/jpeg",
                "document_number": "P123456789",
                "issuing_country": "US",
                "expiry_date": (datetime.utcnow() + timedelta(days=365)).isoformat()
            }
        ],
        "notes": "Initial KYC verification"
    }


class TestKYCCheckCreation:
    """Test cases for KYC check creation endpoint."""
    
    def test_create_kyc_check_success(self, client, test_db, create_test_user):
        """Test successful KYC check creation."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        kyc_data = get_sample_kyc_data()
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["user_id"] == str(create_test_user.id)
        assert data["provider"] == "mock_provider"
        assert data["status"] == "pending"
        assert data["notes"] == "Initial KYC verification"
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_type"] == "passport"
        assert data["documents"][0]["file_name"] == "passport.jpg"
    
    def test_create_kyc_check_multiple_documents(self, client, test_db, create_test_user):
        """Test KYC check creation with multiple documents."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        kyc_data = {
            "provider": "mock_provider",
            "documents": [
                {
                    "document_type": "passport",
                    "file_name": "passport.jpg",
                    "file_path": "/uploads/passport.jpg",
                    "file_hash": "a" * 64,
                    "document_number": "P123456789",
                    "issuing_country": "US",
                    "expiry_date": (datetime.utcnow() + timedelta(days=365)).isoformat()
                },
                {
                    "document_type": "utility_bill",
                    "file_name": "utility_bill.pdf",
                    "file_path": "/uploads/utility_bill.pdf",
                    "file_hash": "b" * 64,
                    "mime_type": "application/pdf"
                }
            ]
        }
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert len(data["documents"]) == 2
        document_types = [doc["document_type"] for doc in data["documents"]]
        assert "passport" in document_types
        assert "utility_bill" in document_types
    
    def test_create_kyc_check_missing_documents(self, client, test_db, create_test_user):
        """Test KYC check creation with missing documents."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        kyc_data = {
            "provider": "mock_provider",
            "documents": []
        }
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 422
    
    def test_create_kyc_check_invalid_document_hash(self, client, test_db, create_test_user):
        """Test KYC check creation with invalid document hash."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        kyc_data = get_sample_kyc_data()
        kyc_data["documents"][0]["file_hash"] = "invalid_hash"
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 400
        assert "File hash must be a valid SHA-256 hash" in response.json()["detail"]
    
    def test_create_kyc_check_expired_document(self, client, test_db, create_test_user):
        """Test KYC check creation with expired document."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        kyc_data = get_sample_kyc_data()
        kyc_data["documents"][0]["expiry_date"] = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 400
        assert "is expired" in response.json()["detail"]
    
    def test_create_kyc_check_duplicate_active(self, client, test_db, create_test_user, create_kyc_check):
        """Test KYC check creation when user already has active check."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        kyc_data = get_sample_kyc_data()
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=headers)
        
        assert response.status_code == 422
        assert "already has an active KYC check" in response.json()["detail"]
    
    def test_create_kyc_check_unauthorized(self, client, test_db):
        """Test KYC check creation without authentication."""
        kyc_data = get_sample_kyc_data()
        
        response = client.post("/api/v1/kyc/checks", json=kyc_data)
        
        assert response.status_code == 403


class TestKYCCheckRetrieval:
    """Test cases for KYC check retrieval endpoints."""
    
    def test_get_kyc_check_success(self, client, test_db, create_test_user, create_kyc_check):
        """Test successful KYC check retrieval."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == check_id
        assert data["user_id"] == str(create_test_user.id)
        assert data["provider"] == "mock_provider"
        assert data["status"] == "pending"
        assert len(data["documents"]) == 1
    
    def test_get_kyc_check_admin_access(self, client, test_db, create_admin_user, create_test_user, create_kyc_check):
        """Test admin can access any KYC check."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == check_id
        assert data["user_id"] == str(create_test_user.id)
    
    def test_get_kyc_check_compliance_access(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test compliance officer can access any KYC check."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == check_id
    
    def test_get_kyc_check_other_user_forbidden(self, client, test_db, create_test_user, create_second_user, create_kyc_check):
        """Test user cannot access another user's KYC check."""
        headers = get_auth_headers(client, "user2@example.com", "TestPassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=headers)
        
        assert response.status_code == 404
    
    def test_get_kyc_check_not_found(self, client, test_db, create_test_user):
        """Test getting non-existent KYC check."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        fake_check_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(f"/api/v1/kyc/checks/{fake_check_id}", headers=headers)
        
        assert response.status_code == 404
        assert "KYC check not found" in response.json()["detail"]
    
    def test_get_kyc_check_invalid_id(self, client, test_db, create_test_user):
        """Test getting KYC check with invalid ID format."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/checks/invalid-id", headers=headers)
        
        assert response.status_code == 400
        assert "Invalid check ID format" in response.json()["detail"]
    
    def test_get_kyc_check_unauthorized(self, client, test_db, create_kyc_check):
        """Test getting KYC check without authentication."""
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}")
        
        assert response.status_code == 403


class TestKYCCheckListing:
    """Test cases for KYC check listing endpoint."""
    
    def test_list_kyc_checks_success(self, client, test_db, create_test_user, create_kyc_check):
        """Test successful KYC check listing."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/checks", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["size"] == 100
        assert data["pages"] == 1
        
        assert data["items"][0]["id"] == str(create_kyc_check.id)
    
    def test_list_kyc_checks_with_pagination(self, client, test_db, create_test_user):
        """Test KYC check listing with pagination."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/checks?skip=0&limit=10", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["size"] == 10
        assert data["page"] == 1
    
    def test_list_kyc_checks_with_status_filter(self, client, test_db, create_test_user, create_kyc_check):
        """Test KYC check listing with status filter."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/checks?status=pending", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "pending"
    
    def test_list_kyc_checks_admin_with_user_filter(self, client, test_db, create_admin_user, create_test_user, create_kyc_check):
        """Test admin listing KYC checks with user filter."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)
        
        response = client.get(f"/api/v1/kyc/checks?user_id={user_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 1
        assert data["items"][0]["user_id"] == user_id
    
    def test_list_kyc_checks_user_filter_forbidden(self, client, test_db, create_test_user, create_second_user, create_kyc_check):
        """Test regular user cannot use user_id filter."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        user_id = str(create_second_user.id)
        
        response = client.get(f"/api/v1/kyc/checks?user_id={user_id}", headers=headers)
        
        assert response.status_code == 403
        assert "Not enough permissions to filter by user ID" in response.json()["detail"]
    
    def test_list_kyc_checks_invalid_user_id(self, client, test_db, create_admin_user):
        """Test listing KYC checks with invalid user ID."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        
        response = client.get("/api/v1/kyc/checks?user_id=invalid-id", headers=headers)
        
        assert response.status_code == 400
        assert "Invalid user ID format" in response.json()["detail"]
    
    def test_list_kyc_checks_unauthorized(self, client, test_db):
        """Test listing KYC checks without authentication."""
        response = client.get("/api/v1/kyc/checks")
        
        assert response.status_code == 403


class TestKYCCheckUpdates:
    """Test cases for KYC check update endpoints."""
    
    def test_update_kyc_check_admin_success(self, client, test_db, create_admin_user, create_test_user, create_kyc_check):
        """Test successful KYC check update by admin."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        check_id = str(create_kyc_check.id)
        
        update_data = {
            "status": "approved",
            "provider_reference": "PROV123456",
            "verification_result": {"score": 95, "confidence": "high"},
            "risk_score": "low",
            "notes": "Verification completed successfully"
        }
        
        response = client.put(f"/api/v1/kyc/checks/{check_id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "approved"
        assert data["provider_reference"] == "PROV123456"
        assert data["verification_result"]["score"] == 95
        assert data["risk_score"] == "low"
        assert data["notes"] == "Verification completed successfully"
    
    def test_update_kyc_check_invalid_status_transition(self, client, test_db, create_admin_user, create_test_user):
        """Test KYC check update with invalid status transition."""
        # Create a completed KYC check
        db = TestingSessionLocal()
        kyc_check = KYCCheck(
            user_id=create_test_user.id,
            provider="mock_provider",
            status=KYCStatus.APPROVED,
            submitted_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(kyc_check)
        db.commit()
        db.refresh(kyc_check)
        db.close()
        
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        check_id = str(kyc_check.id)
        
        update_data = {"status": "pending"}
        
        response = client.put(f"/api/v1/kyc/checks/{check_id}", json=update_data, headers=headers)
        
        assert response.status_code == 400
        assert "Invalid status transition" in response.json()["detail"]
    
    def test_update_kyc_check_not_found(self, client, test_db, create_admin_user):
        """Test updating non-existent KYC check."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        fake_check_id = "00000000-0000-0000-0000-000000000000"
        
        update_data = {"status": "approved"}
        
        response = client.put(f"/api/v1/kyc/checks/{fake_check_id}", json=update_data, headers=headers)
        
        assert response.status_code == 404
        assert "KYC check not found" in response.json()["detail"]
    
    def test_update_kyc_check_non_admin_forbidden(self, client, test_db, create_test_user, create_kyc_check):
        """Test non-admin cannot update KYC checks."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        check_id = str(create_kyc_check.id)
        
        update_data = {"status": "approved"}
        
        response = client.put(f"/api/v1/kyc/checks/{check_id}", json=update_data, headers=headers)
        
        assert response.status_code == 403
    
    def test_update_kyc_status_compliance_success(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test successful KYC status update by compliance officer."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        check_id = str(create_kyc_check.id)
        
        status_update = {
            "status": "manual_review",
            "notes": "Requires additional documentation"
        }
        
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "manual_review"
        assert data["notes"] == "Requires additional documentation"
    
    def test_update_kyc_status_rejected_with_reason(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test KYC status update to rejected with reason."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        check_id = str(create_kyc_check.id)
        
        status_update = {
            "status": "rejected",
            "rejection_reason": "Document quality insufficient",
            "notes": "Please resubmit with clearer images"
        }
        
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "rejected"
        assert "Document quality insufficient" in str(data.get("rejection_reason", ""))
    
    def test_update_kyc_status_rejected_without_reason(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test KYC status update to rejected without reason fails validation."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        check_id = str(create_kyc_check.id)
        
        status_update = {
            "status": "rejected",
            "notes": "Rejected without specific reason"
        }
        
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=headers)
        
        assert response.status_code == 422
    
    def test_update_kyc_status_non_compliance_forbidden(self, client, test_db, create_test_user, create_kyc_check):
        """Test non-compliance user cannot update KYC status."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        check_id = str(create_kyc_check.id)
        
        status_update = {"status": "approved"}
        
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=headers)
        
        assert response.status_code == 403


class TestKYCCheckHistory:
    """Test cases for KYC check history endpoint."""
    
    def test_get_kyc_history_success(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test successful KYC history retrieval."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}/history", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "kyc_check_id" in data
        assert "history" in data
        assert "total_entries" in data
        
        assert data["kyc_check_id"] == check_id
        assert isinstance(data["history"], list)
        assert data["total_entries"] >= 1
    
    def test_get_kyc_history_not_found(self, client, test_db, create_compliance_user):
        """Test getting history for non-existent KYC check."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        fake_check_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(f"/api/v1/kyc/checks/{fake_check_id}/history", headers=headers)
        
        assert response.status_code == 404
        assert "KYC check not found" in response.json()["detail"]
    
    def test_get_kyc_history_non_compliance_forbidden(self, client, test_db, create_test_user, create_kyc_check):
        """Test non-compliance user cannot access KYC history."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        check_id = str(create_kyc_check.id)
        
        response = client.get(f"/api/v1/kyc/checks/{check_id}/history", headers=headers)
        
        assert response.status_code == 403


class TestKYCStatistics:
    """Test cases for KYC statistics endpoint."""
    
    def test_get_kyc_statistics_success(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test successful KYC statistics retrieval."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        response = client.get("/api/v1/kyc/statistics", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "statistics" in data
        assert "generated_at" in data
        assert "generated_by" in data
        
        assert data["generated_by"] == "compliance@example.com"
        assert isinstance(data["statistics"], dict)
    
    def test_get_kyc_statistics_non_compliance_forbidden(self, client, test_db, create_test_user):
        """Test non-compliance user cannot access KYC statistics."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/statistics", headers=headers)
        
        assert response.status_code == 403


class TestKYCPendingChecks:
    """Test cases for pending KYC checks endpoint."""
    
    def test_get_pending_checks_success(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test successful pending checks retrieval."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        response = client.get("/api/v1/kyc/pending", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "pending_checks" in data
        assert "total_pending" in data
        assert "retrieved_at" in data
        
        assert isinstance(data["pending_checks"], list)
        assert data["total_pending"] >= 1
    
    def test_get_pending_checks_with_limit(self, client, test_db, create_compliance_user, create_test_user, create_kyc_check):
        """Test pending checks retrieval with limit."""
        headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        response = client.get("/api/v1/kyc/pending?limit=5", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["pending_checks"]) <= 5
    
    def test_get_pending_checks_non_compliance_forbidden(self, client, test_db, create_test_user):
        """Test non-compliance user cannot access pending checks."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        
        response = client.get("/api/v1/kyc/pending", headers=headers)
        
        assert response.status_code == 403


class TestKYCWorkflows:
    """Test cases for complete KYC workflows."""
    
    def test_complete_kyc_verification_workflow(self, client, test_db, create_test_user, create_compliance_user):
        """Test complete KYC verification workflow."""
        user_headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        compliance_headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        # 1. User creates KYC check
        kyc_data = get_sample_kyc_data()
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=user_headers)
        assert response.status_code == 201
        check_data = response.json()
        check_id = check_data["id"]
        assert check_data["status"] == "pending"
        
        # 2. User checks their KYC status
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        
        # 3. Compliance officer reviews and updates status
        status_update = {
            "status": "manual_review",
            "notes": "Additional verification required"
        }
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=compliance_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "manual_review"
        
        # 4. User checks updated status
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "manual_review"
        
        # 5. Compliance officer approves
        status_update = {
            "status": "approved",
            "notes": "Verification completed successfully"
        }
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=compliance_headers)
        assert response.status_code == 200
        final_data = response.json()
        assert final_data["status"] == "approved"
        assert final_data["is_completed"] is True
        
        # 6. User sees final approved status
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
    
    def test_kyc_rejection_workflow(self, client, test_db, create_test_user, create_compliance_user):
        """Test KYC rejection workflow."""
        user_headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        compliance_headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        # 1. User creates KYC check
        kyc_data = get_sample_kyc_data()
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=user_headers)
        assert response.status_code == 201
        check_id = response.json()["id"]
        
        # 2. Compliance officer rejects with reason
        status_update = {
            "status": "rejected",
            "rejection_reason": "Document quality insufficient",
            "notes": "Please resubmit with clearer document images"
        }
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=compliance_headers)
        assert response.status_code == 200
        rejected_data = response.json()
        assert rejected_data["status"] == "rejected"
        assert rejected_data["is_completed"] is True
        
        # 3. User sees rejection with reason
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user_headers)
        assert response.status_code == 200
        final_data = response.json()
        assert final_data["status"] == "rejected"
        assert "Document quality insufficient" in str(final_data.get("rejection_reason", ""))
    
    def test_kyc_access_control_workflow(self, client, test_db, create_test_user, create_second_user, create_admin_user, create_compliance_user):
        """Test KYC access control across different user roles."""
        user1_headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        user2_headers = get_auth_headers(client, "user2@example.com", "TestPassword123")
        admin_headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        compliance_headers = get_auth_headers(client, "compliance@example.com", "CompliancePassword123")
        
        # User 1 creates KYC check
        kyc_data = get_sample_kyc_data()
        response = client.post("/api/v1/kyc/checks", json=kyc_data, headers=user1_headers)
        assert response.status_code == 201
        check_id = response.json()["id"]
        
        # User 1 can access their own check
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user1_headers)
        assert response.status_code == 200
        
        # User 2 cannot access User 1's check
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=user2_headers)
        assert response.status_code == 404
        
        # Admin can access any check
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=admin_headers)
        assert response.status_code == 200
        
        # Compliance officer can access any check
        response = client.get(f"/api/v1/kyc/checks/{check_id}", headers=compliance_headers)
        assert response.status_code == 200
        
        # Only admin can do full updates
        update_data = {"provider_reference": "ADMIN_UPDATE"}
        response = client.put(f"/api/v1/kyc/checks/{check_id}", json=update_data, headers=admin_headers)
        assert response.status_code == 200
        
        # Compliance can update status
        status_update = {"status": "approved", "notes": "Approved by compliance"}
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=compliance_headers)
        assert response.status_code == 200
        
        # Regular users cannot update
        response = client.put(f"/api/v1/kyc/checks/{check_id}", json=update_data, headers=user1_headers)
        assert response.status_code == 403
        
        response = client.patch(f"/api/v1/kyc/checks/{check_id}/status", json=status_update, headers=user1_headers)
        assert response.status_code == 403