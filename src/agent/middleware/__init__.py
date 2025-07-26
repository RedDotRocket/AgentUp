"""
AgentUp Middleware System.

This module provides middleware functionality for the AgentUp framework
including rate limiting, caching, retry logic, and other middleware capabilities.
"""

import structlog

from .implementation import (
    MiddlewareError,
    RateLimiter,
    RateLimitError,
    RateLimitExceeded,
    apply_ai_routing_middleware,
    apply_caching,
    apply_rate_limiting,
    apply_retry,
    cached,
    clear_cache,
    execute_ai_function_with_middleware,
    execute_with_retry,
    get_ai_compatible_middleware,
    get_cache_stats,
    get_rate_limit_stats,
    rate_limited,
    reset_rate_limits,
    retryable,
    timed,
    with_middleware,
)
from .model import (
    CacheBackendType,
    CacheConfig,
    MiddlewareConfig,
    MiddlewareRegistry,
    MiddlewareType,
    RateLimitConfig,
    RetryConfig,
    create_middleware_validator,
)

# Module logger
logger = structlog.get_logger(__name__)

__all__ = [
    # Models
    "CacheBackendType",
    "CacheConfig",
    "MiddlewareConfig",
    "MiddlewareError",
    "MiddlewareRegistry",
    "MiddlewareType",
    "RateLimitConfig",
    "RetryConfig",
    "create_middleware_validator",
    # Functions
    "RateLimiter",
    "RateLimitError",
    "RateLimitExceeded",
    "apply_ai_routing_middleware",
    "apply_caching",
    "apply_rate_limiting",
    "apply_retry",
    "cached",
    "clear_cache",
    "execute_ai_function_with_middleware",
    "execute_with_retry",
    "get_ai_compatible_middleware",
    "get_cache_stats",
    "get_rate_limit_stats",
    "rate_limited",
    "reset_rate_limits",
    "retryable",
    "timed",
    "with_middleware",
]
