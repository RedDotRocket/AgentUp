"""CLI command for testing middleware functionality."""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import click
import httpx

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--url",
    default="http://localhost:8000",
    help="URL of the AgentUp server to test",
    show_default=True,
)
@click.option(
    "--timeout",
    default=30,
    help="Request timeout in seconds",
    show_default=True,
)
@click.option(
    "--tests",
    default="all",
    type=click.Choice(["all", "rate-limit", "cache", "retry", "timing", "logging"]),
    help="Which middleware tests to run",
    show_default=True,
)
@click.option(
    "--requests",
    default=10,
    help="Number of requests per test",
    show_default=True,
)
@click.option(
    "--concurrent",
    default=5,
    help="Number of concurrent requests for stress testing",
    show_default=True,
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output file for test results (JSON format)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output",
)
@click.option(
    "--no-server-check",
    is_flag=True,
    help="Skip server health check",
)
def test_middleware(
    url: str,
    timeout: int,
    tests: str,
    requests: int,
    concurrent: int,
    output: str | None,
    verbose: bool,
    no_server_check: bool,
):
    """Test middleware functionality of a running AgentUp server.

    This command runs comprehensive tests against a running AgentUp server
    to validate middleware behavior including rate limiting, caching, retry logic,
    timing, and logging.

    Examples:

        # Test all middleware on default server
        agentup agent test-middleware

        # Test only rate limiting with custom parameters
        agentup agent test-middleware --tests rate-limit --requests 20

        # Test with custom server URL and save results
        agentup agent test-middleware --url http://localhost:8001 --output results.json

        # Run stress test with high concurrency
        agentup agent test-middleware --concurrent 20 --requests 50
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Initialize test runner
    runner = MiddlewareTestRunner(
        url=url,
        timeout=timeout,
        verbose=verbose,
        no_server_check=no_server_check,
    )

    # Run tests
    try:
        results = asyncio.run(
            runner.run_tests(
                test_types=tests,
                num_requests=requests,
                concurrent_requests=concurrent,
            )
        )

        # Display results
        runner.display_results(results)

        # Save results if output file specified
        if output:
            runner.save_results(results, output)
            click.echo(f"\nResults saved to: {output}")

        # Exit with error code if tests failed
        if not results.get("overall_success", True):
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\nTest interrupted by user", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Test failed with error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


class MiddlewareTestRunner:
    """Runs middleware tests against a live AgentUp server."""

    def __init__(self, url: str, timeout: int, verbose: bool = False, no_server_check: bool = False):
        self.url = url
        self.timeout = timeout
        self.verbose = verbose
        self.no_server_check = no_server_check
        self.results: dict[str, Any] = {}

    async def run_tests(
        self,
        test_types: str = "all",
        num_requests: int = 10,
        concurrent_requests: int = 5,
    ) -> dict[str, Any]:
        """Run the specified middleware tests."""
        click.echo(f"🧪 Testing middleware on {self.url}")
        click.echo(f"Parameters: {num_requests} requests, {concurrent_requests} concurrent")
        click.echo()

        # Initialize results
        self.results = {
            "timestamp": time.time(),
            "server_url": self.url,
            "test_config": {
                "num_requests": num_requests,
                "concurrent_requests": concurrent_requests,
                "timeout": self.timeout,
            },
            "tests": {},
            "overall_success": True,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Check server health
            if not self.no_server_check:
                await self._check_server_health(client)

            # Determine which tests to run
            test_methods = self._get_test_methods(test_types)

            # Run each test
            for test_name, test_method in test_methods.items():
                click.echo(f"Running {test_name} test...")
                try:
                    test_result = await test_method(client, num_requests, concurrent_requests)
                    self.results["tests"][test_name] = test_result

                    # Display immediate result
                    status = "✅" if test_result.get("success", False) else "❌"
                    click.echo(f"{status} {test_name}: {test_result.get('summary', 'Completed')}")

                    if not test_result.get("success", False):
                        self.results["overall_success"] = False

                except Exception as e:
                    error_result = {
                        "success": False,
                        "error": str(e),
                        "summary": f"Failed with error: {e}",
                    }
                    self.results["tests"][test_name] = error_result
                    self.results["overall_success"] = False
                    click.echo(f"❌ {test_name}: Failed with error: {e}")

                    if self.verbose:
                        import traceback

                        traceback.print_exc()

                click.echo()

        return self.results

    async def _check_server_health(self, client: httpx.AsyncClient):
        """Check if the server is healthy."""
        click.echo("🔍 Checking server health...")
        try:
            response = await client.get(f"{self.url}/health")
            response.raise_for_status()
            click.echo("✅ Server is healthy")
        except Exception as e:
            click.echo(f"❌ Server health check failed: {e}", err=True)
            click.echo(f"Ensure your AgentUp server is running at {self.url}", err=True)
            raise click.ClickException("Server is not available") from e

    def _get_test_methods(self, test_types: str) -> dict[str, Any]:
        """Get the test methods to run based on test_types."""
        all_tests = {
            "rate_limiting": self._test_rate_limiting,
            "caching": self._test_caching,
            "retry": self._test_retry,
            "timing": self._test_timing,
            "logging": self._test_logging,
        }

        if test_types == "all":
            return all_tests
        elif test_types == "rate-limit":
            return {"rate_limiting": all_tests["rate_limiting"]}
        elif test_types in all_tests:
            return {test_types: all_tests[test_types]}
        else:
            # Handle hyphenated test names
            test_key = test_types.replace("-", "_")
            if test_key in all_tests:
                return {test_key: all_tests[test_key]}
            else:
                raise click.ClickException(f"Unknown test type: {test_types}")

    async def _send_message(
        self,
        client: httpx.AsyncClient,
        content: str,
        skill_id: str = "echo",
    ) -> dict[str, Any]:
        """Send a message to the server."""
        payload = {
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": {"messages": [{"role": "user", "content": content}]},
            "id": f"test_{int(time.time() * 1000000)}",
        }

        if skill_id:
            payload["params"]["skill_id"] = skill_id

        response = await client.post(self.url, json=payload)
        return response.json()

    async def _test_rate_limiting(
        self,
        client: httpx.AsyncClient,
        num_requests: int,
        concurrent_requests: int,
    ) -> dict[str, Any]:
        """Test rate limiting middleware."""
        # Send concurrent requests to trigger rate limiting
        tasks = []
        for i in range(concurrent_requests):
            task = self._send_message(client, f"rate limit test {i}")
            tasks.append(task)

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

        # Determine success
        success = successes > 0 and (rate_limited > 0 or concurrent_requests <= 5)

        return {
            "success": success,
            "summary": f"{successes} success, {rate_limited} rate limited, {errors} errors",
            "details": {
                "total_requests": concurrent_requests,
                "successes": successes,
                "rate_limited": rate_limited,
                "errors": errors,
                "exceptions": exceptions,
                "total_time": total_time,
                "requests_per_second": concurrent_requests / total_time if total_time > 0 else 0,
            },
        }

    async def _test_caching(
        self,
        client: httpx.AsyncClient,
        num_requests: int,
        concurrent_requests: int,
    ) -> dict[str, Any]:
        """Test caching middleware."""
        content = "cache test message"

        # First request
        start_time = time.time()
        response1 = await self._send_message(client, content)
        first_duration = time.time() - start_time

        # Second identical request (should be cached)
        start_time = time.time()
        response2 = await self._send_message(client, content)
        second_duration = time.time() - start_time

        # Validate responses
        success = (
            "error" not in response1
            and "error" not in response2
            and response1.get("result", {}).get("messages", [{}])[-1].get("content")
            == response2.get("result", {}).get("messages", [{}])[-1].get("content")
        )

        # Check if second request was potentially cached (faster)
        potentially_cached = second_duration < first_duration * 0.8

        return {
            "success": success,
            "summary": f"Responses identical: {success}, potentially cached: {potentially_cached}",
            "details": {
                "first_duration": first_duration,
                "second_duration": second_duration,
                "responses_identical": success,
                "potentially_cached": potentially_cached,
                "speedup_factor": first_duration / second_duration if second_duration > 0 else 0,
            },
        }

    async def _test_retry(
        self,
        client: httpx.AsyncClient,
        num_requests: int,
        concurrent_requests: int,
    ) -> dict[str, Any]:
        """Test retry middleware."""
        # Test with requests that might trigger retries
        content = "retry test with potential failure conditions"

        start_time = time.time()
        response = await self._send_message(client, content)
        execution_time = time.time() - start_time

        # Validate response
        success = "error" not in response
        potentially_retried = execution_time > 1.0  # Long execution might indicate retries

        return {
            "success": success,
            "summary": f"Request successful: {success}, potentially retried: {potentially_retried}",
            "details": {
                "execution_time": execution_time,
                "request_successful": success,
                "potentially_retried": potentially_retried,
                "response_error": response.get("error", {}).get("message") if "error" in response else None,
            },
        }

    async def _test_timing(
        self,
        client: httpx.AsyncClient,
        num_requests: int,
        concurrent_requests: int,
    ) -> dict[str, Any]:
        """Test timing middleware."""
        # Send multiple requests to measure timing consistency
        times = []
        successes = 0

        for i in range(min(num_requests, 5)):  # Limit for timing test
            start_time = time.time()
            response = await self._send_message(client, f"timing test {i}")
            end_time = time.time()

            times.append(end_time - start_time)
            if "error" not in response:
                successes += 1

        # Calculate timing statistics
        avg_time = sum(times) / len(times) if times else 0
        min_time = min(times) if times else 0
        max_time = max(times) if times else 0

        success = successes > 0 and avg_time < 10.0  # Reasonable response time

        return {
            "success": success,
            "summary": f"Avg: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s",
            "details": {
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "total_requests": len(times),
                "successful_requests": successes,
                "success_rate": successes / len(times) if times else 0,
            },
        }

    async def _test_logging(
        self,
        client: httpx.AsyncClient,
        num_requests: int,
        concurrent_requests: int,
    ) -> dict[str, Any]:
        """Test logging middleware."""
        # Test that logging middleware doesn't break functionality
        content = "logging test message"

        response = await self._send_message(client, content)

        # Validate that the request succeeded (logging shouldn't break functionality)
        success = "error" not in response

        if success:
            result_content = response.get("result", {}).get("messages", [{}])[-1].get("content", "")
            content_preserved = content in result_content
        else:
            content_preserved = False

        return {
            "success": success and content_preserved,
            "summary": f"Request successful: {success}, content preserved: {content_preserved}",
            "details": {
                "request_successful": success,
                "content_preserved": content_preserved,
                "response_error": response.get("error", {}).get("message") if "error" in response else None,
            },
        }

    def display_results(self, results: dict[str, Any]):
        """Display test results in a formatted way."""
        click.echo("=" * 60)
        click.echo("🧪 MIDDLEWARE TEST RESULTS")
        click.echo("=" * 60)

        overall_status = "✅ PASSED" if results["overall_success"] else "❌ FAILED"
        click.echo(f"Overall Status: {overall_status}")
        click.echo(f"Server: {results['server_url']}")
        click.echo(f"Timestamp: {time.ctime(results['timestamp'])}")
        click.echo()

        # Display individual test results
        for test_name, test_result in results["tests"].items():
            status = "✅" if test_result.get("success", False) else "❌"
            click.echo(f"{status} {test_name.replace('_', ' ').title()}")
            click.echo(f"   Summary: {test_result.get('summary', 'No summary')}")

            if self.verbose and "details" in test_result:
                click.echo("   Details:")
                for key, value in test_result["details"].items():
                    if isinstance(value, float):
                        click.echo(f"     {key}: {value:.3f}")
                    else:
                        click.echo(f"     {key}: {value}")

            click.echo()

        # Display recommendations
        self._display_recommendations(results)

    def _display_recommendations(self, results: dict[str, Any]):
        """Display recommendations based on test results."""
        click.echo("💡 RECOMMENDATIONS")
        click.echo("-" * 20)

        recommendations = []

        # Check rate limiting
        rate_test = results["tests"].get("rate_limiting", {})
        if not rate_test.get("success", False):
            recommendations.append(
                "Rate limiting may not be properly configured. Check middleware configuration in agent_config.yaml."
            )
        elif rate_test.get("details", {}).get("rate_limited", 0) == 0:
            recommendations.append(
                "No rate limiting detected. Consider adding rate limiting middleware for production use."
            )

        # Check caching
        cache_test = results["tests"].get("caching", {})
        if cache_test.get("details", {}).get("potentially_cached", False):
            recommendations.append("✅ Caching appears to be working effectively.")
        else:
            recommendations.append(
                "Caching may not be active or effective. Consider enabling caching middleware for better performance."
            )

        # Check timing
        timing_test = results["tests"].get("timing", {})
        avg_time = timing_test.get("details", {}).get("avg_time", 0)
        if avg_time > 2.0:
            recommendations.append(
                f"Average response time is high ({avg_time:.3f}s). Consider optimizing handlers or middleware configuration."
            )

        if not recommendations:
            recommendations.append("✅ All middleware appears to be functioning well!")

        for i, rec in enumerate(recommendations, 1):
            click.echo(f"{i}. {rec}")

        click.echo()

    def save_results(self, results: dict[str, Any], output_path: str):
        """Save test results to a JSON file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)


# Add the command to the CLI
if __name__ == "__main__":
    test_middleware()
