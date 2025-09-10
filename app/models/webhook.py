"""
Webhook event model for audit trail and processing.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (
    Integer,
    String,
    Text,
)

from app.models.base import BaseModel


class WebhookStatus(str, Enum):
    """Webhook processing status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEventType(str, Enum):
    """Webhook event type enumeration."""

    KYC_STATUS_UPDATE = "kyc_status_update"
    KYC_DOCUMENT_VERIFIED = "kyc_document_verified"
    AML_CHECK_COMPLETE = "aml_check_complete"
    VERIFICATION_EXPIRED = "verification_expired"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class WebhookEvent(BaseModel):
    """Webhook event model for audit trail."""

    __tablename__ = "webhook_events"

    # Provider information
    provider = Column(
        String(100), nullable=False, index=True, doc="Name of the webhook provider"
    )

    provider_event_id = Column(
        String(255), nullable=True, index=True, doc="Provider's unique event identifier"
    )

    # Event details
    event_type = Column(
        SQLEnum(WebhookEventType),
        nullable=False,
        index=True,
        doc="Type of webhook event",
    )

    # HTTP request details
    http_method = Column(
        String(10),
        default="POST",
        nullable=False,
        doc="HTTP method used for the webhook",
    )

    headers = Column(JSON, nullable=True, doc="HTTP headers from the webhook request")

    raw_payload = Column(Text, nullable=False, doc="Raw webhook payload as received")

    parsed_payload = Column(
        JSON, nullable=True, doc="Parsed and validated webhook payload"
    )

    # Security
    signature = Column(
        String(500), nullable=True, doc="Webhook signature for verification"
    )

    signature_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the webhook signature was verified",
    )

    # Processing status
    status = Column(
        SQLEnum(WebhookStatus),
        default=WebhookStatus.PENDING,
        nullable=False,
        index=True,
        doc="Processing status of the webhook",
    )

    # Retry mechanism
    retry_count = Column(
        Integer, default=0, nullable=False, doc="Number of processing retry attempts"
    )

    max_retries = Column(
        Integer, default=3, nullable=False, doc="Maximum number of retry attempts"
    )

    next_retry_at = Column(
        DateTime, nullable=True, doc="Timestamp for next retry attempt"
    )

    # Processing timestamps
    received_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        doc="When the webhook was received",
    )

    processed_at = Column(
        DateTime, nullable=True, doc="When the webhook was successfully processed"
    )

    failed_at = Column(
        DateTime, nullable=True, doc="When the webhook processing failed"
    )

    # Error handling
    error_message = Column(
        Text, nullable=True, doc="Error message if processing failed"
    )

    error_details = Column(JSON, nullable=True, doc="Detailed error information")

    # Related entities
    related_kyc_check_id = Column(
        String(255),
        nullable=True,
        index=True,
        doc="ID of related KYC check if applicable",
    )

    related_user_id = Column(
        String(255), nullable=True, index=True, doc="ID of related user if applicable"
    )

    # Processing notes
    processing_notes = Column(Text, nullable=True, doc="Notes from webhook processing")

    def __repr__(self) -> str:
        """String representation of the webhook event."""
        return (
            f"<WebhookEvent(id={self.id}, "
            f"provider={self.provider}, "
            f"type={self.event_type}, "
            f"status={self.status})>"
        )

    @property
    def is_processed(self) -> bool:
        """Check if webhook has been successfully processed."""
        return self.status == WebhookStatus.PROCESSED

    @property
    def is_failed(self) -> bool:
        """Check if webhook processing has failed."""
        return self.status == WebhookStatus.FAILED

    @property
    def can_retry(self) -> bool:
        """Check if webhook can be retried."""
        return (
            self.status in [WebhookStatus.FAILED, WebhookStatus.RETRYING]
            and self.retry_count < self.max_retries
        )

    @property
    def processing_time_seconds(self) -> Optional[int]:
        """Get processing time in seconds if completed."""
        if self.processed_at and self.received_at:
            delta = self.processed_at - self.received_at
            return int(delta.total_seconds())
        return None

    def mark_as_processing(self) -> None:
        """Mark webhook as currently being processed."""
        self.status = WebhookStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_as_processed(self, notes: Optional[str] = None) -> None:
        """Mark webhook as successfully processed."""
        self.status = WebhookStatus.PROCESSED
        self.processed_at = datetime.utcnow()
        if notes:
            self.processing_notes = notes

    def mark_as_failed(
        self, error_message: str, error_details: Optional[dict] = None
    ) -> None:
        """Mark webhook as failed with error details."""
        self.status = WebhookStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details

    def increment_retry(self, next_retry_at: Optional[datetime] = None) -> None:
        """Increment retry count and set next retry time."""
        self.retry_count += 1
        self.status = WebhookStatus.RETRYING
        self.next_retry_at = next_retry_at
        self.updated_at = datetime.utcnow()

    def should_retry_now(self) -> bool:
        """Check if webhook should be retried now."""
        if not self.can_retry:
            return False

        if self.next_retry_at is None:
            return True

        return datetime.utcnow() >= self.next_retry_at
