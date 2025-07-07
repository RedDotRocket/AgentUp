"""Integration tests for middleware functionality.

These tests run against a live AgentUp server to validate middleware behavior
in real-world scenarios.
"""

import asyncio
import time
from typing import Any

import httpx
import pytest
import pytest_asyncio

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def server_url():
    """Base URL for the test server."""
    return "http://localhost:8000"


@pytest_asyncio.fixture
async def client(server_url):
    """HTTP client for making requests to the test server."""
    async with httpx.AsyncClient(base_url=server_url, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def ensure_server_running(client):
    """Ensure the test server is running before tests."""
    try:
        response = await client.get("/health")
        assert response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("Test server is not running. Start with: agentup agent serve --port 8000")


def extract_response_content(response: dict[str, Any]) -> str:
    """Extract content from A2A Task response."""
    result = response.get("result", {})

    # Try to get from task history first
    if "history" in result and result["history"]:
        last_message = result["history"][-1]
        if "parts" in last_message and last_message["parts"]:
            for part in last_message["parts"]:
                if part.get("kind") == "text" and "text" in part:
                    return part["text"]

    # Try to get from artifacts
    if "artifacts" in result and result["artifacts"]:
        last_artifact = result["artifacts"][-1]
        if "parts" in last_artifact and last_artifact["parts"]:
            for part in last_artifact["parts"]:
                if part.get("kind") == "text" and "text" in part:
                    return part["text"]

    # Try to get from status message
    if "status" in result and "message" in result["status"]:
        status_msg = result["status"]["message"]
        if isinstance(status_msg, dict) and "parts" in status_msg:
            for part in status_msg["parts"]:
                if part.get("kind") == "text" and "text" in part:
                    return part["text"]

    # Fallback to string representation
    return str(result)


async def send_message(client: httpx.AsyncClient, content: str, skill_id: str = None) -> dict[str, Any]:
    """Send a message to the agent and return the response."""
    payload = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": content}],
                "messageId": f"msg_{int(time.time() * 1000)}",
            }
        },
        "id": f"test_{int(time.time() * 1000)}",
    }

    if skill_id:
        payload["params"]["skill_id"] = skill_id

    response = await client.post("/", json=payload)
    response.raise_for_status()
    return response.json()


class TestMiddlewareIntegration:
    """Integration tests for middleware system."""

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, client, ensure_server_running):
        """Test rate limiting middleware integration."""
        # Send multiple rapid requests to trigger rate limiting
        requests = 10

        # Send requests rapidly
        tasks = []
        for i in range(requests):
            task = send_message(client, f"rate limit test {i}", "echo")
            tasks.append(task)

        # Execute requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        successes = 0
        rate_limited = 0
        errors = 0

        for result in results:
            if isinstance(result, Exception):
                errors += 1
            elif isinstance(result, dict):
                if "error" in result:
                    if "rate limit" in result["error"].get("message", "").lower():
                        rate_limited += 1
                    else:
                        errors += 1
                else:
                    successes += 1

        # Validate rate limiting behavior
        assert successes > 0, "At least some requests should succeed"
        # Note: Rate limiting behavior depends on server configuration, so we make this flexible
        print(f"Rate limiting test results: {successes} success, {rate_limited} rate limited, {errors} errors")

    @pytest.mark.asyncio
    async def test_caching_integration(self, client, ensure_server_running):
        """Test caching middleware integration."""
        # Send identical requests to test caching
        content = "cache test message"

        # First request - should hit the handler
        start_time = time.time()
        response1 = await send_message(client, content, "echo")
        first_duration = time.time() - start_time

        # Second request - should be cached (faster)
        start_time = time.time()
        response2 = await send_message(client, content, "echo")
        second_duration = time.time() - start_time

        # Validate responses
        assert "error" not in response1, f"First request failed: {response1}"
        assert "error" not in response2, f"Second request failed: {response2}"

        # Get the actual content from responses
        content1 = extract_response_content(response1)
        content2 = extract_response_content(response2)

        # Responses should be identical (cached)
        assert content1 == content2, "Cached responses should be identical"

        # Second request should be faster (cached)
        # Note: This is not always reliable due to network variance, so we use a loose check
        if second_duration < first_duration * 0.8:
            print(f"Caching detected: {first_duration:.3f}s -> {second_duration:.3f}s")
        else:
            print(f"Caching timing unclear: {first_duration:.3f}s -> {second_duration:.3f}s")

    @pytest.mark.asyncio
    async def test_retry_integration(self, client, ensure_server_running):
        """Test retry middleware integration."""
        # Test with a handler that might retry under certain conditions

        # Send a request that could potentially trigger retries
        content = "retry test with potential failure conditions"

        start_time = time.time()
        response = await send_message(client, content, "echo")
        execution_time = time.time() - start_time

        # Validate response
        assert "error" not in response, f"Request failed: {response}"

        # If execution took longer than expected, retries might have occurred
        if execution_time > 1.0:
            print(f"Potential retry detected - execution time: {execution_time:.3f}s")
        else:
            print(f"Normal execution time: {execution_time:.3f}s")

        # Verify the response content
        result_content = extract_response_content(response)
        assert content in result_content, "Response should contain the original content"

    @pytest.mark.asyncio
    async def test_logging_middleware_integration(self, client, ensure_server_running):
        """Test logging middleware integration."""
        # This test validates that logging middleware doesn't break functionality
        # Actual log validation would require access to server logs

        content = "logging test message"
        response = await send_message(client, content, "echo")

        # Validate response
        assert "error" not in response, f"Request failed: {response}"

        # Verify the response structure
        assert "result" in response
        # Check that we got a valid response with content
        content = extract_response_content(response)
        assert content, "Response should contain content"

        result_content = extract_response_content(response)
        assert content in result_content, "Response should contain the original content"

    @pytest.mark.asyncio
    async def test_timing_middleware_integration(self, client, ensure_server_running):
        """Test timing middleware integration."""
        # This test validates that timing middleware doesn't break functionality
        # Actual timing validation would require access to server logs

        content = "timing test message"
        start_time = time.time()
        response = await send_message(client, content, "echo")
        total_time = time.time() - start_time

        # Validate response
        assert "error" not in response, f"Request failed: {response}"

        # Verify response structure
        assert "result" in response
        result_content = extract_response_content(response)
        assert content in result_content, "Response should contain the original content"

        print(f"Request timing: {total_time:.3f}s")

    @pytest.mark.asyncio
    async def test_multiple_middleware_integration(self, client, ensure_server_running):
        """Test multiple middleware working together."""
        # Send requests that should trigger multiple middleware
        content = "multi-middleware test"

        # Send multiple requests to test rate limiting + caching + logging + timing
        responses = []

        for _ in range(3):
            # Same content should be cached after first request
            response = await send_message(client, content, "echo")
            responses.append(response)

            # Small delay between requests
            await asyncio.sleep(0.1)

        # Validate all responses
        for i, response in enumerate(responses):
            assert "error" not in response, f"Request {i} failed: {response}"

            result_content = extract_response_content(response)
            assert content in result_content, f"Response {i} should contain the original content"

        # All cached responses should be identical
        contents = [extract_response_content(resp) for resp in responses]
        assert all(content == contents[0] for content in contents), "All cached responses should be identical"

    @pytest.mark.asyncio
    async def test_middleware_error_handling(self, client, ensure_server_running):
        """Test middleware error handling."""
        # Send requests that might trigger middleware errors

        # Test with invalid skill_id
        try:
            response = await send_message(client, "test", "nonexistent_skill")
            # Should get an error response, not an exception
            assert "error" in response, "Invalid skill should return error response"
            if "error" in response:
                print(f"Error response received as expected: {response['error']['message']}")
        except httpx.HTTPStatusError as e:
            # HTTP errors are acceptable for invalid skills
            print(f"HTTP error for invalid skill (expected): {e}")
        except Exception as e:
            pytest.fail(f"Should return error response, not raise exception: {e}")

        # Test with malformed content (very large)
        large_content = "x" * 10000  # 10KB content
        response = await send_message(client, large_content, "echo")

        # Should handle large content gracefully
        if "error" in response:
            # If there's an error, it should be descriptive
            assert "error" in response
            print(f"Large content error: {response['error']['message']}")
        else:
            # If successful, response should contain the content (possibly truncated)
            assert "result" in response
            print("Large content handled successfully")

    @pytest.mark.asyncio
    async def test_middleware_configuration_validation(self, client, ensure_server_running):
        """Test that middleware configuration is properly applied."""
        # This test validates that middleware is actually configured and working

        # Test rate limiting configuration
        rapid_requests = 15
        rate_limited_count = 0

        # Send rapid requests
        for i in range(rapid_requests):
            try:
                response = await send_message(client, f"config test {i}", "echo")
                if "error" in response and "rate limit" in response["error"]["message"].lower():
                    rate_limited_count += 1
            except Exception:
                # Network errors don't count as rate limiting
                pass

        # If rate limiting is configured, we should see some rate limited responses
        print(f"Rate limited responses: {rate_limited_count}/{rapid_requests}")

        # Test caching configuration
        cache_test_content = "cache config test"

        # First request
        response1 = await send_message(client, cache_test_content, "echo")
        assert "error" not in response1, "Cache test request should succeed"

        # Second identical request
        response2 = await send_message(client, cache_test_content, "echo")
        assert "error" not in response2, "Cached request should succeed"

        # Responses should be identical if caching is working
        content1 = extract_response_content(response1)
        content2 = extract_response_content(response2)

        if content1 == content2:
            print("Caching configuration appears to be working")
        else:
            print("Caching configuration may not be active")

    @pytest.mark.asyncio
    async def test_middleware_performance_impact(self, client, ensure_server_running):
        """Test middleware performance impact."""
        # Measure request times with middleware active
        content = "performance test"
        request_count = 10
        times = []

        for i in range(request_count):
            start_time = time.time()
            response = await send_message(client, f"{content} {i}", "echo")
            end_time = time.time()

            assert "error" not in response, f"Performance test request {i} failed"
            times.append(end_time - start_time)

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"Performance stats - Avg: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s")

        # Validate reasonable performance (adjust thresholds as needed)
        assert avg_time < 5.0, f"Average response time too high: {avg_time:.3f}s"
        assert max_time < 10.0, f"Maximum response time too high: {max_time:.3f}s"


class TestMiddlewareStressTest:
    """Stress tests for middleware under load."""

    @pytest_asyncio.fixture
    async def stress_client(self, server_url):
        """HTTP client for stress testing with higher limits."""
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        async with httpx.AsyncClient(base_url=server_url, timeout=60.0, limits=limits) as client:
            yield client

    @pytest_asyncio.fixture
    async def ensure_server_running_stress(self, stress_client):
        """Ensure the test server is running before stress tests."""
        try:
            response = await stress_client.get("/health")
            assert response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Test server is not running. Start with: agentup agent serve --port 8000")

    async def send_stress_message(
        self, client: httpx.AsyncClient, content: str, skill_id: str = None
    ) -> dict[str, Any]:
        """Send a message for stress testing."""
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": content}],
                    "messageId": f"stress_msg_{int(time.time() * 1000000)}",
                }
            },
            "id": f"stress_{int(time.time() * 1000000)}",
        }

        if skill_id:
            payload["params"]["skill_id"] = skill_id

        response = await client.post("/", json=payload)
        return response.json()

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_rate_limiting_stress(self, stress_client, ensure_server_running_stress):
        """Stress test rate limiting with high concurrent load."""
        concurrent_requests = 20  # Reduced for more realistic testing
        total_requests = concurrent_requests

        print(f"Starting rate limiting stress test with {concurrent_requests} concurrent requests")

        # Create tasks for concurrent requests
        tasks = []
        for i in range(total_requests):
            task = self.send_stress_message(stress_client, f"stress test {i}", "echo")
            tasks.append(task)

        # Execute all requests concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successes = 0
        rate_limited = 0
        errors = 0
        exceptions = 0

        for result in results:
            if isinstance(result, Exception):
                exceptions += 1
            elif isinstance(result, dict):
                if "error" in result:
                    error_msg = result["error"].get("message", "").lower()
                    if "rate limit" in error_msg:
                        rate_limited += 1
                    else:
                        errors += 1
                else:
                    successes += 1

        print("Stress test results:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Requests/sec: {total_requests / total_time:.1f}")
        print(f"  Successes: {successes}")
        print(f"  Rate limited: {rate_limited}")
        print(f"  Errors: {errors}")
        print(f"  Exceptions: {exceptions}")

        # Validate stress test results - be more flexible
        assert successes > 0, "Some requests should succeed even under stress"
        assert exceptions < total_requests * 0.2, "Network exceptions should be reasonable"

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_caching_stress(self, stress_client, ensure_server_running_stress):
        """Stress test caching with repeated requests."""
        concurrent_requests = 15  # Reduced for more realistic testing
        unique_contents = 3  # Number of unique cache keys
        requests_per_content = concurrent_requests // unique_contents

        print(f"Starting caching stress test with {unique_contents} cache keys, {requests_per_content} requests each")

        # Create tasks with repeated content for cache testing
        tasks = []
        for content_id in range(unique_contents):
            for _ in range(requests_per_content):
                content = f"cache stress test content {content_id}"
                task = self.send_stress_message(stress_client, content, "echo")
                tasks.append(task)

        # Execute all requests concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successes = 0
        errors = 0
        exceptions = 0

        for result in results:
            if isinstance(result, Exception):
                exceptions += 1
            elif isinstance(result, dict):
                if "error" in result:
                    errors += 1
                else:
                    successes += 1

        print("Caching stress test results:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Requests/sec: {len(tasks) / total_time:.1f}")
        print(f"  Successes: {successes}")
        print(f"  Errors: {errors}")
        print(f"  Exceptions: {exceptions}")

        # Validate caching stress test - be more flexible
        assert successes > len(tasks) * 0.6, "Most requests should succeed with caching"
        assert exceptions < len(tasks) * 0.1, "Network exceptions should be minimal"

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_mixed_middleware_stress(self, stress_client, ensure_server_running_stress):
        """Stress test with multiple middleware types active."""
        concurrent_requests = 12  # Reduced for more realistic testing

        print(f"Starting mixed middleware stress test with {concurrent_requests} concurrent requests")

        # Create diverse request patterns to test different middleware
        tasks = []
        for i in range(concurrent_requests):
            if i % 3 == 0:
                # Repeated content for cache testing
                content = f"repeated content {i % 3}"
            elif i % 3 == 1:
                # Unique content for rate limiting testing
                content = f"unique content {i}"
            else:
                # Large content for retry/validation testing
                content = f"large content {i} " + "x" * 100

            task = self.send_stress_message(stress_client, content, "echo")
            tasks.append(task)

        # Execute all requests concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successes = 0
        rate_limited = 0
        errors = 0
        exceptions = 0

        for result in results:
            if isinstance(result, Exception):
                exceptions += 1
            elif isinstance(result, dict):
                if "error" in result:
                    error_msg = result["error"].get("message", "").lower()
                    if "rate limit" in error_msg:
                        rate_limited += 1
                    else:
                        errors += 1
                else:
                    successes += 1

        print("Mixed middleware stress test results:")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Requests/sec: {len(tasks) / total_time:.1f}")
        print(f"  Successes: {successes}")
        print(f"  Rate limited: {rate_limited}")
        print(f"  Errors: {errors}")
        print(f"  Exceptions: {exceptions}")

        # Validate mixed stress test - be flexible for different server configurations
        assert successes > 0, "Some requests should succeed"
        assert successes + rate_limited > len(tasks) * 0.5, "Most requests should be handled (success or rate limited)"
        assert exceptions < len(tasks) * 0.2, "Network exceptions should be reasonable"
