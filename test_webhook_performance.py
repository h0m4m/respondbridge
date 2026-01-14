#!/usr/bin/env python3
"""
Test webhook performance and response time
"""
import requests
import time
import json

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_PAYLOAD = {
    "event_type": "message.created",
    "event_id": "test_12345",
    "contact": {
        "id": "test_contact_123",
        "firstName": "Test",
        "lastName": "User",
        "phone": "+1234567890",
        "email": "test@example.com"
    },
    "message": {
        "messageId": "msg_test_123",
        "timestamp": int(time.time() * 1000),
        "message": {
            "type": "text",
            "text": "Test message"
        }
    },
    "channel": {
        "id": "channel_123",
        "name": "Test Channel",
        "source": "whatsapp"
    }
}


def test_response_time(endpoint, payload, num_requests=10):
    """Test webhook response time"""
    url = f"{BASE_URL}{endpoint}"
    times = []

    print(f"\nTesting: {endpoint}")
    print(f"Number of requests: {num_requests}")
    print("-" * 50)

    for i in range(num_requests):
        start = time.time()
        try:
            response = requests.post(url, json=payload, timeout=10)
            elapsed = (time.time() - start) * 1000  # Convert to ms
            times.append(elapsed)

            status = "✅" if response.status_code == 200 else "❌"
            print(f"Request {i+1}: {status} {response.status_code} - {elapsed:.2f}ms")

        except Exception as e:
            print(f"Request {i+1}: ❌ ERROR - {str(e)}")
            continue

        # Small delay between requests
        time.sleep(0.1)

    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print("-" * 50)
        print(f"Average response time: {avg_time:.2f}ms")
        print(f"Min response time: {min_time:.2f}ms")
        print(f"Max response time: {max_time:.2f}ms")
        print(f"Success rate: {len(times)}/{num_requests} ({len(times)/num_requests*100:.1f}%)")

        # Performance evaluation
        if avg_time < 50:
            print("✅ EXCELLENT - Response time < 50ms")
        elif avg_time < 100:
            print("✅ GOOD - Response time < 100ms")
        elif avg_time < 200:
            print("⚠️  ACCEPTABLE - Response time < 200ms")
        else:
            print("❌ SLOW - Response time > 200ms")

    return times


def check_health():
    """Check health endpoint"""
    print("\n" + "=" * 50)
    print("HEALTH CHECK")
    print("=" * 50)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data['status']}")
            print(f"Queue size: {data['queue']['size']}/{data['queue']['max_size']}")
            print(f"Workers: {data['queue']['workers']}")
            print(f"Circuit breaker: {data['circuit_breaker']['status']}")
            print(f"Failures: {data['circuit_breaker']['failures']}/{data['circuit_breaker']['threshold']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Could not connect to server: {str(e)}")
        return False


def main():
    print("=" * 50)
    print("WEBHOOK PERFORMANCE TEST")
    print("=" * 50)
    print(f"Target: {BASE_URL}")

    # Check if server is running
    if not check_health():
        print("\n⚠️  Server not running. Start with: python app.py")
        return

    # Test endpoints
    endpoints = [
        "/webhook/faster/incoming",
        "/webhook/faster/outgoing",
        "/webhook/vip/incoming",
    ]

    all_times = []

    for endpoint in endpoints:
        times = test_response_time(endpoint, TEST_PAYLOAD, num_requests=5)
        all_times.extend(times)
        time.sleep(0.5)

    # Final health check
    check_health()

    # Overall summary
    if all_times:
        print("\n" + "=" * 50)
        print("OVERALL SUMMARY")
        print("=" * 50)
        avg = sum(all_times) / len(all_times)
        print(f"Overall average response time: {avg:.2f}ms")
        print(f"Target: < 50ms")

        if avg < 50:
            print("\n🎉 SUCCESS - Webhook is optimized!")
            print("✅ Response time target achieved")
            print("✅ Ready for production")
        else:
            print(f"\n⚠️  Response time is {avg:.2f}ms (target: <50ms)")


if __name__ == "__main__":
    main()
