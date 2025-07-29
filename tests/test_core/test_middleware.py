import asyncio
import functools
import time
from unittest.mock import patch

import pytest

from agent.middleware import (
    MiddlewareError,
    MiddlewareRegistry,
    RateLimiter,
    RateLimitExceeded,
    RetryConfig,
    apply_caching,
    apply_rate_limiting,
    apply_retry,
    cached,
    clear_cache,
    execute_with_retry,
    get_cache_stats,
    get_rate_limit_stats,
    rate_limited,
    reset_rate_limits,
    retryable,
    timed,
    with_middleware,
)


class TestMiddlewareRegistry:
    def test_registry_initialization(self):
        registry = MiddlewareRegistry()
        assert registry._middleware == {}

    def test_register_middleware(self):
        registry = MiddlewareRegistry()

        def dummy_middleware():
            pass

        registry.register("test_middleware", dummy_middleware)
        assert registry.get("test_middleware") == dummy_middleware

    def test_get_nonexistent_middleware(self):
        registry = MiddlewareRegistry()
        assert registry.get("nonexistent") is None

    def test_apply_middleware_to_handler(self):
        registry = MiddlewareRegistry()

        # Mock middleware function
        def mock_middleware(handler, **kwargs):
            @functools.wraps(handler)
            def wrapper(*args, **kwargs):
                result = handler(*args, **kwargs)
                return f"middleware_applied:{result}"

            return wrapper

        registry.register("test_middleware", mock_middleware)

        # Mock handler
        def mock_handler():
            return "original_result"

        # Apply middleware
        middleware_configs = [{"name": "test_middleware", "params": {}}]
        wrapped_handler = registry.apply(mock_handler, middleware_configs)

        result = wrapped_handler()
        assert result == "middleware_applied:original_result"


class TestRateLimiter:
    def test_rate_limiter_initialization(self):
        limiter = RateLimiter()
        assert limiter.buckets == {}

    def test_rate_limit_within_limit(self):
        limiter = RateLimiter()
        key = "test_key"

        # First request should be allowed
        assert limiter.check_rate_limit(key, requests_per_minute=60) is True

    def test_rate_limit_bucket_initialization(self):
        limiter = RateLimiter()
        key = "test_key"
        requests_per_minute = 60

        limiter.check_rate_limit(key, requests_per_minute)

        bucket = limiter.buckets[key]
        assert bucket["tokens"] == requests_per_minute - 1  # One token consumed
        assert bucket["requests_per_minute"] == requests_per_minute
        assert "last_update" in bucket

    def test_rate_limit_exceeded(self):
        limiter = RateLimiter()
        key = "test_key"

        # Manually set bucket to have no tokens
        limiter.buckets[key] = {"tokens": 0, "last_update": time.time(), "requests_per_minute": 60}

        assert limiter.check_rate_limit(key, requests_per_minute=60) is False

    def test_rate_limit_token_refill(self):
        limiter = RateLimiter()
        key = "test_key"

        # Initialize bucket with no tokens but old timestamp
        past_time = time.time() - 60  # 1 minute ago
        limiter.buckets[key] = {"tokens": 0, "last_update": past_time, "requests_per_minute": 60}

        # Should refill and allow request
        assert limiter.check_rate_limit(key, requests_per_minute=60) is True

    def test_rate_limit_max_tokens(self):
        limiter = RateLimiter()
        key = "test_key"

        # Initialize bucket with tokens and old timestamp
        past_time = time.time() - 3600  # 1 hour ago
        limiter.buckets[key] = {"tokens": 30, "last_update": past_time, "requests_per_minute": 60}

        limiter.check_rate_limit(key, requests_per_minute=60)

        # Should not exceed max tokens (60) even with long time passed
        assert limiter.buckets[key]["tokens"] <= 60

    def test_retry_config_initialization(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_factor == 1.0
        assert config.max_delay == 60.0

    def test_retry_config_custom_values(self):
        config = RetryConfig(max_attempts=5, backoff_factor=2.0, max_delay=120.0)
        assert config.max_attempts == 5
        assert config.backoff_factor == 2.0
        assert config.max_delay == 120.0


class TestExecuteWithRetry:
    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self):
        async def success_func():
            return "success"

        config = RetryConfig(max_attempts=3)
        result = await execute_with_retry(success_func, config)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(self):
        call_count = 0

        async def sometimes_fail_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=3, backoff_factor=0.01)  # Fast backoff for testing
        result = await execute_with_retry(sometimes_fail_func, config)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_all_attempts_fail(self):
        async def always_fail_func():
            raise ValueError("Always fails")

        config = RetryConfig(max_attempts=3, backoff_factor=0.01)  # Fast backoff for testing

        with pytest.raises(ValueError, match="Always fails"):
            await execute_with_retry(always_fail_func, config)

    @pytest.mark.asyncio
    async def test_execute_with_retry_sync_function(self):
        def sync_success_func():
            return "sync_success"

        config = RetryConfig(max_attempts=3)
        result = await execute_with_retry(sync_success_func, config)
        assert result == "sync_success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_backoff_timing(self):
        call_times = []

        async def timing_test_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Fail for timing test")
            return "success"

        config = RetryConfig(max_attempts=3, backoff_factor=0.1)  # Small backoff for testing
        await execute_with_retry(timing_test_func, config)

        # Verify calls were spaced out (allowing for some timing variance)
        assert len(call_times) == 3
        # First retry should be after ~0.1s, second after ~0.2s
        time_diff_1 = call_times[1] - call_times[0]
        time_diff_2 = call_times[2] - call_times[1]
        assert 0.05 <= time_diff_1 <= 0.3  # Allow variance
        assert 0.15 <= time_diff_2 <= 0.5  # Allow variance


class TestMiddlewareDecorators:
    @pytest.mark.asyncio
    async def test_rate_limited_decorator(self):
        @rate_limited(requests_per_minute=60)
        async def test_func():
            return "success"

        # First call should succeed
        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_rate_limited_decorator_exceeded(self):
        @rate_limited(requests_per_minute=1)  # Very low limit
        async def test_func():
            return "success"

        # First call should succeed
        await test_func()

        # Second immediate call should fail
        with pytest.raises(RateLimitExceeded):
            await test_func()

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        call_count = 0

        @cached(ttl=300)
        async def test_func(arg):
            nonlocal call_count
            call_count += 1
            return f"result_{arg}_{call_count}"

        # First call
        result1 = await test_func("test")
        assert result1 == "result_test_1"
        assert call_count == 1

        # Second call with same arg should return cached result
        result2 = await test_func("test")
        assert result2 == "result_test_1"  # Same result, not incremented
        assert call_count == 1  # Function not called again

        # Call with different arg should execute function
        result3 = await test_func("other")
        assert result3 == "result_other_2"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retryable_decorator(self):
        call_count = 0

        @retryable(max_attempts=3, backoff_factor=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await test_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timed_decorator(self):
        with patch("agent.middleware.logger") as mock_logger:

            @timed()
            async def test_func():
                await asyncio.sleep(0.01)  # Small delay
                return "success"

            result = await test_func()
            assert result == "success"

            # Verify timing log was made
            mock_logger.info.assert_called()
            log_call = mock_logger.info.call_args[0][0]
            assert "executed in" in log_call
            assert "test_func" in log_call

    @pytest.mark.asyncio
    async def test_with_middleware_decorator(self):
        call_count = 0

        @with_middleware(
            [
                {"name": "timed", "params": {}},
            ]
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        with patch("agent.middleware.logger"):
            result = await test_func()
            assert result == "success"
            assert call_count == 1


class TestMiddlewareComposition:
    def setup_method(self):
        reset_rate_limits()
        clear_cache()

    @pytest.mark.asyncio
    async def test_multiple_middleware_decorators(self):
        call_count = 0

        @rate_limited(requests_per_minute=3600)  # High rate limit to avoid interference
        @cached(ttl=300)
        @timed()
        async def test_func(arg):
            nonlocal call_count
            call_count += 1
            return f"result_{arg}_{call_count}"

        with patch("agent.middleware.logger"):
            # First call
            result1 = await test_func("test")
            assert result1 == "result_test_1"
            assert call_count == 1

            # Second call should be cached
            result2 = await test_func("test")
            assert result2 == "result_test_1"
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_middleware_error_handling(self):
        @rate_limited(requests_per_minute=3600)  # High rate limit to avoid interference
        async def test_func():
            raise ValueError("Test exception")

        # Test that middleware doesn't interfere with exception propagation
        with pytest.raises(ValueError, match="Test exception"):
            await test_func()


class TestUtilityFunctions:
    def test_apply_rate_limiting(self):
        async def test_handler():
            return "success"

        wrapped = apply_rate_limiting(test_handler, requests_per_minute=60)
        assert callable(wrapped)

    def test_apply_caching(self):
        async def test_handler():
            return "success"

        wrapped = apply_caching(test_handler, ttl=300)
        assert callable(wrapped)

    def test_apply_retry(self):
        async def test_handler():
            return "success"

        wrapped = apply_retry(test_handler, max_attempts=3)
        assert callable(wrapped)

    def test_clear_cache_function(self):
        # This tests the global cache clearing
        clear_cache()  # Should not raise any exceptions

    def test_get_cache_stats(self):
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "total_entries" in stats
        assert "expired_entries" in stats
        assert "active_entries" in stats

    def test_reset_rate_limits(self):
        reset_rate_limits()  # Should not raise any exceptions

    def test_get_rate_limit_stats(self):
        stats = get_rate_limit_stats()
        assert isinstance(stats, dict)
        assert "active_buckets" in stats
        assert "buckets" in stats


class TestMiddlewareExceptions:
    def test_middleware_error(self):
        error = MiddlewareError(error_type="MiddlewareError", message="Test error")
        assert error.message == "Test error"
        assert error.error_type == "MiddlewareError"

    def test_rate_limit_error(self):
        error = RateLimitExceeded("Rate limit exceeded")
        assert error.message == "Rate limit exceeded"
        assert str(error) == "Rate limit exceeded"
        assert isinstance(error, Exception)


class TestCacheKeyGeneration:
    @pytest.mark.asyncio
    async def test_cache_key_with_different_args(self):
        call_count = 0

        @cached(ttl=300)
        async def test_func(arg1, arg2):
            nonlocal call_count
            call_count += 1
            return f"result_{arg1}_{arg2}_{call_count}"

        # Different arguments should create separate cache entries
        result1 = await test_func("a", "b")
        result2 = await test_func("c", "d")
        result3 = await test_func("a", "b")  # Same as first call

        assert result1 == "result_a_b_1"
        assert result2 == "result_c_d_2"
        assert result3 == "result_a_b_1"  # Cached result
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_key_with_kwargs(self):
        call_count = 0

        @cached(ttl=300)
        async def test_func(**kwargs):
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # Same kwargs should use cache
        result1 = await test_func(a=1, b=2)
        result2 = await test_func(a=1, b=2)

        assert result1 == "result_1"
        assert result2 == "result_1"  # Cached
        assert call_count == 1


class TestRateLimitKeyGeneration:
    @pytest.mark.asyncio
    async def test_rate_limit_key_with_different_args(self):
        @rate_limited(requests_per_minute=1)  # Very restrictive
        async def test_func(arg):
            return f"result_{arg}"

        # Different arguments should have separate rate limits
        result1 = await test_func("a")
        result2 = await test_func("b")  # Should succeed even with restrictive limit

        assert result1 == "result_a"
        assert result2 == "result_b"
