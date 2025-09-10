"""
Integration tests for authentication API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User, UserRole
from app.core.security import SecurityUtils


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"

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
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123",
        "confirm_password": "TestPassword123",
        "first_name": "Test",
        "last_name": "User"
    }


@pytest.fixture
def create_test_user(test_db):
    """Create a test user in the database."""
    db = TestingSessionLocal()
    
    hashed_password = SecurityUtils.get_password_hash("TestPassword123")
    user = User(
        email="existing@example.com",
        first_name="Existing",
        last_name="User",
        hashed_password=hashed_password,
        role=UserRole.USER,
        is_active=True,
        is_verified=False
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


class TestAuthenticationEndpoints:
    """Test cases for authentication endpoints."""
    
    def test_register_success(self, client, test_db, test_user_data):
        """Test successful user registration."""
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_register_duplicate_email(self, client, test_db, create_test_user):
        """Test registration with existing email."""
        user_data = {
            "email": "existing@example.com",
            "password": "TestPassword123",
            "confirm_password": "TestPassword123",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    def test_register_password_mismatch(self, client, test_db):
        """Test registration with password mismatch."""
        user_data = {
            "email": "test@example.com",
            "password": "TestPassword123",
            "confirm_password": "DifferentPassword123",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422
    
    def test_register_weak_password(self, client, test_db):
        """Test registration with weak password."""
        user_data = {
            "email": "test@example.com",
            "password": "weak",
            "confirm_password": "weak",
            "first_name": "Test",
            "last_name": "User"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422
    
    def test_login_success(self, client, test_db, create_test_user):
        """Test successful user login."""
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_email(self, client, test_db):
        """Test login with invalid email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "TestPassword123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    def test_login_invalid_password(self, client, test_db, create_test_user):
        """Test login with invalid password."""
        login_data = {
            "email": "existing@example.com",
            "password": "WrongPassword"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    def test_refresh_token_success(self, client, test_db, create_test_user):
        """Test successful token refresh."""
        # First login to get tokens
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()
        
        # Use refresh token
        refresh_data = {
            "refresh_token": tokens["refresh_token"]
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        
        # New tokens should be different
        assert data["access_token"] != tokens["access_token"]
        assert data["refresh_token"] != tokens["refresh_token"]
    
    def test_refresh_token_invalid(self, client, test_db):
        """Test token refresh with invalid token."""
        refresh_data = {
            "refresh_token": "invalid_token"
        }
        
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["detail"]
    
    def test_get_current_user_info(self, client, test_db, create_test_user):
        """Test getting current user info."""
        # Login to get token
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Get user info
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == "existing@example.com"
        assert data["first_name"] == "Existing"
        assert data["last_name"] == "User"
        assert data["role"] == "user"
        assert data["is_active"] is True
    
    def test_get_current_user_info_no_token(self, client, test_db):
        """Test getting current user info without token."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 403
    
    def test_change_password_success(self, client, test_db, create_test_user):
        """Test successful password change."""
        # Login to get token
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Change password
        password_data = {
            "current_password": "TestPassword123",
            "new_password": "NewPassword123",
            "confirm_new_password": "NewPassword123"
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/v1/auth/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]
        
        # Verify old password no longer works
        old_login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        old_response = client.post("/api/v1/auth/login", json=old_login_data)
        assert old_response.status_code == 401
        
        # Verify new password works
        new_login_data = {
            "email": "existing@example.com",
            "password": "NewPassword123"
        }
        
        new_response = client.post("/api/v1/auth/login", json=new_login_data)
        assert new_response.status_code == 200
    
    def test_change_password_wrong_current(self, client, test_db, create_test_user):
        """Test password change with wrong current password."""
        # Login to get token
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Try to change password with wrong current password
        password_data = {
            "current_password": "WrongPassword",
            "new_password": "NewPassword123",
            "confirm_new_password": "NewPassword123"
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/api/v1/auth/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 400
        assert "Incorrect current password" in response.json()["detail"]
    
    def test_verify_token_valid(self, client, test_db, create_test_user):
        """Test token verification with valid token."""
        # Login to get token
        login_data = {
            "email": "existing@example.com",
            "password": "TestPassword123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Verify token
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] is True
        assert data["email"] == "existing@example.com"
    
    def test_verify_token_invalid(self, client, test_db):
        """Test token verification with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 401
    
    def test_logout(self, client, test_db):
        """Test logout endpoint."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]