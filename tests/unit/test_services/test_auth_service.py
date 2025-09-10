"""
Unit tests for authentication service.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_service import AuthService


class TestAuthService:
    """Test cases for AuthService class."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock()

    @pytest.fixture
    def mock_user_repo(self):
        """Mock user repository."""
        return Mock()

    @pytest.fixture
    def auth_service(self, mock_db, mock_user_repo):
        """Create AuthService instance with mocked dependencies."""
        service = AuthService(mock_db)
        service.user_repo = mock_user_repo
        return service

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        user = Mock(spec=User)
        user.id = "test-user-123"
        user.email = "test@example.com"
        user.first_name = "Test"
        user.last_name = "User"
        user.role = UserRole.USER
        user.is_active = True
        user.is_verified = False
        user.hashed_password = "hashed_password"
        return user

    def test_register_user_success(self, auth_service, mock_user_repo, sample_user):
        """Test successful user registration."""
        # Setup
        user_data = UserRegister(
            email="test@example.com",
            password="TestPassword123",
            confirm_password="TestPassword123",
            first_name="Test",
            last_name="User",
        )

        mock_user_repo.is_email_taken.return_value = False
        mock_user_repo.create_user.return_value = sample_user

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.get_password_hash.return_value = "hashed_password"
            mock_security.create_token_pair.return_value = {
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "token_type": "bearer",
            }

            result = auth_service.register_user(user_data)

        # Verify
        assert result["access_token"] == "access_token"
        assert result["refresh_token"] == "refresh_token"
        assert result["token_type"] == "bearer"

        mock_user_repo.is_email_taken.assert_called_once_with("test@example.com")
        mock_user_repo.create_user.assert_called_once()
        mock_security.get_password_hash.assert_called_once_with("TestPassword123")
        mock_security.create_token_pair.assert_called_once_with("test-user-123")

    def test_register_user_email_already_exists(self, auth_service, mock_user_repo):
        """Test user registration with existing email."""
        # Setup
        user_data = UserRegister(
            email="existing@example.com",
            password="TestPassword123",
            confirm_password="TestPassword123",
            first_name="Test",
            last_name="User",
        )

        mock_user_repo.is_email_taken.return_value = True

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            auth_service.register_user(user_data)

        assert exc_info.value.status_code == 400
        assert "Email already registered" in str(exc_info.value.detail)

    def test_authenticate_user_success(self, auth_service, mock_user_repo, sample_user):
        """Test successful user authentication."""
        # Setup
        login_data = UserLogin(email="test@example.com", password="TestPassword123")

        mock_user_repo.authenticate.return_value = sample_user

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.create_token_pair.return_value = {
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "token_type": "bearer",
            }

            result = auth_service.authenticate_user(login_data)

        # Verify
        assert result["access_token"] == "access_token"
        assert result["refresh_token"] == "refresh_token"

        mock_user_repo.authenticate.assert_called_once_with(
            "test@example.com", "TestPassword123"
        )
        mock_security.create_token_pair.assert_called_once_with("test-user-123")

    def test_authenticate_user_invalid_credentials(self, auth_service, mock_user_repo):
        """Test authentication with invalid credentials."""
        # Setup
        login_data = UserLogin(email="test@example.com", password="WrongPassword")

        mock_user_repo.authenticate.return_value = None

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user(login_data)

        assert exc_info.value.status_code == 401
        assert "Incorrect email or password" in str(exc_info.value.detail)

    def test_authenticate_user_inactive_account(
        self, auth_service, mock_user_repo, sample_user
    ):
        """Test authentication with inactive user account."""
        # Setup
        login_data = UserLogin(email="test@example.com", password="TestPassword123")

        sample_user.is_active = False
        mock_user_repo.authenticate.return_value = sample_user

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            auth_service.authenticate_user(login_data)

        assert exc_info.value.status_code == 401
        assert "User account is deactivated" in str(exc_info.value.detail)

    def test_refresh_token_success(self, auth_service, mock_user_repo, sample_user):
        """Test successful token refresh."""
        # Setup
        refresh_token = "valid_refresh_token"
        mock_user_repo.get_by_id.return_value = sample_user

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.get_subject_from_token.return_value = "test-user-123"
            mock_security.create_token_pair.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "token_type": "bearer",
            }

            result = auth_service.refresh_token(refresh_token)

        # Verify
        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"

        mock_security.get_subject_from_token.assert_called_once_with(
            refresh_token, "refresh"
        )
        mock_user_repo.get_by_id.assert_called_once_with("test-user-123")
        mock_security.create_token_pair.assert_called_once_with("test-user-123")

    def test_refresh_token_invalid_token(self, auth_service):
        """Test token refresh with invalid token."""
        # Setup
        refresh_token = "invalid_refresh_token"

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.get_subject_from_token.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                auth_service.refresh_token(refresh_token)

        # Verify
        assert exc_info.value.status_code == 401
        assert "Invalid refresh token" in str(exc_info.value.detail)

    def test_refresh_token_user_not_found(self, auth_service, mock_user_repo):
        """Test token refresh with non-existent user."""
        # Setup
        refresh_token = "valid_refresh_token"
        mock_user_repo.get_by_id.return_value = None

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.get_subject_from_token.return_value = "non-existent-user"

            with pytest.raises(HTTPException) as exc_info:
                auth_service.refresh_token(refresh_token)

        # Verify
        assert exc_info.value.status_code == 401
        assert "User not found or inactive" in str(exc_info.value.detail)

    def test_change_password_success(self, auth_service, mock_user_repo, sample_user):
        """Test successful password change."""
        # Setup
        current_password = "CurrentPassword123"
        new_password = "NewPassword123"

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.verify_password.return_value = True
            mock_security.get_password_hash.return_value = "new_hashed_password"

            result = auth_service.change_password(
                sample_user, current_password, new_password
            )

        # Verify
        assert result is True

        mock_security.verify_password.assert_called_once_with(
            current_password, sample_user.hashed_password
        )
        mock_security.get_password_hash.assert_called_once_with(new_password)
        mock_user_repo.update.assert_called_once_with(
            sample_user, {"hashed_password": "new_hashed_password"}
        )

    def test_change_password_incorrect_current_password(
        self, auth_service, sample_user
    ):
        """Test password change with incorrect current password."""
        # Setup
        current_password = "WrongPassword"
        new_password = "NewPassword123"

        # Execute
        with patch("app.services.auth_service.SecurityUtils") as mock_security:
            mock_security.verify_password.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                auth_service.change_password(
                    sample_user, current_password, new_password
                )

        # Verify
        assert exc_info.value.status_code == 400
        assert "Incorrect current password" in str(exc_info.value.detail)

    def test_get_user_info(self, auth_service, sample_user):
        """Test getting user information."""
        # Execute
        result = auth_service.get_user_info(sample_user)

        # Verify
        expected = {
            "id": "test-user-123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "role": "user",
            "is_active": True,
            "is_verified": False,
        }

        assert result == expected

    def test_verify_user_email(self, auth_service, mock_user_repo, sample_user):
        """Test email verification."""
        # Setup
        user_id = "test-user-123"
        mock_user_repo.verify_user_email.return_value = sample_user

        # Execute
        result = auth_service.verify_user_email(user_id)

        # Verify
        assert result == sample_user
        mock_user_repo.verify_user_email.assert_called_once_with(user_id)

    def test_deactivate_user(self, auth_service, mock_user_repo, sample_user):
        """Test user deactivation."""
        # Setup
        user_id = "test-user-123"
        mock_user_repo.deactivate_user.return_value = sample_user

        # Execute
        result = auth_service.deactivate_user(user_id)

        # Verify
        assert result == sample_user
        mock_user_repo.deactivate_user.assert_called_once_with(user_id)

    def test_activate_user(self, auth_service, mock_user_repo, sample_user):
        """Test user activation."""
        # Setup
        user_id = "test-user-123"
        mock_user_repo.activate_user.return_value = sample_user

        # Execute
        result = auth_service.activate_user(user_id)

        # Verify
        assert result == sample_user
        mock_user_repo.activate_user.assert_called_once_with(user_id)
