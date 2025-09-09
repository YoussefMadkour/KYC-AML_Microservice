"""
Unit tests for Webhook model.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.webhook import WebhookEvent, WebhookStatus, WebhookEventType


# Test database setup
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class TestWebhookEvent:
    """Test cases for WebhookEvent model."""
    
    def test_create_webhook_event(self, db_session):
        """Test creating a webhook event."""
        webhook_event = WebhookEvent(
            provider="mock_provider_1",
            provider_event_id="evt_123456",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            http_method="POST",
            headers={"Content-Type": "application/json", "X-Signature": "abc123"},
            raw_payload='{"status": "approved", "kyc_id": "kyc_123"}',
            parsed_payload={"status": "approved", "kyc_id": "kyc_123"},
            signature="sha256=abc123def456",
            signature_verified=True,
            status=WebhookStatus.PENDING,
            retry_count=0,
            max_retries=3,
            related_kyc_check_id="kyc_123",
            related_user_id="user_456",
            processing_notes="Initial webhook received"
        )
        
        db_session.add(webhook_event)
        db_session.commit()
        
        # Verify webhook event was created
        assert webhook_event.id is not None
        assert webhook_event.provider == "mock_provider_1"
        assert webhook_event.provider_event_id == "evt_123456"
        assert webhook_event.event_type == WebhookEventType.KYC_STATUS_UPDATE
        assert webhook_event.http_method == "POST"
        assert webhook_event.headers["Content-Type"] == "application/json"
        assert webhook_event.raw_payload == '{"status": "approved", "kyc_id": "kyc_123"}'
        assert webhook_event.parsed_payload["status"] == "approved"
        assert webhook_event.signature == "sha256=abc123def456"
        assert webhook_event.signature_verified is True
        assert webhook_event.status == WebhookStatus.PENDING
        assert webhook_event.retry_count == 0
        assert webhook_event.max_retries == 3
        assert webhook_event.related_kyc_check_id == "kyc_123"
        assert webhook_event.related_user_id == "user_456"
        assert webhook_event.received_at is not None
        assert webhook_event.created_at is not None
        assert webhook_event.updated_at is not None
    
    def test_webhook_event_repr(self, db_session):
        """Test webhook event string representation."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_DOCUMENT_VERIFIED,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED
        )
        
        db_session.add(webhook_event)
        db_session.commit()
        
        repr_str = repr(webhook_event)
        assert "WebhookEvent" in repr_str
        assert str(webhook_event.id) in repr_str
        assert "test_provider" in repr_str
        assert "KYC_DOCUMENT_VERIFIED" in repr_str
        assert "PROCESSED" in repr_str
    
    def test_is_processed_property(self):
        """Test is_processed property."""
        processed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED
        )
        assert processed_webhook.is_processed is True
        
        pending_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PENDING
        )
        assert pending_webhook.is_processed is False
    
    def test_is_failed_property(self):
        """Test is_failed property."""
        failed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED
        )
        assert failed_webhook.is_failed is True
        
        processed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED
        )
        assert processed_webhook.is_failed is False
    
    def test_can_retry_property(self):
        """Test can_retry property."""
        # Failed webhook with retries remaining
        failed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED,
            retry_count=1,
            max_retries=3
        )
        assert failed_webhook.can_retry is True
        
        # Failed webhook with no retries remaining
        exhausted_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED,
            retry_count=3,
            max_retries=3
        )
        assert exhausted_webhook.can_retry is False
        
        # Processed webhook (cannot retry)
        processed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED,
            retry_count=0,
            max_retries=3
        )
        assert processed_webhook.can_retry is False
        
        # Retrying webhook with retries remaining
        retrying_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.RETRYING,
            retry_count=1,
            max_retries=3
        )
        assert retrying_webhook.can_retry is True
    
    def test_processing_time_seconds_property(self):
        """Test processing_time_seconds property."""
        now = datetime.utcnow()
        received_time = now - timedelta(seconds=30)  # 30 seconds ago
        
        # Test with processed webhook
        processed_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED,
            received_at=received_time,
            processed_at=now
        )
        
        processing_time = processed_webhook.processing_time_seconds
        assert processing_time == 30
        
        # Test with unprocessed webhook
        pending_webhook = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PENDING,
            received_at=received_time
        )
        
        assert pending_webhook.processing_time_seconds is None
    
    def test_mark_as_processing_method(self):
        """Test mark_as_processing method."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PENDING
        )
        
        original_updated_at = webhook_event.updated_at
        webhook_event.mark_as_processing()
        
        assert webhook_event.status == WebhookStatus.PROCESSING
        assert webhook_event.updated_at != original_updated_at
    
    def test_mark_as_processed_method(self):
        """Test mark_as_processed method."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSING
        )
        
        webhook_event.mark_as_processed("Successfully processed webhook")
        
        assert webhook_event.status == WebhookStatus.PROCESSED
        assert webhook_event.processed_at is not None
        assert webhook_event.processing_notes == "Successfully processed webhook"
    
    def test_mark_as_failed_method(self):
        """Test mark_as_failed method."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSING
        )
        
        error_details = {"error_code": "INVALID_SIGNATURE", "details": "Signature verification failed"}
        webhook_event.mark_as_failed("Signature verification failed", error_details)
        
        assert webhook_event.status == WebhookStatus.FAILED
        assert webhook_event.failed_at is not None
        assert webhook_event.error_message == "Signature verification failed"
        assert webhook_event.error_details["error_code"] == "INVALID_SIGNATURE"
    
    def test_increment_retry_method(self):
        """Test increment_retry method."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED,
            retry_count=0
        )
        
        next_retry_time = datetime.utcnow() + timedelta(minutes=5)
        original_updated_at = webhook_event.updated_at
        
        webhook_event.increment_retry(next_retry_time)
        
        assert webhook_event.retry_count == 1
        assert webhook_event.status == WebhookStatus.RETRYING
        assert webhook_event.next_retry_at == next_retry_time
        assert webhook_event.updated_at != original_updated_at
    
    def test_should_retry_now_method(self):
        """Test should_retry_now method."""
        # Webhook that can retry and has no next_retry_at set
        webhook1 = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED,
            retry_count=1,
            max_retries=3
        )
        assert webhook1.should_retry_now() is True
        
        # Webhook that can retry and next_retry_at is in the past
        past_time = datetime.utcnow() - timedelta(minutes=1)
        webhook2 = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.RETRYING,
            retry_count=1,
            max_retries=3,
            next_retry_at=past_time
        )
        assert webhook2.should_retry_now() is True
        
        # Webhook that can retry but next_retry_at is in the future
        future_time = datetime.utcnow() + timedelta(minutes=5)
        webhook3 = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.RETRYING,
            retry_count=1,
            max_retries=3,
            next_retry_at=future_time
        )
        assert webhook3.should_retry_now() is False
        
        # Webhook that cannot retry (exhausted retries)
        webhook4 = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.FAILED,
            retry_count=3,
            max_retries=3
        )
        assert webhook4.should_retry_now() is False
    
    def test_webhook_status_enum(self):
        """Test WebhookStatus enum values."""
        assert WebhookStatus.PENDING == "pending"
        assert WebhookStatus.PROCESSING == "processing"
        assert WebhookStatus.PROCESSED == "processed"
        assert WebhookStatus.FAILED == "failed"
        assert WebhookStatus.RETRYING == "retrying"
    
    def test_webhook_event_type_enum(self):
        """Test WebhookEventType enum values."""
        assert WebhookEventType.KYC_STATUS_UPDATE == "kyc_status_update"
        assert WebhookEventType.KYC_DOCUMENT_VERIFIED == "kyc_document_verified"
        assert WebhookEventType.AML_CHECK_COMPLETE == "aml_check_complete"
        assert WebhookEventType.VERIFICATION_EXPIRED == "verification_expired"
        assert WebhookEventType.MANUAL_REVIEW_REQUIRED == "manual_review_required"
    
    def test_default_values(self, db_session):
        """Test default values for webhook event fields."""
        webhook_event = WebhookEvent(
            provider="test_provider",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}'
        )
        
        db_session.add(webhook_event)
        db_session.commit()
        
        # Check default values
        assert webhook_event.http_method == "POST"
        assert webhook_event.signature_verified is False
        assert webhook_event.status == WebhookStatus.PENDING
        assert webhook_event.retry_count == 0
        assert webhook_event.max_retries == 3
        assert webhook_event.received_at is not None