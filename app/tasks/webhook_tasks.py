"""
Webhook processing tasks.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from app.database import SessionLocal
from app.services.webhook_service import WebhookService
from app.services.mock_webhook_sender import mock_webhook_sender
from app.services.mock_provider import ProviderType, VerificationOutcome
from app.worker import celery_app
from app.tasks.base import WebhookTask, TaskResult

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async functions in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


@celery_app.task(base=WebhookTask, bind=True)
def process_webhook_event(self, webhook_event_id: str, **kwargs) -> Dict[str, Any]:
    """
    Process webhook event asynchronously.
    
    Args:
        webhook_event_id: The ID of the webhook event to process
        **kwargs: Additional task parameters including idempotency_key
        
    Returns:
        Task result dictionary
    """
    logger.info(f"Processing webhook event {webhook_event_id}")
    
    db = SessionLocal()
    try:
        webhook_service = WebhookService(db)
        
        # Get webhook event
        webhook_event = run_async(webhook_service.webhook_repo.get(UUID(webhook_event_id)))
        if not webhook_event:
            error_msg = f"Webhook event not found: {webhook_event_id}"
            logger.error(error_msg)
            return TaskResult.error_result(
                error=error_msg,
                data={"webhook_event_id": webhook_event_id},
                metadata={
                    "task_id": self.request.id,
                    "idempotency_key": kwargs.get("idempotency_key")
                }
            ).to_dict()
        
        # Process webhook synchronously
        processing_result = run_async(webhook_service.process_webhook_sync(webhook_event))
        
        if processing_result.success:
            result = TaskResult.success_result(
                data={
                    "webhook_event_id": webhook_event_id,
                    "processing_time_ms": processing_result.processing_time_ms,
                    "actions_taken": processing_result.actions_taken
                },
                metadata={
                    "task_id": self.request.id,
                    "idempotency_key": kwargs.get("idempotency_key"),
                    "provider": processing_result.metadata.get("provider"),
                    "event_type": processing_result.metadata.get("event_type")
                }
            )
        else:
            result = TaskResult.error_result(
                error="; ".join(processing_result.errors),
                data={
                    "webhook_event_id": webhook_event_id,
                    "processing_time_ms": processing_result.processing_time_ms,
                    "errors": processing_result.errors,
                    "warnings": processing_result.warnings
                },
                metadata={
                    "task_id": self.request.id,
                    "idempotency_key": kwargs.get("idempotency_key")
                }
            )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Error processing webhook event {webhook_event_id}: {e}", exc_info=True)
        result = TaskResult.error_result(
            error=str(e),
            data={"webhook_event_id": webhook_event_id},
            metadata={
                "task_id": self.request.id,
                "idempotency_key": kwargs.get("idempotency_key")
            }
        )
        return result.to_dict()
    finally:
        db.close()


@celery_app.task(base=WebhookTask, bind=True)
def retry_failed_webhook(self, webhook_event_id: str, **kwargs) -> Dict[str, Any]:
    """
    Retry processing of a failed webhook event.
    
    Args:
        webhook_event_id: The ID of the webhook event to retry
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary
    """
    logger.info(f"Retrying webhook event {webhook_event_id}")
    
    db = SessionLocal()
    try:
        webhook_service = WebhookService(db)
        
        # Get webhook event
        webhook_event = run_async(webhook_service.webhook_repo.get(UUID(webhook_event_id)))
        if not webhook_event:
            error_msg = f"Webhook event not found: {webhook_event_id}"
            logger.error(error_msg)
            return TaskResult.error_result(
                error=error_msg,
                data={"webhook_event_id": webhook_event_id},
                metadata={"task_id": self.request.id}
            ).to_dict()
        
        # Check if webhook can be retried
        if not webhook_event.can_retry:
            error_msg = f"Webhook cannot be retried: retry_count={webhook_event.retry_count}, max_retries={webhook_event.max_retries}"
            logger.warning(error_msg)
            return TaskResult.error_result(
                error=error_msg,
                data={"webhook_event_id": webhook_event_id},
                metadata={"task_id": self.request.id}
            ).to_dict()
        
        # Process webhook synchronously
        processing_result = run_async(webhook_service.process_webhook_sync(webhook_event))
        
        if processing_result.success:
            result = TaskResult.success_result(
                data={
                    "webhook_event_id": webhook_event_id,
                    "retry_count": webhook_event.retry_count,
                    "processing_time_ms": processing_result.processing_time_ms,
                    "actions_taken": processing_result.actions_taken
                },
                metadata={
                    "task_id": self.request.id,
                    "retry_attempt": True
                }
            )
        else:
            # If retry failed, schedule another retry if possible
            if webhook_event.retry_count < webhook_event.max_retries:
                run_async(webhook_service.retry_webhook(UUID(webhook_event_id)))
            
            result = TaskResult.error_result(
                error="; ".join(processing_result.errors),
                data={
                    "webhook_event_id": webhook_event_id,
                    "retry_count": webhook_event.retry_count,
                    "processing_time_ms": processing_result.processing_time_ms,
                    "errors": processing_result.errors,
                    "warnings": processing_result.warnings
                },
                metadata={
                    "task_id": self.request.id,
                    "retry_attempt": True
                }
            )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Error retrying webhook event {webhook_event_id}: {e}", exc_info=True)
        result = TaskResult.error_result(
            error=str(e),
            data={"webhook_event_id": webhook_event_id},
            metadata={
                "task_id": self.request.id,
                "retry_attempt": True
            }
        )
        return result.to_dict()
    finally:
        db.close()


@celery_app.task(base=WebhookTask, bind=True)
def simulate_provider_webhook(
    self,
    kyc_check_id: str,
    user_id: str,
    provider_type: str,
    provider_reference: str,
    outcome: str,
    webhook_url: str = None,
    delay_seconds: float = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Simulate a webhook from an external KYC provider.
    
    This task simulates the webhook callback that would normally be sent
    by an external KYC provider after processing is complete.
    
    Args:
        kyc_check_id: KYC check identifier
        user_id: User identifier
        provider_type: Provider type (jumio, onfido, etc.)
        provider_reference: Provider reference ID
        outcome: Verification outcome (approved, rejected, manual_review)
        webhook_url: Optional custom webhook URL
        delay_seconds: Optional custom delay before sending
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Simulating provider webhook",
        extra={
            "kyc_check_id": kyc_check_id,
            "provider_type": provider_type,
            "outcome": outcome,
            "task_id": task_id,
            "correlation_id": correlation_id
        }
    )
    
    try:
        # Convert string parameters to enums
        try:
            provider_enum = ProviderType(provider_type)
            outcome_enum = VerificationOutcome(outcome)
        except ValueError as e:
            error_msg = f"Invalid parameter: {str(e)}"
            logger.error(error_msg)
            return TaskResult.error_result(
                error=error_msg,
                data={
                    "kyc_check_id": kyc_check_id,
                    "provider_type": provider_type,
                    "outcome": outcome
                },
                metadata={"task_id": task_id, "correlation_id": correlation_id}
            ).to_dict()
        
        # Schedule webhook with mock sender
        webhook_schedule_id = run_async(
            mock_webhook_sender.schedule_webhook(
                kyc_check_id=kyc_check_id,
                user_id=user_id,
                provider_type=provider_enum,
                provider_reference=provider_reference,
                outcome=outcome_enum,
                webhook_url=webhook_url,
                custom_delay=delay_seconds
            )
        )
        
        result_data = {
            "webhook_schedule_id": webhook_schedule_id,
            "kyc_check_id": kyc_check_id,
            "provider_type": provider_type,
            "outcome": outcome,
            "provider_reference": provider_reference,
            "webhook_url": webhook_url,
            "delay_seconds": delay_seconds,
            "scheduled_at": datetime.utcnow().isoformat()
        }
        
        result = TaskResult.success_result(
            data=result_data,
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "webhook_schedule_id": webhook_schedule_id
            }
        )
        
        logger.info(
            f"Provider webhook simulation scheduled",
            extra={
                "webhook_schedule_id": webhook_schedule_id,
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome,
                "task_id": task_id
            }
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error simulating provider webhook: {str(e)}",
            extra={
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome,
                "task_id": task_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        result = TaskResult.error_result(
            error=str(e),
            data={
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome
            },
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id
            }
        )
        
        return result.to_dict()


@celery_app.task(base=WebhookTask, bind=True)
def send_immediate_webhook(
    self,
    kyc_check_id: str,
    user_id: str,
    provider_type: str,
    provider_reference: str,
    outcome: str,
    webhook_url: str = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Send a webhook immediately without delay.
    
    This task sends a webhook callback immediately, useful for testing
    or when immediate notification is required.
    
    Args:
        kyc_check_id: KYC check identifier
        user_id: User identifier
        provider_type: Provider type
        provider_reference: Provider reference ID
        outcome: Verification outcome
        webhook_url: Optional custom webhook URL
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary with delivery result
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Sending immediate webhook",
        extra={
            "kyc_check_id": kyc_check_id,
            "provider_type": provider_type,
            "outcome": outcome,
            "task_id": task_id,
            "correlation_id": correlation_id
        }
    )
    
    try:
        # Convert string parameters to enums
        try:
            provider_enum = ProviderType(provider_type)
            outcome_enum = VerificationOutcome(outcome)
        except ValueError as e:
            error_msg = f"Invalid parameter: {str(e)}"
            logger.error(error_msg)
            return TaskResult.error_result(
                error=error_msg,
                data={
                    "kyc_check_id": kyc_check_id,
                    "provider_type": provider_type,
                    "outcome": outcome
                },
                metadata={"task_id": task_id, "correlation_id": correlation_id}
            ).to_dict()
        
        # Send webhook immediately
        delivery_result = run_async(
            mock_webhook_sender.send_webhook_immediately(
                kyc_check_id=kyc_check_id,
                user_id=user_id,
                provider_type=provider_enum,
                provider_reference=provider_reference,
                outcome=outcome_enum,
                webhook_url=webhook_url
            )
        )
        
        result_data = {
            "kyc_check_id": kyc_check_id,
            "provider_type": provider_type,
            "outcome": outcome,
            "provider_reference": provider_reference,
            "webhook_url": webhook_url,
            "delivery_result": {
                "success": delivery_result.success,
                "status_code": delivery_result.status_code,
                "delivery_time_ms": delivery_result.delivery_time_ms,
                "attempt_number": delivery_result.attempt_number,
                "error_message": delivery_result.error_message
            },
            "sent_at": datetime.utcnow().isoformat()
        }
        
        if delivery_result.success:
            result = TaskResult.success_result(
                data=result_data,
                metadata={
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "delivery_time_ms": delivery_result.delivery_time_ms
                }
            )
            
            logger.info(
                f"Immediate webhook sent successfully",
                extra={
                    "kyc_check_id": kyc_check_id,
                    "provider_type": provider_type,
                    "outcome": outcome,
                    "delivery_time_ms": delivery_result.delivery_time_ms,
                    "task_id": task_id
                }
            )
        else:
            result = TaskResult.error_result(
                error=delivery_result.error_message or "Webhook delivery failed",
                data=result_data,
                metadata={
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "delivery_time_ms": delivery_result.delivery_time_ms
                }
            )
            
            logger.error(
                f"Immediate webhook delivery failed",
                extra={
                    "kyc_check_id": kyc_check_id,
                    "provider_type": provider_type,
                    "outcome": outcome,
                    "error": delivery_result.error_message,
                    "task_id": task_id
                }
            )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error sending immediate webhook: {str(e)}",
            extra={
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome,
                "task_id": task_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        result = TaskResult.error_result(
            error=str(e),
            data={
                "kyc_check_id": kyc_check_id,
                "provider_type": provider_type,
                "outcome": outcome
            },
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id
            }
        )
        
        return result.to_dict()