import asyncio
import functools
import hashlib
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

import structlog

try:
    from a2a.types import Artifact
except ImportError:
    # Mock for testing
    Artifact = str

logger = structlog.get_logger(__name__)

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
class CacheBackend:
    """Base class for cache backends."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        raise NotImplementedError

    async def clear(self) -> None:
        """Clear all cache entries."""
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """Simple in-memory cache with TTL."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        super().__init__(default_ttl)
        self.cache: dict[str, dict[str, Any]] = {}
        self.max_size = max_size

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                logger.debug(f"Cache hit in memory key: {key}")
                return entry["value"]
            else:
                # Expired, remove it
                del self.cache[key]
                logger.debug(f"Cache expired for key: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        # Use provided TTL or fall back to default
        effective_ttl = ttl if ttl is not None else self.default_ttl

        # Simple eviction: remove oldest entry if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[key] = {"value": value, "expires_at": time.time() + effective_ttl}
        logger.debug(f"Cache set in memory for key: {key}, TTL: {effective_ttl}s")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache deleted for key: {key}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.debug("Cache cleared")


class ValkeyCache(CacheBackend):
    """Valkey/Redis cache backend."""

    def __init__(self, url: str, db: int = 1, max_connections: int = 10, default_ttl: int = 300):
        super().__init__(default_ttl)
        self.url = url
        self.db = db
        self.max_connections = max_connections
        self._client = None

    async def _get_client(self):
        """Get Valkey client, creating if needed."""
        if self._client is None:
            try:
                # Try valkey first, then fall back to redis
                try:
                    import valkey.asyncio as valkey

                    self._client = valkey.from_url(
                        self.url, db=self.db, max_connections=self.max_connections, decode_responses=True
                    )
                    logger.info(f"Connected to Valkey at {self.url}")
                except ImportError:
                    # Fallback to redis library for compatibility
                    import redis.asyncio as redis

                    self._client = redis.from_url(
                        self.url, db=self.db, max_connections=self.max_connections, decode_responses=True
                    )
                    logger.info(f"Connected to Redis at {self.url}")
            except ImportError:
                logger.error(
                    "Neither valkey nor redis library available. Install with: pip install valkey or pip install redis"
                )
                raise
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                logger.debug(f"Cache hit in Valkey/Redis for key: {key}")
                # Try to deserialize JSON
                try:
                    import json

                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return None
        except Exception as e:
            logger.error(f"Cache get error in Valkey for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        try:
            client = await self._get_client()
            # Use provided TTL or fall back to default
            effective_ttl = ttl if ttl is not None else self.default_ttl

            # Serialize to JSON if not string
            if not isinstance(value, str):
                import json

                value = json.dumps(value)
            await client.setex(key, effective_ttl, value)
            logger.debug(f"Cache set in Valkey for key: {key}, TTL: {effective_ttl}s")
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        try:
            client = await self._get_client()
            await client.delete(key)
            logger.debug(f"Cache deleted in Valkey for key: {key}")
        except Exception as e:
            logger.error(f"Cache delete error in Valkey for key {key}: {e}")

    async def clear(self) -> None:
        """Clear all cache entries."""
        try:
            client = await self._get_client()
            await client.flushdb()
            logger.debug("Cache in Valkey cleared")
        except Exception as e:
            logger.error(f"Cache in Valkey clear error: {e}")


# Global cache backend instance - will be configured based on agent config
_cache_backend: CacheBackend | None = None


def configure_cache_backend(config: dict[str, Any]) -> CacheBackend:
    """Configure cache backend based on agent configuration."""
    cache_config = config.get("cache", {})
    cache_type = cache_config.get("type", "memory")
    cache_settings = cache_config.get("config", {})

    # Extract default_ttl from cache config
    default_ttl = cache_settings.get("default_ttl", 300)

    if cache_type == "valkey":
        url = cache_settings.get("url", "redis://localhost:6379")
        db = cache_settings.get("db", 1)
        max_connections = cache_settings.get("max_connections", 10)
        return ValkeyCache(url, db, max_connections, default_ttl)
    elif cache_type == "memory":
        max_size = cache_settings.get("max_size", 1000)
        return MemoryCache(max_size, default_ttl)
    else:
        logger.warning(f"Unknown cache type: {cache_type}, falling back to memory")
        return MemoryCache(1000, default_ttl)


def get_cache_backend() -> CacheBackend:
    """Get the configured cache backend."""
    global _cache_backend
    if _cache_backend is None:
        # Load configuration and create backend
        try:
            # Try relative import first (development context)
            try:
                from ..agent.config import load_config
            except ImportError:
                # Try installed package import (agent context)
                from agent.config import load_config

            config = load_config()
            _cache_backend = configure_cache_backend(config)
            logger.info(f"Cache backend configured: {type(_cache_backend).__name__}")
        except Exception as e:
            logger.error(f"Failed to configure cache backend: {e}")
            _cache_backend = MemoryCache()
    return _cache_backend


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


def cached(ttl: int | None = None):
    """Caching middleware decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key based on function name and message content
            # Extract content from Task object if present
            cache_key_parts = [func.__name__]

            for arg in args:
                if hasattr(arg, "history") and arg.history:
                    # Extract message content from Task history
                    try:
                        latest_message = arg.history[-1]  # Get latest message
                        if hasattr(latest_message, "parts") and latest_message.parts:
                            # Extract text from message parts
                            text_parts = []
                            for part in latest_message.parts:
                                if hasattr(part, "root") and hasattr(part.root, "text"):
                                    text_parts.append(part.root.text)
                            if text_parts:
                                cache_key_parts.append(":".join(text_parts))
                        elif hasattr(latest_message, "content"):
                            cache_key_parts.append(str(latest_message.content))
                    except (AttributeError, IndexError):
                        # Fallback to string representation if structure is unexpected
                        cache_key_parts.append(str(arg))
                else:
                    # For non-Task arguments, use string representation
                    cache_key_parts.append(str(arg))

            # Add kwargs to cache key
            for key, value in kwargs.items():
                cache_key_parts.append(f"{key}={value}")

            key_data = ":".join(cache_key_parts)
            cache_key = hashlib.sha256(key_data.encode()).hexdigest()

            # Get configured cache backend
            cache_backend = get_cache_backend()

            # Try to get from cache
            result = await cache_backend.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            # If TTL is provided, use it; otherwise cache backend will use its default_ttl
            result = await func(*args, **kwargs)
            await cache_backend.set(cache_key, result, ttl)
            # Uncomment for debug logging
            # ttl_info = f"TTL: {ttl}s" if ttl is not None else f"TTL: {cache_backend.default_ttl}s (default)"
            # logger.debug(f"Cache miss, stored result for key: {cache_key[:16]}... {ttl_info}")
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
            elif middleware_name == "timed":
                wrapped_func = timed()(wrapped_func)
            elif middleware_name == "validated":
                wrapped_func = validated(**params)(wrapped_func)

        # Preserve AI function attributes and middleware flags on the final wrapped function
        if hasattr(func, "_is_ai_function"):
            wrapped_func._is_ai_function = func._is_ai_function
        if hasattr(func, "_ai_function_schema"):
            wrapped_func._ai_function_schema = func._ai_function_schema
        if hasattr(func, "_agentup_middleware_applied"):
            wrapped_func._agentup_middleware_applied = func._agentup_middleware_applied
        if hasattr(func, "_agentup_state_applied"):
            wrapped_func._agentup_state_applied = func._agentup_state_applied

        return wrapped_func

    return decorator


# Utility functions for manual middleware application
def apply_rate_limiting(handler: Callable, requests_per_minute: int = 60) -> Callable:
    """Apply rate limiting to a handler."""
    return rate_limited(requests_per_minute)(handler)


def apply_caching(handler: Callable, ttl: int | None = None) -> Callable:
    """Apply caching to a handler."""
    return cached(ttl)(handler)


def apply_retry(handler: Callable, max_attempts: int = 3) -> Callable:
    """Apply retry logic to a handler."""
    return retryable(max_attempts)(handler)


# Cache management functions
def clear_cache() -> None:
    """Clear all cached data (sync version for backward compatibility)."""
    cache_backend = get_cache_backend()

    import asyncio

    try:
        asyncio.run(cache_backend.clear())
    except RuntimeError:
        # Already in event loop - create new task
        loop = asyncio.get_event_loop()
        loop.create_task(cache_backend.clear())


async def clear_cache_async() -> None:
    """Clear all cached data (async version)."""
    cache_backend = get_cache_backend()
    await cache_backend.clear()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics (sync version for backward compatibility)."""
    cache_backend = get_cache_backend()

    if isinstance(cache_backend, MemoryCache):
        total_entries = len(cache_backend.cache)
        expired_entries = 0
        current_time = time.time()

        for entry in cache_backend.cache.values():
            if current_time >= entry["expires_at"]:
                expired_entries += 1

        return {
            "backend": "memory",
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
        }
    elif isinstance(cache_backend, ValkeyCache):
        # For sync version, return basic info
        return {
            "backend": "valkey",
            "url": cache_backend.url,
            "db": cache_backend.db,
            "max_connections": cache_backend.max_connections,
        }
    else:
        return {"backend": "unknown"}


async def get_cache_stats_async() -> dict[str, Any]:
    """Get cache statistics (async version)."""
    cache_backend = get_cache_backend()

    if isinstance(cache_backend, MemoryCache):
        total_entries = len(cache_backend.cache)
        expired_entries = 0
        current_time = time.time()

        for entry in cache_backend.cache.values():
            if current_time >= entry["expires_at"]:
                expired_entries += 1

        return {
            "backend": "memory",
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
        }
    elif isinstance(cache_backend, ValkeyCache):
        try:
            client = await cache_backend._get_client()
            info = await client.info("memory")
            return {
                "backend": "valkey",
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "max_memory": info.get("maxmemory", 0),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            logger.error(f"Error getting Valkey stats: {e}")
            return {"backend": "valkey", "error": str(e)}
    else:
        return {"backend": "unknown"}


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
_registry.register("timed", timed)
_registry.register("validated", validated)


# AI-compatible middleware functions
def get_ai_compatible_middleware() -> list[dict[str, Any]]:
    """Get middleware configurations that are compatible with AI routing."""
    try:
        # Try relative import first (development context)
        try:
            from agent.handlers.handlers import _load_middleware_config
        except ImportError:
            try:
                # Try installed package import (agent context)
                from agent.handlers.handlers import _load_middleware_config
            except ImportError:
                logger.debug("Could not import _load_middleware_config, returning empty list")
                return []

        middleware_configs = _load_middleware_config()

        # Filter to only AI-compatible middleware (exclude caching and rate limiting)
        ai_compatible = [
            m
            for m in middleware_configs
            if m.get("name") in ["timed", "validated"]  # Exclude "cached", "rate_limited", "retryable"
        ]

        return ai_compatible
    except Exception as e:
        logger.debug(f"Could not load AI-compatible middleware config: {e}")
        return []


def apply_ai_routing_middleware(func: Callable, func_name: str) -> Callable:
    """Apply only AI-compatible middleware to functions for AI routing."""
    ai_middleware = get_ai_compatible_middleware()

    if not ai_middleware:
        return func

    try:
        # Apply middleware using existing with_middleware function
        wrapped_func = with_middleware(ai_middleware)(func)
        middleware_names = [m.get("name") for m in ai_middleware]
        logger.debug(f"Applied AI-compatible middleware to '{func_name}': {middleware_names}")
        return wrapped_func
    except Exception as e:
        logger.error(f"Failed to apply AI middleware to '{func_name}': {e}")
        return func


async def execute_ai_function_with_middleware(func_name: str, func: Callable, *args, **kwargs) -> Any:
    """Execute AI function with selective middleware application."""
    ai_middleware = get_ai_compatible_middleware()

    if not ai_middleware:
        # No middleware to apply, execute directly
        return await func(*args, **kwargs)

    # Apply middleware dynamically
    wrapped_func = apply_ai_routing_middleware(func, func_name)

    # Execute the wrapped function
    return await wrapped_func(*args, **kwargs)


# Export for external use
__all__ = [
    "rate_limited",
    "cached",
    "retryable",
    "timed",
    "validated",
    "with_middleware",
    "clear_cache",
    "get_cache_stats",
    "reset_rate_limits",
    "get_rate_limit_stats",
    "configure_cache_backend",
    "get_cache_backend",
    "CacheBackend",
    "MemoryCache",
    "ValkeyCache",
    "MiddlewareError",
    "RateLimitError",
    "ValidationError",
    "get_ai_compatible_middleware",
    "apply_ai_routing_middleware",
    "execute_ai_function_with_middleware",
]
