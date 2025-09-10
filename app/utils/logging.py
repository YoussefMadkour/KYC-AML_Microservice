"""
Structured logging setup using structlog with data masking for sensitive information.
"""

import logging
import re
import sys
from typing import Any, Dict, Union

import structlog
from rich.console import Console
from rich.logging import RichHandler

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        mask_processor,  # Add data masking processor
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_FORMAT == "json":
        # JSON formatting for production
        processors.extend(
            [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
        )
    else:
        # Human-readable formatting for development
        processors.extend([structlog.dev.ConsoleRenderer(colors=True)])

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL)
        ),
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up rich handler for development
    if settings.ENVIRONMENT == "development" and settings.LOG_FORMAT == "text":
        console = Console()
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True,
        )

        # Replace the root logger handler
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(rich_handler)


# Sensitive data patterns for masking
SENSITIVE_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\+?[\d\s\-\(\)]{10,}"),
    "passport": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b"),
    "document_number": re.compile(r"\b[A-Z0-9]{6,20}\b"),
}

SENSITIVE_FIELDS = {
    "password",
    "token",
    "secret",
    "key",
    "phone_number",
    "document_number",
    "passport_number",
    "ssn",
    "social_security_number",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
}


def mask_sensitive_data(data: Union[str, Dict, Any]) -> Union[str, Dict, Any]:
    """Mask sensitive data in logs."""
    if isinstance(data, str):
        return _mask_string(data)
    elif isinstance(data, dict):
        return _mask_dict(data)
    elif isinstance(data, (list, tuple)):
        return [mask_sensitive_data(item) for item in data]
    else:
        return data


def _mask_string(text: str) -> str:
    """Mask sensitive patterns in a string."""
    masked_text = text

    # Mask email addresses
    masked_text = SENSITIVE_PATTERNS["email"].sub(
        lambda m: f"{m.group()[:2]}***@{m.group().split('@')[1]}", masked_text
    )

    # Mask phone numbers (more flexible pattern)
    masked_text = SENSITIVE_PATTERNS["phone"].sub("***-***-****", masked_text)

    # Mask passport numbers
    masked_text = SENSITIVE_PATTERNS["passport"].sub("XX******", masked_text)

    # Mask SSN
    masked_text = SENSITIVE_PATTERNS["ssn"].sub("***-**-****", masked_text)

    # Mask credit card numbers
    masked_text = SENSITIVE_PATTERNS["credit_card"].sub(
        "****-****-****-****", masked_text
    )

    return masked_text


def _mask_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive fields in a dictionary."""
    masked_data = {}

    for key, value in data.items():
        key_lower = key.lower()

        # Check if field name indicates sensitive data
        if any(sensitive_field in key_lower for sensitive_field in SENSITIVE_FIELDS):
            if isinstance(value, str) and value:
                # Mask the value but keep some characters for debugging
                if len(value) <= 4:
                    masked_data[key] = "***"
                else:
                    masked_data[key] = f"{value[:2]}***{value[-2:]}"
            else:
                masked_data[key] = "***"
        else:
            # Recursively mask nested data
            masked_data[key] = mask_sensitive_data(value)

    return masked_data


def mask_processor(logger, method_name, event_dict):
    """Structlog processor to mask sensitive data."""
    # Mask the main message
    if "event" in event_dict:
        event_dict["event"] = mask_sensitive_data(event_dict["event"])

    # Mask all other fields
    for key, value in list(event_dict.items()):
        if key != "event":  # Don't double-process the event field
            event_dict[key] = mask_sensitive_data(value)

    return event_dict


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_request_response(
    method: str,
    url: str,
    status_code: int,
    duration: float,
    user_id: str = None,
    **kwargs: Any,
) -> None:
    """Log HTTP request/response with structured data."""
    logger = get_logger("api")

    log_data = {
        "event": "http_request",
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_ms": round(duration * 1000, 2),
        **kwargs,
    }

    if user_id:
        log_data["user_id"] = user_id

    if status_code >= 400:
        logger.warning("HTTP request failed", **log_data)
    else:
        logger.info("HTTP request completed", **log_data)


def log_security_event(
    event_type: str,
    user_id: str = None,
    ip_address: str = None,
    details: Dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """Log security-related events."""
    logger = get_logger("security")

    log_data = {"event": "security_event", "event_type": event_type, **kwargs}

    if user_id:
        log_data["user_id"] = user_id

    if ip_address:
        log_data["ip_address"] = ip_address

    if details:
        log_data["details"] = details

    logger.warning("Security event detected", **log_data)


def log_business_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    user_id: str = None,
    details: Dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """Log business logic events for audit trail."""
    logger = get_logger("business")

    log_data = {
        "event": "business_event",
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        **kwargs,
    }

    if user_id:
        log_data["user_id"] = user_id

    if details:
        log_data["details"] = details

    logger.info("Business event occurred", **log_data)
