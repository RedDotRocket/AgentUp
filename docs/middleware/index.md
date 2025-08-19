# AgentUp Middleware

This document explains AgentUp's universal middleware system and it's automatic / opt-out and over-ride mechanisms.

## How It Works

### 1. Configuration

A root level middleware key is defined in your `agentup.yml`:

```yaml
middleware:
  - name: timed
    params: {}
  - name: cached
    params:
      ttl: 300
  - name: rate_limited
    params:
      requests_per_minute: 60
  - name: retryable
    params:
      max_retries: 3
      backoff_factor: 2
```

This configuration defines a list of middleware to be applied globally to all endpoints and plugins.

### 2. Automatic Application

When the agent starts:

1. **Framework loads** the middleware configuration
2. **Global application** applies middleware to all existing endpoints
    - This means all handlers registered with `register_handler()` automatically receive middleware
3. **Plugin integration** ensures plugin plugins receive middleware

### 3. Available Middleware

| Middleware | Purpose | Key Parameters |
|------------|---------|----------------|
| `timed` | Track execution time | None |
| `cached` | Cache responses | `ttl` (seconds) |
| `rate_limited` | Limit request rate | `requests_per_minute` |
| `retryable` | Retry on failure | `max_retries`, `backoff_factor` |


## Per-Plugin Override

Each Middleware feature can be overridden for specific plugins using the `plugin_override` field.

This allows you to customize middleware behavior for individual plugins, dependig on their specific needs.

This can be achieved in two ways:

1. **Complete Replacement**: Define a new set of middleware that replaces the global configuration for that plugin.
2. **Selective Exclusion**: Specify only the middleware you want to apply, excluding others
3. **Empty Override**: Use an empty `plugin_override` to disable all middleware for that plugin.

### Example Configurations

Let's assume we have the following global middleware configuration:

```yaml
# Global middleware for all handlers
middleware:
  - name: timed
    params: {}
  - name: cached
    params: {ttl: 300}  # 5 minutes default
  - name: rate_limited
    params: {requests_per_minute: 60}
  - name: retryable
    params: {max_retries: 3, backoff_factor: 2}
```

For a specific plugin, you can override this behavior, for example, to disable caching and change the rate limit:

```yaml
plugins:
  - plugin_id: expensive_operation
    name: Expensive Operation
    description: A resource-intensive operation
    plugin_override:
      - name: cached
        params: {ttl: 3600}  # 1 hour for this specific plugin
      - name: rate_limited
        params:
          requests_per_minute: 120  # higher rate limit for this plugin
```

### How Per-Plugin Overrides Work

1. **Global middleware** is defined in the top-level `middleware` section
2. **Per-plugin overrides** completely replace global middleware for that plugin
3. **Order matters** - middleware in the override is applied in the specified order
4. **Complete replacement** - if you use `plugin_override`, only those middleware are applied
5. **Disable all middleware** - use an empty `plugin_override: []` to disable all middleware for a plugin

### Use Cases for Per-Plugin Overrides

1. **Different Cache TTLs**:
   ```yaml
   plugins:
     weather_api:
       plugin_override:
         - name: cached
           config: {ttl: 1800}  # 30 minutes for weather data
   ```

2. **Disable Caching for Real-time Data**:
   ```yaml
   plugins:
     stock_ticker:
       plugin_override:
         - name: timed
           config: {}
         # No caching middleware
   ```

3. **Higher Rate Limits for Admin Functions**:
   ```yaml
   plugins:
     admin_panel:
       plugin_override:
         - name: rate_limited
           config: {requests_per_minute: 300}  # Higher limit
   ```

4. **Disable All Middleware**:
   ```yaml
   plugins:
     raw_performance:
       plugin_override: []  # Empty array disables all middleware
   ```

### Selectively Excluding Middleware

```yaml
plugins:
  - plugin_id: no_cache_plugin
    plugin_override:
      - name: timed
        params: {}
      - name: rate_limited
        params: {requests_per_minute: 60}
      # Note: No caching middleware listed

  # This plugin gets ONLY logging
  - plugin_id: minimal_plugin
    plugin_override:
      - name: timed
        params: {}

  # This plugin gets NO middleware at all
  - plugin_id: bare_metal_plugin
    plugin_override: []
```

Since `plugin_override` completely replaces the global middleware, you can exclude specific
middleware by simply not including them:

```yaml
# Global middleware
middleware:
  - name: timed
    params: {}
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 60}

plugins:
  # This skill gets everything EXCEPT caching
  - plugin_id: no_cache_skill
    plugin_override:
      - name: timed
        params: {}
      - name: rate_limited
        params: {requests_per_minute: 60}
      # Note: No caching middleware listed

  # This skill gets ONLY logging
  - plugin_id: minimal_skill
    plugin_override:
      - name: timed
        params: {}

  # This skill gets NO middleware at all
  - plugin_id: bare_metal_skill
    plugin_override: []
```

## Validation

Use `agentup validate` to check middleware configuration:

```bash
$ agentup validate
✓ Middleware configuration validated (5 middleware items)
```

## Troubleshooting

### Middleware Not Applied

1. **Check configuration** - Ensure `middleware` section exists in `agentup.yml`
2. **Validate syntax** - Use `agentup validate`

### Performance Issues

1. **Order matters** - Put caching before expensive middleware
2. **Tune parameters** - Adjust rate limits and cache TTLs
3. **Monitor metrics** - Use timing middleware to identify bottlenecks

## Best Practices

1. **Start minimal** - Add middleware incrementally
2. **Monitor impact** - Use timing middleware to measure
3. **Cache wisely** - Not all handlers benefit from caching
4. **Rate limit appropriately** - Balance protection vs usability
5. **Log judiciously** - INFO level for production, DEBUG for development
