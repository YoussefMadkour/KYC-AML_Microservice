"""
Webhook request and response schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

from app.models.webhook import WebhookEventType, WebhookStatus


class WebhookEventBase(BaseModel):
    """Base webhook event schema."""
    
    provider: str = Field(..., min_length=1, max_length=100, description="Webhook provider name")
    event_type: WebhookEventType = Field(..., description="Type of webhook event")
    provider_event_id: Optional[str] = Field(None, max_length=255, description="Provider's unique event identifier")


class WebhookEventCreate(WebhookEventBase):
    """Webhook event creation schema."""
    
    http_method: str = Field(default="POST", description="HTTP method used")
    headers: Dict[str, str] = Field(..., description="HTTP headers from request")
    raw_payload: str = Field(..., description="Raw webhook payload")
    signature: Optional[str] = Field(None, description="Webhook signature")
    related_kyc_check_id: Optional[str] = Field(None, description="Related KYC check ID")
    related_user_id: Optional[str] = Field(None, description="Related user ID")
    
    @validator("http_method")
    def validate_http_method(cls, v):
        """Validate HTTP method."""
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        if v.upper() not in allowed_methods:
            raise ValueError(f"HTTP method must be one of: {allowed_methods}")
        return v.upper()


class WebhookEventUpdate(BaseModel):
    """Webhook event update schema."""
    
    status: Optional[WebhookStatus] = Field(None, description="Processing status")
    parsed_payload: Optional[Dict[str, Any]] = Field(None, description="Parsed payload")
    signature_verified: Optional[bool] = Field(None, description="Signature verification status")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")
    processing_notes: Optional[str] = Field(None, description="Processing notes")


class WebhookEventResponse(WebhookEventBase):
    """Webhook event response schema."""
    
    id: str = Field(..., description="Webhook event ID")
    http_method: str = Field(..., description="HTTP method used")
    status: WebhookStatus = Field(..., description="Processing status")
    signature_verified: bool = Field(..., description="Whether signature was verified")
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum retry attempts")
    received_at: datetime = Field(..., description="When webhook was received")
    processed_at: Optional[datetime] = Field(None, description="When webhook was processed")
    failed_at: Optional[datetime] = Field(None, description="When webhook processing failed")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry timestamp")
    error_message: Optional[str] = Field(None, description="Error message")
    processing_notes: Optional[str] = Field(None, description="Processing notes")
    related_kyc_check_id: Optional[str] = Field(None, description="Related KYC check ID")
    related_user_id: Optional[str] = Field(None, description="Related user ID")
    processing_time_seconds: Optional[int] = Field(None, description="Processing time in seconds")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class WebhookEventListResponse(BaseModel):
    """Webhook event list response schema."""
    
    items: List[WebhookEventResponse] = Field(..., description="List of webhook events")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class WebhookRetryRequest(BaseModel):
    """Webhook retry request schema."""
    
    force_retry: bool = Field(default=False, description="Force retry even if max retries exceeded")
    notes: Optional[str] = Field(None, description="Retry notes")


class WebhookRetryResponse(BaseModel):
    """Webhook retry response schema."""
    
    webhook_event_id: str = Field(..., description="Webhook event ID")
    retry_scheduled: bool = Field(..., description="Whether retry was scheduled")
    retry_count: int = Field(..., description="New retry count")
    next_retry_at: Optional[datetime] = Field(None, description="Next retry timestamp")
    message: str = Field(..., description="Response message")


# Provider-specific webhook payload schemas
class KYCWebhookPayload(BaseModel):
    """KYC webhook payload schema."""
    
    check_id: str = Field(..., description="KYC check identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    status: str = Field(..., description="Verification status")
    result: Dict[str, Any] = Field(..., description="Verification result details")
    timestamp: datetime = Field(..., description="Event timestamp")
    provider_reference: Optional[str] = Field(None, description="Provider reference ID")
    
    @validator("status")
    def validate_status(cls, v):
        """Validate KYC status values."""
        allowed_statuses = ["approved", "rejected", "manual_review", "pending", "in_progress"]
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v.lower()


class AMLWebhookPayload(BaseModel):
    """AML webhook payload schema."""
    
    check_id: str = Field(..., description="AML check identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    status: str = Field(..., description="AML check status")
    risk_score: Optional[float] = Field(None, ge=0, le=100, description="Risk score (0-100)")
    risk_level: Optional[str] = Field(None, description="Risk level")
    matches: List[Dict[str, Any]] = Field(default=[], description="AML matches found")
    timestamp: datetime = Field(..., description="Event timestamp")
    provider_reference: Optional[str] = Field(None, description="Provider reference ID")
    
    @validator("status")
    def validate_status(cls, v):
        """Validate AML status values."""
        allowed_statuses = ["clear", "flagged", "review_required", "pending"]
        if v.lower() not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v.lower()
    
    @validator("risk_level")
    def validate_risk_level(cls, v):
        """Validate risk level values."""
        if v is not None:
            allowed_levels = ["low", "medium", "high", "critical"]
            if v.lower() not in allowed_levels:
                raise ValueError(f"Risk level must be one of: {allowed_levels}")
            return v.lower()
        return v


class WebhookProcessingResult(BaseModel):
    """Webhook processing result schema."""
    
    success: bool = Field(..., description="Whether processing was successful")
    webhook_event_id: str = Field(..., description="Webhook event ID")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    actions_taken: List[str] = Field(default=[], description="Actions taken during processing")
    errors: List[str] = Field(default=[], description="Errors encountered")
    warnings: List[str] = Field(default=[], description="Warnings generated")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")


class WebhookStatsResponse(BaseModel):
    """Webhook statistics response schema."""
    
    total_events: int = Field(..., description="Total webhook events")
    processed_events: int = Field(..., description="Successfully processed events")
    failed_events: int = Field(..., description="Failed events")
    pending_events: int = Field(..., description="Pending events")
    retrying_events: int = Field(..., description="Events being retried")
    average_processing_time_ms: Optional[float] = Field(None, description="Average processing time")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate percentage")
    provider_stats: Dict[str, Dict[str, int]] = Field(default={}, description="Per-provider statistics")
    event_type_stats: Dict[str, Dict[str, int]] = Field(default={}, description="Per-event-type statistics")