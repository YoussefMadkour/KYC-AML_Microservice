"""
Unit tests for webhook service.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEvent, WebhookEventType, WebhookStatus
from app.schemas.webhook import WebhookEventCreate
from app.services.webhook_service import WebhookService
from app.utils.webhook_security import WebhookProvider


class TestWebhookService:
    """Test webhook service functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.fixture
    def webhook_service(self, mock_db):
        """Create webhook service with mocked dependencies."""
        service = WebhookService(mock_db)
        service.webhook_repo = AsyncMock()
        service.kyc_repo = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_receive_webhook_new(self, webhook_service):
        """Test receiving a new webhook."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        event_type = WebhookEventType.KYC_STATUS_UPDATE
        headers = {"x-webhook-signature": "test_sig"}
        payload = '{"check_id": "test123", "status": "approved"}'

        # Mock repository methods
        webhook_service.webhook_repo.get_by_provider_event_id.return_value = None

        mock_webhook = WebhookEvent(
            id=uuid4(),
            provider=provider.value,
            event_type=event_type,
            raw_payload=payload,
            signature_verified=True,
        )
        webhook_service.webhook_repo.create_webhook_event.return_value = mock_webhook

        # Mock task queuing
        with patch("app.tasks.webhook_tasks.process_webhook_event") as mock_task:
            mock_task.apply_async = MagicMock()

            result = await webhook_service.receive_webhook(
                provider=provider,
                event_type=event_type,
                headers=headers,
                payload=payload,
                signature_verified=True,
                provider_event_id="event123",
            )

        assert result == mock_webhook
        webhook_service.webhook_repo.get_by_provider_event_id.assert_called_once_with(
            provider.value, "event123"
        )
        webhook_service.webhook_repo.create_webhook_event.assert_called_once()
        mock_task.apply_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_webhook_duplicate(self, webhook_service):
        """Test receiving a duplicate webhook."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        event_type = WebhookEventType.KYC_STATUS_UPDATE
        headers = {"x-webhook-signature": "test_sig"}
        payload = '{"check_id": "test123", "status": "approved"}'

        # Mock existing webhook
        existing_webhook = WebhookEvent(
            id=uuid4(),
            provider=provider.value,
            event_type=event_type,
            raw_payload=payload,
            signature_verified=True,
        )
        webhook_service.webhook_repo.get_by_provider_event_id.return_value = (
            existing_webhook
        )

        result = await webhook_service.receive_webhook(
            provider=provider,
            event_type=event_type,
            headers=headers,
            payload=payload,
            signature_verified=True,
            provider_event_id="event123",
        )

        assert result == existing_webhook
        webhook_service.webhook_repo.create_webhook_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_webhook_sync_kyc_status_update(self, webhook_service):
        """Test synchronous processing of KYC status update webhook."""
        webhook_id = uuid4()
        kyc_check_id = str(uuid4())

        webhook_event = WebhookEvent(
            id=webhook_id,
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload=json.dumps(
                {
                    "check_id": kyc_check_id,
                    "status": "approved",
                    "result": {"confidence": 0.95},
                    "provider_reference": "ref123",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            status=WebhookStatus.PENDING,
            signature_verified=True,
        )

        # Mock KYC check
        mock_kyc_check = MagicMock()
        mock_kyc_check.status = "pending"
        webhook_service.kyc_repo.get_by_id.return_value = mock_kyc_check

        # Mock repository updates
        webhook_service.webhook_repo.update_webhook_status = AsyncMock()
        webhook_service.db.commit = AsyncMock()

        result = await webhook_service.process_webhook_sync(webhook_event)

        # Debug: print result if test fails
        if not result.success:
            print(f"Errors: {result.errors}")
            print(f"Warnings: {result.warnings}")

        assert result.success is True
        assert result.webhook_event_id == str(webhook_id)
        assert len(result.actions_taken) > 0
        assert "Updated KYC status" in result.actions_taken[0]

        # Verify webhook status was updated to processing then processed
        webhook_service.webhook_repo.update_webhook_status.assert_called()

    @pytest.mark.asyncio
    async def test_process_webhook_sync_invalid_json(self, webhook_service):
        """Test processing webhook with invalid JSON payload."""
        webhook_id = uuid4()

        webhook_event = WebhookEvent(
            id=webhook_id,
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload="invalid json",
            status=WebhookStatus.PENDING,
            signature_verified=True,
        )

        webhook_service.webhook_repo.update_webhook_status = AsyncMock()

        result = await webhook_service.process_webhook_sync(webhook_event)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Failed to parse webhook payload" in result.errors[0]

        # Verify webhook was marked as failed
        webhook_service.webhook_repo.update_webhook_status.assert_called()

    @pytest.mark.asyncio
    async def test_process_webhook_sync_kyc_check_not_found(self, webhook_service):
        """Test processing webhook when KYC check is not found."""
        webhook_id = uuid4()
        kyc_check_id = str(uuid4())

        webhook_event = WebhookEvent(
            id=webhook_id,
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload=json.dumps(
                {
                    "check_id": kyc_check_id,
                    "status": "approved",
                    "result": {},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            status=WebhookStatus.PENDING,
            signature_verified=True,
        )

        # Mock KYC check not found
        webhook_service.kyc_repo.get_by_id.return_value = None
        webhook_service.webhook_repo.update_webhook_status = AsyncMock()

        result = await webhook_service.process_webhook_sync(webhook_event)

        assert result.success is False
        assert len(result.errors) > 0
        assert "KYC check not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_retry_webhook_success(self, webhook_service):
        """Test successful webhook retry."""
        webhook_id = uuid4()

        mock_webhook = MagicMock()
        mock_webhook.can_retry = True
        mock_webhook.retry_count = 1
        mock_webhook.max_retries = 3

        webhook_service.webhook_repo.get.return_value = mock_webhook
        webhook_service.webhook_repo.increment_retry_count = AsyncMock()

        with patch("app.tasks.webhook_tasks.retry_failed_webhook") as mock_task:
            mock_task.apply_async = MagicMock()

            success, message = await webhook_service.retry_webhook(webhook_id)

        assert success is True
        assert "Retry scheduled" in message
        webhook_service.webhook_repo.increment_retry_count.assert_called_once()
        mock_task.apply_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_webhook_cannot_retry(self, webhook_service):
        """Test retry when webhook cannot be retried."""
        webhook_id = uuid4()

        mock_webhook = MagicMock()
        mock_webhook.can_retry = False
        mock_webhook.retry_count = 3
        mock_webhook.max_retries = 3

        webhook_service.webhook_repo.get.return_value = mock_webhook

        success, message = await webhook_service.retry_webhook(webhook_id)

        assert success is False
        assert "cannot be retried" in message

    @pytest.mark.asyncio
    async def test_retry_webhook_not_found(self, webhook_service):
        """Test retry when webhook is not found."""
        webhook_id = uuid4()

        webhook_service.webhook_repo.get.return_value = None

        success, message = await webhook_service.retry_webhook(webhook_id)

        assert success is False
        assert "Webhook not found" in message

    @pytest.mark.asyncio
    async def test_get_webhook_events_with_filters(self, webhook_service):
        """Test getting webhook events with various filters."""
        mock_webhooks = [
            WebhookEvent(id=uuid4(), provider="test1"),
            WebhookEvent(id=uuid4(), provider="test2"),
        ]

        webhook_service.webhook_repo.get_webhooks_by_provider.return_value = (
            mock_webhooks,
            2,
        )

        result = await webhook_service.get_webhook_events(
            provider="test_provider", status=WebhookStatus.PROCESSED, limit=10, offset=0
        )

        webhooks, total = result
        assert len(webhooks) == 2
        assert total == 2
        webhook_service.webhook_repo.get_webhooks_by_provider.assert_called_once_with(
            "test_provider", 10, 0, WebhookStatus.PROCESSED
        )

    @pytest.mark.asyncio
    async def test_get_webhook_events_by_kyc_check(self, webhook_service):
        """Test getting webhook events by KYC check ID."""
        kyc_check_id = str(uuid4())
        mock_webhooks = [WebhookEvent(id=uuid4(), related_kyc_check_id=kyc_check_id)]

        webhook_service.webhook_repo.get_webhooks_by_kyc_check.return_value = (
            mock_webhooks
        )

        result = await webhook_service.get_webhook_events(kyc_check_id=kyc_check_id)

        webhooks, total = result
        assert len(webhooks) == 1
        assert total == 1
        webhook_service.webhook_repo.get_webhooks_by_kyc_check.assert_called_once_with(
            kyc_check_id
        )

    @pytest.mark.asyncio
    async def test_get_webhook_statistics(self, webhook_service):
        """Test getting webhook statistics."""
        mock_stats = {
            "total_events": 100,
            "processed_events": 85,
            "failed_events": 10,
            "pending_events": 5,
            "success_rate": 85.0,
        }

        webhook_service.webhook_repo.get_webhook_statistics.return_value = mock_stats

        result = await webhook_service.get_webhook_statistics(
            provider="test_provider", days=30
        )

        assert result == mock_stats
        webhook_service.webhook_repo.get_webhook_statistics.assert_called_once_with(
            "test_provider", None, 30
        )

    @pytest.mark.asyncio
    async def test_cleanup_old_webhooks(self, webhook_service):
        """Test cleaning up old webhooks."""
        webhook_service.webhook_repo.cleanup_old_webhooks.return_value = 25

        result = await webhook_service.cleanup_old_webhooks(
            days_old=90, keep_failed=True
        )

        assert result == 25
        webhook_service.webhook_repo.cleanup_old_webhooks.assert_called_once_with(
            90, True
        )

    def test_extract_related_ids_valid_json(self, webhook_service):
        """Test extracting related IDs from valid JSON payload."""
        payload = json.dumps({"check_id": "kyc123", "user_id": "user456"})

        result = webhook_service._extract_related_ids(
            payload, WebhookEventType.KYC_STATUS_UPDATE
        )

        kyc_check_id, user_id = result
        assert kyc_check_id == "kyc123"
        assert user_id == "user456"

    def test_extract_related_ids_invalid_json(self, webhook_service):
        """Test extracting related IDs from invalid JSON payload."""
        payload = "invalid json"

        result = webhook_service._extract_related_ids(
            payload, WebhookEventType.KYC_STATUS_UPDATE
        )

        kyc_check_id, user_id = result
        assert kyc_check_id is None
        assert user_id is None

    def test_extract_related_ids_alternative_fields(self, webhook_service):
        """Test extracting related IDs from alternative field names."""
        payload = json.dumps({"id": "kyc789", "customer_id": "cust123"})

        result = webhook_service._extract_related_ids(
            payload, WebhookEventType.KYC_STATUS_UPDATE
        )

        kyc_check_id, user_id = result
        assert kyc_check_id == "kyc789"
        assert user_id == "cust123"
