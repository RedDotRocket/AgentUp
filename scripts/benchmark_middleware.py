#!/usr/bin/env python3
"""
Middleware Performance Benchmarking Tool for AgentUp

This script provides comprehensive performance testing and benchmarking
for AgentUp middleware functionality.
"""

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, List, Dict, Optional
from urllib.parse import urlparse

import httpx


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark tests."""
    server_url: str = "http://localhost:8000"
    total_requests: int = 100
    concurrent_requests: int = 10
    warmup_requests: int = 10
    timeout: int = 30
    output_file: Optional[str] = None
    verbose: bool = False
    test_types: List[str] = None
    
    def __post_init__(self):
        if self.test_types is None:
            self.test_types = ["rate_limiting", "caching", "timing", "throughput"]


@dataclass
class RequestResult:
    """Result of a single request."""
    success: bool
    duration: float
    status_code: Optional[int]
    error: Optional[str]
    response_size: int
    rate_limited: bool = False
    cached: bool = False


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    cached_requests: int
    total_duration: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    errors: List[str]
    details: Dict[str, Any]


class MiddlewareBenchmark:
    """Benchmarking tool for middleware performance."""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.session: Optional[httpx.AsyncClient] = None
        self.results: Dict[str, BenchmarkResult] = {}
        
        # Setup logging
        log_level = logging.DEBUG if config.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def run_benchmarks(self) -> Dict[str, BenchmarkResult]:
        """Run all configured benchmark tests."""
        self.logger.info(f"Starting middleware benchmarks on {self.config.server_url}")
        self.logger.info(f"Configuration: {self.config.total_requests} total requests, "
                        f"{self.config.concurrent_requests} concurrent")
        
        # Create HTTP client
        limits = httpx.Limits(
            max_keepalive_connections=self.config.concurrent_requests * 2,
            max_connections=self.config.concurrent_requests * 3
        )
        
        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            limits=limits
        ) as client:
            self.session = client
            
            # Check server health
            await self._check_server_health()
            
            # Run warmup
            await self._warmup()
            
            # Run benchmark tests
            for test_type in self.config.test_types:
                self.logger.info(f"Running {test_type} benchmark...")
                try:
                    result = await self._run_test(test_type)
                    self.results[test_type] = result
                    self.logger.info(f"{test_type} completed: {result.requests_per_second:.1f} req/s")
                except Exception as e:
                    self.logger.error(f"Failed to run {test_type} benchmark: {e}")
                    if self.config.verbose:
                        import traceback
                        traceback.print_exc()
        
        return self.results
    
    async def _check_server_health(self):
        """Check if the server is healthy."""
        try:
            response = await self.session.get(f"{self.config.server_url}/health")
            response.raise_for_status()
            self.logger.info("✅ Server health check passed")
        except Exception as e:
            raise RuntimeError(f"Server health check failed: {e}")
    
    async def _warmup(self):
        """Perform warmup requests."""
        self.logger.info(f"Warming up with {self.config.warmup_requests} requests...")
        
        tasks = []
        for i in range(self.config.warmup_requests):
            task = self._send_request(f"warmup request {i}")
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.info("Warmup completed")
    
    async def _run_test(self, test_type: str) -> BenchmarkResult:
        """Run a specific benchmark test."""
        test_methods = {
            "rate_limiting": self._benchmark_rate_limiting,
            "caching": self._benchmark_caching,
            "timing": self._benchmark_timing,
            "throughput": self._benchmark_throughput,
            "stress": self._benchmark_stress,
        }
        
        if test_type not in test_methods:
            raise ValueError(f"Unknown test type: {test_type}")
        
        return await test_methods[test_type]()
    
    async def _benchmark_rate_limiting(self) -> BenchmarkResult:
        """Benchmark rate limiting performance."""
        # Send many concurrent requests to trigger rate limiting
        requests = min(self.config.total_requests, 50)  # Limit for rate limiting test
        
        start_time = time.time()
        tasks = []
        
        for i in range(requests):
            task = self._send_request(f"rate limit test {i}", plugin_id="echo")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        return self._analyze_results("rate_limiting", results, total_duration, requests)
    
    async def _benchmark_caching(self) -> BenchmarkResult:
        """Benchmark caching performance."""
        # Test with repeated content to measure cache effectiveness
        cache_keys = 5  # Number of unique cache keys
        requests_per_key = self.config.total_requests // cache_keys
        
        start_time = time.time()
        tasks = []
        
        for key_id in range(cache_keys):
            for request_id in range(requests_per_key):
                content = f"cache test key {key_id}"  # Repeated content for caching
                task = self._send_request(content, plugin_id="echo")
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        return self._analyze_results("caching", results, total_duration, len(tasks))
    
    async def _benchmark_timing(self) -> BenchmarkResult:
        """Benchmark timing middleware performance."""
        # Sequential requests to measure timing overhead
        results = []
        start_time = time.time()
        
        for i in range(self.config.total_requests):
            result = await self._send_request(f"timing test {i}", plugin_id="echo")
            results.append(result)
        
        total_duration = time.time() - start_time
        
        return self._analyze_results("timing", results, total_duration, self.config.total_requests)
    
    async def _benchmark_throughput(self) -> BenchmarkResult:
        """Benchmark overall throughput."""
        # Test maximum throughput with controlled concurrency
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)
        
        async def limited_request(request_id: int) -> RequestResult:
            async with semaphore:
                return await self._send_request(f"throughput test {request_id}", plugin_id="echo")
        
        start_time = time.time()
        tasks = [limited_request(i) for i in range(self.config.total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        
        return self._analyze_results("throughput", results, total_duration, self.config.total_requests)
    
    async def _benchmark_stress(self) -> BenchmarkResult:
        """Benchmark under stress conditions."""
        # High concurrency stress test
        stress_requests = self.config.total_requests * 2
        stress_concurrency = self.config.concurrent_requests * 3
        
        start_time = time.time()
        tasks = []
        
        for i in range(stress_requests):
            task = self._send_request(f"stress test {i}", plugin_id="echo")
            tasks.append(task)
        
        # Execute with high concurrency
        results = []
        for i in range(0, len(tasks), stress_concurrency):
            batch = tasks[i:i + stress_concurrency]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        
        total_duration = time.time() - start_time
        
        return self._analyze_results("stress", results, total_duration, stress_requests)
    
    async def _send_request(self, content: str, plugin_id: str = "echo") -> RequestResult:
        """Send a single request and measure performance."""
        payload = {
            "jsonrpc": "2.0",
            "method": "send_message",
            "params": {
                "messages": [{"role": "user", "content": content}]
            },
            "id": f"bench_{int(time.time() * 1000000)}"
        }
        
        if plugin_id:
            payload["params"]["plugin_id"] = plugin_id
        
        start_time = time.time()
        try:
            response = await self.session.post(self.config.server_url, json=payload)
            duration = time.time() - start_time
            
            # Parse response
            response_data = response.json()
            response_size = len(response.content)
            
            # Check for errors
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                rate_limited = "rate limit" in error_msg.lower()
                return RequestResult(
                    success=False,
                    duration=duration,
                    status_code=response.status_code,
                    error=error_msg,
                    response_size=response_size,
                    rate_limited=rate_limited
                )
            
            # Successful request
            return RequestResult(
                success=True,
                duration=duration,
                status_code=response.status_code,
                error=None,
                response_size=response_size,
                rate_limited=False,
                cached=False  # Could be detected by analyzing response times
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return RequestResult(
                success=False,
                duration=duration,
                status_code=None,
                error=str(e),
                response_size=0,
                rate_limited=False
            )
    
    def _analyze_results(
        self,
        test_name: str,
        results: List[Any],
        total_duration: float,
        total_requests: int
    ) -> BenchmarkResult:
        """Analyze request results and generate benchmark metrics."""
        # Filter out exceptions and extract valid results
        valid_results = []
        exceptions = []
        
        for result in results:
            if isinstance(result, Exception):
                exceptions.append(str(result))
            elif isinstance(result, RequestResult):
                valid_results.append(result)
        
        # Calculate metrics
        successful_requests = sum(1 for r in valid_results if r.success)
        failed_requests = len(valid_results) - successful_requests + len(exceptions)
        rate_limited_requests = sum(1 for r in valid_results if r.rate_limited)
        cached_requests = sum(1 for r in valid_results if r.cached)
        
        # Response time statistics
        response_times = [r.duration for r in valid_results]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            median_response_time = statistics.median(response_times)
            
            # Percentiles
            sorted_times = sorted(response_times)
            p95_index = int(0.95 * len(sorted_times))
            p99_index = int(0.99 * len(sorted_times))
            p95_response_time = sorted_times[min(p95_index, len(sorted_times) - 1)]
            p99_response_time = sorted_times[min(p99_index, len(sorted_times) - 1)]
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
            median_response_time = 0
            p95_response_time = 0
            p99_response_time = 0
        
        # Throughput
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        
        # Error collection
        errors = [r.error for r in valid_results if r.error] + exceptions
        unique_errors = list(set(errors))
        
        # Additional details
        details = {
            "total_response_time": sum(response_times),
            "avg_response_size": statistics.mean([r.response_size for r in valid_results]) if valid_results else 0,
            "exception_count": len(exceptions),
            "cache_hit_rate": cached_requests / len(valid_results) if valid_results else 0,
            "rate_limit_rate": rate_limited_requests / len(valid_results) if valid_results else 0,
        }
        
        return BenchmarkResult(
            test_name=test_name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            rate_limited_requests=rate_limited_requests,
            cached_requests=cached_requests,
            total_duration=total_duration,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            median_response_time=median_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            requests_per_second=requests_per_second,
            errors=unique_errors,
            details=details
        )
    
    def display_results(self):
        """Display benchmark results in a formatted way."""
        print("=" * 80)
        print("🚀 MIDDLEWARE PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)
        
        print(f"Server: {self.config.server_url}")
        print(f"Configuration: {self.config.total_requests} requests, {self.config.concurrent_requests} concurrent")
        print(f"Timestamp: {time.ctime()}")
        print()
        
        for test_name, result in self.results.items():
            self._display_test_result(result)
            print()
    
    def _display_test_result(self, result: BenchmarkResult):
        """Display a single test result."""
        print(f"📊 {result.test_name.upper().replace('_', ' ')} TEST")
        print("-" * 40)
        
        # Success metrics
        success_rate = (result.successful_requests / result.total_requests * 100) if result.total_requests > 0 else 0
        print(f"Success Rate:      {success_rate:.1f}% ({result.successful_requests}/{result.total_requests})")
        print(f"Failed Requests:   {result.failed_requests}")
        
        if result.rate_limited_requests > 0:
            print(f"Rate Limited:      {result.rate_limited_requests}")
        
        if result.cached_requests > 0:
            print(f"Cached Responses:  {result.cached_requests}")
        
        print()
        
        # Performance metrics
        print(f"Throughput:        {result.requests_per_second:.2f} req/s")
        print(f"Total Duration:    {result.total_duration:.3f}s")
        print()
        
        # Response time metrics
        print(f"Response Times:")
        print(f"  Average:         {result.avg_response_time:.3f}s")
        print(f"  Median:          {result.median_response_time:.3f}s")
        print(f"  Min:             {result.min_response_time:.3f}s")
        print(f"  Max:             {result.max_response_time:.3f}s")
        print(f"  95th percentile: {result.p95_response_time:.3f}s")
        print(f"  99th percentile: {result.p99_response_time:.3f}s")
        
        # Errors
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(result.errors) > 5:
                print(f"  ... and {len(result.errors) - 5} more")
    
    def save_results(self, output_file: str):
        """Save results to a JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert results to dict format
        results_dict = {
            "timestamp": time.time(),
            "config": asdict(self.config),
            "results": {name: asdict(result) for name, result in self.results.items()}
        }
        
        with open(output_path, "w") as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        self.logger.info(f"Results saved to {output_file}")


def main():
    """Main entry point for the benchmark tool."""
    parser = argparse.ArgumentParser(
        description="Benchmark AgentUp middleware performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python benchmark_middleware.py                              # Default benchmark
  python benchmark_middleware.py --requests 200 --concurrent 20  # High load test
  python benchmark_middleware.py --tests rate_limiting caching    # Specific tests
  python benchmark_middleware.py --output results.json           # Save results
        """
    )
    
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Server URL to benchmark (default: %(default)s)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total number of requests per test (default: %(default)s)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Number of concurrent requests (default: %(default)s)"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Number of warmup requests (default: %(default)s)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: %(default)s)"
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        choices=["rate_limiting", "caching", "timing", "throughput", "stress"],
        default=["rate_limiting", "caching", "timing", "throughput"],
        help="Tests to run (default: %(default)s)"
    )
    parser.add_argument(
        "--output",
        help="Output file for results (JSON format)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate server URL
    try:
        parsed_url = urlparse(args.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Invalid URL format")
    except Exception:
        print(f"Error: Invalid server URL: {args.url}", file=sys.stderr)
        return 1
    
    # Create config
    config = BenchmarkConfig(
        server_url=args.url,
        total_requests=args.requests,
        concurrent_requests=args.concurrent,
        warmup_requests=args.warmup,
        timeout=args.timeout,
        output_file=args.output,
        verbose=args.verbose,
        test_types=args.tests
    )
    
    # Run benchmarks
    try:
        benchmark = MiddlewareBenchmark(config)
        results = asyncio.run(benchmark.run_benchmarks())
        
        # Display results
        benchmark.display_results()
        
        # Save results if requested
        if args.output:
            benchmark.save_results(args.output)
        
        # Determine overall success
        overall_success = all(
            result.successful_requests > 0 and result.successful_requests >= result.total_requests * 0.8
            for result in results.values()
        )
        
        if overall_success:
            print("\n✅ All benchmarks completed successfully!")
            return 0
        else:
            print("\n⚠️  Some benchmarks had issues. Check the results above.")
            return 1
            
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Benchmark failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())