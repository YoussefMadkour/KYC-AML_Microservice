"""
Unit tests for encryption utilities.
"""
import pytest
from unittest.mock import patch

from app.utils.encryption import FieldEncryption, field_encryption, EncryptedType


class TestFieldEncryption:
    """Test cases for FieldEncryption class."""
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        encryption = FieldEncryption()
        original_value = "sensitive_data_123"
        
        # Encrypt the value
        encrypted_value = encryption.encrypt(original_value)
        
        # Verify it's actually encrypted (different from original)
        assert encrypted_value != original_value
        assert len(encrypted_value) > len(original_value)
        
        # Decrypt and verify we get the original back
        decrypted_value = encryption.decrypt(encrypted_value)
        assert decrypted_value == original_value
    
    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        encryption = FieldEncryption()
        
        encrypted = encryption.encrypt("")
        assert encrypted == ""
        
        decrypted = encryption.decrypt("")
        assert decrypted == ""
    
    def test_encrypt_none_value(self):
        """Test encryption of None value."""
        encryption = FieldEncryption()
        
        encrypted = encryption.encrypt(None)
        assert encrypted is None
        
        decrypted = encryption.decrypt(None)
        assert decrypted is None
    
    def test_decrypt_invalid_data(self):
        """Test decryption of invalid encrypted data."""
        encryption = FieldEncryption()
        
        # Should return original value if decryption fails
        invalid_encrypted = "invalid_encrypted_data"
        result = encryption.decrypt(invalid_encrypted)
        assert result == invalid_encrypted
    
    def test_encrypt_unicode_characters(self):
        """Test encryption of unicode characters."""
        encryption = FieldEncryption()
        original_value = "测试数据 🔒 émojis"
        
        encrypted_value = encryption.encrypt(original_value)
        decrypted_value = encryption.decrypt(encrypted_value)
        
        assert decrypted_value == original_value
    
    def test_encrypt_long_string(self):
        """Test encryption of long strings."""
        encryption = FieldEncryption()
        original_value = "a" * 1000  # 1000 character string
        
        encrypted_value = encryption.encrypt(original_value)
        decrypted_value = encryption.decrypt(encrypted_value)
        
        assert decrypted_value == original_value
    
    def test_generate_key(self):
        """Test key generation."""
        key = FieldEncryption.generate_key()
        
        assert isinstance(key, str)
        assert len(key) > 0
        
        # Generated keys should be different
        key2 = FieldEncryption.generate_key()
        assert key != key2
    
    @patch('app.core.config.settings.ENCRYPTION_KEY', 'dGVzdF9lbmNyeXB0aW9uX2tleV8xMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=')
    def test_encryption_with_provided_key(self):
        """Test encryption with a provided key."""
        encryption = FieldEncryption()
        original_value = "test_with_provided_key"
        
        encrypted_value = encryption.encrypt(original_value)
        decrypted_value = encryption.decrypt(encrypted_value)
        
        assert decrypted_value == original_value


class TestEncryptedType:
    """Test cases for EncryptedType SQLAlchemy type."""
    
    def test_process_bind_param(self):
        """Test processing values for database storage."""
        encrypted_type = EncryptedType()
        
        # Test with string value
        result = encrypted_type.process_bind_param("test_value", None)
        assert result is not None
        assert result != "test_value"  # Should be encrypted
        
        # Test with None value
        result = encrypted_type.process_bind_param(None, None)
        assert result is None
    
    def test_process_result_value(self):
        """Test processing values from database."""
        encrypted_type = EncryptedType()
        
        # First encrypt a value
        original = "test_value"
        encrypted = field_encryption.encrypt(original)
        
        # Then test decryption through the type
        result = encrypted_type.process_result_value(encrypted, None)
        assert result == original
        
        # Test with None value
        result = encrypted_type.process_result_value(None, None)
        assert result is None
    
    def test_roundtrip_through_type(self):
        """Test full roundtrip through the SQLAlchemy type."""
        encrypted_type = EncryptedType()
        original_value = "roundtrip_test_value"
        
        # Simulate storing to database
        bound_value = encrypted_type.process_bind_param(original_value, None)
        
        # Simulate loading from database
        result_value = encrypted_type.process_result_value(bound_value, None)
        
        assert result_value == original_value


class TestGlobalEncryptionInstance:
    """Test cases for the global encryption instance."""
    
    def test_global_instance_consistency(self):
        """Test that the global instance works consistently."""
        original_value = "global_instance_test"
        
        encrypted1 = field_encryption.encrypt(original_value)
        encrypted2 = field_encryption.encrypt(original_value)
        
        # Encrypted values should be different (due to Fernet's random IV)
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same original value
        decrypted1 = field_encryption.decrypt(encrypted1)
        decrypted2 = field_encryption.decrypt(encrypted2)
        
        assert decrypted1 == original_value
        assert decrypted2 == original_value