"""
Custom exception classes for the KYC/AML microservice.
"""
from typing import Any, Dict, Optional


class KYCBaseException(Exception):
    """Base exception for KYC/AML service."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(KYCBaseException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, **kwargs):
        details = {"field": field} if field else {}
        details.update(kwargs)
        super().__init__(message, "VALIDATION_ERROR", details)


class AuthenticationError(KYCBaseException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, "AUTHENTICATION_ERROR", kwargs)


class AuthorizationError(KYCBaseException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, "AUTHORIZATION_ERROR", kwargs)


class BusinessLogicError(KYCBaseException):
    """Raised when business logic rules are violated."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, "BUSINESS_LOGIC_ERROR", kwargs)


class KYCCheckNotFoundError(KYCBaseException):
    """Raised when KYC check is not found."""
    
    def __init__(self, check_id: str, **kwargs):
        message = f"KYC check not found: {check_id}"
        details = {"check_id": check_id}
        details.update(kwargs)
        super().__init__(message, "KYC_CHECK_NOT_FOUND", details)


class InvalidKYCStatusTransitionError(KYCBaseException):
    """Raised when invalid KYC status transition is attempted."""
    
    def __init__(self, current_status: str, new_status: str, **kwargs):
        message = f"Invalid status transition from {current_status} to {new_status}"
        details = {"current_status": current_status, "new_status": new_status}
        details.update(kwargs)
        super().__init__(message, "INVALID_STATUS_TRANSITION", details)


class WebhookVerificationError(KYCBaseException):
    """Raised when webhook signature verification fails."""
    
    def __init__(self, message: str = "Webhook signature verification failed", **kwargs):
        super().__init__(message, "WEBHOOK_VERIFICATION_ERROR", kwargs)


class ProviderError(KYCBaseException):
    """Raised when external provider returns an error."""
    
    def __init__(self, provider: str, message: str, **kwargs):
        details = {"provider": provider}
        details.update(kwargs)
        super().__init__(message, "PROVIDER_ERROR", details)


class EncryptionError(KYCBaseException):
    """Raised when encryption/decryption operations fail."""
    
    def __init__(self, message: str = "Encryption operation failed", **kwargs):
        super().__init__(message, "ENCRYPTION_ERROR", kwargs)