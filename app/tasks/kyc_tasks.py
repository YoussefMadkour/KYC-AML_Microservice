"""
KYC processing tasks.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessLogicError, ValidationError
from app.database import get_db
from app.models.kyc import KYCStatus
from app.repositories.kyc_repository import KYCRepository
from app.services.kyc_service import KYCService
from app.services.mock_provider import MockProviderService, ProviderType, VerificationOutcome
from app.tasks.base import KYCTask, TaskResult
from app.utils.logging import get_logger
from app.worker import celery_app

logger = get_logger(__name__)


@celery_app.task(base=KYCTask, bind=True)
def process_kyc_verification(self, kyc_check_id: str, provider: str = "jumio", **kwargs) -> Dict[str, Any]:
    """
    Process KYC verification asynchronously.
    
    This task handles the complete KYC verification workflow:
    1. Updates status to IN_PROGRESS
    2. Calls mock provider for verification
    3. Updates database with results
    4. Handles errors and retries
    
    Args:
        kyc_check_id: The ID of the KYC check to process
        provider: Provider to use for verification (default: jumio)
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Starting KYC verification processing",
        extra={
            "kyc_check_id": kyc_check_id,
            "provider": provider,
            "task_id": task_id,
            "correlation_id": correlation_id,
            "retry_count": self.request.retries
        }
    )
    
    # Get database session
    db: Session = next(get_db())
    
    try:
        # Initialize services
        kyc_service = KYCService(db)
        mock_provider_service = MockProviderService()
        
        # Get KYC check
        kyc_check = kyc_service.get_kyc_check(UUID(kyc_check_id))
        if not kyc_check:
            raise ValidationError(f"KYC check {kyc_check_id} not found")
        
        # Update status to IN_PROGRESS
        logger.info(f"Updating KYC check {kyc_check_id} status to IN_PROGRESS")
        kyc_service.update_kyc_status(
            UUID(kyc_check_id),
            status_update=type('StatusUpdate', (), {
                'status': KYCStatus.IN_PROGRESS,
                'notes': f"Processing started by task {task_id}",
                'rejection_reason': None
            })(),
            updated_by="system"
        )
        
        # Prepare documents for provider
        documents = []
        for doc in kyc_check.documents:
            documents.append({
                "document_type": doc.document_type,
                "document_number": doc.document_number,
                "file_path": doc.file_path,
                "file_hash": doc.file_hash,
                "issuing_country": doc.issuing_country,
                "issue_date": doc.issue_date,
                "expiry_date": doc.expiry_date
            })
        
        # Prepare user data
        user_data = {
            "user_id": str(kyc_check.user_id),
            "kyc_check_id": kyc_check_id
        }
        
        # Call mock provider asynchronously
        logger.info(f"Calling {provider} provider for verification")
        
        # Run async provider call in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            provider_response = loop.run_until_complete(
                mock_provider_service.submit_kyc_verification(
                    provider_type=provider,
                    documents=documents,
                    user_data=user_data,
                    webhook_url=None  # We'll update directly instead of using webhooks
                )
            )
        finally:
            loop.close()
        
        # Map provider outcome to KYC status
        status_mapping = {
            VerificationOutcome.APPROVED: KYCStatus.APPROVED,
            VerificationOutcome.REJECTED: KYCStatus.REJECTED,
            VerificationOutcome.MANUAL_REVIEW: KYCStatus.MANUAL_REVIEW,
            VerificationOutcome.PENDING: KYCStatus.IN_PROGRESS,
            VerificationOutcome.ERROR: KYCStatus.REJECTED
        }
        
        final_status = status_mapping.get(provider_response.overall_status, KYCStatus.REJECTED)
        
        # Prepare verification result
        verification_result = {
            "provider_response": provider_response.dict(),
            "overall_outcome": provider_response.overall_status.value,
            "confidence_score": provider_response.confidence_score,
            "risk_level": provider_response.risk_level.value,
            "processing_time_ms": provider_response.processing_time_ms,
            "document_results": [doc.dict() for doc in provider_response.document_results],
            "biometric_result": provider_response.biometric_result.dict() if provider_response.biometric_result else None,
            "processed_at": datetime.utcnow().isoformat(),
            "task_id": task_id
        }
        
        # Determine rejection reason if applicable
        rejection_reason = None
        if final_status == KYCStatus.REJECTED:
            issues = []
            for doc_result in provider_response.document_results:
                issues.extend(doc_result.issues)
            if provider_response.biometric_result:
                issues.extend(provider_response.biometric_result.issues)
            rejection_reason = "; ".join(issues) if issues else "Verification failed"
        
        # Update KYC check with final results
        logger.info(f"Updating KYC check {kyc_check_id} with final status: {final_status}")
        updated_check = kyc_service.update_kyc_check(
            UUID(kyc_check_id),
            update_data=type('UpdateData', (), {
                'status': final_status,
                'provider_reference': provider_response.provider_reference,
                'verification_result': verification_result,
                'risk_score': provider_response.risk_level.value,
                'notes': f"Verification completed by {provider} provider",
                'rejection_reason': rejection_reason
            })(),
            updated_by="system"
        )
        
        if not updated_check:
            raise BusinessLogicError(f"Failed to update KYC check {kyc_check_id}")
        
        # Create success result
        result_data = {
            "kyc_check_id": kyc_check_id,
            "status": final_status.value,
            "provider": provider,
            "provider_reference": provider_response.provider_reference,
            "confidence_score": provider_response.confidence_score,
            "risk_level": provider_response.risk_level.value,
            "processing_time_ms": provider_response.processing_time_ms,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        result = TaskResult.success_result(
            data=result_data,
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "retry_count": self.request.retries,
                "provider": provider
            }
        )
        
        logger.info(
            f"KYC verification completed successfully",
            extra={
                "kyc_check_id": kyc_check_id,
                "final_status": final_status.value,
                "provider": provider,
                "confidence_score": provider_response.confidence_score,
                "task_id": task_id
            }
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error processing KYC verification {kyc_check_id}: {str(e)}",
            extra={
                "kyc_check_id": kyc_check_id,
                "provider": provider,
                "task_id": task_id,
                "error": str(e),
                "retry_count": self.request.retries
            },
            exc_info=True
        )
        
        # Try to update status to indicate error
        try:
            kyc_service = KYCService(db)
            kyc_service.update_kyc_status(
                UUID(kyc_check_id),
                status_update=type('StatusUpdate', (), {
                    'status': KYCStatus.REJECTED,
                    'notes': f"Processing failed: {str(e)}",
                    'rejection_reason': f"System error: {str(e)}"
                })(),
                updated_by="system"
            )
        except Exception as update_error:
            logger.error(f"Failed to update KYC status after error: {update_error}")
        
        # Create error result
        result = TaskResult.error_result(
            error=str(e),
            data={"kyc_check_id": kyc_check_id, "provider": provider},
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "retry_count": self.request.retries
            }
        )
        
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    
    finally:
        db.close()


@celery_app.task(base=KYCTask, bind=True)
def update_kyc_status(
    self, 
    kyc_check_id: str, 
    status: str, 
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Update KYC check status.
    
    This task provides a way to update KYC status asynchronously,
    useful for webhook processing or manual status updates.
    
    Args:
        kyc_check_id: The ID of the KYC check to update
        status: New status for the KYC check
        details: Additional details about the status update
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Updating KYC check status",
        extra={
            "kyc_check_id": kyc_check_id,
            "new_status": status,
            "task_id": task_id,
            "correlation_id": correlation_id
        }
    )
    
    # Get database session
    db: Session = next(get_db())
    
    try:
        # Initialize service
        kyc_service = KYCService(db)
        
        # Validate status
        try:
            kyc_status = KYCStatus(status)
        except ValueError:
            raise ValidationError(f"Invalid KYC status: {status}")
        
        # Prepare status update
        status_update = type('StatusUpdate', (), {
            'status': kyc_status,
            'notes': details.get('notes') if details else f"Status updated by task {task_id}",
            'rejection_reason': details.get('rejection_reason') if details else None
        })()
        
        # Update status
        updated_check = kyc_service.update_kyc_status(
            UUID(kyc_check_id),
            status_update=status_update,
            updated_by=details.get('updated_by', 'system') if details else 'system'
        )
        
        if not updated_check:
            raise ValidationError(f"KYC check {kyc_check_id} not found")
        
        # Create success result
        result_data = {
            "kyc_check_id": kyc_check_id,
            "status": status,
            "previous_status": details.get('previous_status') if details else None,
            "updated_at": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        result = TaskResult.success_result(
            data=result_data,
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "retry_count": self.request.retries
            }
        )
        
        logger.info(
            f"KYC status updated successfully",
            extra={
                "kyc_check_id": kyc_check_id,
                "new_status": status,
                "task_id": task_id
            }
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error updating KYC status for {kyc_check_id}: {str(e)}",
            extra={
                "kyc_check_id": kyc_check_id,
                "new_status": status,
                "task_id": task_id,
                "error": str(e),
                "retry_count": self.request.retries
            },
            exc_info=True
        )
        
        result = TaskResult.error_result(
            error=str(e),
            data={"kyc_check_id": kyc_check_id, "status": status},
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "retry_count": self.request.retries
            }
        )
        
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
    
    finally:
        db.close()


@celery_app.task(base=KYCTask, bind=True)
def process_kyc_batch(self, kyc_check_ids: list, provider: str = "jumio", **kwargs) -> Dict[str, Any]:
    """
    Process multiple KYC verifications in batch.
    
    This task processes multiple KYC checks efficiently by:
    1. Validating all checks exist and are in correct state
    2. Processing them in parallel where possible
    3. Collecting results and handling partial failures
    
    Args:
        kyc_check_ids: List of KYC check IDs to process
        provider: Provider to use for verification
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary with batch results
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Starting batch KYC processing",
        extra={
            "kyc_check_ids": kyc_check_ids,
            "batch_size": len(kyc_check_ids),
            "provider": provider,
            "task_id": task_id,
            "correlation_id": correlation_id
        }
    )
    
    results = {
        "successful": [],
        "failed": [],
        "total": len(kyc_check_ids),
        "success_count": 0,
        "failure_count": 0
    }
    
    try:
        # Process each KYC check
        for kyc_check_id in kyc_check_ids:
            try:
                # Trigger individual processing task
                task_result = process_kyc_verification.apply_async(
                    args=[kyc_check_id],
                    kwargs={"provider": provider, "correlation_id": correlation_id}
                )
                
                results["successful"].append({
                    "kyc_check_id": kyc_check_id,
                    "task_id": task_result.id,
                    "status": "queued"
                })
                results["success_count"] += 1
                
            except Exception as e:
                logger.error(f"Failed to queue KYC check {kyc_check_id}: {str(e)}")
                results["failed"].append({
                    "kyc_check_id": kyc_check_id,
                    "error": str(e),
                    "status": "queue_failed"
                })
                results["failure_count"] += 1
        
        # Create result
        result = TaskResult.success_result(
            data=results,
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "provider": provider,
                "batch_size": len(kyc_check_ids)
            }
        )
        
        logger.info(
            f"Batch KYC processing completed",
            extra={
                "total": results["total"],
                "successful": results["success_count"],
                "failed": results["failure_count"],
                "task_id": task_id
            }
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error in batch KYC processing: {str(e)}",
            extra={
                "kyc_check_ids": kyc_check_ids,
                "task_id": task_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        result = TaskResult.error_result(
            error=str(e),
            data={"kyc_check_ids": kyc_check_ids, "partial_results": results},
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id
            }
        )
        
        return result.to_dict()


@celery_app.task(base=KYCTask, bind=True)
def track_kyc_progress(self, kyc_check_id: str, **kwargs) -> Dict[str, Any]:
    """
    Track KYC processing progress and update status.
    
    This task can be used to monitor long-running KYC processes
    and provide progress updates to clients.
    
    Args:
        kyc_check_id: The ID of the KYC check to track
        **kwargs: Additional task parameters
        
    Returns:
        Task result dictionary with progress information
    """
    task_id = self.request.id
    correlation_id = kwargs.get("correlation_id", task_id)
    
    logger.info(
        f"Tracking KYC progress",
        extra={
            "kyc_check_id": kyc_check_id,
            "task_id": task_id,
            "correlation_id": correlation_id
        }
    )
    
    # Get database session
    db: Session = next(get_db())
    
    try:
        # Initialize service
        kyc_service = KYCService(db)
        
        # Get current KYC check status
        kyc_check = kyc_service.get_kyc_check(UUID(kyc_check_id))
        if not kyc_check:
            raise ValidationError(f"KYC check {kyc_check_id} not found")
        
        # Calculate progress information
        progress_info = {
            "kyc_check_id": kyc_check_id,
            "current_status": kyc_check.status.value,
            "is_completed": kyc_check.is_completed,
            "is_pending_review": kyc_check.is_pending_review,
            "processing_time_seconds": kyc_check.processing_time_seconds,
            "submitted_at": kyc_check.submitted_at.isoformat() if kyc_check.submitted_at else None,
            "completed_at": kyc_check.completed_at.isoformat() if kyc_check.completed_at else None,
            "provider": kyc_check.provider,
            "provider_reference": kyc_check.provider_reference,
            "documents_count": len(kyc_check.documents),
            "risk_score": kyc_check.risk_score,
            "notes": kyc_check.notes
        }
        
        # Add progress percentage based on status
        status_progress = {
            KYCStatus.PENDING: 10,
            KYCStatus.IN_PROGRESS: 50,
            KYCStatus.MANUAL_REVIEW: 80,
            KYCStatus.APPROVED: 100,
            KYCStatus.REJECTED: 100,
            KYCStatus.EXPIRED: 100
        }
        
        progress_info["progress_percentage"] = status_progress.get(kyc_check.status, 0)
        
        # Create success result
        result = TaskResult.success_result(
            data=progress_info,
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "tracked_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(
            f"KYC progress tracked",
            extra={
                "kyc_check_id": kyc_check_id,
                "status": kyc_check.status.value,
                "progress": progress_info["progress_percentage"],
                "task_id": task_id
            }
        )
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(
            f"Error tracking KYC progress for {kyc_check_id}: {str(e)}",
            extra={
                "kyc_check_id": kyc_check_id,
                "task_id": task_id,
                "error": str(e)
            },
            exc_info=True
        )
        
        result = TaskResult.error_result(
            error=str(e),
            data={"kyc_check_id": kyc_check_id},
            metadata={
                "task_id": task_id,
                "correlation_id": correlation_id
            }
        )
        
        return result.to_dict()
    
    finally:
        db.close()