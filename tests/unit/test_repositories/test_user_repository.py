"""
Unit tests for user repository.
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


class TestUserRepository:
    """Test cases for UserRepository class."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def user_repo(self, mock_db):
        """Create UserRepository instance with mocked database."""
        return UserRepository(mock_db)
    
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
    
    def test_get_by_email_found(self, user_repo, mock_db, sample_user):
        """Test getting user by email when user exists."""
        # Setup
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_user
        mock_db.query.return_value = mock_query
        
        # Execute
        result = user_repo.get_by_email("test@example.com")
        
        # Verify
        assert result == sample_user
        mock_db.query.assert_called_once_with(User)
        mock_query.filter.assert_called_once()
        mock_filter.first.assert_called_once()
    
    def test_get_by_email_not_found(self, user_repo, mock_db):
        """Test getting user by email when user doesn't exist."""
        # Setup
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Execute
        result = user_repo.get_by_email("nonexistent@example.com")
        
        # Verify
        assert result is None
    
    def test_create_user(self, user_repo, sample_user):
        """Test creating a new user."""
        # Setup
        user_data = {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "hashed_password": "hashed_password"
        }
        
        with patch.object(user_repo, 'create_from_dict', return_value=sample_user) as mock_create:
            # Execute
            result = user_repo.create_user(user_data)
            
            # Verify
            assert result == sample_user
            mock_create.assert_called_once_with(user_data)
    
    def test_authenticate_success(self, user_repo, mock_db, sample_user):
        """Test successful user authentication."""
        # Setup
        email = "test@example.com"
        password = "TestPassword123"
        
        with patch.object(user_repo, 'get_by_email', return_value=sample_user):
            with patch('app.core.security.SecurityUtils') as mock_security:
                mock_security.verify_password.return_value = True
                
                # Execute
                result = user_repo.authenticate(email, password)
                
                # Verify
                assert result == sample_user
                mock_security.verify_password.assert_called_once_with(password, sample_user.hashed_password)
    
    def test_authenticate_user_not_found(self, user_repo):
        """Test authentication when user doesn't exist."""
        # Setup
        email = "nonexistent@example.com"
        password = "TestPassword123"
        
        with patch.object(user_repo, 'get_by_email', return_value=None):
            # Execute
            result = user_repo.authenticate(email, password)
            
            # Verify
            assert result is None
    
    def test_authenticate_wrong_password(self, user_repo, sample_user):
        """Test authentication with wrong password."""
        # Setup
        email = "test@example.com"
        password = "WrongPassword"
        
        with patch.object(user_repo, 'get_by_email', return_value=sample_user):
            with patch('app.core.security.SecurityUtils') as mock_security:
                mock_security.verify_password.return_value = False
                
                # Execute
                result = user_repo.authenticate(email, password)
                
                # Verify
                assert result is None
    
    def test_is_email_taken_true(self, user_repo, mock_db, sample_user):
        """Test email taken check when email exists."""
        # Setup
        email = "test@example.com"
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_user
        mock_db.query.return_value = mock_query
        
        # Execute
        result = user_repo.is_email_taken(email)
        
        # Verify
        assert result is True
    
    def test_is_email_taken_false(self, user_repo, mock_db):
        """Test email taken check when email doesn't exist."""
        # Setup
        email = "available@example.com"
        
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Execute
        result = user_repo.is_email_taken(email)
        
        # Verify
        assert result is False
    
    def test_get_active_users(self, user_repo):
        """Test getting active users."""
        # Setup
        skip = 0
        limit = 10
        expected_users = [Mock(spec=User), Mock(spec=User)]
        
        with patch.object(user_repo, 'get_multi', return_value=expected_users) as mock_get_multi:
            # Execute
            result = user_repo.get_active_users(skip, limit)
            
            # Verify
            assert result == expected_users
            mock_get_multi.assert_called_once_with(skip=skip, limit=limit, is_active=True)
    
    def test_get_users_by_role(self, user_repo):
        """Test getting users by role."""
        # Setup
        role = UserRole.ADMIN
        skip = 0
        limit = 10
        expected_users = [Mock(spec=User)]
        
        with patch.object(user_repo, 'get_multi', return_value=expected_users) as mock_get_multi:
            # Execute
            result = user_repo.get_users_by_role(role, skip, limit)
            
            # Verify
            assert result == expected_users
            mock_get_multi.assert_called_once_with(skip=skip, limit=limit, role=role)
    
    def test_deactivate_user_success(self, user_repo, sample_user):
        """Test successful user deactivation."""
        # Setup
        user_id = "test-user-123"
        
        with patch.object(user_repo, 'get_by_id', return_value=sample_user):
            with patch.object(user_repo, 'update', return_value=sample_user) as mock_update:
                # Execute
                result = user_repo.deactivate_user(user_id)
                
                # Verify
                assert result == sample_user
                mock_update.assert_called_once_with(sample_user, {"is_active": False})
    
    def test_deactivate_user_not_found(self, user_repo):
        """Test user deactivation when user doesn't exist."""
        # Setup
        user_id = "nonexistent-user"
        
        with patch.object(user_repo, 'get_by_id', return_value=None):
            # Execute
            result = user_repo.deactivate_user(user_id)
            
            # Verify
            assert result is None
    
    def test_activate_user_success(self, user_repo, sample_user):
        """Test successful user activation."""
        # Setup
        user_id = "test-user-123"
        
        with patch.object(user_repo, 'get_by_id', return_value=sample_user):
            with patch.object(user_repo, 'update', return_value=sample_user) as mock_update:
                # Execute
                result = user_repo.activate_user(user_id)
                
                # Verify
                assert result == sample_user
                mock_update.assert_called_once_with(sample_user, {"is_active": True})
    
    def test_verify_user_email_success(self, user_repo, sample_user):
        """Test successful email verification."""
        # Setup
        user_id = "test-user-123"
        
        with patch.object(user_repo, 'get_by_id', return_value=sample_user):
            with patch.object(user_repo, 'update', return_value=sample_user) as mock_update:
                # Execute
                result = user_repo.verify_user_email(user_id)
                
                # Verify
                assert result == sample_user
                mock_update.assert_called_once_with(sample_user, {"is_verified": True})