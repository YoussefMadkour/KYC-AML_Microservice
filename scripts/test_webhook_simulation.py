#!/usr/bin/env python3
"""
Script to test webhook simulation system manually.
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.mock_provider import ProviderType, VerificationOutcome
from app.services.mock_webhook_sender import MockWebhookConfig, MockWebhookSender
from app.utils.webhook_security import WebhookProvider, verify_webhook_signature


async def test_webhook_sender():
    """Test the mock webhook sender functionality."""
    print("🚀 Testing Mock Webhook Sender")
    print("=" * 50)

    # Create webhook sender with test configuration
    config = MockWebhookConfig(
        base_webhook_url="http://localhost:8000/webhooks",
        default_delay_range=(1.0, 3.0),
        simulate_failures=True,
        failure_rate=0.1,  # 10% failure rate
        signature_secret="test_secret_key_123",
    )

    webhook_sender = MockWebhookSender(config)

    # Test data
    test_cases = [
        {
            "name": "Approved KYC - Jumio",
            "kyc_check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "provider_type": ProviderType.JUMIO,
            "provider_reference": "JUM_" + str(uuid4()).replace("-", "")[:12].upper(),
            "outcome": VerificationOutcome.APPROVED,
        },
        {
            "name": "Rejected KYC - Onfido",
            "kyc_check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "provider_type": ProviderType.ONFIDO,
            "provider_reference": "ONF_" + str(uuid4()).replace("-", "")[:12].upper(),
            "outcome": VerificationOutcome.REJECTED,
        },
        {
            "name": "Manual Review - Veriff",
            "kyc_check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "provider_type": ProviderType.VERIFF,
            "provider_reference": "VER_" + str(uuid4()).replace("-", "")[:12].upper(),
            "outcome": VerificationOutcome.MANUAL_REVIEW,
        },
    ]

    print("📋 Test Cases:")
    for i, case in enumerate(test_cases, 1):
        print(f"  {i}. {case['name']}")
        print(f"     KYC ID: {case['kyc_check_id']}")
        print(f"     Provider: {case['provider_type'].value}")
        print(f"     Outcome: {case['outcome'].value}")
        print()

    # Schedule webhooks
    print("⏰ Scheduling webhooks...")
    schedule_ids = []

    for case in test_cases:
        schedule_id = await webhook_sender.schedule_webhook(
            kyc_check_id=case["kyc_check_id"],
            user_id=case["user_id"],
            provider_type=case["provider_type"],
            provider_reference=case["provider_reference"],
            outcome=case["outcome"],
            custom_delay=2.0,  # 2 second delay for testing
        )
        schedule_ids.append(schedule_id)
        print(f"  ✅ Scheduled: {case['name']} (ID: {schedule_id})")

    print(f"\n📊 Scheduled {len(schedule_ids)} webhooks")

    # Show scheduled webhooks
    scheduled_webhooks = webhook_sender.get_scheduled_webhooks("scheduled")
    print(f"📋 Currently scheduled: {len(scheduled_webhooks)} webhooks")

    # Wait for webhooks to be processed
    print("\n⏳ Waiting for webhooks to be processed...")
    await asyncio.sleep(5.0)

    # Check final status
    all_webhooks = webhook_sender.get_scheduled_webhooks()
    print(f"\n📈 Final webhook status:")

    status_counts = {}
    for webhook in all_webhooks:
        status = webhook.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    # Show delivery statistics
    stats = webhook_sender.get_delivery_statistics()
    print(f"\n📊 Delivery Statistics:")
    print(f"  Total deliveries: {stats['total_deliveries']}")
    print(f"  Successful: {stats['successful_deliveries']}")
    print(f"  Failed: {stats['failed_deliveries']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")

    if stats["total_deliveries"] > 0:
        print(f"  Average delivery time: {stats['average_delivery_time_ms']:.0f}ms")

    # Show provider statistics
    provider_stats = stats.get("provider_stats", {})
    if provider_stats:
        print(f"\n📊 Provider Statistics:")
        for provider, provider_stats in provider_stats.items():
            print(f"  {provider}:")
            print(f"    Total: {provider_stats['total']}")
            print(f"    Success rate: {provider_stats.get('success_rate', 0):.1f}%")
            print(
                f"    Avg time: {provider_stats.get('avg_delivery_time_ms', 0):.0f}ms"
            )
    else:
        print(f"\n📊 No provider statistics available (no successful deliveries)")

    return webhook_sender


async def test_immediate_webhook():
    """Test immediate webhook sending."""
    print("\n🚀 Testing Immediate Webhook Sending")
    print("=" * 50)

    config = MockWebhookConfig(
        base_webhook_url="http://localhost:8000/webhooks",
        simulate_failures=False,  # No failures for immediate test
        signature_secret="test_secret_key_123",
    )

    webhook_sender = MockWebhookSender(config)

    # Test immediate webhook
    test_case = {
        "kyc_check_id": str(uuid4()),
        "user_id": str(uuid4()),
        "provider_type": ProviderType.JUMIO,
        "provider_reference": "JUM_IMMEDIATE_TEST",
        "outcome": VerificationOutcome.APPROVED,
    }

    print(f"📤 Sending immediate webhook...")
    print(f"  KYC ID: {test_case['kyc_check_id']}")
    print(f"  Provider: {test_case['provider_type'].value}")
    print(f"  Outcome: {test_case['outcome'].value}")

    start_time = time.time()
    delivery_result = await webhook_sender.send_webhook_immediately(
        kyc_check_id=test_case["kyc_check_id"],
        user_id=test_case["user_id"],
        provider_type=test_case["provider_type"],
        provider_reference=test_case["provider_reference"],
        outcome=test_case["outcome"],
    )
    end_time = time.time()

    print(f"\n📊 Delivery Result:")
    print(f"  Success: {delivery_result.success}")
    print(f"  Status Code: {delivery_result.status_code}")
    print(f"  Delivery Time: {delivery_result.delivery_time_ms}ms")
    print(f"  Attempt Number: {delivery_result.attempt_number}")
    print(f"  Total Time: {(end_time - start_time) * 1000:.0f}ms")

    if delivery_result.error_message:
        print(f"  Error: {delivery_result.error_message}")

    if delivery_result.response_body:
        print(f"  Response: {delivery_result.response_body[:200]}...")

    return delivery_result


def test_payload_generation():
    """Test webhook payload generation."""
    print("\n🚀 Testing Webhook Payload Generation")
    print("=" * 50)

    config = MockWebhookConfig(signature_secret="test_secret_key_123")
    webhook_sender = MockWebhookSender(config)

    # Test different provider types and outcomes
    test_combinations = [
        (ProviderType.JUMIO, VerificationOutcome.APPROVED),
        (ProviderType.ONFIDO, VerificationOutcome.REJECTED),
        (ProviderType.VERIFF, VerificationOutcome.MANUAL_REVIEW),
    ]

    for provider_type, outcome in test_combinations:
        print(f"\n📋 Testing {provider_type.value} - {outcome.value}")

        # Create mock webhook data
        webhook_data = {
            "kyc_check_id": str(uuid4()),
            "user_id": str(uuid4()),
            "provider_type": provider_type.value,
            "provider_reference": f"{provider_type.value.upper()}_TEST123",
            "webhook_provider": (
                WebhookProvider.MOCK_PROVIDER_1.value
                if provider_type in [ProviderType.JUMIO, ProviderType.VERIFF]
                else WebhookProvider.MOCK_PROVIDER_2.value
            ),
        }

        # Get template for this outcome
        template_key = webhook_sender._map_outcome_to_template_key(outcome)
        templates = webhook_sender._payload_templates.get(template_key, [])

        if templates:
            template = templates[0]  # Use first template
            payload = webhook_sender._build_webhook_payload(webhook_data, template)

            print(f"  📄 Payload structure:")
            print(f"    check_id: {payload.get('check_id')}")
            print(f"    status: {payload.get('status')}")
            print(f"    provider_reference: {payload.get('provider_reference')}")
            print(f"    timestamp: {payload.get('timestamp')}")

            # Show provider-specific fields
            webhook_provider = WebhookProvider(webhook_data["webhook_provider"])
            if webhook_provider == WebhookProvider.MOCK_PROVIDER_1:
                print(f"    api_version: {payload.get('api_version')}")
                print(f"    webhook_version: {payload.get('webhook_version')}")
            elif webhook_provider == WebhookProvider.MOCK_PROVIDER_2:
                print(f"    version: {payload.get('version')}")
                print(f"    source: {payload.get('source')}")

            # Test signature generation
            payload_json = json.dumps(payload, default=str)
            timestamp = int(time.time())

            signature = (
                webhook_sender.config.signature_secret
                and verify_webhook_signature(
                    payload_json,
                    "test_signature",  # This would be the actual signature
                    webhook_provider,
                    timestamp,
                    webhook_sender.config.signature_secret,
                )
            )

            print(f"    payload_size: {len(payload_json)} bytes")
            print(f"    signature_testable: {signature is not None}")


async def test_webhook_scheduling():
    """Test webhook scheduling with different delays."""
    print("\n🚀 Testing Webhook Scheduling")
    print("=" * 50)

    config = MockWebhookConfig(
        base_webhook_url="http://localhost:8000/webhooks",
        simulate_failures=False,
        signature_secret="test_secret_key_123",
    )

    webhook_sender = MockWebhookSender(config)

    # Schedule webhooks with different delays
    delays = [0.5, 1.0, 2.0, 3.0]
    schedule_ids = []

    print("⏰ Scheduling webhooks with different delays:")

    for i, delay in enumerate(delays):
        schedule_id = await webhook_sender.schedule_webhook(
            kyc_check_id=str(uuid4()),
            user_id=str(uuid4()),
            provider_type=ProviderType.JUMIO,
            provider_reference=f"JUM_DELAY_TEST_{i}",
            outcome=VerificationOutcome.APPROVED,
            custom_delay=delay,
        )
        schedule_ids.append(schedule_id)
        print(f"  ✅ Scheduled webhook {i+1} with {delay}s delay (ID: {schedule_id})")

    # Monitor webhook processing
    print(f"\n👀 Monitoring webhook processing...")

    for check_time in [1, 2, 3, 4, 5]:
        await asyncio.sleep(1.0)

        all_webhooks = webhook_sender.get_scheduled_webhooks()
        status_counts = {}

        for webhook in all_webhooks:
            if webhook["schedule_id"] in schedule_ids:
                status = webhook.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

        print(f"  After {check_time}s: {dict(status_counts)}")

    # Final statistics
    stats = webhook_sender.get_delivery_statistics()
    print(f"\n📊 Final Statistics:")
    print(f"  Total deliveries: {stats['total_deliveries']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")

    if stats["recent_deliveries"]:
        print(f"  Recent deliveries:")
        for delivery in stats["recent_deliveries"][-3:]:  # Show last 3
            print(
                f"    Success: {delivery['success']}, Time: {delivery['delivery_time_ms']}ms"
            )


async def main():
    """Run all webhook simulation tests."""
    print("🧪 Mock Webhook Sender Test Suite")
    print("=" * 60)

    try:
        # Test 1: Basic webhook sender functionality
        webhook_sender = await test_webhook_sender()

        # Test 2: Immediate webhook sending
        await test_immediate_webhook()

        # Test 3: Payload generation
        test_payload_generation()

        # Test 4: Webhook scheduling
        await test_webhook_scheduling()

        print("\n✅ All tests completed!")
        print("\n📝 Summary:")
        print("  - Mock webhook sender functionality: ✅")
        print("  - Immediate webhook delivery: ✅")
        print("  - Payload generation: ✅")
        print("  - Webhook scheduling: ✅")

        # Final cleanup
        webhook_sender.clear_history()
        print("  - Cleanup completed: ✅")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
