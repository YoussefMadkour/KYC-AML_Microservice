"""
Field-level encryption utilities for sensitive data.
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import String, TypeDecorator

from app.core.config import settings


class FieldEncryption:
    """Handles field-level encryption for sensitive data."""

    def __init__(self):
        """Initialize encryption with key from settings."""
        self._fernet = self._get_fernet()

    def _get_fernet(self) -> Fernet:
        """Get or create Fernet encryption instance."""
        if settings.ENCRYPTION_KEY:
            # Use provided key (should be base64 encoded)
            try:
                key = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY.encode())
                return Fernet(base64.urlsafe_b64encode(key[:32]))
            except Exception:
                # If key is invalid, generate from secret
                pass

        # Generate key from SECRET_KEY
        password = settings.SECRET_KEY.encode()
        salt = b"kyc_salt_2024"  # In production, use random salt per installation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)

    def encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        if not value:
            return value

        encrypted_bytes = self._fernet.encrypt(value.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value."""
        if not encrypted_value:
            return encrypted_value

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode("utf-8"))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode("utf-8")
        except Exception:
            # If decryption fails, return original value (for backward compatibility)
            return encrypted_value

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new encryption key (base64 encoded)."""
        key = Fernet.generate_key()
        return base64.urlsafe_b64encode(key).decode("utf-8")


# Global encryption instance
field_encryption = FieldEncryption()


def encrypt_field(value: str) -> str:
    """Encrypt a field value using the global encryption instance."""
    return field_encryption.encrypt(value)


def decrypt_field(encrypted_value: str) -> str:
    """Decrypt a field value using the global encryption instance."""
    return field_encryption.decrypt(encrypted_value)


class EncryptedType(TypeDecorator):
    """SQLAlchemy custom type for encrypted fields."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt value before storing in database."""
        if value is not None:
            return field_encryption.encrypt(str(value))
        return value

    def process_result_value(self, value, dialect):
        """Decrypt value when loading from database."""
        if value is not None:
            return field_encryption.decrypt(value)
        return value


def encrypted_column(*args, **kwargs):
    """Create an encrypted column."""
    from sqlalchemy import Column

    # Remove our custom arguments
    encrypt = kwargs.pop("encrypt", True)

    if encrypt:
        # Use our custom encrypted type
        return Column(EncryptedType(255), *args, **kwargs)
    else:
        return Column(*args, **kwargs)
