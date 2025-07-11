# Middleware Auto-Application System

This document explains AgentUp's universal middleware system that automatically applies middleware to all handlers and plugins based on configuration.

## Overview

As of the latest update, AgentUp has transitioned from manual middleware application to a **universal, configuration-driven system**. Middleware defined in `agent_config.yaml` is now automatically applied to:

- All built-in handlers
- All plugin skills
- All newly registered handlers

## Key Benefits

1. **No Manual Decorators** - No need to manually add `@cached()`, `@rate_limited()` etc. to handlers
2. **Consistent Application** - All handlers receive the same middleware stack
3. **Configuration-Driven** - Change behavior through config, not code
4. **Plugin Compatibility** - Plugins automatically inherit middleware

## How It Works

### 1. Configuration

Define middleware in your `agent_config.yaml`:

```yaml
middleware:
  - name: timed
    params: {}
  - name: cached
    params:
      ttl: 300  # 5 minutes
  - name: rate_limited
    params:
      requests_per_minute: 60
  - name: retryable
    params:
      max_retries: 3
      backoff_factor: 2
```

### 2. Automatic Application

When the agent starts:

1. **Framework loads** the middleware configuration
2. **Global application** applies middleware to all existing handlers
3. **Registration hook** applies middleware to new handlers as they're registered
4. **Plugin integration** ensures plugin skills receive middleware

### 3. Available Middleware

| Middleware | Purpose | Key Parameters |
|------------|---------|----------------|
| `timed` | Track execution time | None |
| `cached` | Cache responses | `ttl` (seconds) |
| `rate_limited` | Limit request rate | `requests_per_minute` |
| `retryable` | Retry on failure | `max_retries`, `backoff_factor` |
| `validated` | Validate inputs | `schema` |

## Implementation Details

### Handler Registration

```python
# Old way (manual)
@register_handler("my_skill")
@cached(ttl=300)
@rate_limited(requests_per_minute=60)
async def my_handler(task: Task) -> str:
    return "result"

# New way (automatic)
@register_handler("my_skill")
async def my_handler(task: Task) -> str:
    # Middleware automatically applied from config!
    return "result"
```

### Plugin Skills

Plugins automatically receive middleware through the registration system:

```python
# In plugin
def execute_skill(self, context):
    # This will have middleware applied automatically
    return SkillResult(content="response", success=True)
```

### Global Application

The framework applies middleware during startup:

```python
# In app.py startup
from agent.handlers.handlers import apply_global_middleware

apply_global_middleware()
logger.info("Global middleware applied to existing handlers")
```

## Configuration Examples

### Basic Setup (Minimal Logging)

```yaml
middleware:
  - name: timed
    params: {}
  - name: timed
    params: {}
```

### Production Setup (Full Protection)

```yaml
middleware:
  - name: timed
    params: {}
  - name: rate_limited
    params:
      requests_per_minute: 100
      burst_size: 10
  - name: cached
    params:
      ttl: 600  # 10 minutes
      cache_errors: false
  - name: retryable
    params:
      max_retries: 3
      backoff_factor: 2
      retry_on: [500, 502, 503, 504]
```

### High-Performance Setup

```yaml
middleware:
  - name: cached  # Cache first for best performance
    params:
      ttl: 1800  # 30 minutes
  - name: rate_limited
    params:
      requests_per_minute: 1000
  - name: timed
    params: {}
```

## Order Matters

Middleware is applied in the order specified in the configuration. Consider performance implications:

```yaml
middleware:
  # Good order - check cache before expensive operations
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 60}
  - name: timed
    params: {}
  
  - name: cached
    params: {ttl: 300}
```

## Per-Skill Override

While middleware is applied globally by default, you can override middleware for specific skills using the `middleware_override` field:

```yaml
# Global middleware for all handlers
middleware:
  - name: timed
    params: {}
  - name: cached
    params: {ttl: 300}  # 5 minutes default

# Skill-specific override
skills:
  - skill_id: expensive_operation
    name: Expensive Operation
    description: A resource-intensive operation
    middleware_override:
      - name: cached
        params: {ttl: 3600}  # 1 hour for this specific skill
      - name: timed
        params: {}  # Timing for troubleshooting
      
  - skill_id: realtime_data
    name: Real-time Data
    description: Always needs fresh data
    middleware_override:
      # No caching for real-time data
      - name: timed
        params: {}
        params: {}
```

### How Per-Skill Overrides Work

1. **Global middleware** is defined in the top-level `middleware` section
2. **Per-skill overrides** completely replace global middleware for that skill
3. **Order matters** - middleware in the override is applied in the specified order
4. **Complete replacement** - if you use `middleware_override`, only those middleware are applied
5. **Disable all middleware** - use an empty `middleware_override: []` to disable all middleware for a skill

### Use Cases for Per-Skill Overrides

1. **Different Cache TTLs**:
   ```yaml
   skills:
     - skill_id: weather_api
       middleware_override:
         - name: cached
           params: {ttl: 1800}  # 30 minutes for weather data
   ```

2. **Disable Caching for Real-time Data**:
   ```yaml
   skills:
     - skill_id: stock_ticker
       middleware_override:
         - name: timed
           params: {}
         # No caching middleware
   ```

3. **Higher Rate Limits for Admin Functions**:
   ```yaml
   skills:
     - skill_id: admin_panel
       middleware_override:
         - name: rate_limited
           params: {requests_per_minute: 300}  # Higher limit
   ```

4. **Debug Specific Skills**:
   ```yaml
   skills:
     - skill_id: problematic_skill
       middleware_override:
         - name: timed
           params: {}
           params: {}  # Track performance
   ```

5. **Disable All Middleware**:
   ```yaml
   skills:
     - skill_id: raw_performance
       middleware_override: []  # Empty array disables all middleware
   ```

### Selectively Excluding Middleware

Since `middleware_override` completely replaces the global middleware, you can exclude specific middleware by simply not including them:

```yaml
# Global middleware
middleware:
  - name: timed
    params: {}
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 60}

skills:
  # This skill gets everything EXCEPT caching
  - skill_id: no_cache_skill
    middleware_override:
      - name: timed
        params: {}
      - name: rate_limited
        params: {requests_per_minute: 60}
      # Note: No caching middleware listed
  
  # This skill gets ONLY logging
  - skill_id: minimal_skill
    middleware_override:
      - name: timed
        params: {}
  
  # This skill gets NO middleware at all
  - skill_id: bare_metal_skill
    middleware_override: []
```

## Validation

Use `agentup agent validate` to check middleware configuration:

```bash
$ agentup agent validate
✓ Middleware configuration validated (5 middleware items)
```

## Troubleshooting

### Middleware Not Applied

1. **Check configuration** - Ensure `middleware` section exists in `agent_config.yaml`
2. **Validate syntax** - Use `agentup agent validate`
3. **Check logs** - Look for "Global middleware applied" during startup

### Performance Issues

1. **Order matters** - Put caching before expensive middleware
2. **Tune parameters** - Adjust rate limits and cache TTLs
3. **Monitor metrics** - Use timing middleware to identify bottlenecks

### Plugin Compatibility

Plugins automatically receive middleware if they:
- Use the standard plugin hook system
- Register through `register_skill()` hook
- Return proper `SkillResult` objects

## Migration Guide

### From Manual to Auto-Applied

1. **Remove manual decorators** from handlers:
   ```python
   # Remove these
   @cached(ttl=300)
   @rate_limited(requests_per_minute=60)
   ```

2. **Add to configuration**:
   ```yaml
   middleware:
     - name: cached
       params: {ttl: 300}
     - name: rate_limited
       params: {requests_per_minute: 60}
   ```

3. **Test thoroughly** - Ensure middleware behavior matches expectations

## Best Practices

1. **Start minimal** - Add middleware incrementally
2. **Monitor impact** - Use timing middleware to measure
3. **Cache wisely** - Not all handlers benefit from caching
4. **Rate limit appropriately** - Balance protection vs usability
5. **Log judiciously** - INFO level for production, DEBUG for development

## Summary

The middleware auto-application system provides:

- ✅ **Universal coverage** - All handlers and plugins protected
- ✅ **Configuration control** - Change behavior without code changes
- ✅ **Consistent application** - No missed handlers
- ✅ **Plugin compatibility** - Automatic inheritance
- ✅ **Performance optimization** - Order middleware for efficiency

This system ensures that all AgentUp agents have consistent middleware application, improving security, performance, and reliability across the board.