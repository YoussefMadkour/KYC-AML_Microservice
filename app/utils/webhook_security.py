"""
Webhook signature verification utilities for secure webhook processing.
"""

import hashlib
import hmac
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple, Union

from app.core.config import settings


class WebhookProvider(str, Enum):
    """Supported webhook providers with their signature schemes."""

    MOCK_PROVIDER_1 = "mock_provider_1"
    MOCK_PROVIDER_2 = "mock_provider_2"
    JUMIO = "jumio"
    ONFIDO = "onfido"
    VERIFF = "veriff"


class SignatureScheme(str, Enum):
    """Webhook signature schemes."""

    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA1 = "hmac_sha1"
    HMAC_SHA512 = "hmac_sha512"


class WebhookSecurityError(Exception):
    """Base exception for webhook security errors."""

    pass


class InvalidSignatureError(WebhookSecurityError):
    """Raised when webhook signature verification fails."""

    pass


class TimestampValidationError(WebhookSecurityError):
    """Raised when webhook timestamp validation fails."""

    pass


class WebhookSignatureVerifier:
    """Handles webhook signature generation and verification."""

    # Provider-specific signature schemes and configurations
    PROVIDER_CONFIGS = {
        WebhookProvider.MOCK_PROVIDER_1: {
            "scheme": SignatureScheme.HMAC_SHA256,
            "header_name": "X-Webhook-Signature",
            "signature_prefix": "sha256=",
            "timestamp_header": "X-Webhook-Timestamp",
            "timestamp_tolerance": 300,  # 5 minutes
        },
        WebhookProvider.MOCK_PROVIDER_2: {
            "scheme": SignatureScheme.HMAC_SHA512,
            "header_name": "X-Provider-Signature",
            "signature_prefix": "sha512=",
            "timestamp_header": "X-Provider-Timestamp",
            "timestamp_tolerance": 600,  # 10 minutes
        },
        WebhookProvider.JUMIO: {
            "scheme": SignatureScheme.HMAC_SHA256,
            "header_name": "X-Jumio-Signature",
            "signature_prefix": "sha256=",
            "timestamp_header": "X-Jumio-Timestamp",
            "timestamp_tolerance": 300,  # 5 minutes
        },
        WebhookProvider.ONFIDO: {
            "scheme": SignatureScheme.HMAC_SHA1,
            "header_name": "X-SHA1-Signature",
            "signature_prefix": "sha1=",
            "timestamp_header": "X-Onfido-Timestamp",
            "timestamp_tolerance": 300,  # 5 minutes
        },
        WebhookProvider.VERIFF: {
            "scheme": SignatureScheme.HMAC_SHA256,
            "header_name": "X-Veriff-Signature",
            "signature_prefix": "hmac-sha256=",
            "timestamp_header": "X-Veriff-Timestamp",
            "timestamp_tolerance": 300,  # 5 minutes
        },
    }

    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize webhook signature verifier.

        Args:
            webhook_secret: Secret key for signature generation/verification.
                          If None, uses settings.WEBHOOK_SECRET
        """
        self.webhook_secret = webhook_secret or settings.WEBHOOK_SECRET

    def generate_signature(
        self,
        payload: Union[str, bytes],
        provider: WebhookProvider,
        timestamp: Optional[int] = None,
        secret: Optional[str] = None,
    ) -> str:
        """
        Generate webhook signature for a given payload and provider.

        Args:
            payload: The webhook payload (string or bytes)
            provider: The webhook provider
            timestamp: Unix timestamp (if None, uses current time)
            secret: Provider-specific secret (if None, uses default)

        Returns:
            Generated signature string with appropriate prefix

        Raises:
            WebhookSecurityError: If provider is not supported
        """
        if provider not in self.PROVIDER_CONFIGS:
            raise WebhookSecurityError(f"Unsupported provider: {provider}")

        config = self.PROVIDER_CONFIGS[provider]
        scheme = config["scheme"]
        prefix = config["signature_prefix"]

        # Convert payload to bytes if needed
        if isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        else:
            payload_bytes = payload

        # Add timestamp to payload for some providers
        if timestamp is not None:
            message = f"{timestamp}.{payload_bytes.decode('utf-8')}"
            payload_bytes = message.encode("utf-8")

        # Use provider-specific secret or default
        signing_secret = secret or self.webhook_secret

        # Generate signature based on scheme
        if scheme == SignatureScheme.HMAC_SHA256:
            signature = hmac.new(
                signing_secret.encode("utf-8"), payload_bytes, hashlib.sha256
            ).hexdigest()
        elif scheme == SignatureScheme.HMAC_SHA1:
            signature = hmac.new(
                signing_secret.encode("utf-8"), payload_bytes, hashlib.sha1
            ).hexdigest()
        elif scheme == SignatureScheme.HMAC_SHA512:
            signature = hmac.new(
                signing_secret.encode("utf-8"), payload_bytes, hashlib.sha512
            ).hexdigest()
        else:
            raise WebhookSecurityError(f"Unsupported signature scheme: {scheme}")

        return f"{prefix}{signature}"

    def verify_signature(
        self,
        payload: Union[str, bytes],
        signature: str,
        provider: WebhookProvider,
        timestamp: Optional[int] = None,
        secret: Optional[str] = None,
    ) -> bool:
        """
        Verify webhook signature for a given payload and provider.

        Args:
            payload: The webhook payload (string or bytes)
            signature: The signature to verify
            provider: The webhook provider
            timestamp: Unix timestamp for timestamp-based signatures
            secret: Provider-specific secret (if None, uses default)

        Returns:
            True if signature is valid, False otherwise

        Raises:
            WebhookSecurityError: If provider is not supported
        """
        try:
            expected_signature = self.generate_signature(
                payload, provider, timestamp, secret
            )

            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)

        except Exception:
            return False

    def validate_timestamp(
        self,
        timestamp: Union[int, str],
        provider: WebhookProvider,
        tolerance: Optional[int] = None,
    ) -> bool:
        """
        Validate webhook timestamp to prevent replay attacks.

        Args:
            timestamp: Unix timestamp (int or string)
            provider: The webhook provider
            tolerance: Custom tolerance in seconds (if None, uses provider default)

        Returns:
            True if timestamp is valid, False otherwise

        Raises:
            TimestampValidationError: If timestamp validation fails
        """
        if provider not in self.PROVIDER_CONFIGS:
            raise TimestampValidationError(f"Unsupported provider: {provider}")

        try:
            # Convert timestamp to int if needed
            if isinstance(timestamp, str):
                timestamp_int = int(timestamp)
            else:
                timestamp_int = timestamp

            # Get current time
            current_time = int(time.time())

            # Get tolerance from provider config or use custom
            config = self.PROVIDER_CONFIGS[provider]
            tolerance_seconds = tolerance or config["timestamp_tolerance"]

            # Check if timestamp is within tolerance
            time_diff = abs(current_time - timestamp_int)

            if time_diff > tolerance_seconds:
                raise TimestampValidationError(
                    f"Timestamp {timestamp_int} is outside tolerance window "
                    f"({tolerance_seconds} seconds). Current time: {current_time}, "
                    f"difference: {time_diff} seconds"
                )

            return True

        except ValueError as e:
            raise TimestampValidationError(
                f"Invalid timestamp format: {timestamp}"
            ) from e

    def extract_signature_from_header(
        self, headers: Dict[str, str], provider: WebhookProvider
    ) -> Optional[str]:
        """
        Extract signature from HTTP headers based on provider configuration.

        Args:
            headers: HTTP headers dictionary
            provider: The webhook provider

        Returns:
            Extracted signature string or None if not found

        Raises:
            WebhookSecurityError: If provider is not supported
        """
        if provider not in self.PROVIDER_CONFIGS:
            raise WebhookSecurityError(f"Unsupported provider: {provider}")

        config = self.PROVIDER_CONFIGS[provider]
        header_name = config["header_name"]

        # Look for signature header (case-insensitive)
        for key, value in headers.items():
            if key.lower() == header_name.lower():
                return value

        return None

    def extract_timestamp_from_header(
        self, headers: Dict[str, str], provider: WebhookProvider
    ) -> Optional[int]:
        """
        Extract timestamp from HTTP headers based on provider configuration.

        Args:
            headers: HTTP headers dictionary
            provider: The webhook provider

        Returns:
            Extracted timestamp as integer or None if not found

        Raises:
            WebhookSecurityError: If provider is not supported
        """
        if provider not in self.PROVIDER_CONFIGS:
            raise WebhookSecurityError(f"Unsupported provider: {provider}")

        config = self.PROVIDER_CONFIGS[provider]
        timestamp_header = config["timestamp_header"]

        # Look for timestamp header (case-insensitive)
        for key, value in headers.items():
            if key.lower() == timestamp_header.lower():
                try:
                    return int(value)
                except ValueError:
                    return None

        return None

    def verify_webhook_request(
        self,
        payload: Union[str, bytes],
        headers: Dict[str, str],
        provider: WebhookProvider,
        secret: Optional[str] = None,
        validate_timestamp: bool = True,
    ) -> Tuple[bool, Dict[str, Union[str, bool]]]:
        """
        Comprehensive webhook request verification.

        Args:
            payload: The webhook payload
            headers: HTTP headers dictionary
            provider: The webhook provider
            secret: Provider-specific secret (if None, uses default)
            validate_timestamp: Whether to validate timestamp

        Returns:
            Tuple of (is_valid, verification_details)

        Raises:
            WebhookSecurityError: If provider is not supported
        """
        verification_details = {
            "signature_valid": False,
            "timestamp_valid": False,
            "signature_found": False,
            "timestamp_found": False,
            "error_message": None,
        }

        try:
            # Extract signature from headers
            signature = self.extract_signature_from_header(headers, provider)
            if not signature:
                verification_details["error_message"] = "Signature header not found"
                return False, verification_details

            verification_details["signature_found"] = True

            # Extract timestamp if validation is enabled
            timestamp = None
            if validate_timestamp:
                timestamp = self.extract_timestamp_from_header(headers, provider)
                if timestamp is not None:
                    verification_details["timestamp_found"] = True

                    # Validate timestamp
                    try:
                        self.validate_timestamp(timestamp, provider)
                        verification_details["timestamp_valid"] = True
                    except TimestampValidationError as e:
                        verification_details["error_message"] = str(e)
                        return False, verification_details
                else:
                    verification_details["timestamp_valid"] = (
                        True  # No timestamp required
                    )
            else:
                verification_details["timestamp_valid"] = (
                    True  # Timestamp validation disabled
                )

            # Verify signature
            signature_valid = self.verify_signature(
                payload, signature, provider, timestamp, secret
            )
            verification_details["signature_valid"] = signature_valid

            if not signature_valid:
                verification_details["error_message"] = "Invalid signature"
                return False, verification_details

            return True, verification_details

        except Exception as e:
            verification_details["error_message"] = f"Verification error: {str(e)}"
            return False, verification_details


# Global signature verifier instance
webhook_signature_verifier = WebhookSignatureVerifier()


# Convenience functions
def generate_webhook_signature(
    payload: Union[str, bytes],
    provider: WebhookProvider,
    timestamp: Optional[int] = None,
    secret: Optional[str] = None,
) -> str:
    """Generate webhook signature using the global verifier."""
    return webhook_signature_verifier.generate_signature(
        payload, provider, timestamp, secret
    )


def verify_webhook_signature(
    payload: Union[str, bytes],
    signature: str,
    provider: WebhookProvider,
    timestamp: Optional[int] = None,
    secret: Optional[str] = None,
) -> bool:
    """Verify webhook signature using the global verifier."""
    return webhook_signature_verifier.verify_signature(
        payload, signature, provider, timestamp, secret
    )


def validate_webhook_timestamp(
    timestamp: Union[int, str],
    provider: WebhookProvider,
    tolerance: Optional[int] = None,
) -> bool:
    """Validate webhook timestamp using the global verifier."""
    return webhook_signature_verifier.validate_timestamp(timestamp, provider, tolerance)


def verify_webhook_request(
    payload: Union[str, bytes],
    headers: Dict[str, str],
    provider: WebhookProvider,
    secret: Optional[str] = None,
    validate_timestamp: bool = True,
) -> Tuple[bool, Dict[str, Union[str, bool]]]:
    """Verify complete webhook request using the global verifier."""
    return webhook_signature_verifier.verify_webhook_request(
        payload, headers, provider, secret, validate_timestamp
    )
