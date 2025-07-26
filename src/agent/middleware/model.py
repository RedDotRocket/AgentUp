"""
Pydantic models for AgentUp middleware system.

This module defines all middleware-related data structures using Pydantic models
for type safety and validation.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ..types import JsonValue
from ..utils.validation import BaseValidator, CompositeValidator, ValidationResult


class CacheBackendType(str, Enum):
    """Cache backend type enumeration."""

    MEMORY = "memory"
    VALKEY = "valkey"
    REDIS = "redis"
    FILE = "file"


class MiddlewareType(str, Enum):
    """Middleware type enumeration."""

    RATE_LIMIT = "rate_limit"
    CACHE = "cache"
    RETRY = "retry"
    TIMEOUT = "timeout"
    LOGGING = "logging"
    AUTHENTICATION = "authentication"
    CUSTOM = "custom"


class RateLimitConfig(BaseModel):
    """Rate limiting configuration model."""

    enabled: bool = Field(True, description="Enable rate limiting")
    requests_per_minute: int = Field(60, description="Requests per minute", gt=0)
    burst_limit: int | None = Field(None, description="Burst limit for short periods", gt=0)
    window_size_seconds: int = Field(60, description="Rate limit window size", gt=0, le=3600)
    key_strategy: str = Field("function_name", description="Rate limit key strategy")
    enforcement_mode: str = Field("strict", description="Enforcement mode")
    whitelist: list[str] = Field(default_factory=list, description="Whitelisted keys/patterns")
    custom_limits: dict[str, int] = Field(default_factory=dict, description="Per-function custom limits")

    @field_validator("key_strategy")
    @classmethod
    def validate_key_strategy(cls, v: str) -> str:
        """Validate rate limit key strategy."""
        valid_strategies = {"function_name", "user_id", "ip_address", "session_id", "custom"}
        if v not in valid_strategies:
            raise ValueError(f"Key strategy must be one of {valid_strategies}")
        return v

    @field_validator("enforcement_mode")
    @classmethod
    def validate_enforcement_mode(cls, v: str) -> str:
        """Validate enforcement mode."""
        valid_modes = {"strict", "soft", "log_only"}
        if v not in valid_modes:
            raise ValueError(f"Enforcement mode must be one of {valid_modes}")
        return v

    @model_validator(mode="after")
    def validate_rate_limit_config(self) -> RateLimitConfig:
        """Validate rate limit configuration consistency."""
        if self.burst_limit and self.burst_limit <= self.requests_per_minute:
            raise ValueError("Burst limit must be greater than requests_per_minute")

        # Validate custom limits
        for key, limit in self.custom_limits.items():
            if limit <= 0:
                raise ValueError(f"Custom limit for '{key}' must be positive")

        return self

    @property
    def effective_rate_per_second(self) -> float:
        """Calculate effective rate per second."""
        return self.requests_per_minute / 60.0

    @property
    def has_burst_capability(self) -> bool:
        """Check if burst limiting is enabled."""
        return self.burst_limit is not None

    @property
    def has_custom_limits(self) -> bool:
        """Check if custom per-function limits are defined."""
        return len(self.custom_limits) > 0


class CacheConfig(BaseModel):
    """Cache configuration model."""

    enabled: bool = Field(True, description="Enable caching")
    backend_type: CacheBackendType = Field(CacheBackendType.MEMORY, description="Cache backend type")
    default_ttl: int = Field(300, description="Default TTL in seconds", gt=0)
    max_size: int = Field(1000, description="Maximum cache size", gt=0)
    key_prefix: str = Field("agentup", description="Cache key prefix")
    compression_enabled: bool = Field(False, description="Enable value compression")
    serialization_format: str = Field("json", description="Serialization format")

    # Memory cache specific
    memory_max_size: int = Field(1000, description="Memory cache max size", gt=0)

    # Valkey/Redis specific
    valkey_url: str = Field("redis://localhost:6379", description="Valkey/Redis connection URL")
    valkey_db: int = Field(1, description="Valkey/Redis database number", ge=0, le=15)
    valkey_max_connections: int = Field(10, description="Maximum connections", gt=0)
    valkey_connection_timeout: int = Field(5, description="Connection timeout", gt=0)

    # File cache specific
    file_cache_dir: str = Field(
        default_factory=lambda: tempfile.mkdtemp(prefix="agentup_cache_"), description="File cache directory"
    )
    file_max_size_mb: int = Field(100, description="Max file cache size in MB", gt=0)

    # Cache policies
    eviction_policy: str = Field("lru", description="Cache eviction policy")
    cache_miss_strategy: str = Field("passthrough", description="Cache miss strategy")
    invalidate_on_error: bool = Field(True, description="Invalidate cache on errors")

    @field_validator("serialization_format")
    @classmethod
    def validate_serialization_format(cls, v: str) -> str:
        """Validate serialization format."""
        valid_formats = {"json", "pickle", "msgpack"}
        if v not in valid_formats:
            raise ValueError(f"Serialization format must be one of {valid_formats}")
        return v

    @field_validator("eviction_policy")
    @classmethod
    def validate_eviction_policy(cls, v: str) -> str:
        """Validate eviction policy."""
        valid_policies = {"lru", "lfu", "fifo", "random", "ttl"}
        if v not in valid_policies:
            raise ValueError(f"Eviction policy must be one of {valid_policies}")
        return v

    @field_validator("cache_miss_strategy")
    @classmethod
    def validate_cache_miss_strategy(cls, v: str) -> str:
        """Validate cache miss strategy."""
        valid_strategies = {"passthrough", "fail_fast", "log_and_continue"}
        if v not in valid_strategies:
            raise ValueError(f"Cache miss strategy must be one of {valid_strategies}")
        return v

    @field_validator("valkey_url")
    @classmethod
    def validate_valkey_url(cls, v: str) -> str:
        """Validate Valkey/Redis URL format."""
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("Valkey URL must start with redis://, rediss://, or unix://")
        return v

    @model_validator(mode="after")
    def validate_cache_config(self) -> CacheConfig:
        """Validate cache configuration consistency."""
        # Backend-specific validations
        if self.backend_type == CacheBackendType.MEMORY:
            if self.max_size != self.memory_max_size:
                self.max_size = self.memory_max_size

        # TTL validations
        if self.default_ttl > 86400:  # 24 hours
            raise ValueError("Default TTL should not exceed 24 hours for performance")

        return self

    @property
    def is_distributed(self) -> bool:
        """Check if cache backend is distributed."""
        return self.backend_type in (CacheBackendType.VALKEY, CacheBackendType.REDIS)

    @property
    def is_persistent(self) -> bool:
        """Check if cache backend is persistent."""
        return self.backend_type in (CacheBackendType.VALKEY, CacheBackendType.REDIS, CacheBackendType.FILE)

    @property
    def estimated_memory_usage_mb(self) -> float:
        """Estimate memory usage in MB."""
        if self.backend_type == CacheBackendType.MEMORY:
            # Rough estimate: average 1KB per cache entry
            return (self.max_size * 1024) / (1024 * 1024)
        return 0.0  # External backends don't use local memory


class RetryConfig(BaseModel):
    """Retry configuration model."""

    enabled: bool = Field(True, description="Enable retry logic")
    max_attempts: int = Field(3, description="Maximum retry attempts", ge=1, le=10)
    backoff_factor: float = Field(1.0, description="Backoff multiplier", ge=0.01, le=10.0)
    max_delay: float = Field(60.0, description="Maximum delay between retries", gt=0, le=300)
    backoff_strategy: str = Field("exponential", description="Backoff strategy")
    jitter_enabled: bool = Field(True, description="Add random jitter to delays")
    retry_on_exceptions: list[str] = Field(
        default_factory=lambda: ["ConnectionError", "TimeoutError", "HTTPError"],
        description="Exception types to retry on",
    )
    do_not_retry_on: list[str] = Field(
        default_factory=lambda: ["AuthenticationError", "ValidationError"],
        description="Exception types to never retry",
    )

    @field_validator("backoff_strategy")
    @classmethod
    def validate_backoff_strategy(cls, v: str) -> str:
        """Validate backoff strategy."""
        valid_strategies = {"exponential", "linear", "fixed", "fibonacci"}
        if v not in valid_strategies:
            raise ValueError(f"Backoff strategy must be one of {valid_strategies}")
        return v

    @model_validator(mode="after")
    def validate_retry_config(self) -> RetryConfig:
        """Validate retry configuration consistency."""
        if self.max_attempts == 1 and self.enabled:
            raise ValueError("If retries are enabled, max_attempts must be > 1")

        # Calculate max total delay
        max_total_delay = self.calculate_max_total_delay()
        if max_total_delay > 600:  # 10 minutes
            raise ValueError("Total retry delay may exceed 10 minutes - consider reducing attempts or delays")

        return self

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for specific attempt."""
        if self.backoff_strategy == "exponential":
            delay = self.backoff_factor * (2**attempt)
        elif self.backoff_strategy == "linear":
            delay = self.backoff_factor * attempt
        elif self.backoff_strategy == "fibonacci":
            if attempt <= 1:
                delay = self.backoff_factor
            else:
                # Simplified fibonacci for delays
                delay = self.backoff_factor * (attempt + (attempt - 1))
        else:  # fixed
            delay = self.backoff_factor

        return min(delay, self.max_delay)

    def calculate_max_total_delay(self) -> float:
        """Calculate maximum total delay across all attempts."""
        return sum(self.calculate_delay(i) for i in range(self.max_attempts - 1))

    @property
    def has_exception_filtering(self) -> bool:
        """Check if exception filtering is configured."""
        return bool(self.retry_on_exceptions or self.do_not_retry_on)


class MiddlewareConfig(BaseModel):
    """Overall middleware configuration model."""

    enabled: bool = Field(True, description="Enable middleware system")
    middleware_order: list[MiddlewareType] = Field(
        default_factory=lambda: [
            MiddlewareType.AUTHENTICATION,
            MiddlewareType.RATE_LIMIT,
            MiddlewareType.CACHE,
            MiddlewareType.RETRY,
            MiddlewareType.LOGGING,
        ],
        description="Middleware execution order",
    )

    # Individual middleware configs
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Rate limiting config")
    cache: CacheConfig = Field(default_factory=CacheConfig, description="Cache config")
    retry: RetryConfig = Field(default_factory=RetryConfig, description="Retry config")

    # Global middleware settings
    timeout_seconds: int = Field(300, description="Global timeout", gt=0, le=3600)
    enable_metrics: bool = Field(True, description="Enable middleware metrics")
    debug_mode: bool = Field(False, description="Enable debug logging")
    custom_middleware: dict[str, dict[str, JsonValue]] = Field(
        default_factory=dict, description="Custom middleware configurations"
    )

    @field_validator("middleware_order")
    @classmethod
    def validate_middleware_order(cls, v: list[MiddlewareType]) -> list[MiddlewareType]:
        """Validate middleware execution order."""
        if MiddlewareType.AUTHENTICATION in v and MiddlewareType.AUTHENTICATION != v[0]:
            raise ValueError("Authentication middleware should be first in order")

        if len(set(v)) != len(v):
            raise ValueError("Duplicate middleware types in execution order")

        return v

    @model_validator(mode="after")
    def validate_middleware_config(self) -> MiddlewareConfig:
        """Validate overall middleware configuration."""
        # Ensure enabled middleware have valid configs
        if MiddlewareType.RATE_LIMIT in self.middleware_order and not self.rate_limit.enabled:
            raise ValueError("Rate limiting is in execution order but disabled")

        if MiddlewareType.CACHE in self.middleware_order and not self.cache.enabled:
            raise ValueError("Caching is in execution order but disabled")

        if MiddlewareType.RETRY in self.middleware_order and not self.retry.enabled:
            raise ValueError("Retry is in execution order but disabled")

        return self

    @property
    def active_middleware_count(self) -> int:
        """Get count of active middleware."""
        return len(self.middleware_order)

    @property
    def has_custom_middleware(self) -> bool:
        """Check if custom middleware is configured."""
        return len(self.custom_middleware) > 0

    @property
    def estimated_overhead_ms(self) -> float:
        """Estimate middleware overhead in milliseconds."""
        overhead = 0.0

        if MiddlewareType.AUTHENTICATION in self.middleware_order:
            overhead += 5.0  # Auth check overhead

        if MiddlewareType.RATE_LIMIT in self.middleware_order:
            overhead += 1.0  # Rate limit check

        if MiddlewareType.CACHE in self.middleware_order:
            if self.cache.backend_type == CacheBackendType.MEMORY:
                overhead += 0.5  # Memory cache access
            else:
                overhead += 10.0  # Network cache access

        return overhead


class MiddlewareRegistry(BaseModel):
    """Middleware registry model for managing middleware functions."""

    middleware: dict[str, Any] = Field(default_factory=dict, description="Registered middleware functions")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last registry update")
    version: str = Field("1.0.0", description="Registry version")

    # Add backward compatibility property
    @property
    def _middleware(self) -> dict[str, Any]:
        """Get middleware dict (backward compatibility)."""
        return self.middleware

    def register_middleware(self, name: str, config: dict[str, JsonValue]) -> None:
        """Register middleware in the registry."""
        self.middleware[name] = config
        self.last_updated = datetime.utcnow()

    # Add backward compatibility methods
    def register(self, name: str, middleware: Any) -> None:
        """Register middleware (backward compatibility)."""
        self.middleware[name] = middleware
        self.last_updated = datetime.utcnow()

    def unregister_middleware(self, name: str) -> bool:
        """Unregister middleware from the registry."""
        if name in self.middleware:
            del self.middleware[name]
            self.last_updated = datetime.utcnow()
            return True
        return False

    def get_middleware(self, name: str) -> dict[str, JsonValue] | None:
        """Get middleware configuration by name."""
        return self.middleware.get(name)

    # Add backward compatibility method
    def get(self, name: str) -> Any:
        """Get middleware (backward compatibility)."""
        return self.middleware.get(name)

    def apply(self, handler: Any, middleware_configs: list[dict[str, Any]]) -> Any:
        """Apply middleware to a handler."""
        wrapped = handler
        for config in middleware_configs:
            middleware_name = config.get("name")
            middleware_func = self.middleware.get(middleware_name)
            if middleware_func and callable(middleware_func):
                params = config.get("params", {})
                wrapped = middleware_func(wrapped, **params)
        return wrapped

    def list_middleware(self, middleware_type: MiddlewareType | None = None) -> list[str]:
        """List all middleware names, optionally filtered by type."""
        if middleware_type:
            return [name for name, config in self.middleware.items() if config.get("type") == middleware_type.value]
        return list(self.middleware.keys())

    @property
    def middleware_count(self) -> int:
        """Get total number of registered middleware."""
        return len(self.middleware)


class MiddlewareError(BaseModel):
    """Middleware error model."""

    error_type: str = Field(..., description="Error type", min_length=1, max_length=64)
    message: str = Field(..., description="Error message", min_length=1, max_length=500)
    middleware_name: str | None = Field(None, description="Middleware that caused the error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    context: dict[str, JsonValue] = Field(default_factory=dict, description="Error context")
    recoverable: bool = Field(True, description="Whether error is recoverable")
    retry_after: int | None = Field(None, description="Retry after seconds", ge=0)

    @field_validator("error_type")
    @classmethod
    def validate_error_type(cls, v: str) -> str:
        """Validate error type format."""
        import re

        if not re.match(r"^[A-Z][a-zA-Z0-9_]*Error$", v):
            raise ValueError("Error type must be CamelCase ending with 'Error'")
        return v

    @property
    def is_timeout_error(self) -> bool:
        """Check if error is timeout-related."""
        return "timeout" in self.error_type.lower()

    @property
    def is_rate_limit_error(self) -> bool:
        """Check if error is rate limit-related."""
        return "ratelimit" in self.error_type.lower() or "rate_limit" in self.error_type.lower()

    @property
    def should_retry(self) -> bool:
        """Check if operation should be retried."""
        return self.recoverable and not self.is_rate_limit_error


# Middleware Validators using validation framework
class RateLimitConfigValidator(BaseValidator[RateLimitConfig]):
    """Business rule validator for rate limit configuration."""

    def validate(self, model: RateLimitConfig) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for very permissive rate limits
        if model.requests_per_minute > 1000:
            result.add_warning("Very high rate limit may not provide effective protection")

        # Check for very restrictive limits
        if model.requests_per_minute < 10:
            result.add_warning("Very low rate limit may impact user experience")

        # Validate enforcement mode usage
        if model.enforcement_mode == "log_only":
            result.add_suggestion("Log-only mode should only be used for testing")

        # Check custom limits consistency
        avg_custom_limit = sum(model.custom_limits.values()) / len(model.custom_limits) if model.custom_limits else 0
        if avg_custom_limit > model.requests_per_minute * 2:
            result.add_warning("Custom limits are much higher than base rate limit")

        return result


class CacheConfigValidator(BaseValidator[CacheConfig]):
    """Business rule validator for cache configuration."""

    def validate(self, model: CacheConfig) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for potentially expensive cache settings
        if model.backend_type == CacheBackendType.MEMORY and model.max_size > 10000:
            result.add_warning("Large memory cache may impact application memory usage")

        # Validate TTL settings
        if model.default_ttl < 60:
            result.add_suggestion("Very short TTL may reduce cache effectiveness")
        elif model.default_ttl > 3600:
            result.add_warning("Long TTL may lead to stale data issues")

        # Check compression usage
        if not model.compression_enabled and model.backend_type in (CacheBackendType.VALKEY, CacheBackendType.REDIS):
            result.add_suggestion("Consider enabling compression for network cache backends")

        # Validate file cache directory
        if model.backend_type == CacheBackendType.FILE:
            import os
            import stat

            # Check if directory exists and has secure permissions
            if os.path.exists(model.file_cache_dir):
                dir_stat = os.stat(model.file_cache_dir)
                # Check that directory is not world-writable (secure)
                if dir_stat.st_mode & stat.S_IWOTH:
                    result.add_warning("File cache directory has world-writable permissions - potential security risk")

                # Warn about insecure temporary directory usage
                # Bandit false positive: We are warning about /tmp usage, not creating it
                if model.file_cache_dir.startswith("/tmp/"):  # nosec
                    result.add_warning(
                        "Using /tmp/ directly can be insecure - consider using tempfile.mkdtemp() for secure temporary directories"
                    )

        return result


class RetryConfigValidator(BaseValidator[RetryConfig]):
    """Business rule validator for retry configuration."""

    def validate(self, model: RetryConfig) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Check for excessive retry attempts
        if model.max_attempts > 5:
            result.add_warning("High retry attempts may cause long delays and resource usage")

        # Validate backoff settings
        if model.backoff_factor > 2.0 and model.backoff_strategy == "exponential":
            result.add_warning("High backoff factor with exponential strategy may cause very long delays")

        # Check exception filtering
        if not model.retry_on_exceptions:
            result.add_suggestion("Consider specifying which exceptions should trigger retries")

        # Calculate and warn about total delay
        total_delay = model.calculate_max_total_delay()
        if total_delay > 300:  # 5 minutes
            result.add_warning(f"Maximum total retry delay is {total_delay:.1f} seconds")

        return result


class MiddlewareConfigValidator(BaseValidator[MiddlewareConfig]):
    """Business rule validator for overall middleware configuration."""

    def validate(self, model: MiddlewareConfig) -> ValidationResult:
        result = ValidationResult(valid=True)

        # Validate individual middleware configs
        if model.rate_limit.enabled:
            rate_validator = RateLimitConfigValidator(RateLimitConfig)
            rate_result = rate_validator.validate(model.rate_limit)
            result.merge(rate_result)

        if model.cache.enabled:
            cache_validator = CacheConfigValidator(CacheConfig)
            cache_result = cache_validator.validate(model.cache)
            result.merge(cache_result)

        if model.retry.enabled:
            retry_validator = RetryConfigValidator(RetryConfig)
            retry_result = retry_validator.validate(model.retry)
            result.merge(retry_result)

        # Check middleware overhead
        estimated_overhead = model.estimated_overhead_ms
        if estimated_overhead > 50:
            result.add_warning(f"High estimated middleware overhead: {estimated_overhead:.1f}ms")

        # Validate timeout
        if model.timeout_seconds < 30:
            result.add_warning("Short global timeout may cause premature failures")

        return result


# Composite validator for middleware models
def create_middleware_validator() -> CompositeValidator[MiddlewareConfig]:
    """Create a comprehensive middleware validator."""
    validators = [
        MiddlewareConfigValidator(MiddlewareConfig),
    ]
    return CompositeValidator(MiddlewareConfig, validators)


# Re-export key models
__all__ = [
    "CacheBackendType",
    "MiddlewareType",
    "RateLimitConfig",
    "CacheConfig",
    "RetryConfig",
    "MiddlewareConfig",
    "MiddlewareRegistry",
    "MiddlewareError",
    "RateLimitConfigValidator",
    "CacheConfigValidator",
    "RetryConfigValidator",
    "MiddlewareConfigValidator",
    "create_middleware_validator",
]
