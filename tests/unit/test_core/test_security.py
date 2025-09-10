"""
Unit tests for security utilities.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.core.security import SecurityUtils


class TestSecurityUtils:
    """Test cases for SecurityUtils class."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "TestPassword123"
        
        # Hash password
        hashed = SecurityUtils.get_password_hash(password)
        
        # Verify password
        assert SecurityUtils.verify_password(password, hashed)
        assert not SecurityUtils.verify_password("WrongPassword", hashed)
        assert not SecurityUtils.verify_password("", hashed)
    
    def test_create_access_token(self):
        """Test JWT access token creation."""
        user_id = "test-user-123"
        
        # Create token
        token = SecurityUtils.create_access_token(user_id)
        
        # Verify token
        payload = SecurityUtils.verify_token(token, "access")
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert "exp" in payload
    
    def test_create_refresh_token(self):
        """Test JWT refresh token creation."""
        user_id = "test-user-123"
        
        # Create token
        token = SecurityUtils.create_refresh_token(user_id)
        
        # Verify token
        payload = SecurityUtils.verify_token(token, "refresh")
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert "exp" in payload
    
    def test_create_access_token_with_custom_expiry(self):
        """Test JWT access token creation with custom expiry."""
        user_id = "test-user-123"
        expires_delta = timedelta(minutes=15)
        
        # Create token with custom expiry
        token = SecurityUtils.create_access_token(user_id, expires_delta)
        
        # Verify token
        payload = SecurityUtils.verify_token(token, "access")
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        
        # Check that expiry exists and is in the future
        exp_timestamp = payload["exp"]
        current_timestamp = datetime.utcnow().timestamp()
        
        assert exp_timestamp > current_timestamp
    
    def test_verify_token_wrong_type(self):
        """Test token verification with wrong token type."""
        user_id = "test-user-123"
        
        # Create access token
        access_token = SecurityUtils.create_access_token(user_id)
        
        # Try to verify as refresh token
        payload = SecurityUtils.verify_token(access_token, "refresh")
        
        assert payload is None
    
    def test_verify_invalid_token(self):
        """Test verification of invalid tokens."""
        # Test with invalid token
        assert SecurityUtils.verify_token("invalid-token") is None
        
        # Test with empty token
        assert SecurityUtils.verify_token("") is None
        
        # Test with malformed token
        assert SecurityUtils.verify_token("not.a.jwt") is None
    
    @patch('app.core.security.jwt.decode')
    def test_verify_expired_token(self, mock_decode):
        """Test verification of expired token."""
        from jwt import ExpiredSignatureError
        
        # Mock expired token
        mock_decode.side_effect = ExpiredSignatureError()
        
        result = SecurityUtils.verify_token("expired-token")
        assert result is None
    
    def test_get_subject_from_token(self):
        """Test extracting subject from token."""
        user_id = "test-user-123"
        
        # Create token
        token = SecurityUtils.create_access_token(user_id)
        
        # Extract subject
        extracted_id = SecurityUtils.get_subject_from_token(token)
        
        assert extracted_id == user_id
    
    def test_get_subject_from_invalid_token(self):
        """Test extracting subject from invalid token."""
        result = SecurityUtils.get_subject_from_token("invalid-token")
        assert result is None
    
    def test_create_token_pair(self):
        """Test creating access and refresh token pair."""
        user_id = "test-user-123"
        
        # Create token pair
        tokens = SecurityUtils.create_token_pair(user_id)
        
        # Verify structure
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
        
        # Verify tokens are valid
        access_payload = SecurityUtils.verify_token(tokens["access_token"], "access")
        refresh_payload = SecurityUtils.verify_token(tokens["refresh_token"], "refresh")
        
        assert access_payload is not None
        assert refresh_payload is not None
        assert access_payload["sub"] == user_id
        assert refresh_payload["sub"] == user_id
    
    def test_password_hashing_empty_password(self):
        """Test password hashing with empty password."""
        # Should handle empty password gracefully
        hashed = SecurityUtils.get_password_hash("")
        assert hashed != ""
        assert SecurityUtils.verify_password("", hashed)
    
    def test_password_verification_edge_cases(self):
        """Test password verification edge cases."""
        password = "TestPassword123"
        hashed = SecurityUtils.get_password_hash(password)
        
        # Test case sensitivity
        assert not SecurityUtils.verify_password("testpassword123", hashed)
        assert not SecurityUtils.verify_password("TESTPASSWORD123", hashed)
        
        # Test with None values (should not crash)
        assert not SecurityUtils.verify_password(None, hashed)
        assert not SecurityUtils.verify_password(password, None)
        assert not SecurityUtils.verify_password(None, None)


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_create_access_token_function(self):
        """Test standalone create_access_token function."""
        from app.core.security import create_access_token
        
        user_id = "test-user-123"
        token = create_access_token(user_id)
        
        # Verify token using SecurityUtils
        payload = SecurityUtils.verify_token(token, "access")
        assert payload is not None
        assert payload["sub"] == user_id
    
    def test_verify_password_function(self):
        """Test standalone verify_password function."""
        from app.core.security import verify_password, get_password_hash
        
        password = "TestPassword123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)
    
    def test_get_password_hash_function(self):
        """Test standalone get_password_hash function."""
        from app.core.security import get_password_hash
        
        password = "TestPassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0