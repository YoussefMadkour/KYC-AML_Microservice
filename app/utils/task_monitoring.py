"""
Task monitoring and logging utilities.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from celery import current_app
from app.worker import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskMonitor:
    """
    Task monitoring utility for tracking Celery task performance and status.
    """
    
    def __init__(self, celery_app_instance=None):
        self.celery_app = celery_app_instance or celery_app
    
    def get_active_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get currently active tasks across all workers.
        
        Returns:
            Dictionary mapping worker names to their active tasks
        """
        try:
            inspect = self.celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return {}
            
            # Format task information
            formatted_tasks = {}
            for worker, tasks in active_tasks.items():
                formatted_tasks[worker] = [
                    {
                        "task_id": task["id"],
                        "task_name": task["name"],
                        "args": task.get("args", []),
                        "kwargs": task.get("kwargs", {}),
                        "time_start": task.get("time_start"),
                        "worker": worker,
                    }
                    for task in tasks
                ]
            
            return formatted_tasks
            
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}")
            return {}
    
    def get_scheduled_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get scheduled (reserved) tasks across all workers.
        
        Returns:
            Dictionary mapping worker names to their scheduled tasks
        """
        try:
            inspect = self.celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            
            if not scheduled_tasks:
                return {}
            
            # Format task information
            formatted_tasks = {}
            for worker, tasks in scheduled_tasks.items():
                formatted_tasks[worker] = [
                    {
                        "task_id": task["request"]["id"],
                        "task_name": task["request"]["task"],
                        "args": task["request"].get("args", []),
                        "kwargs": task["request"].get("kwargs", {}),
                        "eta": task.get("eta"),
                        "priority": task.get("priority"),
                        "worker": worker,
                    }
                    for task in tasks
                ]
            
            return formatted_tasks
            
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {e}")
            return {}
    
    def get_worker_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get worker statistics and health information.
        
        Returns:
            Dictionary mapping worker names to their statistics
        """
        try:
            inspect = self.celery_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {}
            
            # Format worker statistics
            formatted_stats = {}
            for worker, worker_stats in stats.items():
                formatted_stats[worker] = {
                    "status": "online",
                    "pool": worker_stats.get("pool", {}),
                    "total_tasks": worker_stats.get("total", {}),
                    "rusage": worker_stats.get("rusage", {}),
                    "clock": worker_stats.get("clock"),
                    "pid": worker_stats.get("pid"),
                    "broker": worker_stats.get("broker", {}),
                }
            
            return formatted_stats
            
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {}
    
    def get_queue_lengths(self) -> Dict[str, int]:
        """
        Get the length of each queue.
        
        Returns:
            Dictionary mapping queue names to their lengths
        """
        try:
            # This would require additional Redis connection for accurate queue lengths
            # For now, return placeholder data
            return {
                "kyc_queue": 0,
                "webhook_queue": 0,
                "celery": 0,
            }
        except Exception as e:
            logger.error(f"Error getting queue lengths: {e}")
            return {}
    
    def get_failed_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recently failed tasks.
        
        Args:
            limit: Maximum number of failed tasks to return
            
        Returns:
            List of failed task information
        """
        try:
            # This would require storing failed task information
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            logger.error(f"Error getting failed tasks: {e}")
            return []
    
    def get_task_history(
        self, 
        task_name: Optional[str] = None, 
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get task execution history.
        
        Args:
            task_name: Filter by specific task name (optional)
            hours: Number of hours to look back
            
        Returns:
            List of task execution records
        """
        try:
            # This would require storing task execution history
            # For now, return empty list as placeholder
            return []
        except Exception as e:
            logger.error(f"Error getting task history: {e}")
            return []
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of the task system.
        
        Returns:
            Health check results
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
        }
        
        try:
            # Check worker connectivity
            inspect = self.celery_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                health_status["checks"]["workers"] = {
                    "status": "healthy",
                    "worker_count": len(stats),
                    "workers": list(stats.keys()),
                }
            else:
                health_status["checks"]["workers"] = {
                    "status": "unhealthy",
                    "error": "No workers available",
                }
                health_status["status"] = "unhealthy"
            
            # Check broker connectivity
            try:
                # Simple ping to check broker
                inspect.ping()
                health_status["checks"]["broker"] = {
                    "status": "healthy",
                    "broker_url": settings.CELERY_BROKER_URL,
                }
            except Exception as e:
                health_status["checks"]["broker"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "unhealthy"
            
            # Check result backend
            try:
                # Test result backend connectivity
                test_result = self.celery_app.AsyncResult("test-connection")
                health_status["checks"]["result_backend"] = {
                    "status": "healthy",
                    "backend_url": settings.CELERY_RESULT_BACKEND,
                }
            except Exception as e:
                health_status["checks"]["result_backend"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "unhealthy"
            
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status


class TaskLogger:
    """
    Enhanced logging for Celery tasks with structured logging.
    """
    
    def __init__(self, task_name: str, task_id: str):
        self.task_name = task_name
        self.task_id = task_id
        self.logger = logging.getLogger(f"tasks.{task_name}")
        self.start_time = time.time()
    
    def info(self, message: str, **kwargs):
        """Log info message with task context."""
        self.logger.info(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                "duration": time.time() - self.start_time,
                **kwargs
            }
        )
    
    def warning(self, message: str, **kwargs):
        """Log warning message with task context."""
        self.logger.warning(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                "duration": time.time() - self.start_time,
                **kwargs
            }
        )
    
    def error(self, message: str, **kwargs):
        """Log error message with task context."""
        self.logger.error(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                "duration": time.time() - self.start_time,
                **kwargs
            }
        )
    
    def debug(self, message: str, **kwargs):
        """Log debug message with task context."""
        self.logger.debug(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                "duration": time.time() - self.start_time,
                **kwargs
            }
        )


# Global task monitor instance
task_monitor = TaskMonitor()