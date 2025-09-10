"""
Unit tests for encryption utilities.
"""

from unittest.mock import patch

import pytest

from app.utils.encryption import EncryptedType, FieldEncryption, field_encryption


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

    @patch(
        "app.core.config.settings.ENCRYPTION_KEY",
        "dGVzdF9lbmNyeXB0aW9uX2tleV8xMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=",
    )
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


class TestEncryptionSecurity:
    """Test cases for encryption security features."""

    def test_encryption_key_rotation(self):
        """Test that different keys produce different encrypted values."""
        original_value = "sensitive_data"

        # Create two encryption instances with different keys
        encryption1 = FieldEncryption()

        # Mock different encryption key
        with patch("app.core.config.settings.SECRET_KEY", "different_secret_key"):
            encryption2 = FieldEncryption()

        # Encrypt with both instances
        encrypted1 = encryption1.encrypt(original_value)
        encrypted2 = encryption2.encrypt(original_value)

        # Encrypted values should be different
        assert encrypted1 != encrypted2

        # Each should decrypt correctly with its own instance
        assert encryption1.decrypt(encrypted1) == original_value
        assert encryption2.decrypt(encrypted2) == original_value

        # Cross-decryption should fail gracefully
        assert (
            encryption1.decrypt(encrypted2) == encrypted2
        )  # Returns original if decryption fails
        assert encryption2.decrypt(encrypted1) == encrypted1

    def test_encryption_with_special_characters(self):
        """Test encryption of data with special characters."""
        special_values = [
            "password123!@#",
            "user@domain.com",
            "+1-555-123-4567",
            "P123456789",  # Passport format
            "123-45-6789",  # SSN format
            "4111-1111-1111-1111",  # Credit card format
        ]

        encryption = FieldEncryption()

        for value in special_values:
            encrypted = encryption.encrypt(value)
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == value, f"Failed for value: {value}"

    def test_encryption_performance(self):
        """Test encryption performance with large data."""
        import time

        # Test with various data sizes
        test_data = [
            "small",
            "medium" * 100,
            "large" * 1000,
        ]

        encryption = FieldEncryption()

        for data in test_data:
            start_time = time.time()
            encrypted = encryption.encrypt(data)
            encrypt_time = time.time() - start_time

            start_time = time.time()
            decrypted = encryption.decrypt(encrypted)
            decrypt_time = time.time() - start_time

            # Verify correctness
            assert decrypted == data

            # Performance should be reasonable (less than 1 second for these sizes)
            assert encrypt_time < 1.0, f"Encryption too slow: {encrypt_time}s"
            assert decrypt_time < 1.0, f"Decryption too slow: {decrypt_time}s"

    def test_encryption_with_none_and_empty_edge_cases(self):
        """Test encryption edge cases."""
        encryption = FieldEncryption()

        # Test various edge cases
        edge_cases = [
            None,
            "",
            " ",
            "\n",
            "\t",
            "0",
            "false",
            "null",
        ]

        for case in edge_cases:
            encrypted = encryption.encrypt(case)
            decrypted = encryption.decrypt(encrypted)
            assert decrypted == case, f"Failed for edge case: {repr(case)}"
