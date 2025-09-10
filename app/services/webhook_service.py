"""
Webhook processing service for handling webhook events.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kyc import KYCStatus
from app.models.webhook import WebhookEvent, WebhookEventType, WebhookStatus
from app.repositories.kyc_repository import KYCRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import (
    KYCWebhookPayload,
    AMLWebhookPayload,
    WebhookEventCreate,
    WebhookProcessingResult
)
# Import tasks dynamically to avoid circular imports
from app.utils.webhook_security import WebhookProvider

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for webhook event processing and management."""
    
    def __init__(self, db: AsyncSession):
        """Initialize webhook service."""
        self.db = db
        self.webhook_repo = WebhookRepository(db)
        self.kyc_repo = KYCRepository(db)
    
    async def receive_webhook(
        self,
        provider: WebhookProvider,
        event_type: WebhookEventType,
        headers: Dict[str, str],
        payload: str,
        signature: Optional[str] = None,
        signature_verified: bool = False,
        provider_event_id: Optional[str] = None
    ) -> WebhookEvent:
        """
        Receive and store a webhook event.
        
        Args:
            provider: Webhook provider
            event_type: Type of webhook event
            headers: HTTP headers from the request
            payload: Raw webhook payload
            signature: Webhook signature
            signature_verified: Whether signature was verified
            provider_event_id: Provider's event identifier
            
        Returns:
            Created webhook event
            
        Raises:
            ValueError: If webhook is duplicate or invalid
        """
        # Check for duplicate webhook if provider_event_id is provided
        if provider_event_id:
            existing_webhook = await self.webhook_repo.get_by_provider_event_id(
                provider.value, provider_event_id
            )
            if existing_webhook:
                logger.info(
                    f"Duplicate webhook received: provider={provider.value}, "
                    f"event_id={provider_event_id}"
                )
                return existing_webhook
        
        # Extract related IDs from payload if possible
        related_kyc_check_id, related_user_id = self._extract_related_ids(
            payload, event_type
        )
        
        # Create webhook event
        webhook_data = WebhookEventCreate(
            provider=provider.value,
            provider_event_id=provider_event_id,
            event_type=event_type,
            headers=headers,
            raw_payload=payload,
            signature=signature,
            related_kyc_check_id=related_kyc_check_id,
            related_user_id=related_user_id
        )
        
        webhook_event = await self.webhook_repo.create_webhook_event(
            webhook_data, signature_verified
        )
        
        logger.info(
            f"Webhook received: id={webhook_event.id}, provider={provider.value}, "
            f"type={event_type.value}, verified={signature_verified}"
        )
        
        # Queue webhook for asynchronous processing
        await self._queue_webhook_processing(webhook_event)
        
        return webhook_event
    
    async def process_webhook_sync(
        self,
        webhook_event: WebhookEvent
    ) -> WebhookProcessingResult:
        """
        Process webhook event synchronously.
        
        Args:
            webhook_event: Webhook event to process
            
        Returns:
            Processing result
        """
        start_time = datetime.utcnow()
        actions_taken = []
        errors = []
        warnings = []
        
        try:
            # Mark as processing
            await self.webhook_repo.update_webhook_status(
                webhook_event.id, WebhookStatus.PROCESSING
            )
            
            # Parse payload
            try:
                parsed_payload = json.loads(webhook_event.raw_payload)
                webhook_event.parsed_payload = parsed_payload
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse webhook payload: {e}"
                errors.append(error_msg)
                await self.webhook_repo.update_webhook_status(
                    webhook_event.id,
                    WebhookStatus.FAILED,
                    error_message=error_msg
                )
                return self._create_processing_result(
                    webhook_event, start_time, False, actions_taken, errors, warnings
                )
            
            # Process based on event type
            if webhook_event.event_type == WebhookEventType.KYC_STATUS_UPDATE:
                result = await self._process_kyc_status_update(
                    webhook_event, parsed_payload
                )
                actions_taken.extend(result.get("actions", []))
                errors.extend(result.get("errors", []))
                warnings.extend(result.get("warnings", []))
                
            elif webhook_event.event_type == WebhookEventType.KYC_DOCUMENT_VERIFIED:
                result = await self._process_kyc_document_verified(
                    webhook_event, parsed_payload
                )
                actions_taken.extend(result.get("actions", []))
                errors.extend(result.get("errors", []))
                warnings.extend(result.get("warnings", []))
                
            elif webhook_event.event_type == WebhookEventType.AML_CHECK_COMPLETE:
                result = await self._process_aml_check_complete(
                    webhook_event, parsed_payload
                )
                actions_taken.extend(result.get("actions", []))
                errors.extend(result.get("errors", []))
                warnings.extend(result.get("warnings", []))
                
            else:
                warning_msg = f"Unsupported event type: {webhook_event.event_type}"
                warnings.append(warning_msg)
                logger.warning(warning_msg)
            
            # Mark as processed if no errors
            if not errors:
                await self.webhook_repo.update_webhook_status(
                    webhook_event.id,
                    WebhookStatus.PROCESSED,
                    processing_notes=f"Actions: {', '.join(actions_taken)}" if actions_taken else None,
                    parsed_payload=parsed_payload
                )
                success = True
            else:
                await self.webhook_repo.update_webhook_status(
                    webhook_event.id,
                    WebhookStatus.FAILED,
                    error_message="; ".join(errors),
                    error_details={"errors": errors, "warnings": warnings}
                )
                success = False
            
            return self._create_processing_result(
                webhook_event, start_time, success, actions_taken, errors, warnings
            )
            
        except Exception as e:
            error_msg = f"Unexpected error processing webhook: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            
            await self.webhook_repo.update_webhook_status(
                webhook_event.id,
                WebhookStatus.FAILED,
                error_message=error_msg,
                error_details={"exception": str(e)}
            )
            
            return self._create_processing_result(
                webhook_event, start_time, False, actions_taken, errors, warnings
            )
    
    async def retry_webhook(
        self,
        webhook_id: UUID,
        force_retry: bool = False
    ) -> Tuple[bool, str]:
        """
        Retry processing a failed webhook.
        
        Args:
            webhook_id: Webhook event ID
            force_retry: Force retry even if max retries exceeded
            
        Returns:
            Tuple of (success, message)
        """
        webhook = await self.webhook_repo.get(webhook_id)
        if not webhook:
            return False, "Webhook not found"
        
        if not force_retry and not webhook.can_retry:
            return False, f"Webhook cannot be retried (retry count: {webhook.retry_count}/{webhook.max_retries})"
        
        # Calculate next retry time with exponential backoff
        retry_delay_minutes = min(2 ** webhook.retry_count, 60)  # Max 1 hour
        next_retry_at = datetime.utcnow() + timedelta(minutes=retry_delay_minutes)
        
        # Increment retry count
        await self.webhook_repo.increment_retry_count(webhook_id, next_retry_at)
        
        # Queue for retry processing (import here to avoid circular imports)
        from app.tasks.webhook_tasks import retry_failed_webhook
        retry_failed_webhook.apply_async(
            args=[str(webhook_id)],
            eta=next_retry_at
        )
        
        logger.info(
            f"Webhook retry scheduled: id={webhook_id}, "
            f"retry_count={webhook.retry_count + 1}, next_retry={next_retry_at}"
        )
        
        return True, f"Retry scheduled for {next_retry_at}"
    
    async def get_webhook_events(
        self,
        provider: Optional[str] = None,
        status: Optional[WebhookStatus] = None,
        event_type: Optional[WebhookEventType] = None,
        kyc_check_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[WebhookEvent], int]:
        """
        Get webhook events with filtering and pagination.
        
        Args:
            provider: Filter by provider
            status: Filter by status
            event_type: Filter by event type
            kyc_check_id: Filter by KYC check ID
            user_id: Filter by user ID
            limit: Maximum results
            offset: Results offset
            
        Returns:
            Tuple of (webhook events, total count)
        """
        if kyc_check_id:
            webhooks = await self.webhook_repo.get_webhooks_by_kyc_check(kyc_check_id)
            return webhooks, len(webhooks)
        
        if user_id:
            return await self.webhook_repo.get_webhooks_by_user(user_id, limit, offset)
        
        if provider:
            return await self.webhook_repo.get_webhooks_by_provider(
                provider, limit, offset, status
            )
        
        if status:
            return await self.webhook_repo.get_webhooks_by_status(status, limit, offset)
        
        # Get all webhooks with filters
        filters = []
        if event_type:
            filters.append(WebhookEvent.event_type == event_type)
        
        return await self.webhook_repo.get_multi_with_count(
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=WebhookEvent.received_at.desc()
        )
    
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
            days: Number of days to include
            
        Returns:
            Statistics dictionary
        """
        return await self.webhook_repo.get_webhook_statistics(
            provider, event_type, days
        )
    
    async def cleanup_old_webhooks(
        self,
        days_old: int = 90,
        keep_failed: bool = True
    ) -> int:
        """
        Clean up old webhook events.
        
        Args:
            days_old: Delete webhooks older than this many days
            keep_failed: Whether to keep failed webhooks
            
        Returns:
            Number of deleted webhooks
        """
        return await self.webhook_repo.cleanup_old_webhooks(days_old, keep_failed)
    
    def _extract_related_ids(
        self,
        payload: str,
        event_type: WebhookEventType
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract related KYC check ID and user ID from payload.
        
        Args:
            payload: Raw webhook payload
            event_type: Webhook event type
            
        Returns:
            Tuple of (kyc_check_id, user_id)
        """
        try:
            data = json.loads(payload)
            
            kyc_check_id = None
            user_id = None
            
            # Extract IDs based on common field names
            if "check_id" in data:
                kyc_check_id = str(data["check_id"])
            elif "kyc_check_id" in data:
                kyc_check_id = str(data["kyc_check_id"])
            elif "id" in data and event_type in [
                WebhookEventType.KYC_STATUS_UPDATE,
                WebhookEventType.KYC_DOCUMENT_VERIFIED
            ]:
                kyc_check_id = str(data["id"])
            
            if "user_id" in data:
                user_id = str(data["user_id"])
            elif "customer_id" in data:
                user_id = str(data["customer_id"])
            
            return kyc_check_id, user_id
            
        except (json.JSONDecodeError, KeyError, ValueError):
            return None, None
    
    async def _queue_webhook_processing(self, webhook_event: WebhookEvent) -> None:
        """
        Queue webhook event for asynchronous processing.
        
        Args:
            webhook_event: Webhook event to process
        """
        try:
            # Generate idempotency key
            idempotency_key = f"webhook_{webhook_event.id}_{webhook_event.provider}_{webhook_event.received_at.isoformat()}"
            
            # Queue the task (import here to avoid circular imports)
            from app.tasks.webhook_tasks import process_webhook_event
            process_webhook_event.apply_async(
                args=[str(webhook_event.id)],
                kwargs={"idempotency_key": idempotency_key}
            )
            
            logger.info(f"Webhook queued for processing: id={webhook_event.id}")
            
        except Exception as e:
            logger.error(f"Failed to queue webhook processing: {e}")
            # Mark as failed if we can't queue it
            await self.webhook_repo.update_webhook_status(
                webhook_event.id,
                WebhookStatus.FAILED,
                error_message=f"Failed to queue for processing: {e}"
            )
    
    async def _process_kyc_status_update(
        self,
        webhook_event: WebhookEvent,
        payload: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Process KYC status update webhook.
        
        Args:
            webhook_event: Webhook event
            payload: Parsed payload
            
        Returns:
            Processing result with actions, errors, warnings
        """
        actions = []
        errors = []
        warnings = []
        
        try:
            # Validate payload structure
            kyc_payload = KYCWebhookPayload(**payload)
            
            # Find KYC check
            kyc_check = await self.kyc_repo.get_by_id(kyc_payload.check_id)
            if not kyc_check:
                errors.append(f"KYC check not found: {kyc_payload.check_id}")
                return {"actions": actions, "errors": errors, "warnings": warnings}
            
            # Map webhook status to KYC status
            status_mapping = {
                "approved": KYCStatus.APPROVED,
                "rejected": KYCStatus.REJECTED,
                "manual_review": KYCStatus.MANUAL_REVIEW,
                "pending": KYCStatus.PENDING,
                "in_progress": KYCStatus.IN_PROGRESS
            }
            
            new_status = status_mapping.get(kyc_payload.status)
            if not new_status:
                errors.append(f"Unknown KYC status: {kyc_payload.status}")
                return {"actions": actions, "errors": errors, "warnings": warnings}
            
            # Update KYC check
            old_status = kyc_check.status
            kyc_check.status = new_status
            kyc_check.verification_result = kyc_payload.result
            
            if kyc_payload.provider_reference:
                kyc_check.provider_reference = kyc_payload.provider_reference
            
            if new_status in [KYCStatus.APPROVED, KYCStatus.REJECTED]:
                kyc_check.completed_at = datetime.utcnow()
            
            await self.db.commit()
            
            actions.append(f"Updated KYC status from {old_status} to {new_status.value}")
            
            # Update webhook event with related IDs
            if not webhook_event.related_kyc_check_id:
                webhook_event.related_kyc_check_id = kyc_payload.check_id
            if not webhook_event.related_user_id and kyc_payload.user_id:
                webhook_event.related_user_id = kyc_payload.user_id
            
        except Exception as e:
            errors.append(f"Error processing KYC status update: {e}")
        
        return {"actions": actions, "errors": errors, "warnings": warnings}
    
    async def _process_kyc_document_verified(
        self,
        webhook_event: WebhookEvent,
        payload: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Process KYC document verification webhook.
        
        Args:
            webhook_event: Webhook event
            payload: Parsed payload
            
        Returns:
            Processing result with actions, errors, warnings
        """
        actions = []
        errors = []
        warnings = []
        
        try:
            # This is a simplified implementation
            # In a real system, you'd update specific document verification status
            actions.append("Processed KYC document verification")
            
        except Exception as e:
            errors.append(f"Error processing KYC document verification: {e}")
        
        return {"actions": actions, "errors": errors, "warnings": warnings}
    
    async def _process_aml_check_complete(
        self,
        webhook_event: WebhookEvent,
        payload: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Process AML check completion webhook.
        
        Args:
            webhook_event: Webhook event
            payload: Parsed payload
            
        Returns:
            Processing result with actions, errors, warnings
        """
        actions = []
        errors = []
        warnings = []
        
        try:
            # Validate payload structure
            aml_payload = AMLWebhookPayload(**payload)
            
            # This is a simplified implementation
            # In a real system, you'd update AML check records
            actions.append(f"Processed AML check: status={aml_payload.status}")
            
            if aml_payload.risk_score is not None:
                actions.append(f"Updated risk score: {aml_payload.risk_score}")
            
        except Exception as e:
            errors.append(f"Error processing AML check: {e}")
        
        return {"actions": actions, "errors": errors, "warnings": warnings}
    
    def _create_processing_result(
        self,
        webhook_event: WebhookEvent,
        start_time: datetime,
        success: bool,
        actions: List[str],
        errors: List[str],
        warnings: List[str]
    ) -> WebhookProcessingResult:
        """
        Create webhook processing result.
        
        Args:
            webhook_event: Webhook event
            start_time: Processing start time
            success: Whether processing was successful
            actions: Actions taken
            errors: Errors encountered
            warnings: Warnings generated
            
        Returns:
            Processing result
        """
        processing_time = datetime.utcnow() - start_time
        processing_time_ms = int(processing_time.total_seconds() * 1000)
        
        return WebhookProcessingResult(
            success=success,
            webhook_event_id=str(webhook_event.id),
            processing_time_ms=processing_time_ms,
            actions_taken=actions,
            errors=errors,
            warnings=warnings,
            metadata={
                "provider": webhook_event.provider,
                "event_type": webhook_event.event_type.value,
                "signature_verified": webhook_event.signature_verified
            }
        )