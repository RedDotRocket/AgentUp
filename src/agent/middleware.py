"""Middleware system for handler functions."""

import asyncio
import functools
import hashlib
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

try:
    from a2a.types import Artifact
except ImportError:
    # Mock for testing
    Artifact = str

logger = logging.getLogger(__name__)

# Type for handler functions
T = TypeVar("T")
Handler = Callable[..., Artifact]


class MiddlewareError(Exception):
    """Base exception for middleware errors."""

    pass


class RateLimitError(MiddlewareError):
    """Raised when rate limit is exceeded."""

    pass


class ValidationError(MiddlewareError):
    """Raised when validation fails."""

    pass


class MiddlewareRegistry:
    """Registry for middleware functions."""

    def __init__(self):
        self._middleware: dict[str, Callable] = {}

    def register(self, name: str, middleware: Callable) -> None:
        """Register a middleware function."""
        self._middleware[name] = middleware

    def get(self, name: str) -> Callable | None:
        """Get a middleware function by name."""
        return self._middleware.get(name)

    def apply(self, handler: Handler, middleware_configs: list[dict[str, Any]]) -> Handler:
        """Apply multiple middleware to a handler."""
        for config in reversed(middleware_configs):
            middleware_name = config.get("name")
            middleware_func = self.get(middleware_name)
            if middleware_func:
                handler = middleware_func(handler, **config.get("params", {}))
        return handler


# Global middleware registry
_registry = MiddlewareRegistry()


# Rate limiting
class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self):
        self.buckets: dict[str, dict[str, Any]] = defaultdict(dict)

    def check_rate_limit(self, key: str, requests_per_minute: int = 60) -> bool:
        """Check if request is within rate limit."""
        current_time = time.time()
        bucket = self.buckets[key]

        # Initialize bucket if not exists
        if "tokens" not in bucket:
            bucket["tokens"] = requests_per_minute
            bucket["last_update"] = current_time
            bucket["requests_per_minute"] = requests_per_minute

        # Calculate tokens to add based on time passed
        time_passed = current_time - bucket["last_update"]
        tokens_to_add = time_passed * (requests_per_minute / 60.0)
        bucket["tokens"] = min(requests_per_minute, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = current_time

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


# Global rate limiter
_rate_limiter = RateLimiter()


# Caching
class SimpleCache:
    """Simple in-memory cache with TTL."""

    def __init__(self):
        self.cache: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                logger.debug(f"Cache hit for key: {key}")
                return entry["value"]
            else:
                # Expired, remove it
                del self.cache[key]
                logger.debug(f"Cache expired for key: {key}")
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL."""
        self.cache[key] = {"value": value, "expires_at": time.time() + ttl}
        logger.debug(f"Cache set for key: {key}, TTL: {ttl}s")

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache deleted for key: {key}")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.debug("Cache cleared")


# Global cache
_cache = SimpleCache()


# Retry logic
class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(self, max_attempts: int = 3, backoff_factor: float = 1.0, max_delay: float = 60.0):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay


async def execute_with_retry(func: Callable, retry_config: RetryConfig, *args, **kwargs) -> Any:
    """Execute function with retry logic."""
    last_exception = None

    for attempt in range(retry_config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < retry_config.max_attempts - 1:
                delay = min(retry_config.backoff_factor * (2**attempt), retry_config.max_delay)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {retry_config.max_attempts} attempts failed")

    raise last_exception


# Middleware decorators
def rate_limited(requests_per_minute: int = 60):
    """Rate limiting middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate rate limit key based on function name and arguments
            key = f"{func.__name__}:{hash(str(args))}"

            if not _rate_limiter.check_rate_limit(key, requests_per_minute):
                raise RateLimitError(f"Rate limit exceeded for {func.__name__}")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def cached(ttl: int = 300):
    """Caching middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = hashlib.sha256(key_data.encode()).hexdigest()

            # Try to get from cache
            result = _cache.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            _cache.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def retryable(max_attempts: int = 3, backoff_factor: float = 1.0, max_delay: float = 60.0):
    """Retry middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retry_config = RetryConfig(max_attempts, backoff_factor, max_delay)
            return await execute_with_retry(func, retry_config, *args, **kwargs)

        return wrapper

    return decorator


def logged(log_level: int = logging.INFO):
    """Logging middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.log(log_level, f"Starting {func.__name__}")

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.log(log_level, f"Completed {func.__name__} in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Failed {func.__name__} after {execution_time:.3f}s: {e}")
                raise

        return wrapper

    return decorator


def timed():
    """Timing middleware decorator that logs execution time."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.warning(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
                raise

        return wrapper

    return decorator


def validated(schema: dict[str, Any]):
    """Input validation middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Simple validation implementation
            # In production, integrate with proper validation library like Pydantic
            if "required_fields" in schema:
                for field in schema["required_fields"]:
                    if field not in kwargs:
                        raise ValidationError(f"Required field '{field}' is missing")

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def with_middleware(middleware_configs: list[dict[str, Any]]):
    """Apply multiple middleware based on configuration."""

    def decorator(func: Callable) -> Callable:
        # Apply middleware in reverse order (last middleware wraps first)
        wrapped_func = func
        for config in reversed(middleware_configs):
            middleware_name = config.get("name")
            params = config.get("params", {})

            if middleware_name == "rate_limited":
                wrapped_func = rate_limited(**params)(wrapped_func)
            elif middleware_name == "cached":
                wrapped_func = cached(**params)(wrapped_func)
            elif middleware_name == "retryable":
                wrapped_func = retryable(**params)(wrapped_func)
            elif middleware_name == "logged":
                wrapped_func = logged(**params)(wrapped_func)
            elif middleware_name == "timed":
                wrapped_func = timed()(wrapped_func)
            elif middleware_name == "validated":
                wrapped_func = validated(**params)(wrapped_func)

        # Preserve AI function attributes on the final wrapped function
        if hasattr(func, "_is_ai_function"):
            wrapped_func._is_ai_function = func._is_ai_function
        if hasattr(func, "_ai_function_schema"):
            wrapped_func._ai_function_schema = func._ai_function_schema

        return wrapped_func

    return decorator


# Utility functions for manual middleware application
def apply_rate_limiting(handler: Callable, requests_per_minute: int = 60) -> Callable:
    """Apply rate limiting to a handler."""
    return rate_limited(requests_per_minute)(handler)


def apply_caching(handler: Callable, ttl: int = 300) -> Callable:
    """Apply caching to a handler."""
    return cached(ttl)(handler)


def apply_retry(handler: Callable, max_attempts: int = 3) -> Callable:
    """Apply retry logic to a handler."""
    return retryable(max_attempts)(handler)


# Cache management functions
def clear_cache() -> None:
    """Clear all cached data."""
    _cache.clear()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    total_entries = len(_cache.cache)
    expired_entries = 0
    current_time = time.time()

    for entry in _cache.cache.values():
        if current_time >= entry["expires_at"]:
            expired_entries += 1

    return {
        "total_entries": total_entries,
        "expired_entries": expired_entries,
        "active_entries": total_entries - expired_entries,
    }


# Rate limiter management functions
def reset_rate_limits() -> None:
    """Reset all rate limit buckets."""
    _rate_limiter.buckets.clear()


def get_rate_limit_stats() -> dict[str, Any]:
    """Get rate limiter statistics."""
    return {"active_buckets": len(_rate_limiter.buckets), "buckets": dict(_rate_limiter.buckets)}


# Register middleware with the registry
_registry.register("rate_limited", rate_limited)
_registry.register("cached", cached)
_registry.register("retryable", retryable)
_registry.register("logged", logged)
_registry.register("timed", timed)
_registry.register("validated", validated)


# Export for external use
__all__ = [
    "rate_limited",
    "cached",
    "retryable",
    "logged",
    "timed",
    "validated",
    "with_middleware",
    "clear_cache",
    "get_cache_stats",
    "reset_rate_limits",
    "get_rate_limit_stats",
    "MiddlewareError",
    "RateLimitError",
    "ValidationError",
]
