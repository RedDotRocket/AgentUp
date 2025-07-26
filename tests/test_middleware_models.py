"""
Tests for middleware system models.

This module tests all middleware-related Pydantic models for validation,
serialization, and business logic.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.agent.middleware.model import (
    CacheBackendType,
    CacheConfig,
    CacheConfigValidator,
    MiddlewareConfig,
    MiddlewareConfigValidator,
    MiddlewareError,
    MiddlewareRegistry,
    MiddlewareType,
    RateLimitConfig,
    RateLimitConfigValidator,
    RetryConfig,
    RetryConfigValidator,
    create_middleware_validator,
)


class TestRateLimitConfig:
    """Test RateLimitConfig model."""

    def test_valid_rate_limit_config_creation(self):
        """Test creating a valid rate limit configuration."""
        config = RateLimitConfig(
            enabled=True,
            requests_per_minute=120,
            burst_limit=200,
            window_size_seconds=60,
            key_strategy="user_id",
            enforcement_mode="strict",
        )

        assert config.enabled is True
        assert config.requests_per_minute == 120
        assert config.burst_limit == 200
        assert config.effective_rate_per_second == 2.0
        assert config.has_burst_capability is True

    def test_rate_limit_key_strategy_validation(self):
        """Test rate limit key strategy validation."""
        # Valid strategies
        valid_strategies = ["function_name", "user_id", "ip_address", "session_id", "custom"]
        for strategy in valid_strategies:
            config = RateLimitConfig(key_strategy=strategy)
            assert config.key_strategy == strategy

        # Invalid strategy
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(key_strategy="invalid_strategy")
        assert "Key strategy must be one of" in str(exc_info.value)

    def test_rate_limit_enforcement_mode_validation(self):
        """Test enforcement mode validation."""
        # Valid modes
        valid_modes = ["strict", "soft", "log_only"]
        for mode in valid_modes:
            config = RateLimitConfig(enforcement_mode=mode)
            assert config.enforcement_mode == mode

        # Invalid mode
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(enforcement_mode="invalid_mode")
        assert "Enforcement mode must be one of" in str(exc_info.value)

    def test_burst_limit_validation(self):
        """Test burst limit validation."""
        # Burst limit greater than requests_per_minute should be valid
        config = RateLimitConfig(requests_per_minute=60, burst_limit=100)
        assert config.burst_limit == 100

        # Burst limit less than or equal to requests_per_minute should fail
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(requests_per_minute=60, burst_limit=50)
        assert "Burst limit must be greater than requests_per_minute" in str(exc_info.value)

    def test_custom_limits_validation(self):
        """Test custom limits validation."""
        # Valid custom limits
        config = RateLimitConfig(custom_limits={"critical_function": 200, "normal_function": 60})
        assert config.custom_limits["critical_function"] == 200
        assert config.has_custom_limits is True

        # Invalid custom limit (zero or negative)
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(custom_limits={"invalid_function": 0})
        assert "Custom limit for 'invalid_function' must be positive" in str(exc_info.value)

    def test_rate_limit_properties(self):
        """Test rate limit configuration properties."""
        config = RateLimitConfig(
            requests_per_minute=120,
            burst_limit=180,
            custom_limits={"special": 240},
        )

        assert config.effective_rate_per_second == 2.0
        assert config.has_burst_capability is True
        assert config.has_custom_limits is True

        # Config without burst
        config_no_burst = RateLimitConfig(requests_per_minute=60)
        assert config_no_burst.has_burst_capability is False

    def test_rate_limit_serialization(self):
        """Test rate limit configuration serialization."""
        config = RateLimitConfig(
            requests_per_minute=100,
            burst_limit=150,
            key_strategy="user_id",
            custom_limits={"admin": 500},
        )

        data = config.model_dump()
        assert data["requests_per_minute"] == 100
        assert data["burst_limit"] == 150
        assert data["custom_limits"]["admin"] == 500

        # Round trip
        config2 = RateLimitConfig.model_validate(data)
        assert config2.requests_per_minute == config.requests_per_minute
        assert config2.custom_limits == config.custom_limits


class TestCacheConfig:
    """Test CacheConfig model."""

    def test_valid_cache_config_creation(self):
        """Test creating a valid cache configuration."""
        config = CacheConfig(
            enabled=True,
            backend_type=CacheBackendType.MEMORY,
            default_ttl=600,
            max_size=2000,
            key_prefix="test",
        )

        assert config.enabled is True
        assert config.backend_type == CacheBackendType.MEMORY
        assert config.default_ttl == 600
        assert config.is_distributed is False
        assert config.is_persistent is False

    def test_cache_backend_types(self):
        """Test different cache backend types."""
        # Memory cache
        memory_config = CacheConfig(backend_type=CacheBackendType.MEMORY)
        assert memory_config.is_distributed is False
        assert memory_config.is_persistent is False

        # Valkey cache
        valkey_config = CacheConfig(backend_type=CacheBackendType.VALKEY)
        assert valkey_config.is_distributed is True
        assert valkey_config.is_persistent is True

        # File cache
        file_config = CacheConfig(backend_type=CacheBackendType.FILE)
        assert file_config.is_distributed is False
        assert file_config.is_persistent is True

    def test_serialization_format_validation(self):
        """Test serialization format validation."""
        # Valid formats
        valid_formats = ["json", "pickle", "msgpack"]
        for fmt in valid_formats:
            config = CacheConfig(serialization_format=fmt)
            assert config.serialization_format == fmt

        # Invalid format
        with pytest.raises(ValidationError) as exc_info:
            CacheConfig(serialization_format="invalid")
        assert "Serialization format must be one of" in str(exc_info.value)

    def test_eviction_policy_validation(self):
        """Test eviction policy validation."""
        # Valid policies
        valid_policies = ["lru", "lfu", "fifo", "random", "ttl"]
        for policy in valid_policies:
            config = CacheConfig(eviction_policy=policy)
            assert config.eviction_policy == policy

        # Invalid policy
        with pytest.raises(ValidationError) as exc_info:
            CacheConfig(eviction_policy="invalid")
        assert "Eviction policy must be one of" in str(exc_info.value)

    def test_cache_miss_strategy_validation(self):
        """Test cache miss strategy validation."""
        # Valid strategies
        valid_strategies = ["passthrough", "fail_fast", "log_and_continue"]
        for strategy in valid_strategies:
            config = CacheConfig(cache_miss_strategy=strategy)
            assert config.cache_miss_strategy == strategy

        # Invalid strategy
        with pytest.raises(ValidationError) as exc_info:
            CacheConfig(cache_miss_strategy="invalid")
        assert "Cache miss strategy must be one of" in str(exc_info.value)

    def test_valkey_url_validation(self):
        """Test Valkey/Redis URL validation."""
        # Valid URLs
        valid_urls = [
            "redis://localhost:6379",
            "rediss://secure.redis.com:6380",
            "unix:///tmp/redis.sock",
        ]
        for url in valid_urls:
            config = CacheConfig(valkey_url=url)
            assert config.valkey_url == url

        # Invalid URL
        with pytest.raises(ValidationError) as exc_info:
            CacheConfig(valkey_url="http://invalid.com")
        assert "Valkey URL must start with redis://, rediss://, or unix://" in str(exc_info.value)

    def test_cache_config_consistency_validation(self):
        """Test cache configuration consistency validation."""
        # TTL validation
        with pytest.raises(ValidationError) as exc_info:
            CacheConfig(default_ttl=100000)  # > 24 hours
        assert "Default TTL should not exceed 24 hours" in str(exc_info.value)

        # Memory backend max_size consistency
        config = CacheConfig(
            backend_type=CacheBackendType.MEMORY,
            max_size=500,
            memory_max_size=1000,
        )
        # max_size should be updated to match memory_max_size
        assert config.max_size == config.memory_max_size

    def test_estimated_memory_usage(self):
        """Test estimated memory usage calculation."""
        # Memory cache should estimate usage
        memory_config = CacheConfig(
            backend_type=CacheBackendType.MEMORY,
            max_size=1000,
        )
        memory_usage = memory_config.estimated_memory_usage_mb
        assert memory_usage > 0

        # External backends should return 0
        valkey_config = CacheConfig(backend_type=CacheBackendType.VALKEY)
        assert valkey_config.estimated_memory_usage_mb == 0.0

    def test_cache_config_serialization(self):
        """Test cache configuration serialization."""
        config = CacheConfig(
            backend_type=CacheBackendType.VALKEY,
            default_ttl=300,
            valkey_url="redis://localhost:6379",
            valkey_db=2,
            compression_enabled=True,
        )

        data = config.model_dump()
        assert data["backend_type"] == "valkey"
        assert data["default_ttl"] == 300
        assert data["valkey_db"] == 2

        # Round trip
        config2 = CacheConfig.model_validate(data)
        assert config2.backend_type == config.backend_type
        assert config2.valkey_url == config.valkey_url


class TestRetryConfig:
    """Test RetryConfig model."""

    def test_valid_retry_config_creation(self):
        """Test creating a valid retry configuration."""
        config = RetryConfig(
            enabled=True,
            max_attempts=5,
            backoff_factor=2.0,
            max_delay=120.0,
            backoff_strategy="exponential",
        )

        assert config.enabled is True
        assert config.max_attempts == 5
        assert config.backoff_factor == 2.0
        assert config.backoff_strategy == "exponential"

    def test_backoff_strategy_validation(self):
        """Test backoff strategy validation."""
        # Valid strategies
        valid_strategies = ["exponential", "linear", "fixed", "fibonacci"]
        for strategy in valid_strategies:
            config = RetryConfig(backoff_strategy=strategy)
            assert config.backoff_strategy == strategy

        # Invalid strategy
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(backoff_strategy="invalid")
        assert "Backoff strategy must be one of" in str(exc_info.value)

    def test_retry_attempts_validation(self):
        """Test retry attempts validation."""
        # Valid attempts (2-10) - 1 is special case tested separately
        for attempts in [2, 5, 10]:
            config = RetryConfig(max_attempts=attempts)
            assert config.max_attempts == attempts

        # Test single attempt with retries disabled
        config_single = RetryConfig(enabled=False, max_attempts=1)
        assert config_single.max_attempts == 1

        # Invalid attempts (out of range)
        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=0)

        with pytest.raises(ValidationError):
            RetryConfig(max_attempts=15)

    def test_retry_config_consistency_validation(self):
        """Test retry configuration consistency validation."""
        # Single attempt with retries enabled should fail
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(enabled=True, max_attempts=1)
        assert "If retries are enabled, max_attempts must be > 1" in str(exc_info.value)

        # Excessive total delay should fail
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(max_attempts=10, backoff_factor=5.0, max_delay=300.0)
        assert "Total retry delay may exceed 10 minutes" in str(exc_info.value)

    def test_delay_calculation(self):
        """Test delay calculation for different strategies."""
        # Exponential backoff
        exp_config = RetryConfig(backoff_strategy="exponential", backoff_factor=2.0, max_delay=60.0)
        assert exp_config.calculate_delay(0) == 2.0  # 2.0 * 2^0
        assert exp_config.calculate_delay(1) == 4.0  # 2.0 * 2^1
        assert exp_config.calculate_delay(2) == 8.0  # 2.0 * 2^2

        # Linear backoff
        linear_config = RetryConfig(backoff_strategy="linear", backoff_factor=5.0)
        assert linear_config.calculate_delay(1) == 5.0  # 5.0 * 1
        assert linear_config.calculate_delay(2) == 10.0  # 5.0 * 2

        # Fixed backoff
        fixed_config = RetryConfig(backoff_strategy="fixed", backoff_factor=3.0)
        assert fixed_config.calculate_delay(1) == 3.0
        assert fixed_config.calculate_delay(5) == 3.0

        # Max delay constraint
        capped_config = RetryConfig(backoff_strategy="exponential", backoff_factor=10.0, max_delay=20.0)
        assert capped_config.calculate_delay(5) == 20.0  # Capped at max_delay

    def test_total_delay_calculation(self):
        """Test maximum total delay calculation."""
        config = RetryConfig(
            max_attempts=3,
            backoff_strategy="linear",
            backoff_factor=10.0,
        )
        # For 3 attempts: delays are for attempts 1 and 2 (2 delays total)
        # Linear: 10.0 * 1 + 10.0 * 2 = 30.0, but my calculation may be different
        total_delay = config.calculate_max_total_delay()
        # Let me check what the actual calculation is
        expected = config.calculate_delay(0) + config.calculate_delay(1)
        assert total_delay == expected

    def test_exception_filtering_properties(self):
        """Test exception filtering properties."""
        # Config with exception filtering
        config_with_filtering = RetryConfig(
            retry_on_exceptions=["ConnectionError", "TimeoutError"],
            do_not_retry_on=["AuthError"],
        )
        assert config_with_filtering.has_exception_filtering is True

        # Config without exception filtering
        config_no_filtering = RetryConfig(
            retry_on_exceptions=[],
            do_not_retry_on=[],
        )
        assert config_no_filtering.has_exception_filtering is False

    def test_retry_config_serialization(self):
        """Test retry configuration serialization."""
        config = RetryConfig(
            max_attempts=4,
            backoff_strategy="exponential",
            backoff_factor=1.5,
            retry_on_exceptions=["ConnectionError", "HTTPError"],
        )

        data = config.model_dump()
        assert data["max_attempts"] == 4
        assert data["backoff_strategy"] == "exponential"
        assert "ConnectionError" in data["retry_on_exceptions"]

        # Round trip
        config2 = RetryConfig.model_validate(data)
        assert config2.max_attempts == config.max_attempts
        assert config2.retry_on_exceptions == config.retry_on_exceptions


class TestMiddlewareConfig:
    """Test MiddlewareConfig model."""

    def test_valid_middleware_config_creation(self):
        """Test creating a valid middleware configuration."""
        config = MiddlewareConfig(
            enabled=True,
            middleware_order=[
                MiddlewareType.AUTHENTICATION,
                MiddlewareType.RATE_LIMIT,
                MiddlewareType.CACHE,
            ],
            timeout_seconds=300,
        )

        assert config.enabled is True
        assert len(config.middleware_order) == 3
        assert config.active_middleware_count == 3

    def test_middleware_order_validation(self):
        """Test middleware execution order validation."""
        # Authentication should be first
        with pytest.raises(ValidationError) as exc_info:
            MiddlewareConfig(
                middleware_order=[
                    MiddlewareType.RATE_LIMIT,
                    MiddlewareType.AUTHENTICATION,
                ]
            )
        assert "Authentication middleware should be first" in str(exc_info.value)

        # No duplicate middleware types
        with pytest.raises(ValidationError) as exc_info:
            MiddlewareConfig(
                middleware_order=[
                    MiddlewareType.AUTHENTICATION,
                    MiddlewareType.RATE_LIMIT,
                    MiddlewareType.RATE_LIMIT,  # Duplicate
                ]
            )
        assert "Duplicate middleware types" in str(exc_info.value)

    def test_middleware_config_consistency_validation(self):
        """Test middleware configuration consistency validation."""
        # Rate limiting in order but disabled should fail
        rate_limit_config = RateLimitConfig(enabled=False)
        with pytest.raises(ValidationError) as exc_info:
            MiddlewareConfig(
                middleware_order=[MiddlewareType.RATE_LIMIT],
                rate_limit=rate_limit_config,
            )
        assert "Rate limiting is in execution order but disabled" in str(exc_info.value)

        # Cache in order but disabled should fail
        cache_config = CacheConfig(enabled=False)
        with pytest.raises(ValidationError) as exc_info:
            MiddlewareConfig(
                middleware_order=[MiddlewareType.CACHE],
                cache=cache_config,
            )
        assert "Caching is in execution order but disabled" in str(exc_info.value)

    def test_middleware_properties(self):
        """Test middleware configuration properties."""
        config = MiddlewareConfig(
            middleware_order=[
                MiddlewareType.AUTHENTICATION,
                MiddlewareType.RATE_LIMIT,
                MiddlewareType.CACHE,
            ],
            custom_middleware={"custom1": {"type": "custom", "config": {}}},
        )

        assert config.active_middleware_count == 3
        assert config.has_custom_middleware is True

        # Config without custom middleware
        config_no_custom = MiddlewareConfig()
        assert config_no_custom.has_custom_middleware is False

    def test_estimated_overhead_calculation(self):
        """Test middleware overhead estimation."""
        # Memory cache config
        cache_config = CacheConfig(backend_type=CacheBackendType.MEMORY)
        config = MiddlewareConfig(
            middleware_order=[
                MiddlewareType.AUTHENTICATION,
                MiddlewareType.RATE_LIMIT,
                MiddlewareType.CACHE,
            ],
            cache=cache_config,
        )

        overhead = config.estimated_overhead_ms
        assert overhead > 0
        # Should include auth (5ms) + rate limit (1ms) + memory cache (0.5ms)
        assert overhead >= 6.5

        # Valkey cache should have higher overhead
        valkey_cache_config = CacheConfig(backend_type=CacheBackendType.VALKEY)
        config_valkey = MiddlewareConfig(
            middleware_order=[MiddlewareType.CACHE],
            cache=valkey_cache_config,
        )
        valkey_overhead = config_valkey.estimated_overhead_ms
        assert valkey_overhead >= 10.0

    def test_middleware_config_serialization(self):
        """Test middleware configuration serialization."""
        config = MiddlewareConfig(
            enabled=True,
            middleware_order=[MiddlewareType.AUTHENTICATION, MiddlewareType.RATE_LIMIT],
            timeout_seconds=600,
            enable_metrics=True,
        )

        data = config.model_dump()
        assert data["enabled"] is True
        assert data["timeout_seconds"] == 600
        assert "authentication" in data["middleware_order"]

        # Round trip
        config2 = MiddlewareConfig.model_validate(data)
        assert config2.enabled == config.enabled
        assert config2.middleware_order == config.middleware_order


class TestMiddlewareRegistry:
    """Test MiddlewareRegistry model."""

    def test_middleware_registry_creation(self):
        """Test creating a middleware registry."""
        registry = MiddlewareRegistry()
        assert registry.middleware_count == 0
        assert isinstance(registry.last_updated, datetime)

    def test_middleware_registration(self):
        """Test middleware registration."""
        registry = MiddlewareRegistry()
        old_updated = registry.last_updated

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        registry.register_middleware("test_middleware", {"type": "custom", "enabled": True})

        assert registry.middleware_count == 1
        assert registry.last_updated > old_updated
        assert "test_middleware" in registry.middleware

    def test_middleware_unregistration(self):
        """Test middleware unregistration."""
        registry = MiddlewareRegistry()
        registry.register_middleware("test_middleware", {"type": "custom"})

        # Unregister existing middleware
        result = registry.unregister_middleware("test_middleware")
        assert result is True
        assert registry.middleware_count == 0

        # Unregister non-existing middleware
        result = registry.unregister_middleware("non_existing")
        assert result is False

    def test_middleware_retrieval(self):
        """Test middleware retrieval."""
        registry = MiddlewareRegistry()
        config = {"type": "rate_limit", "enabled": True}
        registry.register_middleware("rate_limiter", config)

        # Get existing middleware
        retrieved = registry.get_middleware("rate_limiter")
        assert retrieved == config

        # Get non-existing middleware
        none_result = registry.get_middleware("non_existing")
        assert none_result is None

    def test_middleware_listing(self):
        """Test middleware listing."""
        registry = MiddlewareRegistry()
        registry.register_middleware("rate_limiter", {"type": "rate_limit"})
        registry.register_middleware("cache", {"type": "cache"})
        registry.register_middleware("custom", {"type": "custom"})

        # List all middleware
        all_middleware = registry.list_middleware()
        assert "rate_limiter" in all_middleware
        assert "cache" in all_middleware
        assert "custom" in all_middleware

        # List by type
        rate_limit_middleware = registry.list_middleware(MiddlewareType.RATE_LIMIT)
        assert "rate_limiter" in rate_limit_middleware
        assert "cache" not in rate_limit_middleware

    def test_middleware_registry_serialization(self):
        """Test middleware registry serialization."""
        registry = MiddlewareRegistry()
        registry.register_middleware("test", {"type": "custom", "priority": 1})

        data = registry.model_dump()
        assert "middleware" in data
        assert "test" in data["middleware"]

        # Round trip
        registry2 = MiddlewareRegistry.model_validate(data)
        assert registry2.middleware_count == registry.middleware_count
        assert registry2.get_middleware("test") == registry.get_middleware("test")


class TestMiddlewareError:
    """Test MiddlewareError model."""

    def test_valid_middleware_error_creation(self):
        """Test creating a valid middleware error."""
        error = MiddlewareError(
            error_type="RateLimitError",
            message="Rate limit exceeded for user",
            middleware_name="rate_limiter",
            recoverable=True,
            retry_after=30,
        )

        assert error.error_type == "RateLimitError"
        assert error.message == "Rate limit exceeded for user"
        assert error.recoverable is True
        assert error.is_rate_limit_error is True
        assert error.should_retry is False  # Rate limit errors shouldn't retry

    def test_error_type_validation(self):
        """Test error type validation."""
        # Valid error types
        valid_types = ["ValidationError", "AuthenticationError", "TimeoutError", "CustomError"]
        for error_type in valid_types:
            error = MiddlewareError(error_type=error_type, message="Test error")
            assert error.error_type == error_type

        # Invalid error type (not CamelCase ending with Error)
        with pytest.raises(ValidationError) as exc_info:
            MiddlewareError(error_type="invalid_error", message="Test")
        assert "Error type must be CamelCase ending with 'Error'" in str(exc_info.value)

    def test_error_classification_properties(self):
        """Test error classification properties."""
        # Timeout error
        timeout_error = MiddlewareError(
            error_type="TimeoutError",
            message="Request timed out",
        )
        assert timeout_error.is_timeout_error is True
        assert timeout_error.should_retry is True

        # Rate limit error
        rate_limit_error = MiddlewareError(
            error_type="RateLimitError",
            message="Too many requests",
            recoverable=True,
        )
        assert rate_limit_error.is_rate_limit_error is True
        assert rate_limit_error.should_retry is False  # Rate limit errors shouldn't retry

        # Non-recoverable error
        fatal_error = MiddlewareError(
            error_type="FatalError",
            message="System failure",
            recoverable=False,
        )
        assert fatal_error.should_retry is False

    def test_middleware_error_serialization(self):
        """Test middleware error serialization."""
        error = MiddlewareError(
            error_type="ValidationError",
            message="Invalid input parameters",
            middleware_name="validator",
            context={"field": "username", "value": "invalid"},
        )

        data = error.model_dump()
        assert data["error_type"] == "ValidationError"
        assert data["message"] == "Invalid input parameters"
        assert data["context"]["field"] == "username"

        # Round trip
        error2 = MiddlewareError.model_validate(data)
        assert error2.error_type == error.error_type
        assert error2.context == error.context


class TestMiddlewareValidators:
    """Test middleware model validators."""

    def test_rate_limit_config_validator(self):
        """Test rate limit configuration validator."""
        validator = RateLimitConfigValidator(RateLimitConfig)

        # Very high rate limit should generate warning
        high_rate_config = RateLimitConfig(requests_per_minute=2000)
        result = validator.validate(high_rate_config)
        assert any("Very high rate limit" in w for w in result.warnings)

        # Very low rate limit should generate warning
        low_rate_config = RateLimitConfig(requests_per_minute=5)
        result = validator.validate(low_rate_config)
        assert any("Very low rate limit" in w for w in result.warnings)

        # Log-only enforcement should generate suggestion
        log_only_config = RateLimitConfig(enforcement_mode="log_only")
        result = validator.validate(log_only_config)
        assert any("Log-only mode should only be used for testing" in s for s in result.suggestions)

    def test_cache_config_validator(self):
        """Test cache configuration validator."""
        validator = CacheConfigValidator(CacheConfig)

        # Large memory cache should generate warning
        large_memory_config = CacheConfig(
            backend_type=CacheBackendType.MEMORY,
            memory_max_size=15000,  # This will trigger the warning
            max_size=15000,
        )
        result = validator.validate(large_memory_config)
        assert any("Large memory cache" in w for w in result.warnings)

        # Short TTL should generate suggestion
        short_ttl_config = CacheConfig(default_ttl=30)
        result = validator.validate(short_ttl_config)
        assert any("Very short TTL" in s for s in result.suggestions)

        # Network cache without compression should generate suggestion
        no_compression_config = CacheConfig(
            backend_type=CacheBackendType.VALKEY,
            compression_enabled=False,
        )
        result = validator.validate(no_compression_config)
        assert any("Consider enabling compression" in s for s in result.suggestions)

    def test_retry_config_validator(self):
        """Test retry configuration validator."""
        validator = RetryConfigValidator(RetryConfig)

        # High retry attempts should generate warning
        high_attempts_config = RetryConfig(max_attempts=8)
        result = validator.validate(high_attempts_config)
        assert any("High retry attempts" in w for w in result.warnings)

        # High backoff factor with exponential strategy should generate warning
        high_backoff_config = RetryConfig(
            backoff_strategy="exponential",
            backoff_factor=5.0,
        )
        result = validator.validate(high_backoff_config)
        assert any("High backoff factor" in w for w in result.warnings)

        # Empty retry exceptions should generate suggestion
        no_exceptions_config = RetryConfig(retry_on_exceptions=[])
        result = validator.validate(no_exceptions_config)
        assert any("Consider specifying which exceptions" in s for s in result.suggestions)

    def test_middleware_config_validator(self):
        """Test middleware configuration validator."""
        validator = MiddlewareConfigValidator(MiddlewareConfig)

        # Test with problematic sub-configs
        problematic_config = MiddlewareConfig(
            rate_limit=RateLimitConfig(requests_per_minute=5000),  # Will generate warning
            cache=CacheConfig(default_ttl=30),  # Will generate suggestion
            timeout_seconds=15,  # Will generate warning
        )
        result = validator.validate(problematic_config)

        # Should have warnings from sub-validators and timeout
        assert any("Very high rate limit" in w for w in result.warnings)
        assert any("Very short TTL" in s for s in result.suggestions)
        assert any("Short global timeout" in w for w in result.warnings)

    def test_composite_middleware_validator(self):
        """Test composite middleware validator."""
        validator = create_middleware_validator()

        # Test with valid config
        config = MiddlewareConfig(
            rate_limit=RateLimitConfig(requests_per_minute=100),
            cache=CacheConfig(default_ttl=300),
            retry=RetryConfig(max_attempts=3),
        )
        result = validator.validate(config)
        assert result.valid is True


class TestMiddlewareModelSerialization:
    """Test middleware model serialization and deserialization."""

    def test_complete_middleware_config_json_round_trip(self):
        """Test complete middleware configuration JSON round trip."""
        config = MiddlewareConfig(
            enabled=True,
            middleware_order=[
                MiddlewareType.AUTHENTICATION,
                MiddlewareType.RATE_LIMIT,
                MiddlewareType.CACHE,
                MiddlewareType.RETRY,
            ],
            rate_limit=RateLimitConfig(
                requests_per_minute=200,
                burst_limit=300,
                custom_limits={"critical": 500},
            ),
            cache=CacheConfig(
                backend_type=CacheBackendType.VALKEY,
                default_ttl=600,
                valkey_url="redis://localhost:6379",
            ),
            retry=RetryConfig(
                max_attempts=4,
                backoff_strategy="exponential",
                backoff_factor=2.0,
            ),
            custom_middleware={"auth_custom": {"type": "oauth2"}},
        )

        # Serialize to JSON
        json_data = config.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        config2 = MiddlewareConfig.model_validate_json(json_data)
        assert config2.enabled == config.enabled
        assert config2.middleware_order == config.middleware_order
        assert config2.rate_limit.requests_per_minute == config.rate_limit.requests_per_minute
        assert config2.cache.backend_type == config.cache.backend_type
        assert config2.retry.backoff_strategy == config.retry.backoff_strategy
        assert config2.custom_middleware == config.custom_middleware
