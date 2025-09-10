"""
Mock webhook sender service for simulating external provider callbacks.
"""
import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from app.models.kyc import KYCStatus
from app.models.webhook import WebhookEventType
from app.services.mock_provider import ProviderType, VerificationOutcome
from app.utils.webhook_security import WebhookProvider, generate_webhook_signature
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookPayloadTemplate(BaseModel):
    """Template for webhook payload generation."""
    
    event_type: WebhookEventType
    provider: WebhookProvider
    template_data: Dict[str, Any]
    delay_range: tuple[float, float] = Field(default=(1.0, 10.0))
    weight: float = Field(default=1.0, description="Probability weight for this outcome")


class MockWebhookConfig(BaseModel):
    """Configuration for mock webhook behavior."""
    
    base_webhook_url: str = Field(default="http://localhost:8000/webhooks")
    default_delay_range: tuple[float, float] = Field(default=(2.0, 30.0))
    signature_secret: Optional[str] = None
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=5.0)
    simulate_failures: bool = Field(default=True)
    failure_rate: float = Field(default=0.05, ge=0.0, le=1.0)


class WebhookDeliveryResult(BaseModel):
    """Result of webhook delivery attempt."""
    
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    delivery_time_ms: int
    attempt_number: int
    webhook_url: str


class MockWebhookSender:
    """Service for sending mock webhook callbacks."""
    
    def __init__(self, config: Optional[MockWebhookConfig] = None):
        """
        Initialize mock webhook sender.
        
        Args:
            config: Webhook configuration
        """
        self.config = config or MockWebhookConfig()
        self._scheduled_webhooks: Dict[str, Dict] = {}
        self._delivery_history: List[WebhookDeliveryResult] = []
        
        # Define webhook payload templates for different outcomes
        self._payload_templates = self._initialize_payload_templates()
    
    def _initialize_payload_templates(self) -> Dict[str, List[WebhookPayloadTemplate]]:
        """Initialize webhook payload templates for different providers and outcomes."""
        templates = {
            # KYC Status Update templates
            "kyc_approved": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "status": "approved",
                        "result": {
                            "overall_result": "PASS",
                            "confidence_score": 0.95,
                            "risk_level": "low",
                            "verification_checks": {
                                "document_verification": "PASS",
                                "face_match": "PASS",
                                "liveness_check": "PASS"
                            },
                            "extracted_data": {
                                "first_name": "John",
                                "last_name": "Doe",
                                "date_of_birth": "1990-01-15",
                                "document_number": "P123456789",
                                "nationality": "US"
                            }
                        }
                    },
                    delay_range=(5.0, 15.0),
                    weight=0.7
                ),
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_2,
                    template_data={
                        "status": "approved",
                        "result": {
                            "decision": "APPROVED",
                            "score": 92,
                            "reasons": ["High confidence document verification", "Successful biometric match"],
                            "document_analysis": {
                                "authenticity": "AUTHENTIC",
                                "quality": "HIGH",
                                "tampering": "NONE_DETECTED"
                            }
                        }
                    },
                    delay_range=(3.0, 12.0),
                    weight=0.7
                )
            ],
            
            "kyc_rejected": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "status": "rejected",
                        "result": {
                            "overall_result": "FAIL",
                            "confidence_score": 0.25,
                            "risk_level": "high",
                            "verification_checks": {
                                "document_verification": "FAIL",
                                "face_match": "FAIL",
                                "liveness_check": "PASS"
                            },
                            "rejection_reasons": [
                                "Document appears to be tampered",
                                "Face match confidence too low",
                                "Suspicious document patterns detected"
                            ]
                        }
                    },
                    delay_range=(8.0, 20.0),
                    weight=0.15
                ),
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_2,
                    template_data={
                        "status": "rejected",
                        "result": {
                            "decision": "DECLINED",
                            "score": 18,
                            "reasons": ["Poor document quality", "Failed liveness detection", "Potential fraud indicators"],
                            "document_analysis": {
                                "authenticity": "SUSPICIOUS",
                                "quality": "LOW",
                                "tampering": "DETECTED"
                            }
                        }
                    },
                    delay_range=(10.0, 25.0),
                    weight=0.15
                )
            ],
            
            "kyc_manual_review": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "status": "manual_review",
                        "result": {
                            "overall_result": "REVIEW",
                            "confidence_score": 0.65,
                            "risk_level": "medium",
                            "verification_checks": {
                                "document_verification": "PASS",
                                "face_match": "REVIEW",
                                "liveness_check": "PASS"
                            },
                            "review_reasons": [
                                "Borderline face match score requires human review",
                                "Document quality acceptable but not optimal"
                            ]
                        }
                    },
                    delay_range=(15.0, 45.0),
                    weight=0.15
                ),
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_STATUS_UPDATE,
                    provider=WebhookProvider.MOCK_PROVIDER_2,
                    template_data={
                        "status": "manual_review",
                        "result": {
                            "decision": "REVIEW_REQUIRED",
                            "score": 68,
                            "reasons": ["Ambiguous document features", "Moderate confidence scores"],
                            "document_analysis": {
                                "authenticity": "UNCLEAR",
                                "quality": "MEDIUM",
                                "tampering": "NONE_DETECTED"
                            },
                            "review_notes": "Manual verification recommended due to borderline automated results"
                        }
                    },
                    delay_range=(20.0, 60.0),
                    weight=0.15
                )
            ],
            
            # Document verification templates
            "document_verified": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.KYC_DOCUMENT_VERIFIED,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "document_type": "passport",
                        "verification_status": "verified",
                        "extracted_data": {
                            "document_number": "P987654321",
                            "expiry_date": "2030-12-31",
                            "issuing_country": "US",
                            "holder_name": "Jane Smith"
                        },
                        "quality_checks": {
                            "image_quality": "HIGH",
                            "text_clarity": "GOOD",
                            "security_features": "VERIFIED"
                        }
                    },
                    delay_range=(2.0, 8.0),
                    weight=1.0
                )
            ],
            
            # AML check templates
            "aml_clear": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.AML_CHECK_COMPLETE,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "status": "clear",
                        "risk_score": 15,
                        "risk_level": "low",
                        "matches": [],
                        "screening_results": {
                            "sanctions_check": "CLEAR",
                            "pep_check": "CLEAR",
                            "adverse_media": "CLEAR",
                            "watchlist_check": "CLEAR"
                        }
                    },
                    delay_range=(3.0, 10.0),
                    weight=0.8
                )
            ],
            
            "aml_flagged": [
                WebhookPayloadTemplate(
                    event_type=WebhookEventType.AML_CHECK_COMPLETE,
                    provider=WebhookProvider.MOCK_PROVIDER_1,
                    template_data={
                        "status": "flagged",
                        "risk_score": 85,
                        "risk_level": "high",
                        "matches": [
                            {
                                "list_type": "sanctions",
                                "match_strength": "strong",
                                "entity_name": "John Doe",
                                "match_details": "Name and DOB match"
                            }
                        ],
                        "screening_results": {
                            "sanctions_check": "MATCH",
                            "pep_check": "CLEAR",
                            "adverse_media": "POTENTIAL_MATCH",
                            "watchlist_check": "CLEAR"
                        }
                    },
                    delay_range=(5.0, 15.0),
                    weight=0.1
                )
            ]
        }
        
        return templates
    
    async def schedule_webhook(
        self,
        kyc_check_id: str,
        user_id: str,
        provider_type: ProviderType,
        provider_reference: str,
        outcome: VerificationOutcome,
        webhook_url: Optional[str] = None,
        custom_delay: Optional[float] = None
    ) -> str:
        """
        Schedule a webhook to be sent after a delay.
        
        Args:
            kyc_check_id: KYC check identifier
            user_id: User identifier
            provider_type: Provider type
            provider_reference: Provider reference ID
            outcome: Verification outcome
            webhook_url: Custom webhook URL
            custom_delay: Custom delay in seconds
            
        Returns:
            Webhook schedule ID
        """
        schedule_id = str(uuid4())
        
        # Map provider type to webhook provider
        provider_mapping = {
            ProviderType.JUMIO: WebhookProvider.MOCK_PROVIDER_1,
            ProviderType.ONFIDO: WebhookProvider.MOCK_PROVIDER_2,
            ProviderType.VERIFF: WebhookProvider.MOCK_PROVIDER_1,
            ProviderType.SHUFTI_PRO: WebhookProvider.MOCK_PROVIDER_2
        }
        
        webhook_provider = provider_mapping.get(provider_type, WebhookProvider.MOCK_PROVIDER_1)
        
        # Select appropriate template based on outcome
        template_key = self._map_outcome_to_template_key(outcome)
        templates = self._payload_templates.get(template_key, [])
        
        if not templates:
            logger.warning(f"No templates found for outcome: {outcome}")
            # Use a default template
            templates = self._payload_templates["kyc_approved"]
        
        # Select template based on provider and weights
        provider_templates = [t for t in templates if t.provider == webhook_provider]
        if not provider_templates:
            provider_templates = templates
        
        selected_template = random.choices(
            provider_templates,
            weights=[t.weight for t in provider_templates]
        )[0]
        
        # Calculate delay
        if custom_delay is not None:
            delay = custom_delay
        else:
            delay = random.uniform(*selected_template.delay_range)
        
        # Build webhook URL
        target_url = webhook_url or f"{self.config.base_webhook_url}/kyc/{webhook_provider.value}"
        
        # Schedule webhook
        scheduled_time = datetime.utcnow() + timedelta(seconds=delay)
        
        webhook_data = {
            "schedule_id": schedule_id,
            "kyc_check_id": kyc_check_id,
            "user_id": user_id,
            "provider_type": provider_type.value,
            "provider_reference": provider_reference,
            "webhook_provider": webhook_provider.value,
            "template": selected_template,
            "target_url": target_url,
            "scheduled_time": scheduled_time,
            "created_at": datetime.utcnow(),
            "status": "scheduled"
        }
        
        self._scheduled_webhooks[schedule_id] = webhook_data
        
        logger.info(
            f"Webhook scheduled: id={schedule_id}, delay={delay:.1f}s, "
            f"outcome={outcome}, provider={webhook_provider.value}"
        )
        
        # Schedule the actual webhook sending
        asyncio.create_task(self._send_webhook_after_delay(schedule_id, delay))
        
        return schedule_id
    
    async def send_webhook_immediately(
        self,
        kyc_check_id: str,
        user_id: str,
        provider_type: ProviderType,
        provider_reference: str,
        outcome: VerificationOutcome,
        webhook_url: Optional[str] = None
    ) -> WebhookDeliveryResult:
        """
        Send webhook immediately without scheduling.
        
        Args:
            kyc_check_id: KYC check identifier
            user_id: User identifier
            provider_type: Provider type
            provider_reference: Provider reference ID
            outcome: Verification outcome
            webhook_url: Custom webhook URL
            
        Returns:
            Webhook delivery result
        """
        schedule_id = await self.schedule_webhook(
            kyc_check_id, user_id, provider_type, provider_reference, outcome, webhook_url, 0.0
        )
        
        # Wait a moment for the webhook to be sent
        await asyncio.sleep(0.1)
        
        # Return the delivery result
        webhook_data = self._scheduled_webhooks.get(schedule_id)
        if webhook_data and "delivery_result" in webhook_data:
            return webhook_data["delivery_result"]
        
        # If not found, return a default result
        return WebhookDeliveryResult(
            success=False,
            error_message="Webhook not found or not yet delivered",
            delivery_time_ms=0,
            attempt_number=1,
            webhook_url=webhook_url or f"{self.config.base_webhook_url}/kyc/{provider_type.value}"
        )
    
    async def _send_webhook_after_delay(self, schedule_id: str, delay: float) -> None:
        """
        Send webhook after specified delay.
        
        Args:
            schedule_id: Webhook schedule ID
            delay: Delay in seconds
        """
        await asyncio.sleep(delay)
        
        webhook_data = self._scheduled_webhooks.get(schedule_id)
        if not webhook_data:
            logger.error(f"Webhook data not found for schedule_id: {schedule_id}")
            return
        
        try:
            webhook_data["status"] = "sending"
            delivery_result = await self._deliver_webhook(webhook_data)
            webhook_data["delivery_result"] = delivery_result
            webhook_data["status"] = "completed" if delivery_result.success else "failed"
            
            # Store in delivery history
            self._delivery_history.append(delivery_result)
            
            # Keep only recent history (last 1000 deliveries)
            if len(self._delivery_history) > 1000:
                self._delivery_history = self._delivery_history[-1000:]
                
        except Exception as e:
            logger.error(f"Error sending webhook {schedule_id}: {e}", exc_info=True)
            webhook_data["status"] = "error"
            webhook_data["error"] = str(e)
    
    async def _deliver_webhook(self, webhook_data: Dict) -> WebhookDeliveryResult:
        """
        Deliver webhook to target URL.
        
        Args:
            webhook_data: Webhook data dictionary
            
        Returns:
            Webhook delivery result
        """
        start_time = time.time()
        template = webhook_data["template"]
        target_url = webhook_data["target_url"]
        
        # Build payload
        payload = self._build_webhook_payload(webhook_data, template)
        payload_json = json.dumps(payload, default=str)
        
        # Generate signature
        webhook_provider = WebhookProvider(webhook_data["webhook_provider"])
        timestamp = int(time.time())
        signature = generate_webhook_signature(
            payload_json,
            webhook_provider,
            timestamp,
            self.config.signature_secret
        )
        
        # Build headers
        headers = self._build_webhook_headers(webhook_provider, signature, timestamp)
        
        # Simulate delivery failure if configured
        if self.config.simulate_failures and random.random() < self.config.failure_rate:
            delivery_time_ms = int((time.time() - start_time) * 1000)
            return WebhookDeliveryResult(
                success=False,
                error_message="Simulated delivery failure",
                delivery_time_ms=delivery_time_ms,
                attempt_number=1,
                webhook_url=target_url
            )
        
        # Send webhook with retries
        for attempt in range(1, self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        target_url,
                        content=payload_json,
                        headers=headers
                    )
                    
                    delivery_time_ms = int((time.time() - start_time) * 1000)
                    
                    if response.status_code in [200, 201, 202]:
                        logger.info(
                            f"Webhook delivered successfully: {target_url} "
                            f"(attempt {attempt}, {delivery_time_ms}ms)"
                        )
                        return WebhookDeliveryResult(
                            success=True,
                            status_code=response.status_code,
                            response_body=response.text[:500],  # Truncate response
                            delivery_time_ms=delivery_time_ms,
                            attempt_number=attempt,
                            webhook_url=target_url
                        )
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        logger.warning(f"Webhook delivery failed: {error_msg} (attempt {attempt})")
                        
                        if attempt == self.config.max_retries:
                            return WebhookDeliveryResult(
                                success=False,
                                status_code=response.status_code,
                                response_body=response.text[:500],
                                error_message=error_msg,
                                delivery_time_ms=delivery_time_ms,
                                attempt_number=attempt,
                                webhook_url=target_url
                            )
                        
                        # Wait before retry
                        await asyncio.sleep(self.config.retry_delay * attempt)
                        
            except Exception as e:
                error_msg = f"Delivery error: {str(e)}"
                logger.error(f"Webhook delivery error: {error_msg} (attempt {attempt})")
                
                if attempt == self.config.max_retries:
                    delivery_time_ms = int((time.time() - start_time) * 1000)
                    return WebhookDeliveryResult(
                        success=False,
                        error_message=error_msg,
                        delivery_time_ms=delivery_time_ms,
                        attempt_number=attempt,
                        webhook_url=target_url
                    )
                
                # Wait before retry
                await asyncio.sleep(self.config.retry_delay * attempt)
        
        # Should not reach here, but just in case
        delivery_time_ms = int((time.time() - start_time) * 1000)
        return WebhookDeliveryResult(
            success=False,
            error_message="Max retries exceeded",
            delivery_time_ms=delivery_time_ms,
            attempt_number=self.config.max_retries,
            webhook_url=target_url
        )
    
    def _build_webhook_payload(self, webhook_data: Dict, template: WebhookPayloadTemplate) -> Dict:
        """
        Build webhook payload from template and webhook data.
        
        Args:
            webhook_data: Webhook data
            template: Payload template
            
        Returns:
            Webhook payload dictionary
        """
        # Start with template data
        payload = template.template_data.copy()
        
        # Add common fields
        payload.update({
            "check_id": webhook_data["kyc_check_id"],
            "user_id": webhook_data["user_id"],
            "provider_reference": webhook_data["provider_reference"],
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": str(uuid4()),
            "event_type": template.event_type.value
        })
        
        # Add provider-specific fields
        webhook_provider = WebhookProvider(webhook_data["webhook_provider"])
        
        if webhook_provider == WebhookProvider.MOCK_PROVIDER_1:
            payload.update({
                "api_version": "v2.1",
                "webhook_version": "1.0",
                "environment": "sandbox"
            })
        elif webhook_provider == WebhookProvider.MOCK_PROVIDER_2:
            payload.update({
                "version": "2.0",
                "source": "kyc_service",
                "test_mode": True
            })
        
        return payload
    
    def _build_webhook_headers(
        self,
        provider: WebhookProvider,
        signature: str,
        timestamp: int
    ) -> Dict[str, str]:
        """
        Build webhook headers for the specified provider.
        
        Args:
            provider: Webhook provider
            signature: Generated signature
            timestamp: Timestamp
            
        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"MockWebhookSender/{provider.value}/1.0"
        }
        
        # Add provider-specific headers
        if provider == WebhookProvider.MOCK_PROVIDER_1:
            headers.update({
                "X-Webhook-Signature": signature,
                "X-Webhook-Timestamp": str(timestamp),
                "X-Provider-Name": "mock_provider_1",
                "X-Event-ID": str(uuid4())
            })
        elif provider == WebhookProvider.MOCK_PROVIDER_2:
            headers.update({
                "X-Provider-Signature": signature,
                "X-Provider-Timestamp": str(timestamp),
                "X-Provider-ID": "mock_provider_2",
                "X-Delivery-ID": str(uuid4())
            })
        
        return headers
    
    def _map_outcome_to_template_key(self, outcome: VerificationOutcome) -> str:
        """
        Map verification outcome to template key.
        
        Args:
            outcome: Verification outcome
            
        Returns:
            Template key
        """
        mapping = {
            VerificationOutcome.APPROVED: "kyc_approved",
            VerificationOutcome.REJECTED: "kyc_rejected",
            VerificationOutcome.MANUAL_REVIEW: "kyc_manual_review",
            VerificationOutcome.PENDING: "kyc_approved",  # Default to approved for pending
            VerificationOutcome.ERROR: "kyc_rejected"
        }
        
        return mapping.get(outcome, "kyc_approved")
    
    def get_scheduled_webhooks(self, status: Optional[str] = None) -> List[Dict]:
        """
        Get list of scheduled webhooks.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of webhook data dictionaries
        """
        webhooks = list(self._scheduled_webhooks.values())
        
        if status:
            webhooks = [w for w in webhooks if w.get("status") == status]
        
        return webhooks
    
    def get_delivery_statistics(self) -> Dict[str, Any]:
        """
        Get webhook delivery statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self._delivery_history:
            return {
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "success_rate": 0.0,
                "average_delivery_time_ms": 0.0,
                "provider_stats": {},
                "recent_deliveries": []
            }
        
        total = len(self._delivery_history)
        successful = sum(1 for d in self._delivery_history if d.success)
        failed = total - successful
        
        avg_delivery_time = sum(d.delivery_time_ms for d in self._delivery_history) / total
        
        return {
            "total_deliveries": total,
            "successful_deliveries": successful,
            "failed_deliveries": failed,
            "success_rate": (successful / total) * 100 if total > 0 else 0.0,
            "average_delivery_time_ms": avg_delivery_time,
            "provider_stats": self._get_provider_statistics(),
            "recent_deliveries": [
                {
                    "success": d.success,
                    "status_code": d.status_code,
                    "delivery_time_ms": d.delivery_time_ms,
                    "webhook_url": d.webhook_url
                }
                for d in self._delivery_history[-10:]  # Last 10 deliveries
            ]
        }
    
    def _get_provider_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics by provider."""
        provider_stats = {}
        
        for delivery in self._delivery_history:
            # Extract provider from webhook URL
            provider = "unknown"
            if "/mock_provider_1" in delivery.webhook_url:
                provider = "mock_provider_1"
            elif "/mock_provider_2" in delivery.webhook_url:
                provider = "mock_provider_2"
            
            if provider not in provider_stats:
                provider_stats[provider] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "avg_delivery_time_ms": 0.0
                }
            
            stats = provider_stats[provider]
            stats["total"] += 1
            
            if delivery.success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
        
        # Calculate averages and success rates
        for provider, stats in provider_stats.items():
            if stats["total"] > 0:
                provider_deliveries = [
                    d for d in self._delivery_history
                    if f"/{provider}" in d.webhook_url
                ]
                stats["avg_delivery_time_ms"] = sum(
                    d.delivery_time_ms for d in provider_deliveries
                ) / len(provider_deliveries)
                stats["success_rate"] = (stats["successful"] / stats["total"]) * 100
        
        return provider_stats
    
    def clear_history(self) -> None:
        """Clear delivery history and scheduled webhooks."""
        self._delivery_history.clear()
        self._scheduled_webhooks.clear()
        logger.info("Webhook history and scheduled webhooks cleared")


# Global mock webhook sender instance
mock_webhook_sender = MockWebhookSender()