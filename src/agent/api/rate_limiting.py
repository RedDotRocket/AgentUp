import threading
import time
from collections import defaultdict
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class NetworkRateLimitMiddleware(BaseHTTPMiddleware):
    """Network-level rate limiting middleware for FastAPI applications.

    This middleware provides per-endpoint rate limiting with different
    limits for different endpoint types. It uses a simple in-memory
    token bucket algorithm.
    """

    def __init__(self, app, endpoint_limits: dict[str, dict[str, Any]] | None = None):
        """
        Initialize rate limiting middleware.

        Args:
            app: FastAPI application instance
            endpoint_limits: Dictionary mapping endpoint patterns to rate limit configs
                Example:
                {
                    "/": {"rpm": 100, "burst": 120},
                    "/mcp": {"rpm": 50, "burst": 60},
                    "/health": {"rpm": 200, "burst": 240}
                }
        """
        super().__init__(app)

        # Default endpoint limits
        self.endpoint_limits = endpoint_limits or {
            "/": {"rpm": 100, "burst": 120},  # Main JSON-RPC endpoint
            "/mcp": {"rpm": 50, "burst": 60},  # MCP endpoints
            "/health": {"rpm": 200, "burst": 240},  # Health check
            "/status": {"rpm": 60, "burst": 72},  # Status endpoint
            "default": {"rpm": 60, "burst": 72},  # Default for other endpoints
        }

        # In-memory storage for rate limiting
        # Format: {client_ip: {endpoint: {"tokens": float, "last_refill": float}}}
        self.client_buckets: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))

        # Thread safety lock for bucket modifications
        self._bucket_lock = threading.RLock()

        logger.debug("Network rate limiting middleware initialized", endpoint_limits=self.endpoint_limits)

    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting.

        Uses the client IP address. In production, you might want to use
        authenticated user ID instead or in addition to IP.
        """
        # Try to get real IP from X-Forwarded-For header (if behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            # Fallback to direct client IP
            client_ip = request.client.host if request.client else "unknown"

        return client_ip

    def _get_endpoint_config(self, path: str) -> dict[str, Any]:
        # Exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]

        # Pattern matching for endpoints with parameters
        for endpoint_pattern, config in self.endpoint_limits.items():
            if endpoint_pattern == "default":
                continue
            if path.startswith(endpoint_pattern):
                return config

        # Default configuration
        return self.endpoint_limits.get("default", {"rpm": 60, "burst": 72})

    def _is_rate_limited(self, client_id: str, endpoint: str, rpm: int, burst: int) -> bool:
        """Check if client is rate limited using token bucket algorithm.

        Args:
            client_id: Client identifier
            endpoint: Endpoint path
            rpm: Requests per minute limit
            burst: Burst capacity (tokens in bucket)

        Returns:
            True if rate limited, False if allowed
        """
        with self._bucket_lock:
            current_time = time.time()

            # Get or initialize bucket for this client/endpoint
            bucket = self.client_buckets[client_id][endpoint]

            if "tokens" not in bucket:
                # Initialize bucket with full capacity
                bucket["tokens"] = float(burst)
                bucket["last_refill"] = current_time
                logger.debug(
                    "Initialized token bucket",
                    client_id=client_id,
                    endpoint=endpoint,
                    initial_tokens=burst,
                    bucket_id=id(bucket),
                )

            # Calculate time since last refill
            time_passed = current_time - bucket["last_refill"]
            tokens_before = bucket["tokens"]

            # Refill tokens based on time passed (rpm rate)
            tokens_to_add = time_passed * (rpm / 60.0)  # Convert rpm to tokens per second
            bucket["tokens"] = min(burst, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = current_time

            logger.debug(
                "Token bucket refill",
                client_id=client_id,
                endpoint=endpoint,
                time_passed=f"{time_passed:.3f}s",
                tokens_before=f"{tokens_before:.2f}",
                tokens_added=f"{tokens_to_add:.2f}",
                tokens_after_refill=f"{bucket['tokens']:.2f}",
                burst_limit=burst,
            )

            # Check if we have tokens available
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                logger.debug(
                    "Request allowed - token consumed",
                    client_id=client_id,
                    endpoint=endpoint,
                    tokens_remaining=f"{bucket['tokens']:.2f}",
                    rate_limited=False,
                    bucket_id=id(bucket),
                )
                return False  # Not rate limited
            else:
                logger.warning(
                    "Request rate limited - insufficient tokens",
                    client_id=client_id,
                    endpoint=endpoint,
                    tokens_available=f"{bucket['tokens']:.2f}",
                    rate_limited=True,
                )
                return True  # Rate limited

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Get client identifier and endpoint config
        client_id = self._get_client_identifier(request)
        endpoint_path = request.url.path
        endpoint_config = self._get_endpoint_config(endpoint_path)

        rpm = endpoint_config["rpm"]
        burst = endpoint_config["burst"]

        logger.debug(
            "Processing rate limit check",
            client_id=client_id,
            endpoint=endpoint_path,
            rpm=rpm,
            burst=burst,
            method=request.method,
        )

        # Check rate limit
        if self._is_rate_limited(client_id, endpoint_path, rpm, burst):
            # Rate limited - return 429 Too Many Requests
            logger.warning(
                "Rate limit exceeded", client_id=client_id, endpoint=endpoint_path, rpm_limit=rpm, method=request.method
            )

            # Calculate retry-after header (simple approach)
            retry_after = 60 / rpm  # Seconds until next token is available

            return Response(
                content='{"error": "Rate limit exceeded", "detail": "Too many requests"}',
                status_code=429,
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(rpm),
                    "X-RateLimit-Remaining": "0",
                    "Content-Type": "application/json",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        # IMPORTANT: Get the same bucket reference that _is_rate_limited used
        # This caused me untold pain when I use a different bucket reference
        bucket = self.client_buckets[client_id][endpoint_path]
        remaining_tokens = int(bucket.get("tokens", 0))
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining_tokens)

        logger.debug(
            "Rate limit headers added",
            client_id=client_id,
            endpoint=endpoint_path,
            remaining_tokens=remaining_tokens,
            bucket_tokens=f"{bucket.get('tokens', 0):.2f}",
            bucket_id=id(bucket),
        )

        # Log request processing time
        process_time = time.time() - start_time
        logger.debug(
            "Request processed",
            client_id=client_id,
            endpoint=endpoint_path,
            method=request.method,
            status_code=response.status_code,
            process_time=f"{process_time:.3f}s",
            rate_limit_remaining=remaining_tokens,
        )

        return response

    def get_rate_limit_stats(self) -> dict[str, Any]:
        current_time = time.time()
        stats = {
            "total_clients": len(self.client_buckets),
            "endpoint_limits": self.endpoint_limits,
            "active_buckets": 0,
            "clients_by_endpoint": defaultdict(int),
        }

        for _client_id, endpoints in self.client_buckets.items():
            for endpoint, bucket in endpoints.items():
                if current_time - bucket.get("last_refill", 0) < 300:  # Active in last 5 minutes
                    stats["active_buckets"] += 1
                    stats["clients_by_endpoint"][endpoint] += 1

        return stats
