"""
Webhook API endpoints for receiving and managing webhook events.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_user, get_current_user, get_db
from app.api.middleware.webhook_auth import webhook_auth_dependency
from app.models.user import User
from app.models.webhook import WebhookEventType, WebhookStatus
from app.schemas.webhook import (
    WebhookEventListResponse,
    WebhookEventResponse,
    WebhookProcessingResult,
    WebhookRetryRequest,
    WebhookRetryResponse,
    WebhookStatsResponse,
)
from app.services.webhook_service import WebhookService
from app.utils.webhook_security import WebhookProvider

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/kyc/{provider}",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Receive KYC webhook",
    description="Receive webhook notifications from KYC providers",
)
async def receive_kyc_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_data: Dict = Depends(webhook_auth_dependency),
):
    """
    Receive KYC webhook from external providers.

    This endpoint receives webhook notifications from KYC providers and queues them
    for asynchronous processing. The webhook signature is verified by middleware.
    """
    try:
        webhook_provider = WebhookProvider(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported KYC provider: {provider}",
        )

    webhook_service = WebhookService(db)

    try:
        # Determine event type from payload or headers
        event_type = _determine_event_type(auth_data["payload"], auth_data["headers"])

        # Extract provider event ID if available
        provider_event_id = _extract_provider_event_id(
            auth_data["payload"], auth_data["headers"], webhook_provider
        )

        # Receive and store webhook
        webhook_event = await webhook_service.receive_webhook(
            provider=webhook_provider,
            event_type=event_type,
            headers=auth_data["headers"],
            payload=auth_data["payload"],
            signature=auth_data["headers"].get("x-webhook-signature"),
            signature_verified=True,  # Verified by middleware
            provider_event_id=provider_event_id,
        )

        logger.info(
            f"KYC webhook received successfully: id={webhook_event.id}, "
            f"provider={provider}, type={event_type.value}"
        )

        return {
            "status": "received",
            "webhook_id": str(webhook_event.id),
            "message": "Webhook received and queued for processing",
        }

    except Exception as e:
        logger.error(
            f"Error processing KYC webhook from {provider}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook",
        )


@router.post(
    "/aml/{provider}",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Receive AML webhook",
    description="Receive webhook notifications from AML providers",
)
async def receive_aml_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_data: Dict = Depends(webhook_auth_dependency),
):
    """
    Receive AML webhook from external providers.

    This endpoint receives webhook notifications from AML providers and queues them
    for asynchronous processing. The webhook signature is verified by middleware.
    """
    try:
        webhook_provider = WebhookProvider(provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported AML provider: {provider}",
        )

    webhook_service = WebhookService(db)

    try:
        # AML webhooks are typically completion events
        event_type = WebhookEventType.AML_CHECK_COMPLETE

        # Extract provider event ID if available
        provider_event_id = _extract_provider_event_id(
            auth_data["payload"], auth_data["headers"], webhook_provider
        )

        # Receive and store webhook
        webhook_event = await webhook_service.receive_webhook(
            provider=webhook_provider,
            event_type=event_type,
            headers=auth_data["headers"],
            payload=auth_data["payload"],
            signature=auth_data["headers"].get("x-webhook-signature"),
            signature_verified=True,  # Verified by middleware
            provider_event_id=provider_event_id,
        )

        logger.info(
            f"AML webhook received successfully: id={webhook_event.id}, "
            f"provider={provider}, type={event_type.value}"
        )

        return {
            "status": "received",
            "webhook_id": str(webhook_event.id),
            "message": "Webhook received and queued for processing",
        }

    except Exception as e:
        logger.error(
            f"Error processing AML webhook from {provider}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook",
        )


@router.get(
    "/events",
    response_model=WebhookEventListResponse,
    summary="List webhook events",
    description="Get list of webhook events with filtering and pagination",
)
async def list_webhook_events(
    provider: Optional[str] = None,
    status: Optional[WebhookStatus] = None,
    event_type: Optional[WebhookEventType] = None,
    kyc_check_id: Optional[str] = None,
    user_id: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List webhook events with filtering and pagination.

    Regular users can only see webhooks related to their own records.
    Admin users can see all webhooks.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Page must be >= 1"
        )

    if size < 1 or size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Size must be between 1 and 100",
        )

    webhook_service = WebhookService(db)

    # Non-admin users can only see their own webhooks
    if not current_user.is_admin and not user_id:
        user_id = str(current_user.id)
    elif not current_user.is_admin and user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: can only view your own webhook events",
        )

    offset = (page - 1) * size

    webhooks, total = await webhook_service.get_webhook_events(
        provider=provider,
        status=status,
        event_type=event_type,
        kyc_check_id=kyc_check_id,
        user_id=user_id,
        limit=size,
        offset=offset,
    )

    pages = (total + size - 1) // size  # Ceiling division

    return WebhookEventListResponse(
        items=[WebhookEventResponse.from_orm(webhook) for webhook in webhooks],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/events/{webhook_id}",
    response_model=WebhookEventResponse,
    summary="Get webhook event",
    description="Get details of a specific webhook event",
)
async def get_webhook_event(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific webhook event.

    Regular users can only access webhooks related to their own records.
    Admin users can access all webhooks.
    """
    webhook_service = WebhookService(db)
    webhook = await webhook_service.webhook_repo.get(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook event not found"
        )

    # Check access permissions
    if not current_user.is_admin:
        if webhook.related_user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: can only view your own webhook events",
            )

    return WebhookEventResponse.from_orm(webhook)


@router.post(
    "/events/{webhook_id}/retry",
    response_model=WebhookRetryResponse,
    summary="Retry webhook processing",
    description="Retry processing of a failed webhook event",
)
async def retry_webhook_event(
    webhook_id: UUID,
    retry_request: WebhookRetryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Retry processing of a failed webhook event.

    Only admin users can retry webhook processing.
    """
    webhook_service = WebhookService(db)
    webhook = await webhook_service.webhook_repo.get(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook event not found"
        )

    success, message = await webhook_service.retry_webhook(
        webhook_id, retry_request.force_retry
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    # Refresh webhook to get updated retry info
    await db.refresh(webhook)

    return WebhookRetryResponse(
        webhook_event_id=str(webhook_id),
        retry_scheduled=True,
        retry_count=webhook.retry_count,
        next_retry_at=webhook.next_retry_at,
        message=message,
    )


@router.post(
    "/events/{webhook_id}/process",
    response_model=WebhookProcessingResult,
    summary="Process webhook synchronously",
    description="Process a webhook event synchronously (for testing/debugging)",
)
async def process_webhook_sync(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Process a webhook event synchronously.

    This endpoint is primarily for testing and debugging purposes.
    Only admin users can trigger synchronous processing.
    """
    webhook_service = WebhookService(db)
    webhook = await webhook_service.webhook_repo.get(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Webhook event not found"
        )

    try:
        result = await webhook_service.process_webhook_sync(webhook)
        return result
    except Exception as e:
        logger.error(f"Error in synchronous webhook processing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing error: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=WebhookStatsResponse,
    summary="Get webhook statistics",
    description="Get webhook processing statistics",
)
async def get_webhook_statistics(
    provider: Optional[str] = None,
    event_type: Optional[WebhookEventType] = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get webhook processing statistics.

    Only admin users can access webhook statistics.
    """
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365",
        )

    webhook_service = WebhookService(db)
    stats = await webhook_service.get_webhook_statistics(
        provider=provider, event_type=event_type, days=days
    )

    return WebhookStatsResponse(**stats)


@router.delete(
    "/cleanup",
    response_model=Dict[str, int],
    summary="Clean up old webhooks",
    description="Clean up old webhook events",
)
async def cleanup_old_webhooks(
    days_old: int = 90,
    keep_failed: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Clean up old webhook events.

    Only admin users can perform cleanup operations.
    """
    if days_old < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="days_old must be >= 1"
        )

    webhook_service = WebhookService(db)
    deleted_count = await webhook_service.cleanup_old_webhooks(
        days_old=days_old, keep_failed=keep_failed
    )

    return {
        "deleted_count": deleted_count,
        "days_old": days_old,
        "kept_failed": keep_failed,
    }


def _determine_event_type(payload: str, headers: Dict[str, str]) -> WebhookEventType:
    """
    Determine webhook event type from payload or headers.

    Args:
        payload: Webhook payload
        headers: HTTP headers

    Returns:
        WebhookEventType
    """
    # Check headers for event type hints
    event_type_header = headers.get("x-event-type", "").lower()
    if "document" in event_type_header:
        return WebhookEventType.KYC_DOCUMENT_VERIFIED
    elif "status" in event_type_header:
        return WebhookEventType.KYC_STATUS_UPDATE
    elif "manual" in event_type_header or "review" in event_type_header:
        return WebhookEventType.MANUAL_REVIEW_REQUIRED
    elif "expired" in event_type_header:
        return WebhookEventType.VERIFICATION_EXPIRED

    # Try to parse payload to determine type
    try:
        import json

        data = json.loads(payload)

        # Look for status field to determine if it's a status update
        if "status" in data:
            status = data["status"].lower()
            if status == "manual_review":
                return WebhookEventType.MANUAL_REVIEW_REQUIRED
            elif status in ["approved", "rejected", "pending", "in_progress"]:
                return WebhookEventType.KYC_STATUS_UPDATE

        # Look for document-related fields
        if "document" in data or "documents" in data:
            return WebhookEventType.KYC_DOCUMENT_VERIFIED

    except (json.JSONDecodeError, KeyError):
        pass

    # Default to status update
    return WebhookEventType.KYC_STATUS_UPDATE


def _extract_provider_event_id(
    payload: str, headers: Dict[str, str], provider: WebhookProvider
) -> Optional[str]:
    """
    Extract provider event ID from payload or headers.

    Args:
        payload: Webhook payload
        headers: HTTP headers
        provider: Webhook provider

    Returns:
        Provider event ID if found
    """
    # Check headers first
    event_id_headers = [
        "x-event-id",
        "x-webhook-id",
        "x-request-id",
        f"x-{provider.value}-event-id",
    ]

    for header in event_id_headers:
        if header in headers:
            return headers[header]

    # Try to extract from payload
    try:
        import json

        data = json.loads(payload)

        # Common field names for event IDs
        id_fields = ["event_id", "webhook_id", "id", "reference_id"]
        for field in id_fields:
            if field in data:
                return str(data[field])

    except (json.JSONDecodeError, KeyError):
        pass

    return None


# Webhook simulation endpoints for testing and development
@router.post(
    "/simulate/kyc",
    response_model=Dict[str, str],
    summary="Simulate KYC webhook",
    description="Simulate a KYC webhook for testing purposes",
)
async def simulate_kyc_webhook(
    kyc_check_id: str,
    user_id: str,
    provider_type: str,
    provider_reference: str,
    outcome: str,
    webhook_url: Optional[str] = None,
    delay_seconds: Optional[float] = None,
    immediate: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Simulate a KYC webhook for testing purposes.

    This endpoint allows admin users to simulate webhook callbacks from KYC providers
    for testing and development purposes.

    Args:
        kyc_check_id: KYC check identifier
        user_id: User identifier
        provider_type: Provider type (jumio, onfido, veriff, shufti_pro)
        provider_reference: Provider reference ID
        outcome: Verification outcome (approved,
            rejected,
            manual_review,
            pending,
            error)
        webhook_url: Optional custom webhook URL (defaults to local webhook endpoint)
        delay_seconds: Optional custom delay before sending (ignored if immediate=True)
        immediate: If True, send webhook immediately without delay
    """
    from app.tasks.webhook_tasks import (
        send_immediate_webhook,
        simulate_provider_webhook,
    )

    # Validate provider type
    valid_providers = ["jumio", "onfido", "veriff", "shufti_pro"]
    if provider_type not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider_type. Must be one of: {valid_providers}",
        )

    # Validate outcome
    valid_outcomes = ["approved", "rejected", "manual_review", "pending", "error"]
    if outcome not in valid_outcomes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid outcome. Must be one of: {valid_outcomes}",
        )

    try:
        if immediate:
            # Send webhook immediately
            task_result = send_immediate_webhook.apply_async(
                args=[
                    kyc_check_id,
                    user_id,
                    provider_type,
                    provider_reference,
                    outcome,
                ],
                kwargs={"webhook_url": webhook_url},
            )

            return {
                "status": "sent",
                "task_id": task_result.id,
                "message": "Webhook sent immediately",
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome,
            }
        else:
            # Schedule webhook with delay
            task_result = simulate_provider_webhook.apply_async(
                args=[
                    kyc_check_id,
                    user_id,
                    provider_type,
                    provider_reference,
                    outcome,
                ],
                kwargs={"webhook_url": webhook_url, "delay_seconds": delay_seconds},
            )

            return {
                "status": "scheduled",
                "task_id": task_result.id,
                "message": "Webhook scheduled for delivery",
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome,
                "delay_seconds": delay_seconds,
            }

    except Exception as e:
        logger.error(f"Error simulating KYC webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to simulate webhook: {str(e)}",
        )


@router.get(
    "/simulate/stats",
    response_model=Dict[str, Any],
    summary="Get webhook simulation statistics",
    description="Get statistics about webhook simulation and delivery",
)
async def get_webhook_simulation_stats(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Get webhook simulation statistics.

    This endpoint provides statistics about webhook simulation including
    delivery success rates, timing, and provider-specific metrics.
    """
    from app.services.mock_webhook_sender import mock_webhook_sender

    try:
        stats = mock_webhook_sender.get_delivery_statistics()
        scheduled_webhooks = mock_webhook_sender.get_scheduled_webhooks()

        # Add scheduled webhook summary
        scheduled_summary = {
            "total_scheduled": len(scheduled_webhooks),
            "by_status": {},
        }

        for webhook in scheduled_webhooks:
            status = webhook.get("status", "unknown")
            scheduled_summary["by_status"][status] = (
                scheduled_summary["by_status"].get(status, 0) + 1
            )

        return {
            "delivery_stats": stats,
            "scheduled_webhooks": scheduled_summary,
            "simulation_active": True,
        }

    except Exception as e:
        logger.error(f"Error getting webhook simulation stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get simulation stats: {str(e)}",
        )


@router.post(
    "/simulate/clear",
    response_model=Dict[str, str],
    summary="Clear webhook simulation history",
    description="Clear webhook simulation history and scheduled webhooks",
)
async def clear_webhook_simulation_history(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Clear webhook simulation history and scheduled webhooks.

    This endpoint clears all webhook simulation history and cancels
    any scheduled webhooks. Useful for testing cleanup.
    """
    from app.services.mock_webhook_sender import mock_webhook_sender

    try:
        mock_webhook_sender.clear_history()

        return {
            "status": "cleared",
            "message": "Webhook simulation history and scheduled webhooks cleared",
        }

    except Exception as e:
        logger.error(f"Error clearing webhook simulation history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear simulation history: {str(e)}",
        )


@router.get(
    "/simulate/scheduled",
    response_model=List[Dict[str, Any]],
    summary="List scheduled webhooks",
    description="Get list of currently scheduled webhook simulations",
)
async def list_scheduled_webhooks(
    status: Optional[str] = None, current_user: User = Depends(get_current_admin_user)
):
    """
    Get list of currently scheduled webhook simulations.

    Args:
        status: Optional status filter (scheduled, sending, completed, failed, error)
    """
    from app.services.mock_webhook_sender import mock_webhook_sender

    try:
        scheduled_webhooks = mock_webhook_sender.get_scheduled_webhooks(status)

        # Convert datetime objects to ISO strings for JSON serialization
        for webhook in scheduled_webhooks:
            if "scheduled_time" in webhook and webhook["scheduled_time"]:
                webhook["scheduled_time"] = webhook["scheduled_time"].isoformat()
            if "created_at" in webhook and webhook["created_at"]:
                webhook["created_at"] = webhook["created_at"].isoformat()

        return scheduled_webhooks

    except Exception as e:
        logger.error(f"Error listing scheduled webhooks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scheduled webhooks: {str(e)}",
        )
