"""
Integration tests for webhook API endpoints.
"""

import json
import time
from datetime import datetime
from typing import Dict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.webhook import WebhookEvent, WebhookEventType, WebhookStatus
from app.utils.webhook_security import WebhookProvider, generate_webhook_signature
from tests.conftest import create_test_admin, create_test_user


class TestWebhookReceiver:
    """Test webhook receiver endpoints."""

    def test_receive_kyc_webhook_success(self, client: TestClient, db: Session):
        """Test successful KYC webhook reception."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())

        # Create webhook payload
        payload = {
            "check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "status": "approved",
            "result": {"overall_result": "approved", "confidence_score": 0.95},
            "timestamp": datetime.utcnow().isoformat(),
            "provider_reference": "ref_123456",
        }

        payload_str = json.dumps(payload)

        # Generate signature
        signature = generate_webhook_signature(payload_str, provider, timestamp)

        # Prepare headers
        headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "Content-Type": "application/json",
        }

        # Send webhook
        response = client.post(
            f"/api/v1/webhooks/kyc/{provider.value}", data=payload_str, headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "webhook_id" in data
        assert data["message"] == "Webhook received and queued for processing"

        # Verify webhook was stored in database
        webhook = (
            db.query(WebhookEvent).filter(WebhookEvent.id == data["webhook_id"]).first()
        )

        assert webhook is not None
        assert webhook.provider == provider.value
        assert webhook.event_type == WebhookEventType.KYC_STATUS_UPDATE
        assert webhook.signature_verified is True
        assert webhook.status == WebhookStatus.PENDING
        assert webhook.raw_payload == payload_str
        assert webhook.related_kyc_check_id == payload["check_id"]
        assert webhook.related_user_id == payload["user_id"]

    def test_receive_aml_webhook_success(self, client: TestClient, db: Session):
        """Test successful AML webhook reception."""
        provider = WebhookProvider.MOCK_PROVIDER_2
        timestamp = int(time.time())

        # Create webhook payload
        payload = {
            "check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "status": "clear",
            "risk_score": 15.5,
            "risk_level": "low",
            "matches": [],
            "timestamp": datetime.utcnow().isoformat(),
            "provider_reference": "aml_ref_789",
        }

        payload_str = json.dumps(payload)

        # Generate signature
        signature = generate_webhook_signature(payload_str, provider, timestamp)

        # Prepare headers
        headers = {
            "X-Provider-Signature": signature,
            "X-Provider-Timestamp": str(timestamp),
            "Content-Type": "application/json",
        }

        # Send webhook
        response = client.post(
            f"/api/v1/webhooks/aml/{provider.value}", data=payload_str, headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "received"
        assert "webhook_id" in data

        # Verify webhook was stored in database
        webhook = (
            db.query(WebhookEvent).filter(WebhookEvent.id == data["webhook_id"]).first()
        )

        assert webhook is not None
        assert webhook.provider == provider.value
        assert webhook.event_type == WebhookEventType.AML_CHECK_COMPLETE
        assert webhook.signature_verified is True

    def test_receive_webhook_invalid_signature(self, client: TestClient):
        """Test webhook with invalid signature."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())

        payload = {"check_id": str(uuid4()), "status": "approved"}
        payload_str = json.dumps(payload)

        # Use invalid signature
        headers = {
            "X-Webhook-Signature": "sha256=invalid_signature",
            "X-Webhook-Timestamp": str(timestamp),
            "Content-Type": "application/json",
        }

        response = client.post(
            f"/api/v1/webhooks/kyc/{provider.value}", data=payload_str, headers=headers
        )

        assert response.status_code == 401
        assert "Webhook authentication failed" in response.json()["detail"]

    def test_receive_webhook_unsupported_provider(self, client: TestClient):
        """Test webhook with unsupported provider."""
        payload = {"check_id": str(uuid4()), "status": "approved"}
        payload_str = json.dumps(payload)

        headers = {
            "X-Webhook-Signature": "sha256=test",
            "Content-Type": "application/json",
        }

        response = client.post(
            "/api/v1/webhooks/kyc/unsupported_provider",
            data=payload_str,
            headers=headers,
        )

        assert response.status_code == 400
        assert "Unsupported KYC provider" in response.json()["detail"]

    def test_receive_duplicate_webhook(self, client: TestClient, db: Session):
        """Test handling of duplicate webhooks."""
        provider = WebhookProvider.MOCK_PROVIDER_1
        timestamp = int(time.time())
        provider_event_id = "unique_event_123"

        payload = {
            "event_id": provider_event_id,
            "check_id": str(uuid4()),
            "status": "approved",
        }
        payload_str = json.dumps(payload)

        signature = generate_webhook_signature(payload_str, provider, timestamp)

        headers = {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Event-Id": provider_event_id,
            "Content-Type": "application/json",
        }

        # Send webhook first time
        response1 = client.post(
            f"/api/v1/webhooks/kyc/{provider.value}", data=payload_str, headers=headers
        )

        assert response1.status_code == 200
        webhook_id_1 = response1.json()["webhook_id"]

        # Send same webhook again
        response2 = client.post(
            f"/api/v1/webhooks/kyc/{provider.value}", data=payload_str, headers=headers
        )

        assert response2.status_code == 200
        webhook_id_2 = response2.json()["webhook_id"]

        # Should return the same webhook ID (duplicate detection)
        assert webhook_id_1 == webhook_id_2


class TestWebhookManagement:
    """Test webhook management endpoints."""

    def test_list_webhook_events_admin(self, client: TestClient, db: Session):
        """Test listing webhook events as admin."""
        admin_user = create_test_admin(db)

        # Create test webhook events
        webhook1 = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data1"}',
            status=WebhookStatus.PROCESSED,
            signature_verified=True,
        )
        webhook2 = WebhookEvent(
            provider="mock_provider_2",
            event_type=WebhookEventType.AML_CHECK_COMPLETE,
            raw_payload='{"test": "data2"}',
            status=WebhookStatus.FAILED,
            signature_verified=True,
        )

        db.add_all([webhook1, webhook2])
        db.commit()

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # List webhooks
        response = client.get(
            "/api/v1/webhooks/events", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2
        assert data["page"] == 1
        assert data["size"] == 50

    def test_list_webhook_events_user_restricted(self, client: TestClient, db: Session):
        """Test that regular users can only see their own webhooks."""
        user = create_test_user(db)

        # Create webhook for user
        webhook = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "data"}',
            status=WebhookStatus.PROCESSED,
            signature_verified=True,
            related_user_id=str(user.id),
        )

        # Create webhook for another user
        other_webhook = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"test": "other"}',
            status=WebhookStatus.PROCESSED,
            signature_verified=True,
            related_user_id=str(uuid4()),
        )

        db.add_all([webhook, other_webhook])
        db.commit()

        # Login as regular user
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": "testpass123"},
        )
        token = login_response.json()["access_token"]

        # List webhooks
        response = client.get(
            "/api/v1/webhooks/events", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see own webhook
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["related_user_id"] == str(user.id)

    def test_get_webhook_event_details(self, client: TestClient, db: Session):
        """Test getting webhook event details."""
        admin_user = create_test_admin(db)

        webhook = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"check_id": "test123", "status": "approved"}',
            status=WebhookStatus.PROCESSED,
            signature_verified=True,
            processing_notes="Successfully processed",
        )

        db.add(webhook)
        db.commit()

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Get webhook details
        response = client.get(
            f"/api/v1/webhooks/events/{webhook.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(webhook.id)
        assert data["provider"] == "mock_provider_1"
        assert data["event_type"] == "kyc_status_update"
        assert data["status"] == "processed"
        assert data["signature_verified"] is True
        assert data["processing_notes"] == "Successfully processed"

    def test_retry_webhook_event(self, client: TestClient, db: Session):
        """Test retrying a failed webhook event."""
        admin_user = create_test_admin(db)

        webhook = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"check_id": "test123", "status": "approved"}',
            status=WebhookStatus.FAILED,
            signature_verified=True,
            retry_count=1,
            max_retries=3,
            error_message="Processing failed",
        )

        db.add(webhook)
        db.commit()

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Retry webhook
        response = client.post(
            f"/api/v1/webhooks/events/{webhook.id}/retry",
            json={"force_retry": False, "notes": "Manual retry"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["webhook_event_id"] == str(webhook.id)
        assert data["retry_scheduled"] is True
        assert data["retry_count"] == 2  # Incremented
        assert "next_retry_at" in data

    def test_get_webhook_statistics(self, client: TestClient, db: Session):
        """Test getting webhook statistics."""
        admin_user = create_test_admin(db)

        # Create test webhooks with different statuses
        webhooks = [
            WebhookEvent(
                provider="mock_provider_1",
                event_type=WebhookEventType.KYC_STATUS_UPDATE,
                raw_payload='{"test": "data1"}',
                status=WebhookStatus.PROCESSED,
                signature_verified=True,
            ),
            WebhookEvent(
                provider="mock_provider_1",
                event_type=WebhookEventType.KYC_STATUS_UPDATE,
                raw_payload='{"test": "data2"}',
                status=WebhookStatus.FAILED,
                signature_verified=True,
            ),
            WebhookEvent(
                provider="mock_provider_2",
                event_type=WebhookEventType.AML_CHECK_COMPLETE,
                raw_payload='{"test": "data3"}',
                status=WebhookStatus.PENDING,
                signature_verified=True,
            ),
        ]

        db.add_all(webhooks)
        db.commit()

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Get statistics
        response = client.get(
            "/api/v1/webhooks/stats", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_events"] >= 3
        assert data["processed_events"] >= 1
        assert data["failed_events"] >= 1
        assert data["pending_events"] >= 1
        assert "success_rate" in data
        assert "provider_stats" in data
        assert "event_type_stats" in data

    def test_cleanup_old_webhooks(self, client: TestClient, db: Session):
        """Test cleaning up old webhook events."""
        admin_user = create_test_admin(db)

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Cleanup old webhooks
        response = client.delete(
            "/api/v1/webhooks/cleanup?days_old=30&keep_failed=true",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "deleted_count" in data
        assert data["days_old"] == 30
        assert data["kept_failed"] is True


class TestWebhookProcessing:
    """Test webhook processing functionality."""

    def test_process_webhook_sync(self, client: TestClient, db: Session):
        """Test synchronous webhook processing."""
        admin_user = create_test_admin(db)

        webhook = WebhookEvent(
            provider="mock_provider_1",
            event_type=WebhookEventType.KYC_STATUS_UPDATE,
            raw_payload='{"check_id": "test123", "status": "approved", "result": {}}',
            status=WebhookStatus.PENDING,
            signature_verified=True,
        )

        db.add(webhook)
        db.commit()

        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": admin_user.email, "password": "admin123"},
        )
        token = login_response.json()["access_token"]

        # Process webhook synchronously
        response = client.post(
            f"/api/v1/webhooks/events/{webhook.id}/process",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["webhook_event_id"] == str(webhook.id)
        assert "processing_time_ms" in data
        assert "actions_taken" in data
        assert "success" in data
