"""
Structured logging setup using structlog.
"""
import logging
import sys
from typing import Any, Dict

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
        structlog.processors.StackInfoRenderer(),
    ]
    
    if settings.LOG_FORMAT == "json":
        # JSON formatting for production
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ])
    else:
        # Human-readable formatting for development
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
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


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_request_response(
    method: str,
    url: str,
    status_code: int,
    duration: float,
    user_id: str = None,
    **kwargs: Any
) -> None:
    """Log HTTP request/response with structured data."""
    logger = get_logger("api")
    
    log_data = {
        "event": "http_request",
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_ms": round(duration * 1000, 2),
        **kwargs
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
    **kwargs: Any
) -> None:
    """Log security-related events."""
    logger = get_logger("security")
    
    log_data = {
        "event": "security_event",
        "event_type": event_type,
        **kwargs
    }
    
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
    **kwargs: Any
) -> None:
    """Log business logic events for audit trail."""
    logger = get_logger("business")
    
    log_data = {
        "event": "business_event",
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        **kwargs
    }
    
    if user_id:
        log_data["user_id"] = user_id
    
    if details:
        log_data["details"] = details
    
    logger.info("Business event occurred", **log_data)