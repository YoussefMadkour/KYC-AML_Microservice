# Webhook Simulation System

The KYC/AML microservice includes a comprehensive webhook simulation system that mimics real-world external provider callbacks without requiring paid third-party services.

## Overview

The webhook simulation system consists of several components:

1. **Mock Webhook Sender** - Simulates external provider webhook callbacks
2. **Webhook Scheduling** - Manages delayed webhook delivery to simulate processing times
3. **Signature Generation** - Creates authentic webhook signatures for security testing
4. **Delivery Tracking** - Monitors webhook delivery success and performance
5. **API Endpoints** - Provides control over webhook simulation

## Features

### Realistic Webhook Payloads

The system generates realistic webhook payloads for different KYC outcomes:

- **Approved**: High confidence scores, successful verification checks
- **Rejected**: Low confidence scores, failed verification with detailed reasons
- **Manual Review**: Borderline scores requiring human intervention
- **Document Verified**: Specific document verification results
- **AML Clear/Flagged**: Anti-money laundering check results

### Provider-Specific Formats

Supports multiple mock providers with authentic payload formats:

- **Mock Provider 1** (Jumio-style): Uses `api_version`, `webhook_version` fields
- **Mock Provider 2** (Onfido-style): Uses `version`, `source` fields
- **Veriff-style**: Nested verification objects
- **Custom providers**: Extensible for additional formats

### Signature Authentication

Implements proper webhook signature schemes:

- **HMAC-SHA256**: Most common signature method
- **HMAC-SHA1**: Legacy provider support
- **HMAC-SHA512**: High-security signatures
- **Timestamp validation**: Prevents replay attacks

### Configurable Delays

Simulates realistic processing delays:

- **Default ranges**: 2-30 seconds for different outcomes
- **Custom delays**: Specify exact timing for testing
- **Immediate delivery**: For synchronous testing
- **Exponential backoff**: For retry scenarios

## Usage

### Programmatic Usage

```python
from app.services.mock_webhook_sender import MockWebhookSender, MockWebhookConfig
from app.services.mock_provider import ProviderType, VerificationOutcome

# Configure webhook sender
config = MockWebhookConfig(
    base_webhook_url="http://localhost:8000/webhooks",
    default_delay_range=(5.0, 15.0),
    simulate_failures=True,
    failure_rate=0.05  # 5% failure rate
)

webhook_sender = MockWebhookSender(config)

# Schedule a webhook
schedule_id = await webhook_sender.schedule_webhook(
    kyc_check_id="kyc_123",
    user_id="user_456",
    provider_type=ProviderType.JUMIO,
    provider_reference="JUM_ABC123",
    outcome=VerificationOutcome.APPROVED
)

# Send immediately
delivery_result = await webhook_sender.send_webhook_immediately(
    kyc_check_id="kyc_123",
    user_id="user_456",
    provider_type=ProviderType.ONFIDO,
    provider_reference="ONF_XYZ789",
    outcome=VerificationOutcome.MANUAL_REVIEW
)
```

### API Endpoints

#### Simulate KYC Webhook

```bash
POST /api/v1/webhooks/simulate/kyc
```

```json
{
  "kyc_check_id": "kyc_123",
  "user_id": "user_456",
  "provider_type": "jumio",
  "provider_reference": "JUM_ABC123",
  "outcome": "approved",
  "webhook_url": "http://localhost:8000/webhooks/kyc/jumio",
  "delay_seconds": 10.0,
  "immediate": false
}
```

#### Get Simulation Statistics

```bash
GET /api/v1/webhooks/simulate/stats
```

Response:
```json
{
  "delivery_stats": {
    "total_deliveries": 150,
    "successful_deliveries": 142,
    "failed_deliveries": 8,
    "success_rate": 94.7,
    "average_delivery_time_ms": 245.3
  },
  "scheduled_webhooks": {
    "total_scheduled": 5,
    "by_status": {
      "scheduled": 2,
      "sending": 1,
      "completed": 2
    }
  }
}
```

#### List Scheduled Webhooks

```bash
GET /api/v1/webhooks/simulate/scheduled?status=scheduled
```

#### Clear Simulation History

```bash
POST /api/v1/webhooks/simulate/clear
```

### Celery Tasks

The system provides Celery tasks for asynchronous webhook simulation:

#### Simulate Provider Webhook

```python
from app.tasks.webhook_tasks import simulate_provider_webhook

# Schedule webhook simulation
task_result = simulate_provider_webhook.apply_async(
    args=["kyc_123", "user_456", "jumio", "JUM_ABC123", "approved"],
    kwargs={"delay_seconds": 15.0}
)
```

#### Send Immediate Webhook

```python
from app.tasks.webhook_tasks import send_immediate_webhook

# Send webhook immediately
task_result = send_immediate_webhook.apply_async(
    args=["kyc_123", "user_456", "onfido", "ONF_XYZ789", "rejected"]
)
```

## Testing

### Manual Testing Script

Run the comprehensive test script:

```bash
python scripts/test_webhook_simulation.py
```

This script tests:
- Webhook scheduling with different delays
- Immediate webhook delivery
- Payload generation for all providers
- Signature generation and verification
- Delivery statistics tracking

### Integration Tests

Run the integration test suite:

```bash
pytest tests/integration/test_webhook_simulation.py -v
```

Tests cover:
- Mock webhook sender functionality
- Celery task execution
- API endpoint behavior
- End-to-end workflow simulation

### Unit Tests

Individual components can be tested:

```bash
# Test webhook sender
pytest tests/unit/test_services/test_mock_webhook_sender.py -v

# Test webhook tasks
pytest tests/unit/test_tasks/test_webhook_simulation.py -v

# Test API endpoints
pytest tests/unit/test_api/test_webhook_simulation.py -v
```

## Configuration

### Environment Variables

```bash
# Webhook simulation settings
WEBHOOK_SECRET=your_webhook_secret_key
WEBHOOK_SIMULATION_ENABLED=true
WEBHOOK_BASE_URL=http://localhost:8000/webhooks

# Failure simulation
WEBHOOK_SIMULATE_FAILURES=true
WEBHOOK_FAILURE_RATE=0.05

# Timing configuration
WEBHOOK_MIN_DELAY=2.0
WEBHOOK_MAX_DELAY=30.0
WEBHOOK_RETRY_DELAY=5.0
WEBHOOK_MAX_RETRIES=3
```

### Provider Configuration

Add new providers by extending the webhook sender:

```python
# Add new payload templates
webhook_sender._payload_templates["custom_outcome"] = [
    WebhookPayloadTemplate(
        event_type=WebhookEventType.KYC_STATUS_UPDATE,
        provider=WebhookProvider.CUSTOM_PROVIDER,
        template_data={
            "status": "custom_status",
            "result": {"custom_field": "custom_value"}
        },
        delay_range=(5.0, 20.0),
        weight=1.0
    )
]
```

## Monitoring

### Delivery Statistics

Track webhook delivery performance:

- **Success Rate**: Percentage of successful deliveries
- **Average Delivery Time**: Mean time for webhook delivery
- **Provider Statistics**: Per-provider success rates and timing
- **Recent Deliveries**: Last 10 delivery attempts with details

### Scheduled Webhooks

Monitor pending webhooks:

- **Total Scheduled**: Number of webhooks awaiting delivery
- **Status Breakdown**: Count by status (scheduled, sending, completed, failed)
- **Delivery Timeline**: When webhooks are scheduled to be sent

### Error Tracking

Failed webhook deliveries are tracked with:

- **Error Messages**: Detailed failure reasons
- **Retry Attempts**: Number of retry attempts made
- **Status Codes**: HTTP response codes from delivery attempts
- **Timing Information**: How long delivery attempts took

## Best Practices

### Development

1. **Use Short Delays**: Set delays to 0.1-1.0 seconds for faster testing
2. **Disable Failures**: Set `simulate_failures=False` for predictable tests
3. **Clear History**: Regularly clear simulation history during development
4. **Monitor Statistics**: Check delivery stats to identify issues

### Testing

1. **Test All Outcomes**: Verify approved, rejected, and manual review scenarios
2. **Test All Providers**: Ensure each provider format works correctly
3. **Test Signature Verification**: Verify webhook signatures are valid
4. **Test Error Handling**: Simulate failures and verify retry behavior

### Production Simulation

1. **Realistic Delays**: Use production-like delays (5-60 seconds)
2. **Enable Failures**: Simulate realistic failure rates (1-5%)
3. **Monitor Performance**: Track delivery statistics over time
4. **Cleanup Regularly**: Clear old simulation data periodically

## Troubleshooting

### Common Issues

#### Webhooks Not Being Delivered

1. Check if the target URL is accessible
2. Verify webhook signature configuration
3. Check for network connectivity issues
4. Review delivery statistics for error patterns

#### Signature Verification Failures

1. Ensure webhook secret is configured correctly
2. Verify timestamp tolerance settings
3. Check signature generation algorithm matches verification
4. Review provider-specific signature formats

#### Performance Issues

1. Monitor delivery timing statistics
2. Check for network latency issues
3. Verify webhook endpoint response times
4. Consider adjusting retry and timeout settings

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.getLogger('app.services.mock_webhook_sender').setLevel(logging.DEBUG)
logging.getLogger('app.tasks.webhook_tasks').setLevel(logging.DEBUG)
```

This will provide detailed logs of:
- Webhook scheduling decisions
- Payload generation process
- Signature creation steps
- Delivery attempt details
- Error conditions and retries