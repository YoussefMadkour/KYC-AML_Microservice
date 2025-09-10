"""
Integration tests for user management API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import SecurityUtils
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User, UserRole

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_user.db"

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
        country="US",
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
        is_verified=True,
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
        is_verified=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    return user


def get_auth_headers(client, email: str, password: str):
    """Helper function to get authentication headers."""
    login_data = {"email": email, "password": password}
    response = client.post("/api/v1/auth/login", json=login_data)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestUserProfileEndpoints:
    """Test cases for user profile endpoints."""

    def test_get_user_profile_success(self, client, test_db, create_test_user):
        """Test successful retrieval of user profile."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        response = client.get("/api/v1/users/profile", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "testuser@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert data["full_name"] == "Test User"
        assert data["phone_number"] == "1234567890"
        assert data["address_line1"] == "123 Test St"
        assert data["city"] == "Test City"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_user_profile_unauthorized(self, client, test_db):
        """Test getting user profile without authentication."""
        response = client.get("/api/v1/users/profile")

        assert response.status_code == 403

    def test_update_user_profile_success(self, client, test_db, create_test_user):
        """Test successful user profile update."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "phone_number": "9876543210",
            "address_line1": "456 New St",
            "address_line2": "Apt 2B",
            "city": "New City",
            "state_province": "New State",
            "postal_code": "54321",
            "country": "CA",
        }

        response = client.put(
            "/api/v1/users/profile", json=update_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["full_name"] == "Updated Name"
        assert data["phone_number"] == "9876543210"
        assert data["address_line1"] == "456 New St"
        assert data["address_line2"] == "Apt 2B"
        assert data["city"] == "New City"
        assert data["state_province"] == "New State"
        assert data["postal_code"] == "54321"
        assert data["country"] == "CA"

    def test_update_user_profile_partial(self, client, test_db, create_test_user):
        """Test partial user profile update."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        update_data = {"first_name": "PartialUpdate"}

        response = client.put(
            "/api/v1/users/profile", json=update_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["first_name"] == "PartialUpdate"
        assert data["last_name"] == "User"  # Should remain unchanged
        assert data["email"] == "testuser@example.com"  # Should remain unchanged

    def test_update_user_profile_invalid_country(
        self, client, test_db, create_test_user
    ):
        """Test user profile update with invalid country code."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        update_data = {"country": "INVALID"}  # Should be 2 characters

        response = client.put(
            "/api/v1/users/profile", json=update_data, headers=headers
        )

        assert response.status_code == 422

    def test_update_user_profile_unauthorized(self, client, test_db, create_test_user):
        """Test updating user profile without authentication."""
        update_data = {"first_name": "Unauthorized"}

        response = client.put("/api/v1/users/profile", json=update_data)

        assert response.status_code == 403


class TestUserListEndpoints:
    """Test cases for user list endpoints (admin only)."""

    def test_list_users_admin_success(
        self, client, test_db, create_admin_user, create_test_user, create_second_user
    ):
        """Test successful user listing by admin."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")

        response = client.get("/api/v1/users", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 3  # admin + 2 test users

        # Check that all users are returned
        emails = [user["email"] for user in data]
        assert "admin@example.com" in emails
        assert "testuser@example.com" in emails
        assert "user2@example.com" in emails

    def test_list_users_with_pagination(
        self, client, test_db, create_admin_user, create_test_user, create_second_user
    ):
        """Test user listing with pagination."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")

        response = client.get("/api/v1/users?skip=1&limit=1", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_users_with_role_filter(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test user listing with role filter."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")

        response = client.get("/api/v1/users?role=admin", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["role"] == "admin"
        assert data[0]["email"] == "admin@example.com"

    def test_list_users_with_active_filter(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test user listing with active status filter."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")

        response = client.get("/api/v1/users?is_active=true", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert all(user["is_active"] for user in data)

    def test_list_users_non_admin_forbidden(self, client, test_db, create_test_user):
        """Test that non-admin users cannot list users."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        response = client.get("/api/v1/users", headers=headers)

        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]

    def test_list_users_unauthorized(self, client, test_db):
        """Test user listing without authentication."""
        response = client.get("/api/v1/users")

        assert response.status_code == 403


class TestUserDetailEndpoints:
    """Test cases for individual user detail endpoints."""

    def test_get_user_by_id_own_data(self, client, test_db, create_test_user):
        """Test user getting their own data by ID."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        user_id = str(create_test_user.id)

        response = client.get(f"/api/v1/users/{user_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == user_id
        assert data["email"] == "testuser@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"

    def test_get_user_by_id_admin_access(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test admin getting any user's data by ID."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)

        response = client.get(f"/api/v1/users/{user_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == user_id
        assert data["email"] == "testuser@example.com"

    def test_get_user_by_id_forbidden_other_user(
        self, client, test_db, create_test_user, create_second_user
    ):
        """Test user cannot access another user's data."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        other_user_id = str(create_second_user.id)

        response = client.get(f"/api/v1/users/{other_user_id}", headers=headers)

        assert response.status_code == 403
        assert "Not enough permissions" in response.json()["detail"]

    def test_get_user_by_id_not_found(self, client, test_db, create_admin_user):
        """Test getting non-existent user by ID."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        response = client.get(f"/api/v1/users/{fake_user_id}", headers=headers)

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_user_by_id_unauthorized(self, client, test_db, create_test_user):
        """Test getting user by ID without authentication."""
        user_id = str(create_test_user.id)

        response = client.get(f"/api/v1/users/{user_id}")

        assert response.status_code == 403


class TestUserAdminEndpoints:
    """Test cases for admin-only user management endpoints."""

    def test_update_user_admin_success(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test admin updating any user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)

        update_data = {
            "first_name": "AdminUpdated",
            "last_name": "Name",
            "email": "updated@example.com",
            "role": "compliance_officer",
            "is_active": False,
            "is_verified": True,
        }

        response = client.put(
            f"/api/v1/users/{user_id}", json=update_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["first_name"] == "AdminUpdated"
        assert data["last_name"] == "Name"
        assert data["email"] == "updated@example.com"
        assert data["role"] == "compliance_officer"
        assert data["is_active"] is False
        assert data["is_verified"] is True

    def test_update_user_admin_duplicate_email(
        self, client, test_db, create_admin_user, create_test_user, create_second_user
    ):
        """Test admin updating user with duplicate email."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)

        update_data = {"email": "user2@example.com"}  # Email of second user

        response = client.put(
            f"/api/v1/users/{user_id}", json=update_data, headers=headers
        )

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_update_user_admin_not_found(self, client, test_db, create_admin_user):
        """Test admin updating non-existent user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        update_data = {"first_name": "Updated"}

        response = client.put(
            f"/api/v1/users/{fake_user_id}", json=update_data, headers=headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_update_user_non_admin_forbidden(
        self, client, test_db, create_test_user, create_second_user
    ):
        """Test non-admin user cannot update other users."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        other_user_id = str(create_second_user.id)

        update_data = {"first_name": "Unauthorized"}

        response = client.put(
            f"/api/v1/users/{other_user_id}", json=update_data, headers=headers
        )

        assert response.status_code == 403

    def test_deactivate_user_admin_success(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test admin deactivating a user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)

        response = client.post(f"/api/v1/users/{user_id}/deactivate", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["is_active"] is False
        assert data["id"] == user_id

    def test_activate_user_admin_success(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test admin activating a user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        user_id = str(create_test_user.id)

        # First deactivate
        client.post(f"/api/v1/users/{user_id}/deactivate", headers=headers)

        # Then activate
        response = client.post(f"/api/v1/users/{user_id}/activate", headers=headers)

        assert response.status_code == 200
        data = response.json()

        assert data["is_active"] is True
        assert data["id"] == user_id

    def test_deactivate_user_not_found(self, client, test_db, create_admin_user):
        """Test deactivating non-existent user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        response = client.post(
            f"/api/v1/users/{fake_user_id}/deactivate", headers=headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_activate_user_not_found(self, client, test_db, create_admin_user):
        """Test activating non-existent user."""
        headers = get_auth_headers(client, "admin@example.com", "AdminPassword123")
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        response = client.post(
            f"/api/v1/users/{fake_user_id}/activate", headers=headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_deactivate_user_non_admin_forbidden(
        self, client, test_db, create_test_user, create_second_user
    ):
        """Test non-admin cannot deactivate users."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        other_user_id = str(create_second_user.id)

        response = client.post(
            f"/api/v1/users/{other_user_id}/deactivate", headers=headers
        )

        assert response.status_code == 403

    def test_activate_user_non_admin_forbidden(
        self, client, test_db, create_test_user, create_second_user
    ):
        """Test non-admin cannot activate users."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")
        other_user_id = str(create_second_user.id)

        response = client.post(
            f"/api/v1/users/{other_user_id}/activate", headers=headers
        )

        assert response.status_code == 403


class TestUserManagementWorkflows:
    """Test cases for complete user management workflows."""

    def test_complete_user_profile_workflow(self, client, test_db, create_test_user):
        """Test complete user profile management workflow."""
        headers = get_auth_headers(client, "testuser@example.com", "TestPassword123")

        # 1. Get initial profile
        response = client.get("/api/v1/users/profile", headers=headers)
        assert response.status_code == 200
        initial_data = response.json()
        assert initial_data["first_name"] == "Test"

        # 2. Update profile
        update_data = {
            "first_name": "Updated",
            "phone_number": "9999999999",
            "address_line1": "New Address",
        }
        response = client.put(
            "/api/v1/users/profile", json=update_data, headers=headers
        )
        assert response.status_code == 200
        updated_data = response.json()
        assert updated_data["first_name"] == "Updated"
        assert updated_data["phone_number"] == "9999999999"

        # 3. Verify changes persisted
        response = client.get("/api/v1/users/profile", headers=headers)
        assert response.status_code == 200
        final_data = response.json()
        assert final_data["first_name"] == "Updated"
        assert final_data["phone_number"] == "9999999999"
        assert final_data["address_line1"] == "New Address"

    def test_admin_user_management_workflow(
        self, client, test_db, create_admin_user, create_test_user
    ):
        """Test complete admin user management workflow."""
        admin_headers = get_auth_headers(
            client, "admin@example.com", "AdminPassword123"
        )
        user_id = str(create_test_user.id)

        # 1. List all users
        response = client.get("/api/v1/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) == 2  # admin + test user

        # 2. Get specific user
        response = client.get(f"/api/v1/users/{user_id}", headers=admin_headers)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["is_active"] is True

        # 3. Update user
        update_data = {"role": "compliance_officer", "is_verified": True}
        response = client.put(
            f"/api/v1/users/{user_id}", json=update_data, headers=admin_headers
        )
        assert response.status_code == 200
        updated_user = response.json()
        assert updated_user["role"] == "compliance_officer"
        assert updated_user["is_verified"] is True

        # 4. Deactivate user
        response = client.post(
            f"/api/v1/users/{user_id}/deactivate", headers=admin_headers
        )
        assert response.status_code == 200
        deactivated_user = response.json()
        assert deactivated_user["is_active"] is False

        # 5. Reactivate user
        response = client.post(
            f"/api/v1/users/{user_id}/activate", headers=admin_headers
        )
        assert response.status_code == 200
        reactivated_user = response.json()
        assert reactivated_user["is_active"] is True

    def test_user_access_control_workflow(
        self, client, test_db, create_test_user, create_second_user, create_admin_user
    ):
        """Test user access control across different scenarios."""
        user1_headers = get_auth_headers(
            client, "testuser@example.com", "TestPassword123"
        )
        user2_headers = get_auth_headers(client, "user2@example.com", "TestPassword123")
        admin_headers = get_auth_headers(
            client, "admin@example.com", "AdminPassword123"
        )

        user1_id = str(create_test_user.id)
        user2_id = str(create_second_user.id)

        # User 1 can access their own data
        response = client.get(f"/api/v1/users/{user1_id}", headers=user1_headers)
        assert response.status_code == 200

        # User 1 cannot access User 2's data
        response = client.get(f"/api/v1/users/{user2_id}", headers=user1_headers)
        assert response.status_code == 403

        # User 1 cannot list all users
        response = client.get("/api/v1/users", headers=user1_headers)
        assert response.status_code == 403

        # Admin can access any user's data
        response = client.get(f"/api/v1/users/{user1_id}", headers=admin_headers)
        assert response.status_code == 200

        response = client.get(f"/api/v1/users/{user2_id}", headers=admin_headers)
        assert response.status_code == 200

        # Admin can list all users
        response = client.get("/api/v1/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) == 3  # 2 test users + admin
