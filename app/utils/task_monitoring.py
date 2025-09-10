"""
Task monitoring utilities for tracking KYC processing progress.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID

from celery.result import AsyncResult
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.kyc import KYCStatus
from app.repositories.kyc_repository import KYCRepository
from app.utils.logging import get_logger
from app.worker import celery_app

logger = get_logger(__name__)


class TaskMonitor:
    """Monitor and track task execution progress."""
    
    def __init__(self, db: Session = None):
        """
        Initialize task monitor.
        
        Args:
            db: Database session (optional, will create if not provided)
        """
        self.db = db or next(get_db())
        self.kyc_repository = KYCRepository(self.db)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed task status information.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information or None if not found
        """
        try:
            result = celery_app.AsyncResult(task_id)
            
            status_info = {
                "task_id": task_id,
                "status": result.status,
                "ready": result.ready(),
                "successful": result.successful() if result.ready() else None,
                "failed": result.failed() if result.ready() else None,
                "result": result.result if result.ready() else None,
                "traceback": result.traceback if result.failed() else None,
                "date_done": result.date_done.isoformat() if result.date_done else None,
                "task_name": getattr(result, 'task_name', None),
                "args": getattr(result, 'args', None),
                "kwargs": getattr(result, 'kwargs', None)
            }
            
            # Add retry information if available
            if hasattr(result, 'retries'):
                status_info["retries"] = result.retries
            
            return status_info
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return None
    
    def get_kyc_processing_status(self, kyc_check_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive KYC processing status including task information.
        
        Args:
            kyc_check_id: KYC check ID
            
        Returns:
            Comprehensive status information
        """
        # Get KYC check from database
        kyc_check = self.kyc_repository.get_with_documents(kyc_check_id)
        if not kyc_check:
            return {"error": "KYC check not found"}
        
        # Base status information
        status_info = {
            "kyc_check_id": str(kyc_check_id),
            "status": kyc_check.status.value,
            "is_completed": kyc_check.is_completed,
            "is_pending_review": kyc_check.is_pending_review,
            "provider": kyc_check.provider,
            "provider_reference": kyc_check.provider_reference,
            "submitted_at": kyc_check.submitted_at.isoformat() if kyc_check.submitted_at else None,
            "completed_at": kyc_check.completed_at.isoformat() if kyc_check.completed_at else None,
            "processing_time_seconds": kyc_check.processing_time_seconds,
            "documents_count": len(kyc_check.documents),
            "risk_score": kyc_check.risk_score,
            "notes": kyc_check.notes,
            "rejection_reason": kyc_check.rejection_reason
        }
        
        # Add progress percentage
        status_progress = {
            KYCStatus.PENDING: 10,
            KYCStatus.IN_PROGRESS: 50,
            KYCStatus.MANUAL_REVIEW: 80,
            KYCStatus.APPROVED: 100,
            KYCStatus.REJECTED: 100,
            KYCStatus.EXPIRED: 100
        }
        status_info["progress_percentage"] = status_progress.get(kyc_check.status, 0)
        
        # Add estimated completion time for in-progress checks
        if kyc_check.status == KYCStatus.IN_PROGRESS and kyc_check.submitted_at:
            elapsed = datetime.utcnow() - kyc_check.submitted_at
            # Estimate 5-10 minutes for typical processing
            estimated_total = timedelta(minutes=7)
            if elapsed < estimated_total:
                remaining = estimated_total - elapsed
                status_info["estimated_completion_seconds"] = int(remaining.total_seconds())
            else:
                status_info["estimated_completion_seconds"] = 0
        
        # Add verification result summary if available
        if kyc_check.verification_result:
            result_summary = self._extract_verification_summary(kyc_check.verification_result)
            status_info["verification_summary"] = result_summary
        
        return status_info
    
    def get_active_tasks_for_kyc(self, kyc_check_id: UUID) -> List[Dict[str, Any]]:
        """
        Get active Celery tasks related to a specific KYC check.
        
        Args:
            kyc_check_id: KYC check ID
            
        Returns:
            List of active task information
        """
        active_tasks = []
        
        try:
            # Get active tasks from Celery
            inspect = celery_app.control.inspect()
            active = inspect.active()
            
            if active:
                for worker, tasks in active.items():
                    for task in tasks:
                        # Check if task is related to this KYC check
                        if self._is_kyc_related_task(task, str(kyc_check_id)):
                            task_info = {
                                "task_id": task.get("id"),
                                "task_name": task.get("name"),
                                "worker": worker,
                                "args": task.get("args", []),
                                "kwargs": task.get("kwargs", {}),
                                "time_start": task.get("time_start"),
                                "acknowledged": task.get("acknowledged", False),
                                "delivery_info": task.get("delivery_info", {})
                            }
                            active_tasks.append(task_info)
            
        except Exception as e:
            logger.error(f"Error getting active tasks for KYC {kyc_check_id}: {e}")
        
        return active_tasks
    
    def get_task_history_for_kyc(self, kyc_check_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get task execution history for a KYC check.
        
        Note: This is a simplified implementation. In production, you might want
        to store task history in a database for better tracking.
        
        Args:
            kyc_check_id: KYC check ID
            limit: Maximum number of history entries to return
            
        Returns:
            List of task history entries
        """
        # This is a placeholder implementation
        # In a real system, you would store task execution history in a database
        history = []
        
        try:
            # Get recent task results from Celery backend
            # This is limited by Celery's result expiration settings
            
            # For now, return basic history based on KYC check status changes
            kyc_check = self.kyc_repository.get(kyc_check_id)
            if kyc_check:
                history.append({
                    "timestamp": kyc_check.created_at.isoformat(),
                    "event": "kyc_check_created",
                    "status": KYCStatus.PENDING.value,
                    "details": "KYC check created and queued for processing"
                })
                
                if kyc_check.status != KYCStatus.PENDING:
                    history.append({
                        "timestamp": kyc_check.updated_at.isoformat(),
                        "event": "status_updated",
                        "status": kyc_check.status.value,
                        "details": f"Status updated to {kyc_check.status.value}"
                    })
                
                if kyc_check.completed_at:
                    history.append({
                        "timestamp": kyc_check.completed_at.isoformat(),
                        "event": "processing_completed",
                        "status": kyc_check.status.value,
                        "details": "KYC processing completed"
                    })
        
        except Exception as e:
            logger.error(f"Error getting task history for KYC {kyc_check_id}: {e}")
        
        return history[:limit]
    
    def get_system_task_statistics(self) -> Dict[str, Any]:
        """
        Get system-wide task processing statistics.
        
        Returns:
            Task processing statistics
        """
        stats = {
            "active_tasks": 0,
            "scheduled_tasks": 0,
            "reserved_tasks": 0,
            "workers": [],
            "queues": {},
            "task_types": {}
        }
        
        try:
            inspect = celery_app.control.inspect()
            
            # Get active tasks
            active = inspect.active()
            if active:
                for worker, tasks in active.items():
                    stats["active_tasks"] += len(tasks)
                    stats["workers"].append({
                        "name": worker,
                        "active_tasks": len(tasks)
                    })
                    
                    # Count task types
                    for task in tasks:
                        task_name = task.get("name", "unknown")
                        stats["task_types"][task_name] = stats["task_types"].get(task_name, 0) + 1
            
            # Get scheduled tasks
            scheduled = inspect.scheduled()
            if scheduled:
                for worker, tasks in scheduled.items():
                    stats["scheduled_tasks"] += len(tasks)
            
            # Get reserved tasks
            reserved = inspect.reserved()
            if reserved:
                for worker, tasks in reserved.items():
                    stats["reserved_tasks"] += len(tasks)
            
            # Get queue information
            try:
                queue_info = inspect.active_queues()
                if queue_info:
                    for worker, queues in queue_info.items():
                        for queue in queues:
                            queue_name = queue.get("name", "unknown")
                            if queue_name not in stats["queues"]:
                                stats["queues"][queue_name] = {
                                    "workers": [],
                                    "routing_key": queue.get("routing_key"),
                                    "exchange": queue.get("exchange", {}).get("name") if queue.get("exchange") else None
                                }
                            stats["queues"][queue_name]["workers"].append(worker)
            except Exception as e:
                logger.warning(f"Could not get queue information: {e}")
        
        except Exception as e:
            logger.error(f"Error getting system task statistics: {e}")
        
        return stats
    
    def cancel_kyc_processing(self, kyc_check_id: UUID, reason: str = "Cancelled by user") -> bool:
        """
        Cancel active KYC processing tasks.
        
        Args:
            kyc_check_id: KYC check ID
            reason: Cancellation reason
            
        Returns:
            True if cancellation was successful
        """
        try:
            # Get active tasks for this KYC check
            active_tasks = self.get_active_tasks_for_kyc(kyc_check_id)
            
            cancelled_count = 0
            for task_info in active_tasks:
                task_id = task_info.get("task_id")
                if task_id:
                    try:
                        # Revoke the task
                        celery_app.control.revoke(task_id, terminate=True)
                        cancelled_count += 1
                        logger.info(f"Cancelled task {task_id} for KYC {kyc_check_id}")
                    except Exception as e:
                        logger.error(f"Failed to cancel task {task_id}: {e}")
            
            # Update KYC check status if tasks were cancelled
            if cancelled_count > 0:
                try:
                    kyc_check = self.kyc_repository.get(kyc_check_id)
                    if kyc_check and kyc_check.status in [KYCStatus.PENDING, KYCStatus.IN_PROGRESS]:
                        self.kyc_repository.update_status(
                            kyc_check_id=kyc_check_id,
                            new_status=KYCStatus.REJECTED,
                            notes=f"Processing cancelled: {reason}",
                            rejection_reason=reason
                        )
                        logger.info(f"Updated KYC {kyc_check_id} status to cancelled")
                except Exception as e:
                    logger.error(f"Failed to update KYC status after cancellation: {e}")
            
            return cancelled_count > 0
            
        except Exception as e:
            logger.error(f"Error cancelling KYC processing for {kyc_check_id}: {e}")
            return False
    
    def _extract_verification_summary(self, verification_result: Dict) -> Dict[str, Any]:
        """
        Extract summary information from verification result.
        
        Args:
            verification_result: Full verification result
            
        Returns:
            Summary information
        """
        summary = {}
        
        try:
            if "overall_outcome" in verification_result:
                summary["outcome"] = verification_result["overall_outcome"]
            
            if "confidence_score" in verification_result:
                summary["confidence"] = verification_result["confidence_score"]
            
            if "risk_level" in verification_result:
                summary["risk_level"] = verification_result["risk_level"]
            
            if "processing_time_ms" in verification_result:
                summary["processing_time_ms"] = verification_result["processing_time_ms"]
            
            # Count document results
            if "document_results" in verification_result:
                doc_results = verification_result["document_results"]
                summary["documents_processed"] = len(doc_results)
                summary["documents_approved"] = sum(
                    1 for doc in doc_results 
                    if doc.get("status") == "approved"
                )
            
            # Include biometric result if available
            if "biometric_result" in verification_result and verification_result["biometric_result"]:
                biometric = verification_result["biometric_result"]
                summary["biometric_match"] = biometric.get("face_match_score")
                summary["liveness_score"] = biometric.get("liveness_score")
        
        except Exception as e:
            logger.error(f"Error extracting verification summary: {e}")
        
        return summary
    
    def _is_kyc_related_task(self, task_info: Dict, kyc_check_id: str) -> bool:
        """
        Check if a task is related to a specific KYC check.
        
        Args:
            task_info: Task information from Celery
            kyc_check_id: KYC check ID to match
            
        Returns:
            True if task is related to the KYC check
        """
        try:
            # Check task name
            task_name = task_info.get("name", "")
            if not task_name.startswith("app.tasks.kyc_tasks"):
                return False
            
            # Check args for KYC check ID
            args = task_info.get("args", [])
            if args and len(args) > 0 and str(args[0]) == kyc_check_id:
                return True
            
            # Check kwargs for KYC check ID
            kwargs = task_info.get("kwargs", {})
            if kwargs.get("kyc_check_id") == kyc_check_id:
                return True
            
            return False
            
        except Exception:
            return False


def get_task_monitor(db: Session = None) -> TaskMonitor:
    """
    Get a task monitor instance.
    
    Args:
        db: Database session (optional)
        
    Returns:
        TaskMonitor instance
    """
    return TaskMonitor(db)