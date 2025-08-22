"""
Middleware implementations using Pydantic models.

This module provides the actual middleware function implementations that use
the Pydantic models for configuration and validation.
"""

import asyncio
import functools
import hashlib
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import structlog

from .model import (
    CacheBackendType,
    CacheConfig,
    RateLimitConfig,
    RetryConfig,
)

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# For backward compatibility with old imports
RateLimitError = RateLimitExceeded


class CacheBackend:
    def __init__(self, config: CacheConfig):
        self.config = config

    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def clear(self) -> None:
        raise NotImplementedError


class MemoryCache(CacheBackend):
    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self.cache: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> Any | None:
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

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self.config.default_ttl

        # Simple eviction: remove oldest entry if at capacity
        if len(self.cache) >= self.config.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

        self.cache[key] = {"value": value, "expires_at": time.time() + effective_ttl}
        logger.debug(f"Cache set for key: {key}, TTL: {effective_ttl}s")

    async def delete(self, key: str) -> None:
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache deleted for key: {key}")

    async def clear(self) -> None:
        self.cache.clear()
        logger.debug("Cache cleared")


class ValkeyCache(CacheBackend):
    def __init__(self, config: CacheConfig):
        super().__init__(config)
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                try:
                    import valkey.asyncio as valkey

                    self._client = valkey.from_url(
                        self.config.valkey_url,
                        db=self.config.valkey_db,
                        max_connections=self.config.valkey_max_connections,
                        decode_responses=True,
                    )
                    logger.info(f"Connected to Valkey at {self.config.valkey_url}")
                except ImportError:
                    import redis.asyncio as redis

                    self._client = redis.from_url(
                        self.config.valkey_url,
                        db=self.config.valkey_db,
                        max_connections=self.config.valkey_max_connections,
                        decode_responses=True,
                    )
                    logger.info(f"Connected to Redis at {self.config.valkey_url}")
            except ImportError:
                logger.error("Neither valkey nor redis library available")
                raise
        return self._client

    async def get(self, key: str) -> Any | None:
        try:
            client = await self._get_client()
            value = await client.get(f"{self.config.key_prefix}:{key}")
            if value:
                logger.debug(f"Cache hit in Valkey for key: {key}")
                if self.config.serialization_format == "json":
                    import json

                    return json.loads(value)
                return value
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            client = await self._get_client()
            effective_ttl = ttl if ttl is not None else self.config.default_ttl

            if self.config.serialization_format == "json":
                import json

                value = json.dumps(value)

            await client.setex(f"{self.config.key_prefix}:{key}", effective_ttl, value)
            logger.debug(f"Cache set in Valkey for key: {key}, TTL: {effective_ttl}s")
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")

    async def delete(self, key: str) -> None:
        try:
            client = await self._get_client()
            await client.delete(f"{self.config.key_prefix}:{key}")
            logger.debug(f"Cache deleted in Valkey for key: {key}")
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")

    async def clear(self) -> None:
        try:
            client = await self._get_client()
            await client.flushdb()
            logger.debug("Valkey cache cleared")
        except Exception as e:
            logger.error(f"Valkey cache clear error: {e}")


class RateLimiter:
    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig(
            enabled=False,
            requests_per_minute=60,  # 1 per second average
            burst_limit=120,  # Allow 2-minute burst capacity
            window_size_seconds=10,  # 10-second detection window
            key_strategy="function_name",
            enforcement_mode="strict",
        )
        self.buckets: dict[str, dict[str, Any]] = defaultdict(dict)

    def check_rate_limit(
        self, key: str, requests_per_minute: int | None = None, custom_limit: int | None = None
    ) -> bool:
        if not self.config.enabled:
            return True

        # Check whitelist
        if key in self.config.whitelist:
            return True

        current_time = time.time()
        bucket = self.buckets[key]

        # Determine effective rate limit
        effective_rate = requests_per_minute or custom_limit or self.config.requests_per_minute

        # Initialize bucket if not exists
        if "tokens" not in bucket:
            bucket["tokens"] = effective_rate
            bucket["last_update"] = current_time
            bucket["requests_per_minute"] = effective_rate

        # Calculate tokens to add based on time passed
        time_passed = current_time - bucket["last_update"]
        tokens_to_add = time_passed * (effective_rate / 60.0)
        bucket["tokens"] = min(effective_rate, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = current_time

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


# Global instances
# Global shared cache configuration
_global_cache_config: CacheConfig | None = None


def get_global_cache_config() -> CacheConfig:
    global _global_cache_config
    if _global_cache_config is None:
        try:
            from agent.config import Config

            middleware_config = Config.middleware.model_dump()
            cache_params = {}
            if isinstance(middleware_config, dict) and middleware_config.get("caching", {}).get("enabled", False):
                caching_section = middleware_config.get("caching", {})
                cache_params = {
                    "backend_type": caching_section.get("backend", "memory"),
                    "default_ttl": caching_section.get("default_ttl", 300),
                    "max_size": caching_section.get("max_size", 1000),
                }

            _global_cache_config = CacheConfig(**cache_params)
            logger.debug(f"Created global cache config: {_global_cache_config}")
        except FileNotFoundError as e:
            logger.warning(f"Could not load global cache config, falling back to default config: {e}")
            _global_cache_config = CacheConfig()

    return _global_cache_config


def reset_global_cache_config():
    global _global_cache_config
    _global_cache_config = None
    logger.debug("Reset global cache configuration")


_cache_backends: dict[str, CacheBackend] = {}
_rate_limiters: dict[str, RateLimiter] = {}


def get_cache_backend(config: CacheConfig) -> CacheBackend:
    cache_key = f"{config.backend_type}:{config.key_prefix}:{config.default_ttl}:{config.max_size}"
    if cache_key not in _cache_backends:
        if config.backend_type == CacheBackendType.MEMORY:
            _cache_backends[cache_key] = MemoryCache(config)
        elif config.backend_type in (CacheBackendType.VALKEY, CacheBackendType.REDIS):
            _cache_backends[cache_key] = ValkeyCache(config)
        else:
            _cache_backends[cache_key] = MemoryCache(config)
    return _cache_backends[cache_key]


def get_rate_limiter(config: RateLimitConfig) -> RateLimiter:
    limiter_key = f"{config.key_strategy}:{config.requests_per_minute}"
    if limiter_key not in _rate_limiters:
        _rate_limiters[limiter_key] = RateLimiter(config)
    return _rate_limiters[limiter_key]


async def execute_with_retry(func: Callable, config: RetryConfig, *args, **kwargs) -> Any:
    if not config.enabled:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    last_exception = None
    for attempt in range(config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = config.calculate_delay(attempt)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {config.max_attempts} attempts failed")

    raise last_exception


# Middleware decorators
def rate_limited(config: RateLimitConfig | None = None, requests_per_minute: int = 60):
    if config is None:
        config = RateLimitConfig(requests_per_minute=requests_per_minute)

    def decorator(func: Callable) -> Callable:
        rate_limiter = get_rate_limiter(config)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate rate limit key based on strategy
            if config.key_strategy == "function_name" and not args and not kwargs:
                # Only use function name if no arguments provided
                key = func.__name__
            elif config.key_strategy == "user_id" and "user_id" in kwargs:
                key = f"{func.__name__}:{kwargs['user_id']}"
            else:
                # Include arguments in the key for separate buckets per argument combination
                key = f"{func.__name__}:{hash(str(args))}"

            # Check custom limits
            custom_limit = config.custom_limits.get(func.__name__)

            if not rate_limiter.check_rate_limit(key, custom_limit):
                error_msg = f"Rate limit exceeded for {func.__name__}"
                if config.enforcement_mode == "log_only":
                    logger.warning(error_msg)
                elif config.enforcement_mode == "soft":
                    logger.warning(f"{error_msg} (soft limit)")
                else:  # strict
                    raise RateLimitExceeded(error_msg)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def cached(config: CacheConfig | None = None, ttl: int | None = None):
    if config is None:
        config = get_global_cache_config()

    def decorator(func: Callable) -> Callable:
        cache_backend = get_cache_backend(config)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not config.enabled:
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key_parts = [func.__name__]

            # Skip Task objects in args since they contain unique IDs
            for arg in args:
                # Check if this is a Task object (has 'id' attribute)
                if hasattr(arg, "id") and hasattr(arg, "status"):
                    # Skip Task objects - they have unique IDs that prevent caching
                    continue
                cache_key_parts.append(str(arg))

            for key, value in kwargs.items():
                # Skip context objects that might contain unique data
                if key == "context" and hasattr(value, "user_id"):
                    continue
                cache_key_parts.append(f"{key}={value}")

            key_data = ":".join(cache_key_parts)
            cache_key = hashlib.sha256(key_data.encode()).hexdigest()

            # Try to get from cache
            result = await cache_backend.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            effective_ttl = ttl if ttl is not None else config.default_ttl
            await cache_backend.set(cache_key, result, effective_ttl)
            return result

        return wrapper

    return decorator


def retryable(config: RetryConfig | None = None, max_attempts: int = 3, backoff_factor: float | None = None):
    if config is None:
        kwargs = {"max_attempts": max_attempts}
        if backoff_factor is not None:
            kwargs["backoff_factor"] = backoff_factor
        config = RetryConfig(**kwargs)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await execute_with_retry(func, config, *args, **kwargs)

        return wrapper

    return decorator


def timed():
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Import module logger to match test expectations
            from . import logger as middleware_logger

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                middleware_logger.info(f"{func.__name__} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                middleware_logger.warning(f"{func.__name__} failed after {execution_time:.3f}s: {e}")
                raise

        return wrapper

    return decorator


def with_middleware(middleware_configs: list[dict[str, Any]]):
    # Import module logger for consistency

    def decorator(func: Callable) -> Callable:
        wrapped_func = func

        # Apply middleware in reverse order (last middleware wraps first)
        for config in reversed(middleware_configs):
            middleware_name = config.get("name")
            params = config.get("params", {})

            if middleware_name == "rate_limited":
                rate_config = RateLimitConfig(**params) if params else RateLimitConfig()
                wrapped_func = rate_limited(rate_config)(wrapped_func)
            elif middleware_name == "cached":
                if params:
                    cache_config = CacheConfig(**params)
                else:
                    cache_config = get_global_cache_config()
                wrapped_func = cached(cache_config)(wrapped_func)
            elif middleware_name == "retryable":
                retry_config = RetryConfig(**params) if params else RetryConfig()
                wrapped_func = retryable(retry_config)(wrapped_func)
            elif middleware_name == "timed":
                wrapped_func = timed()(wrapped_func)

        # Preserve function attributes
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


# AI-compatible middleware functions
def get_ai_compatible_middleware() -> list[dict[str, Any]]:
    try:
        from ..capabilities.manager import _load_middleware_config

        middleware_configs = _load_middleware_config()

        # Filter to only AI-compatible middleware (exclude caching and rate limiting)
        ai_compatible = [
            m
            for m in middleware_configs
            if m.get("name") in ["timed"]  # Only timing middleware is AI-compatible
        ]

        return ai_compatible
    except Exception as e:
        logger.debug(f"Could not load AI-compatible middleware config: {e}")
        return []


def apply_ai_routing_middleware(func: Callable, func_name: str) -> Callable:
    ai_middleware = get_ai_compatible_middleware()

    if not ai_middleware:
        return func

    try:
        wrapped_func = with_middleware(ai_middleware)(func)
        middleware_names = [m.get("name") for m in ai_middleware]
        logger.debug(f"Applied AI-compatible middleware to '{func_name}': {middleware_names}")
        return wrapped_func
    except Exception as e:
        logger.error(f"Failed to apply AI middleware to '{func_name}': {e}")
        return func


async def execute_ai_function_with_middleware(func_name: str, func: Callable, *args, **kwargs) -> Any:
    ai_middleware = get_ai_compatible_middleware()

    if not ai_middleware:
        # No middleware to apply, execute directly
        return await func(*args, **kwargs)

    # Apply middleware dynamically
    wrapped_func = apply_ai_routing_middleware(func, func_name)

    # Execute the wrapped function
    return await wrapped_func(*args, **kwargs)


# Utility functions for manual middleware application
def apply_rate_limiting(
    handler: Callable, config: RateLimitConfig | None = None, requests_per_minute: int | None = None
) -> Callable:
    if config is None:
        if requests_per_minute is not None:
            config = RateLimitConfig(requests_per_minute=requests_per_minute)
        else:
            config = RateLimitConfig()
    return rate_limited(config)(handler)


def apply_caching(handler: Callable, config: CacheConfig | None = None, ttl: int | None = None) -> Callable:
    if config is None:
        if ttl is not None:
            global_config = get_global_cache_config()
            config = CacheConfig(
                enabled=global_config.enabled,
                backend_type=global_config.backend_type,
                default_ttl=ttl,
                max_size=global_config.max_size,
                key_prefix=global_config.key_prefix,
            )
        else:
            config = get_global_cache_config()
    return cached(config)(handler)


def apply_retry(handler: Callable, config: RetryConfig | None = None, max_attempts: int | None = None) -> Callable:
    if config is None:
        if max_attempts is not None:
            config = RetryConfig(max_attempts=max_attempts)
        else:
            config = RetryConfig()
    return retryable(config)(handler)


# Cache management functions
async def clear_cache_async(config: CacheConfig | None = None) -> None:
    if config is None:
        config = get_global_cache_config()
    cache_backend = get_cache_backend(config)
    await cache_backend.clear()


def clear_cache(config: CacheConfig | None = None) -> None:
    if config is None:
        config = get_global_cache_config()
    cache_backend = get_cache_backend(config)

    try:
        asyncio.run(cache_backend.clear())
    except RuntimeError:
        # Already in event loop - create new task
        loop = asyncio.get_event_loop()
        loop.create_task(cache_backend.clear())


async def get_cache_stats_async(config: CacheConfig | None = None) -> dict[str, Any]:
    if config is None:
        config = get_global_cache_config()
    cache_backend = get_cache_backend(config)

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


def get_cache_stats(config: CacheConfig | None = None) -> dict[str, Any]:
    if config is None:
        config = get_global_cache_config()
    cache_backend = get_cache_backend(config)

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
            "url": cache_backend.config.valkey_url,
            "db": cache_backend.config.valkey_db,
            "max_connections": cache_backend.config.valkey_max_connections,
        }
    else:
        return {"backend": "unknown"}


# Rate limiter management functions
def reset_rate_limits() -> None:
    for limiter in _rate_limiters.values():
        limiter.buckets.clear()


def get_rate_limit_stats() -> dict[str, Any]:
    total_buckets = sum(len(limiter.buckets) for limiter in _rate_limiters.values())
    return {
        "active_limiters": len(_rate_limiters),
        "total_buckets": total_buckets,
        "active_buckets": total_buckets,  # Backward compatibility
        "buckets": total_buckets,  # Also add 'buckets' field for test compatibility
    }


# For backward compatibility, also export execute_with_retry directly
# (it's already defined above, just making it clear it's exported)
