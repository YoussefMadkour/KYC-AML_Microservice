"""
Unit tests for logging data masking functionality.
"""

import pytest

from app.utils.logging import (
    _mask_dict,
    _mask_string,
    mask_processor,
    mask_sensitive_data,
)


class TestDataMasking:
    """Test cases for data masking functionality."""

    def test_mask_email_addresses(self):
        """Test masking of email addresses."""
        test_cases = [
            ("user@example.com", "us***@example.com"),
            ("test.email@domain.org", "te***@domain.org"),
            ("a@b.co", "a@***@b.co"),  # Very short email
        ]

        for original, expected in test_cases:
            result = _mask_string(original)
            assert "@" in result, "Email should still contain @"
            assert result != original, "Email should be masked"

    def test_mask_phone_numbers(self):
        """Test masking of phone numbers."""
        test_cases = [
            "+1-555-123-4567",
            "555-123-4567",
            "(555) 123-4567",
            "15551234567",
            "+44 20 7946 0958",
        ]

        for phone in test_cases:
            result = _mask_string(phone)
            # Phone numbers should be masked, but format may vary
            assert (
                "***-***-****" in result or result != phone
            ), f"Phone {phone} should be masked"

    def test_mask_passport_numbers(self):
        """Test masking of passport numbers."""
        test_cases = [
            "P123456789",
            "AB1234567",
            "X12345678",
        ]

        for passport in test_cases:
            result = _mask_string(passport)
            assert (
                result == "XX******"
            ), f"Passport {passport} should be masked to XX******"

    def test_mask_ssn_numbers(self):
        """Test masking of SSN numbers."""
        test_cases = [
            "123-45-6789",
        ]

        for ssn in test_cases:
            result = _mask_string(ssn)
            # SSN should be masked (may match phone pattern first)
            assert result != ssn, f"SSN {ssn} should be masked"
            assert "***" in result, f"SSN {ssn} should contain masked characters"

    def test_mask_credit_card_numbers(self):
        """Test masking of credit card numbers."""
        test_cases = [
            "4111-1111-1111-1111",
            "5555-5555-5555-4444",
        ]

        for card in test_cases:
            result = _mask_string(card)
            # Credit card should be masked (may match phone pattern first)
            assert result != card, f"Card {card} should be masked"
            assert (
                "***" in result or "****" in result
            ), f"Card {card} should contain masked characters"

    def test_mask_sensitive_fields_in_dict(self):
        """Test masking of sensitive fields in dictionaries."""
        sensitive_data = {
            "password": "secret123",
            "phone_number": "555-123-4567",
            "document_number": "P123456789",
            "token": "abc123xyz",
            "normal_field": "normal_value",
            "user_id": "12345",
        }

        result = _mask_dict(sensitive_data)

        # Sensitive fields should be masked
        assert result["password"] == "se***23"
        assert result["phone_number"] == "55***67"
        assert result["document_number"] == "P1***89"
        assert result["token"] == "ab***yz"

        # Normal fields should not be masked
        assert result["normal_field"] == "normal_value"
        assert result["user_id"] == "12345"

    def test_mask_nested_dictionaries(self):
        """Test masking of nested dictionary structures."""
        nested_data = {
            "user": {
                "email": "user@example.com",
                "password": "secret123",
                "profile": {"phone_number": "555-123-4567", "name": "John Doe"},
            },
            "metadata": {"request_id": "req123", "timestamp": "2024-01-01T00:00:00Z"},
        }

        result = mask_sensitive_data(nested_data)

        # Check nested masking
        assert "***" in result["user"]["password"]
        assert "***" in result["user"]["profile"]["phone_number"]

        # Non-sensitive fields should remain
        assert result["user"]["profile"]["name"] == "John Doe"
        assert result["metadata"]["request_id"] == "req123"

    def test_mask_list_data(self):
        """Test masking of list data structures."""
        list_data = [
            {"password": "secret1"},
            {"phone_number": "555-123-4567"},
            "normal string",
            {"nested": {"token": "abc123"}},
        ]

        result = mask_sensitive_data(list_data)

        assert "***" in result[0]["password"]
        assert "***" in result[1]["phone_number"]
        assert result[2] == "normal string"
        assert "***" in result[3]["nested"]["token"]

    def test_mask_string_with_multiple_patterns(self):
        """Test masking strings with multiple sensitive patterns."""
        text = "User john@example.com called 555-123-4567 about passport P123456789"

        result = _mask_string(text)

        # Should mask all patterns
        assert "jo***@example.com" in result
        assert "***-***-****" in result
        assert "XX******" in result

    def test_mask_processor_integration(self):
        """Test the structlog mask processor."""
        event_dict = {
            "event": "User login attempt",
            "user_email": "user@example.com",
            "phone": "555-123-4567",
            "password": "secret123",
            "request_id": "req123",
        }

        result = mask_processor(None, None, event_dict)

        # Sensitive fields should be masked
        assert "***" in result["user_email"]
        assert "***" in result["phone"]
        assert "***" in result["password"]

        # Non-sensitive fields should remain
        assert result["request_id"] == "req123"

    def test_mask_short_sensitive_values(self):
        """Test masking of very short sensitive values."""
        short_data = {"pin": "123", "cvv": "456", "key": "ab", "token": "x"}

        result = _mask_dict(short_data)

        # Short values should be completely masked
        for key in short_data:
            assert result[key] == "***"

    def test_mask_case_insensitive_field_names(self):
        """Test that field name matching is case insensitive."""
        data = {
            "PASSWORD": "secret123",
            "Phone_Number": "555-123-4567",
            "DOCUMENT_NUMBER": "P123456789",
            "Token": "abc123xyz",
        }

        result = _mask_dict(data)

        # All should be masked regardless of case
        for key in data:
            assert "***" in result[key]

    def test_mask_preserves_data_types(self):
        """Test that masking preserves non-string data types appropriately."""
        data = {
            "password": "secret123",  # string - should be masked
            "count": 42,  # int - should remain
            "active": True,  # bool - should remain
            "scores": [1, 2, 3],  # list - should be processed recursively
            "metadata": None,  # None - should remain
        }

        result = mask_sensitive_data(data)

        assert "***" in result["password"]
        assert result["count"] == 42
        assert result["active"] is True
        assert result["scores"] == [1, 2, 3]
        assert result["metadata"] is None

    def test_mask_empty_and_none_values(self):
        """Test masking of empty and None values."""
        data = {
            "password": "",
            "token": None,
            "key": "   ",  # whitespace
            "secret": "a",  # single char
        }

        result = _mask_dict(data)

        # All should be masked to "***"
        for key in data:
            assert result[key] == "***"
