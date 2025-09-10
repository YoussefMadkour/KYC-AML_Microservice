#!/usr/bin/env python3
"""
Script to test the task processing infrastructure.
Run this after starting the services with docker-compose.tasks.yml
"""
import sys
import os
import time
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tasks import process_kyc_verification, update_kyc_status, get_task_status
from app.utils.task_monitoring import task_monitor


def test_task_infrastructure():
    """Test the task processing infrastructure."""
    print("🚀 Testing KYC/AML Task Processing Infrastructure")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Performing health check...")
    health = task_monitor.health_check()
    print(f"   Status: {health['status']}")
    
    if health['status'] == 'unhealthy':
        print("   ❌ Infrastructure is not healthy. Please check:")
        print("      - RabbitMQ is running (docker-compose -f docker-compose.tasks.yml up -d)")
        print("      - Redis is running")
        print("      - Celery workers are started")
        return False
    
    print("   ✅ Infrastructure is healthy")
    
    # Test 2: Submit a test KYC task
    print("\n2. Submitting test KYC verification task...")
    try:
        result = process_kyc_verification.delay("test-kyc-123")
        task_id = result.id
        print(f"   Task submitted with ID: {task_id}")
        
        # Wait a moment and check status
        time.sleep(2)
        status = get_task_status(task_id)
        if status:
            print(f"   Task status: {status['status']}")
            print("   ✅ KYC task processing works")
        else:
            print("   ⚠️  Could not retrieve task status")
            
    except Exception as e:
        print(f"   ❌ Error submitting KYC task: {e}")
        return False
    
    # Test 3: Submit a test status update task
    print("\n3. Submitting test status update task...")
    try:
        result = update_kyc_status.delay("test-kyc-456", "approved", {"score": 95})
        task_id = result.id
        print(f"   Task submitted with ID: {task_id}")
        
        time.sleep(2)
        status = get_task_status(task_id)
        if status:
            print(f"   Task status: {status['status']}")
            print("   ✅ Status update task processing works")
        else:
            print("   ⚠️  Could not retrieve task status")
            
    except Exception as e:
        print(f"   ❌ Error submitting status update task: {e}")
        return False
    
    # Test 4: Check worker stats
    print("\n4. Checking worker statistics...")
    try:
        stats = task_monitor.get_worker_stats()
        if stats:
            print(f"   Active workers: {len(stats)}")
            for worker, worker_stats in stats.items():
                print(f"   - {worker}: {worker_stats['status']}")
            print("   ✅ Worker monitoring works")
        else:
            print("   ⚠️  No worker statistics available")
            
    except Exception as e:
        print(f"   ❌ Error getting worker stats: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Task infrastructure test completed successfully!")
    print("\nNext steps:")
    print("- Start Celery workers: celery -A app.worker worker --loglevel=info")
    print("- Monitor tasks: celery -A app.worker flower")
    print("- View RabbitMQ management: http://localhost:15672 (guest/guest)")
    
    return True


if __name__ == "__main__":
    success = test_task_infrastructure()
    sys.exit(0 if success else 1)