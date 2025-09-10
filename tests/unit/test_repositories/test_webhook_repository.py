"""
Unit tests for webhook repository.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookEvent, WebhookEventType, WebhookStatus
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookEventCreate


class TestWebhookRepository:
    """Test webhook repository functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.fixture
    def webhook_repo(self, mock_db):
        """Create webhook repository with mocked database."""
        return WebhookRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_webhook_event(self, webhook_repo):
        """Test creating a webhook event."""
        webhook_data = WebhookEventCreate(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            headers={"x-signature": "test"},
            raw_payload='{"test": "data"}',
            signature="test_signature",
            related_kyc_check_id="kyc123",
        )

        # Mock the create method
        webhook_repo.create = AsyncMock()
        mock_webhook = WebhookEvent(
            id=uuid4(),
            provider=webhook_data.provider,
            event_type=webhook_data.event_type,
            raw_payload=webhook_data.raw_payload,
            status=WebhookStatus.PENDING,
        )
        webhook_repo.create.return_value = mock_webhook

        result = await webhook_repo.create_webhook_event(
            webhook_data, signature_verified=True
        )

        assert result == mock_webhook
        webhook_repo.create.assert_called_once()

        # Verify the webhook event was created with correct properties
        call_args = webhook_repo.create.call_args[0][0]
        assert call_args.provider == webhook_data.provider
        assert call_args.event_type == webhook_data.event_type
        assert call_args.raw_payload == webhook_data.raw_payload
        assert call_args.signature == webhook_data.signature
        assert call_args.signature_verified is True
        assert call_args.status == WebhookStatus.PENDING
        assert call_args.related_kyc_check_id == webhook_data.related_kyc_check_id

    @pytest.mark.asyncio
    async def test_get_by_provider_event_id(self, webhook_repo):
        """Test getting webhook by provider and event ID."""
        provider = "mock_provider_1"
        event_id = "event123"

        mock_webhook = WebhookEvent(
            id=uuid4(),
            provider=provider,
            provider_event_id=event_id,
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
        )

        webhook_repo.get_by_filters = AsyncMock(return_value=mock_webhook)

        result = await webhook_repo.get_by_provider_event_id(provider, event_id)

        assert result == mock_webhook
        webhook_repo.get_by_filters.assert_called_once_with(
            provider=provider, provider_event_id=event_id
        )

    @pytest.mark.asyncio
    async def test_get_pending_webhooks(self, webhook_repo):
        """Test getting pending webhook events."""
        mock_webhooks = [
            WebhookEvent(id=uuid4(), status=WebhookStatus.PENDING),
            WebhookEvent(id=uuid4(), status=WebhookStatus.PENDING),
        ]

        webhook_repo.get_multi_by_filters = AsyncMock(return_value=mock_webhooks)

        result = await webhook_repo.get_pending_webhooks(limit=10)

        assert result == mock_webhooks
        webhook_repo.get_multi_by_filters.assert_called_once()

        # Verify filters were applied correctly
        call_args = webhook_repo.get_multi_by_filters.call_args
        assert call_args[1]["limit"] == 10
        assert call_args[1]["order_by"] == WebhookEvent.received_at

    @pytest.mark.asyncio
    async def test_get_pending_webhooks_with_age_filter(self, webhook_repo):
        """Test getting pending webhooks older than specified minutes."""
        mock_webhooks = [WebhookEvent(id=uuid4(), status=WebhookStatus.PENDING)]

        webhook_repo.get_multi_by_filters = AsyncMock(return_value=mock_webhooks)

        result = await webhook_repo.get_pending_webhooks(
            limit=10, older_than_minutes=30
        )

        assert result == mock_webhooks
        webhook_repo.get_multi_by_filters.assert_called_once()

        # Verify time filter was applied
        call_args = webhook_repo.get_multi_by_filters.call_args[0]
        assert len(call_args) == 2  # Status filter + time filter

    @pytest.mark.asyncio
    async def test_get_failed_webhooks_for_retry(self, webhook_repo):
        """Test getting failed webhooks eligible for retry."""
        mock_webhooks = [
            WebhookEvent(
                id=uuid4(), status=WebhookStatus.FAILED, retry_count=1, max_retries=3
            )
        ]

        webhook_repo.get_multi_by_filters = AsyncMock(return_value=mock_webhooks)

        result = await webhook_repo.get_failed_webhooks_for_retry(limit=20)

        assert result == mock_webhooks
        webhook_repo.get_multi_by_filters.assert_called_once()

        call_args = webhook_repo.get_multi_by_filters.call_args
        assert call_args[1]["limit"] == 20
        assert call_args[1]["order_by"] == WebhookEvent.next_retry_at

    @pytest.mark.asyncio
    async def test_get_webhooks_by_status(self, webhook_repo):
        """Test getting webhooks by status with pagination."""
        status = WebhookStatus.PROCESSED
        mock_webhooks = [WebhookEvent(id=uuid4(), status=status)]
        total_count = 1

        webhook_repo.get_multi_with_count = AsyncMock(
            return_value=(mock_webhooks, total_count)
        )

        result = await webhook_repo.get_webhooks_by_status(status, limit=50, offset=0)

        webhooks, total = result
        assert webhooks == mock_webhooks
        assert total == total_count

        webhook_repo.get_multi_with_count.assert_called_once()
        call_args = webhook_repo.get_multi_with_count.call_args
        assert call_args[1]["limit"] == 50
        assert call_args[1]["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_webhooks_by_provider(self, webhook_repo):
        """Test getting webhooks by provider."""
        provider = "mock_provider_1"
        mock_webhooks = [WebhookEvent(id=uuid4(), provider=provider)]
        total_count = 1

        webhook_repo.get_multi_with_count = AsyncMock(
            return_value=(mock_webhooks, total_count)
        )

        result = await webhook_repo.get_webhooks_by_provider(
            provider, limit=25, offset=10, status=WebhookStatus.PROCESSED
        )

        webhooks, total = result
        assert webhooks == mock_webhooks
        assert total == total_count

        webhook_repo.get_multi_with_count.assert_called_once()
        call_args = webhook_repo.get_multi_with_count.call_args

        # Verify filters include both provider and status
        filters = call_args[1]["filters"]
        assert len(filters) == 2  # Provider filter + status filter

    @pytest.mark.asyncio
    async def test_get_webhooks_by_kyc_check(self, webhook_repo):
        """Test getting webhooks by KYC check ID."""
        kyc_check_id = "kyc123"
        mock_webhooks = [WebhookEvent(id=uuid4(), related_kyc_check_id=kyc_check_id)]

        webhook_repo.get_multi_by_filters = AsyncMock(return_value=mock_webhooks)

        result = await webhook_repo.get_webhooks_by_kyc_check(kyc_check_id)

        assert result == mock_webhooks
        webhook_repo.get_multi_by_filters.assert_called_once()

        # Verify filter was applied correctly
        call_args = webhook_repo.get_multi_by_filters.call_args[0]
        # Should have one filter for related_kyc_check_id
        assert len(call_args) == 1

    @pytest.mark.asyncio
    async def test_get_webhooks_by_user(self, webhook_repo):
        """Test getting webhooks by user ID."""
        user_id = "user123"
        mock_webhooks = [WebhookEvent(id=uuid4(), related_user_id=user_id)]
        total_count = 1

        webhook_repo.get_multi_with_count = AsyncMock(
            return_value=(mock_webhooks, total_count)
        )

        result = await webhook_repo.get_webhooks_by_user(user_id, limit=30, offset=5)

        webhooks, total = result
        assert webhooks == mock_webhooks
        assert total == total_count

        webhook_repo.get_multi_with_count.assert_called_once()
        call_args = webhook_repo.get_multi_with_count.call_args
        assert call_args[1]["limit"] == 30
        assert call_args[1]["offset"] == 5

    @pytest.mark.asyncio
    async def test_update_webhook_status_to_processing(self, webhook_repo):
        """Test updating webhook status to processing."""
        webhook_id = uuid4()
        mock_webhook = MagicMock()
        mock_webhook.mark_as_processing = MagicMock()

        webhook_repo.get = AsyncMock(return_value=mock_webhook)
        webhook_repo.db.commit = AsyncMock()
        webhook_repo.db.refresh = AsyncMock()

        result = await webhook_repo.update_webhook_status(
            webhook_id, WebhookStatus.PROCESSING
        )

        assert result == mock_webhook
        mock_webhook.mark_as_processing.assert_called_once()
        webhook_repo.db.commit.assert_called_once()
        webhook_repo.db.refresh.assert_called_once_with(mock_webhook)

    @pytest.mark.asyncio
    async def test_update_webhook_status_to_processed(self, webhook_repo):
        """Test updating webhook status to processed."""
        webhook_id = uuid4()
        notes = "Successfully processed"
        mock_webhook = MagicMock()
        mock_webhook.mark_as_processed = MagicMock()

        webhook_repo.get = AsyncMock(return_value=mock_webhook)
        webhook_repo.db.commit = AsyncMock()
        webhook_repo.db.refresh = AsyncMock()

        result = await webhook_repo.update_webhook_status(
            webhook_id, WebhookStatus.PROCESSED, processing_notes=notes
        )

        assert result == mock_webhook
        mock_webhook.mark_as_processed.assert_called_once_with(notes)
        webhook_repo.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_webhook_status_to_failed(self, webhook_repo):
        """Test updating webhook status to failed."""
        webhook_id = uuid4()
        error_message = "Processing failed"
        error_details = {"error": "test"}
        mock_webhook = MagicMock()
        mock_webhook.mark_as_failed = MagicMock()

        webhook_repo.get = AsyncMock(return_value=mock_webhook)
        webhook_repo.db.commit = AsyncMock()
        webhook_repo.db.refresh = AsyncMock()

        result = await webhook_repo.update_webhook_status(
            webhook_id,
            WebhookStatus.FAILED,
            error_message=error_message,
            error_details=error_details,
        )

        assert result == mock_webhook
        mock_webhook.mark_as_failed.assert_called_once_with(
            error_message, error_details
        )

    @pytest.mark.asyncio
    async def test_update_webhook_status_not_found(self, webhook_repo):
        """Test updating webhook status when webhook not found."""
        webhook_id = uuid4()

        webhook_repo.get = AsyncMock(return_value=None)

        result = await webhook_repo.update_webhook_status(
            webhook_id, WebhookStatus.PROCESSED
        )

        assert result is None
        webhook_repo.db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_increment_retry_count(self, webhook_repo):
        """Test incrementing webhook retry count."""
        webhook_id = uuid4()
        next_retry_at = datetime.utcnow() + timedelta(minutes=5)
        mock_webhook = MagicMock()
        mock_webhook.increment_retry = MagicMock()

        webhook_repo.get = AsyncMock(return_value=mock_webhook)
        webhook_repo.db.commit = AsyncMock()
        webhook_repo.db.refresh = AsyncMock()

        result = await webhook_repo.increment_retry_count(webhook_id, next_retry_at)

        assert result == mock_webhook
        mock_webhook.increment_retry.assert_called_once_with(next_retry_at)
        webhook_repo.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_retry_count_not_found(self, webhook_repo):
        """Test incrementing retry count when webhook not found."""
        webhook_id = uuid4()

        webhook_repo.get = AsyncMock(return_value=None)

        result = await webhook_repo.increment_retry_count(webhook_id)

        assert result is None
        webhook_repo.db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_old_webhooks(self, webhook_repo):
        """Test cleaning up old webhook events."""
        old_webhooks = [
            WebhookEvent(id=uuid4(), status=WebhookStatus.PROCESSED),
            WebhookEvent(id=uuid4(), status=WebhookStatus.PROCESSED),
        ]

        webhook_repo.get_multi_by_filters = AsyncMock(return_value=old_webhooks)
        webhook_repo.delete = AsyncMock()

        result = await webhook_repo.cleanup_old_webhooks(days_old=30, keep_failed=True)

        assert result == 2
        webhook_repo.get_multi_by_filters.assert_called_once()
        assert webhook_repo.delete.call_count == 2

        # Verify delete was called for each webhook
        delete_calls = webhook_repo.delete.call_args_list
        assert delete_calls[0][0][0] == old_webhooks[0].id
        assert delete_calls[1][0][0] == old_webhooks[1].id

    @pytest.mark.asyncio
    async def test_cleanup_old_webhooks_no_webhooks(self, webhook_repo):
        """Test cleanup when no old webhooks exist."""
        webhook_repo.get_multi_by_filters = AsyncMock(return_value=[])

        result = await webhook_repo.cleanup_old_webhooks(days_old=30)

        assert result == 0
        webhook_repo.delete.assert_not_called()
