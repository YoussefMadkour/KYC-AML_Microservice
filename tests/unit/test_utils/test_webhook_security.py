"""
Unit tests for webhook security utilities.
"""
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.utils.webhook_security import (
    WebhookProvider,
    SignatureScheme,
    WebhookSecurityError,
    InvalidSignatureError,
    TimestampValidationError,
    WebhookSignatureVerifier,
    generate_webhook_signature,
    verify_webhook_signature,
    validate_webhook_timestamp,
    verify_webhook_request
)


class TestWebhookSignatureVerifier:
    """Test cases for WebhookSignatureVerifier class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.verifier = WebhookSignatureVerifier(webhook_secret="test-secret-key")
        self.test_payload = '{"status": "approved", "kyc_id": "kyc_123"}'
        self.test_payload_bytes = self.test_payload.encode('utf-8')
    
    def test_init_with_custom_secret(self):
        """Test initializing verifier with custom secret."""
        custom_secret = "custom-secret"
        verifier = WebhookSignatureVerifier(webhook_secret=custom_secret)
        assert verifier.webhook_secret == custom_secret
    
    def test_init_with_default_secret(self):
        """Test initializing verifier with default secret from settings."""
        verifier = WebhookSignatureVerifier()
        # Should use settings.WEBHOOK_SECRET
        assert verifier.webhook_secret is not None
    
    def test_provider_configs_exist(self):
        """Test that all providers have configurations."""
        expected_providers = [
            WebhookProvider.MOCK_PROVIDER_1,
            WebhookProvider.MOCK_PROVIDER_2,
            WebhookProvider.JUMIO,
            WebhookProvider.ONFIDO,
            WebhookProvider.VERIFF
        ]
        
        for provider in expected_providers:
            assert provider in self.verifier.PROVIDER_CONFIGS
            config = self.verifier.PROVIDER_CONFIGS[provider]
            
            # Check required config fields
            assert "scheme" in config
            assert "header_name" in config
            assert "signature_prefix" in config
            assert "timestamp_header" in config
            assert "timestamp_tolerance" in config
    
    def test_generate_signature_mock_provider_1(self):
        """Test signature generation for mock provider 1 (SHA256)."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        signature = self.verifier.generate_signature(self.test_payload, provider)
        
        # Should have sha256= prefix
        assert signature.startswith("sha256=")
        
        # Verify signature manually
        expected_signature = hmac.new(
            self.verifier.webhook_secret.encode('utf-8'),
            self.test_payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        assert signature == f"sha256={expected_signature}"
    
    def test_generate_signature_mock_provider_2(self):
        """Test signature generation for mock provider 2 (SHA512)."""
        provider = WebhookProvider.MOCK_PROVIDER_2
        signature = self.verifier.generate_signature(self.test_payload, provider)
        
        # Should have sha512= prefix
        assert signature.startswith("sha512=")
        
        # Verify signature manually
        expected_signature = hmac.new(
            self.verifier.webhook_secret.encode('utf-8'),
            self.test_payload_bytes,
            hashlib.sha512
        ).hexdigest()
        
        assert signature == f"sha512={expected_signature}"
    
    def test_generate_signature_onfido(self):
        """Test signature generation for Onfido (SHA1)."""
        provider = WebhookProvider.ONFIDO
        signature = self.verifier.generate_signature(self.test_payload, provider)
        
        # Should have sha1= prefix
        assert signature.startswith("sha1=")
        
        # Verify signature manually
        expected_signature = hmac.new(
            self.verifier.webhook_secret.encode('utf-8'),
            self.test_payload_bytes,
            hashlib.sha1
        ).hexdigest()
        
        assert signature == f"sha1={expected_signature}"
    
    def test_generate_signature_with_timestamp(self):
        """Test signature generation with timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())
        
        signature = self.verifier.generate_signature(
            self.test_payload, provider, timestamp=timestamp
        )
        
        # Should include timestamp in the message
        message = f"{timestamp}.{self.test_payload}"
        expected_signature = hmac.new(
            self.verifier.webhook_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        assert signature == f"sha256={expected_signature}"
    
    def test_generate_signature_with_custom_secret(self):
        """Test signature generation with custom secret."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        custom_secret = "custom-provider-secret"
        
        signature = self.verifier.generate_signature(
            self.test_payload, provider, secret=custom_secret
        )
        
        # Verify with custom secret
        expected_signature = hmac.new(
            custom_secret.encode('utf-8'),
            self.test_payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        assert signature == f"sha256={expected_signature}"
    
    def test_generate_signature_bytes_payload(self):
        """Test signature generation with bytes payload."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        signature = self.verifier.generate_signature(self.test_payload_bytes, provider)
        
        # Should produce same result as string payload
        string_signature = self.verifier.generate_signature(self.test_payload, provider)
        assert signature == string_signature
    
    def test_generate_signature_unsupported_provider(self):
        """Test signature generation with unsupported provider."""
        with pytest.raises(WebhookSecurityError, match="Unsupported provider"):
            self.verifier.generate_signature(self.test_payload, "invalid_provider")
    
    def test_verify_signature_valid(self):
        """Test signature verification with valid signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        signature = self.verifier.generate_signature(self.test_payload, provider)
        
        is_valid = self.verifier.verify_signature(
            self.test_payload, signature, provider
        )
        
        assert is_valid is True
    
    def test_verify_signature_invalid(self):
        """Test signature verification with invalid signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        invalid_signature = "sha256=invalid_signature_hash"
        
        is_valid = self.verifier.verify_signature(
            self.test_payload, invalid_signature, provider
        )
        
        assert is_valid is False
    
    def test_verify_signature_with_timestamp(self):
        """Test signature verification with timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())
        
        signature = self.verifier.generate_signature(
            self.test_payload, provider, timestamp=timestamp
        )
        
        is_valid = self.verifier.verify_signature(
            self.test_payload, signature, provider, timestamp=timestamp
        )
        
        assert is_valid is True
    
    def test_verify_signature_wrong_timestamp(self):
        """Test signature verification with wrong timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())
        wrong_timestamp = timestamp + 100
        
        signature = self.verifier.generate_signature(
            self.test_payload, provider, timestamp=timestamp
        )
        
        is_valid = self.verifier.verify_signature(
            self.test_payload, signature, provider, timestamp=wrong_timestamp
        )
        
        assert is_valid is False
    
    def test_verify_signature_exception_handling(self):
        """Test signature verification handles exceptions gracefully."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        # Test with malformed signature
        is_valid = self.verifier.verify_signature(
            self.test_payload, "malformed", provider
        )
        
        assert is_valid is False
    
    def test_validate_timestamp_valid(self):
        """Test timestamp validation with valid timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        current_timestamp = int(time.time())
        
        is_valid = self.verifier.validate_timestamp(current_timestamp, provider)
        assert is_valid is True
    
    def test_validate_timestamp_string(self):
        """Test timestamp validation with string timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        current_timestamp = str(int(time.time()))
        
        is_valid = self.verifier.validate_timestamp(current_timestamp, provider)
        assert is_valid is True
    
    def test_validate_timestamp_too_old(self):
        """Test timestamp validation with timestamp too old."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        
        with pytest.raises(TimestampValidationError, match="outside tolerance window"):
            self.verifier.validate_timestamp(old_timestamp, provider)
    
    def test_validate_timestamp_too_new(self):
        """Test timestamp validation with timestamp too new."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        future_timestamp = int(time.time()) + 600  # 10 minutes in future
        
        with pytest.raises(TimestampValidationError, match="outside tolerance window"):
            self.verifier.validate_timestamp(future_timestamp, provider)
    
    def test_validate_timestamp_custom_tolerance(self):
        """Test timestamp validation with custom tolerance."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        
        # Should pass with custom tolerance of 15 minutes
        is_valid = self.verifier.validate_timestamp(
            old_timestamp, provider, tolerance=900
        )
        assert is_valid is True
    
    def test_validate_timestamp_invalid_format(self):
        """Test timestamp validation with invalid format."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        with pytest.raises(TimestampValidationError, match="Invalid timestamp format"):
            self.verifier.validate_timestamp("not_a_timestamp", provider)
    
    def test_validate_timestamp_unsupported_provider(self):
        """Test timestamp validation with unsupported provider."""
        with pytest.raises(TimestampValidationError, match="Unsupported provider"):
            self.verifier.validate_timestamp(int(time.time()), "invalid_provider")
    
    def test_extract_signature_from_header(self):
        """Test extracting signature from headers."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        test_signature = "sha256=test_signature"
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": test_signature,
            "User-Agent": "WebhookBot/1.0"
        }
        
        extracted = self.verifier.extract_signature_from_header(headers, provider)
        assert extracted == test_signature
    
    def test_extract_signature_case_insensitive(self):
        """Test extracting signature with case-insensitive header matching."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        test_signature = "sha256=test_signature"
        
        headers = {
            "content-type": "application/json",
            "x-webhook-signature": test_signature,  # lowercase
            "user-agent": "WebhookBot/1.0"
        }
        
        extracted = self.verifier.extract_signature_from_header(headers, provider)
        assert extracted == test_signature
    
    def test_extract_signature_not_found(self):
        """Test extracting signature when header is not present."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WebhookBot/1.0"
        }
        
        extracted = self.verifier.extract_signature_from_header(headers, provider)
        assert extracted is None
    
    def test_extract_signature_unsupported_provider(self):
        """Test extracting signature with unsupported provider."""
        headers = {"X-Webhook-Signature": "test"}
        
        with pytest.raises(WebhookSecurityError, match="Unsupported provider"):
            self.verifier.extract_signature_from_header(headers, "invalid_provider")
    
    def test_extract_timestamp_from_header(self):
        """Test extracting timestamp from headers."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        test_timestamp = int(time.time())
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": str(test_timestamp)
        }
        
        extracted = self.verifier.extract_timestamp_from_header(headers, provider)
        assert extracted == test_timestamp
    
    def test_extract_timestamp_invalid_format(self):
        """Test extracting timestamp with invalid format."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        headers = {
            "X-Webhook-Timestamp": "not_a_timestamp"
        }
        
        extracted = self.verifier.extract_timestamp_from_header(headers, provider)
        assert extracted is None
    
    def test_extract_timestamp_not_found(self):
        """Test extracting timestamp when header is not present."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        headers = {
            "Content-Type": "application/json"
        }
        
        extracted = self.verifier.extract_timestamp_from_header(headers, provider)
        assert extracted is None
    
    def test_verify_webhook_request_success(self):
        """Test complete webhook request verification success."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())
        
        # Generate valid signature
        signature = self.verifier.generate_signature(
            self.test_payload, provider, timestamp=timestamp
        )
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp)
        }
        
        is_valid, details = self.verifier.verify_webhook_request(
            self.test_payload, headers, provider
        )
        
        assert is_valid is True
        assert details["signature_valid"] is True
        assert details["timestamp_valid"] is True
        assert details["signature_found"] is True
        assert details["timestamp_found"] is True
        assert details["error_message"] is None
    
    def test_verify_webhook_request_no_signature(self):
        """Test webhook request verification with missing signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        headers = {
            "Content-Type": "application/json"
        }
        
        is_valid, details = self.verifier.verify_webhook_request(
            self.test_payload, headers, provider
        )
        
        assert is_valid is False
        assert details["signature_found"] is False
        assert details["error_message"] == "Signature header not found"
    
    def test_verify_webhook_request_invalid_signature(self):
        """Test webhook request verification with invalid signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": "sha256=invalid_signature"
        }
        
        is_valid, details = self.verifier.verify_webhook_request(
            self.test_payload, headers, provider
        )
        
        assert is_valid is False
        assert details["signature_valid"] is False
        assert details["error_message"] == "Invalid signature"
    
    def test_verify_webhook_request_invalid_timestamp(self):
        """Test webhook request verification with invalid timestamp."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        old_timestamp = int(time.time()) - 600  # 10 minutes ago
        
        # Generate signature with old timestamp
        signature = self.verifier.generate_signature(
            self.test_payload, provider, timestamp=old_timestamp
        )
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(old_timestamp)
        }
        
        is_valid, details = self.verifier.verify_webhook_request(
            self.test_payload, headers, provider
        )
        
        assert is_valid is False
        assert details["timestamp_valid"] is False
        assert "outside tolerance window" in details["error_message"]
    
    def test_verify_webhook_request_no_timestamp_validation(self):
        """Test webhook request verification without timestamp validation."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        
        # Generate signature without timestamp
        signature = self.verifier.generate_signature(self.test_payload, provider)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature
        }
        
        is_valid, details = self.verifier.verify_webhook_request(
            self.test_payload, headers, provider, validate_timestamp=False
        )
        
        assert is_valid is True
        assert details["signature_valid"] is True
        assert details["timestamp_valid"] is True  # Should be True when disabled
        assert details["timestamp_found"] is False


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_payload = '{"status": "approved", "kyc_id": "kyc_123"}'
        self.provider = WebhookProvider.MOCK_PROVIDER_1
    
    def test_generate_webhook_signature(self):
        """Test generate_webhook_signature convenience function."""
        signature = generate_webhook_signature(self.test_payload, self.provider)
        
        assert signature.startswith("sha256=")
        assert len(signature) > 10  # Should have actual hash
    
    def test_verify_webhook_signature(self):
        """Test verify_webhook_signature convenience function."""
        signature = generate_webhook_signature(self.test_payload, self.provider)
        
        is_valid = verify_webhook_signature(
            self.test_payload, signature, self.provider
        )
        
        assert is_valid is True
    
    def test_validate_webhook_timestamp(self):
        """Test validate_webhook_timestamp convenience function."""
        current_timestamp = int(time.time())
        
        is_valid = validate_webhook_timestamp(current_timestamp, self.provider)
        assert is_valid is True
    
    def test_verify_webhook_request(self):
        """Test verify_webhook_request convenience function."""
        signature = generate_webhook_signature(self.test_payload, self.provider)
        
        headers = {
            "X-Webhook-Signature": signature
        }
        
        is_valid, details = verify_webhook_request(
            self.test_payload, headers, self.provider, validate_timestamp=False
        )
        
        assert is_valid is True
        assert details["signature_valid"] is True


class TestWebhookProviderEnum:
    """Test cases for WebhookProvider enum."""
    
    def test_provider_values(self):
        """Test webhook provider enum values."""
        assert WebhookProvider.MOCK_PROVIDER_1 == "mock_provider_1"
        assert WebhookProvider.MOCK_PROVIDER_2 == "mock_provider_2"
        assert WebhookProvider.JUMIO == "jumio"
        assert WebhookProvider.ONFIDO == "onfido"
        assert WebhookProvider.VERIFF == "veriff"
    
    def test_provider_from_string(self):
        """Test creating provider from string."""
        provider = WebhookProvider("mock_provider_1")
        assert provider == WebhookProvider.MOCK_PROVIDER_1
    
    def test_invalid_provider(self):
        """Test creating provider from invalid string."""
        with pytest.raises(ValueError):
            WebhookProvider("invalid_provider")


class TestSignatureSchemeEnum:
    """Test cases for SignatureScheme enum."""
    
    def test_scheme_values(self):
        """Test signature scheme enum values."""
        assert SignatureScheme.HMAC_SHA256 == "hmac_sha256"
        assert SignatureScheme.HMAC_SHA1 == "hmac_sha1"
        assert SignatureScheme.HMAC_SHA512 == "hmac_sha512"


class TestExceptions:
    """Test cases for custom exceptions."""
    
    def test_webhook_security_error(self):
        """Test WebhookSecurityError exception."""
        with pytest.raises(WebhookSecurityError):
            raise WebhookSecurityError("Test error")
    
    def test_invalid_signature_error(self):
        """Test InvalidSignatureError exception."""
        with pytest.raises(InvalidSignatureError):
            raise InvalidSignatureError("Invalid signature")
        
        # Should be instance of WebhookSecurityError
        try:
            raise InvalidSignatureError("Invalid signature")
        except WebhookSecurityError:
            pass  # Should catch as parent class
    
    def test_timestamp_validation_error(self):
        """Test TimestampValidationError exception."""
        with pytest.raises(TimestampValidationError):
            raise TimestampValidationError("Invalid timestamp")
        
        # Should be instance of WebhookSecurityError
        try:
            raise TimestampValidationError("Invalid timestamp")
        except WebhookSecurityError:
            pass  # Should catch as parent class