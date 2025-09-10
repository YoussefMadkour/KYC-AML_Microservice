"""
Webhook event repository for database operations.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.webhook import WebhookEvent, WebhookEventType, WebhookStatus
from app.repositories.base import BaseRepository
from app.schemas.webhook import WebhookEventCreate, WebhookEventUpdate

logger = logging.getLogger(__name__)


class WebhookRepository(BaseRepository[WebhookEvent, WebhookEventCreate, WebhookEventUpdate]):
    """Repository for webhook event operations."""
    
    def __init__(self, db: AsyncSession):
        """Initialize webhook repository."""
        super().__init__(WebhookEvent, db)
    
    async def create_webhook_event(
        self,
        webhook_data: WebhookEventCreate,
        signature_verified: bool = False
    ) -> WebhookEvent:
        """
        Create a new webhook event.
        
        Args:
            webhook_data: Webhook event creation data
            signature_verified: Whether the webhook signature was verified
            
        Returns:
            Created webhook event
        """
        webhook_event = WebhookEvent(
            provider=webhook_data.provider,
            provider_event_id=webhook_data.provider_event_id,
            event_type=webhook_data.event_type,
            http_method=webhook_data.http_method,
            headers=webhook_data.headers,
            raw_payload=webhook_data.raw_payload,
            signature=webhook_data.signature,
            signature_verified=signature_verified,
            status=WebhookStatus.PENDING,
            related_kyc_check_id=webhook_data.related_kyc_check_id,
            related_user_id=webhook_data.related_user_id,
            received_at=datetime.utcnow()
        )
        
        return await self.create(webhook_event)
    
    async def get_by_provider_event_id(
        self,
        provider: str,
        provider_event_id: str
    ) -> Optional[WebhookEvent]:
        """
        Get webhook event by provider and provider event ID.
        
        Args:
            provider: Webhook provider name
            provider_event_id: Provider's event identifier
            
        Returns:
            Webhook event if found, None otherwise
        """
        return await self.get_by_filters(
            provider=provider,
            provider_event_id=provider_event_id
        )
    
    async def get_pending_webhooks(
        self,
        limit: int = 100,
        older_than_minutes: Optional[int] = None
    ) -> List[WebhookEvent]:
        """
        Get pending webhook events for processing.
        
        Args:
            limit: Maximum number of webhooks to return
            older_than_minutes: Only return webhooks older than this many minutes
            
        Returns:
            List of pending webhook events
        """
        filters = [WebhookEvent.status == WebhookStatus.PENDING]
        
        if older_than_minutes:
            cutoff_time = datetime.utcnow() - timedelta(minutes=older_than_minutes)
            filters.append(WebhookEvent.received_at <= cutoff_time)
        
        return await self.get_multi_by_filters(
            *filters,
            limit=limit,
            order_by=WebhookEvent.received_at
        )
    
    async def get_failed_webhooks_for_retry(
        self,
        limit: int = 50
    ) -> List[WebhookEvent]:
        """
        Get failed webhook events that can be retried.
        
        Args:
            limit: Maximum number of webhooks to return
            
        Returns:
            List of webhook events eligible for retry
        """
        current_time = datetime.utcnow()
        
        filters = [
            or_(
                WebhookEvent.status == WebhookStatus.FAILED,
                WebhookEvent.status == WebhookStatus.RETRYING
            ),
            WebhookEvent.retry_count < WebhookEvent.max_retries,
            or_(
                WebhookEvent.next_retry_at.is_(None),
                WebhookEvent.next_retry_at <= current_time
            )
        ]
        
        return await self.get_multi_by_filters(
            *filters,
            limit=limit,
            order_by=WebhookEvent.next_retry_at
        )
    
    async def get_webhooks_by_status(
        self,
        status: WebhookStatus,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[WebhookEvent], int]:
        """
        Get webhook events by status with pagination.
        
        Args:
            status: Webhook status to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Tuple of (webhook events, total count)
        """
        return await self.get_multi_with_count(
            filters=[WebhookEvent.status == status],
            limit=limit,
            offset=offset,
            order_by=desc(WebhookEvent.received_at)
        )
    
    async def get_webhooks_by_provider(
        self,
        provider: str,
        limit: int = 100,
        offset: int = 0,
        status: Optional[WebhookStatus] = None
    ) -> Tuple[List[WebhookEvent], int]:
        """
        Get webhook events by provider with pagination.
        
        Args:
            provider: Provider name to filter by
            limit: Maximum number of results
            offset: Number of results to skip
            status: Optional status filter
            
        Returns:
            Tuple of (webhook events, total count)
        """
        filters = [WebhookEvent.provider == provider]
        if status:
            filters.append(WebhookEvent.status == status)
        
        return await self.get_multi_with_count(
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=desc(WebhookEvent.received_at)
        )
    
    async def get_webhooks_by_kyc_check(
        self,
        kyc_check_id: str
    ) -> List[WebhookEvent]:
        """
        Get all webhook events related to a KYC check.
        
        Args:
            kyc_check_id: KYC check identifier
            
        Returns:
            List of related webhook events
        """
        return await self.get_multi_by_filters(
            WebhookEvent.related_kyc_check_id == kyc_check_id,
            order_by=WebhookEvent.received_at
        )
    
    async def get_webhooks_by_user(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[WebhookEvent], int]:
        """
        Get webhook events related to a user with pagination.
        
        Args:
            user_id: User identifier
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            Tuple of (webhook events, total count)
        """
        return await self.get_multi_with_count(
            filters=[WebhookEvent.related_user_id == user_id],
            limit=limit,
            offset=offset,
            order_by=desc(WebhookEvent.received_at)
        )
    
    async def update_webhook_status(
        self,
        webhook_id: UUID,
        status: WebhookStatus,
        error_message: Optional[str] = None,
        error_details: Optional[Dict] = None,
        processing_notes: Optional[str] = None,
        parsed_payload: Optional[Dict] = None
    ) -> Optional[WebhookEvent]:
        """
        Update webhook event status and related fields.
        
        Args:
            webhook_id: Webhook event ID
            status: New status
            error_message: Error message if applicable
            error_details: Detailed error information
            processing_notes: Processing notes
            parsed_payload: Parsed payload data
            
        Returns:
            Updated webhook event or None if not found
        """
        webhook = await self.get(webhook_id)
        if not webhook:
            return None
        
        # Update status-specific fields
        if status == WebhookStatus.PROCESSING:
            webhook.mark_as_processing()
        elif status == WebhookStatus.PROCESSED:
            webhook.mark_as_processed(processing_notes)
        elif status == WebhookStatus.FAILED:
            webhook.mark_as_failed(error_message or "Processing failed", error_details)
        else:
            webhook.status = status
            webhook.updated_at = datetime.utcnow()
        
        # Update additional fields
        if parsed_payload is not None:
            webhook.parsed_payload = parsed_payload
        if processing_notes and status != WebhookStatus.PROCESSED:
            webhook.processing_notes = processing_notes
        
        await self.db.commit()
        await self.db.refresh(webhook)
        return webhook
    
    async def increment_retry_count(
        self,
        webhook_id: UUID,
        next_retry_at: Optional[datetime] = None
    ) -> Optional[WebhookEvent]:
        """
        Increment retry count for a webhook event.
        
        Args:
            webhook_id: Webhook event ID
            next_retry_at: Next retry timestamp
            
        Returns:
            Updated webhook event or None if not found
        """
        webhook = await self.get(webhook_id)
        if not webhook:
            return None
        
        webhook.increment_retry(next_retry_at)
        await self.db.commit()
        await self.db.refresh(webhook)
        return webhook
    
    async def get_webhook_statistics(
        self,
        provider: Optional[str] = None,
        event_type: Optional[WebhookEventType] = None,
        days: int = 30
    ) -> Dict:
        """
        Get webhook processing statistics.
        
        Args:
            provider: Optional provider filter
            event_type: Optional event type filter
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Build base query
        query = self.db.query(WebhookEvent).filter(
            WebhookEvent.received_at >= cutoff_date
        )
        
        if provider:
            query = query.filter(WebhookEvent.provider == provider)
        if event_type:
            query = query.filter(WebhookEvent.event_type == event_type)
        
        # Get status counts
        status_counts = await self.db.execute(
            query.with_entities(
                WebhookEvent.status,
                func.count(WebhookEvent.id).label('count')
            ).group_by(WebhookEvent.status)
        )
        
        status_stats = {status: count for status, count in status_counts}
        
        # Get provider stats if not filtered by provider
        provider_stats = {}
        if not provider:
            provider_counts = await self.db.execute(
                self.db.query(WebhookEvent).filter(
                    WebhookEvent.received_at >= cutoff_date
                ).with_entities(
                    WebhookEvent.provider,
                    WebhookEvent.status,
                    func.count(WebhookEvent.id).label('count')
                ).group_by(WebhookEvent.provider, WebhookEvent.status)
            )
            
            for prov, status, count in provider_counts:
                if prov not in provider_stats:
                    provider_stats[prov] = {}
                provider_stats[prov][status.value] = count
        
        # Get event type stats if not filtered by event type
        event_type_stats = {}
        if not event_type:
            event_type_counts = await self.db.execute(
                self.db.query(WebhookEvent).filter(
                    WebhookEvent.received_at >= cutoff_date
                ).with_entities(
                    WebhookEvent.event_type,
                    WebhookEvent.status,
                    func.count(WebhookEvent.id).label('count')
                ).group_by(WebhookEvent.event_type, WebhookEvent.status)
            )
            
            for evt_type, status, count in event_type_counts:
                if evt_type not in event_type_stats:
                    event_type_stats[evt_type] = {}
                event_type_stats[evt_type][status.value] = count
        
        # Calculate average processing time
        avg_processing_time = await self.db.execute(
            query.filter(
                WebhookEvent.processed_at.isnot(None)
            ).with_entities(
                func.avg(
                    func.extract('epoch', WebhookEvent.processed_at - WebhookEvent.received_at)
                ).label('avg_seconds')
            )
        )
        
        avg_time_seconds = avg_processing_time.scalar()
        avg_time_ms = int(avg_time_seconds * 1000) if avg_time_seconds else None
        
        # Calculate totals
        total_events = sum(status_stats.values())
        processed_events = status_stats.get(WebhookStatus.PROCESSED, 0)
        success_rate = (processed_events / total_events * 100) if total_events > 0 else 0
        
        return {
            "total_events": total_events,
            "processed_events": processed_events,
            "failed_events": status_stats.get(WebhookStatus.FAILED, 0),
            "pending_events": status_stats.get(WebhookStatus.PENDING, 0),
            "retrying_events": status_stats.get(WebhookStatus.RETRYING, 0),
            "average_processing_time_ms": avg_time_ms,
            "success_rate": round(success_rate, 2),
            "status_breakdown": status_stats,
            "provider_stats": provider_stats,
            "event_type_stats": event_type_stats
        }
    
    async def cleanup_old_webhooks(
        self,
        days_old: int = 90,
        keep_failed: bool = True
    ) -> int:
        """
        Clean up old webhook events.
        
        Args:
            days_old: Delete webhooks older than this many days
            keep_failed: Whether to keep failed webhooks for debugging
            
        Returns:
            Number of deleted webhook events
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        filters = [WebhookEvent.received_at < cutoff_date]
        
        if keep_failed:
            filters.append(WebhookEvent.status != WebhookStatus.FAILED)
        
        # Get webhooks to delete
        webhooks_to_delete = await self.get_multi_by_filters(*filters)
        
        if not webhooks_to_delete:
            return 0
        
        # Delete webhooks
        for webhook in webhooks_to_delete:
            await self.delete(webhook.id)
        
        logger.info(f"Cleaned up {len(webhooks_to_delete)} old webhook events")
        return len(webhooks_to_delete)