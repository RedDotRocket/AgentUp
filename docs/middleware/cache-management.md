# Cache Management

AgentUp provides a comprehensive caching system to optimize performance by storing frequently accessed data, API responses, and computed results. This reduces latency and external API costs while improving user experience.

## Overview

Caching in AgentUp allows agents to:

- **Cache API responses** from external APIs, and databases
- **Store computed results** to avoid expensive recalculations
- **Reduce costs** by minimizing repeated external service calls
- **Improve response times** with instant cache hits
- **Handle rate limiting** by serving cached responses when APIs are unavailable

## Cache vs State

It's important to understand the distinction between **cache** and **state** in AgentUp:

| Aspect | Cache | State |
|--------|-------|-------|
| **Purpose** | Performance optimization | Conversation memory |
| **Data Type** | API responses, calculations | User context, preferences |
| **Lifecycle** | Short-term, expendable | Long-term, persistent |
| **Failure Impact** | Slower responses | Lost conversation memory |
| **TTL Policy** | Short (minutes/hours) | Long (hours/days) |
| **Use Cases** | LLM responses, weather data | Chat history, user settings |

## Cache Backends

### Valkey / Redis Cache (Recommended)
- **Type**: `valkey`
- **Performance**: Excellent for high concurrency
- **Persistence**: Optional (configurable)
- **Scalability**: Supports multiple agent instances
- **Features**: TTL, atomic operations, distributed caching

### Memory Cache
- **Type**: `memory`
- **Performance**: Fastest (no network overhead)
- **Persistence**: No (lost on restart)
- **Scalability**: Single instance only
- **Use case**: Development and testing

## Configuration

### Memory Cache Configuration

For development and testing:

```yaml
cache:
  type: memory
  config:
    max_size: 1000           # Maximum number of cached items
    default_ttl: 300         # Default TTL: 5 minutes
```

### Valkey Cache Configuration

For production environments:

```yaml
cache:
  type: valkey
  config:
    url: "${VALKEY_URL:valkey://localhost:6379}"
    db: 1                    # Use DB 1 for cache (DB 0 for state)
    max_connections: 10      # Connection pool size
    default_ttl: 300         # Default TTL: 5 minutes
```

!!! note "Redis / Valkey"
    As of time of writing, Redis and Valkey are interchangable, e.g. if you have redis, just use
    the value `valkey` and it will be the same. 

## TTL Configuration

AgentUp supports hierarchical TTL configuration with the following priority order (each overwritten
in sequence)

### 1. Cache-Level Default TTL (Global)

Set default TTL for all cached items in the cache configuration:

```yaml
cache:
  type: memory
  config:
    max_size: 1
    default_ttl: 300
```

### 2. Middleware TTL Override (Per-Handler)

Override cache default TTL for specific middleware:

```yaml
middleware:
  - name: cached
    params:
      ttl: 350
```

### 3. Plugin-Level TTL Override (Per-Plugin)

Override both cache and middleware TTL for specific plugins:

```yaml
plugins:
  - plugin_id: plugin
    middleware_override:
      - name: cached
        params:
          ttl: 100
```

## Multiple Cache Backends

AgentUp supports running **multiple cache backends simultaneously**. Each unique combination of backend type, TTL, max_size, and key_prefix creates a separate cache backend instance.

**Backend Key Format**: `{backend_type}:{key_prefix}:{default_ttl}:{max_size}`

Examples:
- `memory:agentup:300:1000` - Memory cache, 5min TTL, 1000 items
- `valkey:agentup:1800:1000` - Valkey cache, 30min TTL, 1000 items  
- `memory:myapp:60:500` - Memory cache, custom prefix, 1min TTL, 500 items

### Different TTLs per Plugin

```yaml
# Global cac`he configuration
cache:
  type: memory
  config:
    max_size: 1000
    default_ttl: 300  # 5 minutes default

middleware:
  caching:
    enabled: true
    backend: memory
    default_ttl: 300
    max_size: 1000

plugins:
  # Fast-changing data - short cache
  - plugin_id: stock_prices
    middleware_override:
      - name: cached
        params:
          ttl: 30  # 30 seconds
          # Creates backend: memory:agentup:30:1000

  # Slow-changing data - long cache  
  - plugin_id: weather
    middleware_override:  
      - name: cached
        params:
          ttl: 1800  # 30 minutes
          # Creates backend: memory:agentup:1800:1000
```

### Different Backend Types per Plugin

```yaml
# Global cache configuration
cache:
  type: memory
  config:
    max_size: 1000
    default_ttl: 300

middleware:
  caching:
    enabled: true
    backend: memory
    default_ttl: 300
    max_size: 1000

plugins:
  # Local data - fast memory cache
  - plugin_id: calculations
    middleware_override:
      - name: cached
        params:
          backend_type: memory
          ttl: 300
          # Creates backend: memory:agentup:300:1000
          
  # Shared data - persistent Valkey cache
  - plugin_id: user_preferences  
    middleware_override:
      - name: cached
        params:
          backend_type: valkey
          ttl: 3600
          valkey_url: "redis://localhost:6379"
          valkey_db: 2
          # Creates backend: valkey:agentup:3600:1000
```

## Complete Configuration Examples

### Development Setup (Memory Cache)

```yaml
# Cache configuration
cache:
  type: memory
  config:
    max_size: 1000
    default_ttl: 300  # 5 minutes

# Enable caching middleware
middleware:
  caching:
    enabled: true
    backend: memory
    default_ttl: 300
    max_size: 1000

# Override for specific plugin
plugins:
  - plugin_id: weather
    middleware_override:
      - name: cached
        params:
          ttl: 600  # Weather data cached for 10 minutes
```

### Production Setup (Valkey Cache)

```yaml
# Cache configuration
cache:
  type: valkey
  config:
    url: "${VALKEY_URL:valkey://localhost:6379}"
    db: 1
    max_connections: 20
    default_ttl: 300  # 5 minutes default

# Global middleware with custom TTL
middleware:
  - name: cached
    params:
      ttl: 1800  # 30 minutes for most operations

# Per-plugin overrides

# Slow to change
plugins:
  - plugin_id: todays_date
    middleware_override:
      - name: cached
        params:
          ttl: 86400  # cached for 1 day

# Fast to change
  - plugin_id: bitcoin
    middleware_override:
      - name: cached
        params:
          ttl: 10  # Bitcoin data cached for 10 seconds
```

## Cache Management

### Disable Caching for Specific Plugins

```yaml
plugins:
  - plugin_id: real_time_data
    middleware_override: []  # Disable all middleware including caching
```

Or disable only caching while keeping other middleware:

```yaml
plugins:
  - plugin_id: real_time_data
    middleware_override:
      - name: timed
      - name: rate_limited
      # Notice: no 'cached' middleware = caching disabled
```

### Environment Variables

Use environment variables for dynamic configuration:

```yaml
cache:
  type: valkey
  config:
    url: "${VALKEY_URL:valkey://localhost:6379}"
    default_ttl: "${CACHE_TTL:300}"
```

## What Gets Cached vs What Doesn't

### ✓ What AgentUp Caches

- **Handler/Plugin responses** - Results from plugin execution (e.g., weather data, calculations)
- **External API responses** - Third-party API calls (weather, stock prices, etc.)
- **Expensive computations** - Complex calculations, data processing
- **Database queries** - User preferences, configuration data
- **Static content** - Documentation, file contents, reference data

### ✗ What AgentUp Does NOT Cache

**Task Objects with Dynamic Data** - AgentUp automatically excludes certain dynamic data from cache keys:

- **Task UUIDs** - Each task has a unique ID that is filtered out of cache key generation
- **Context objects** - User-specific context with unique identifiers is excluded  
- **Timestamp data** - Dynamic timestamps and session-specific data

**LLM Calls** - AgentUp deliberately does **not** cache LLM API calls or AI routing decisions because:

- **Non-deterministic responses** - Same input produces different outputs due to temperature, sampling
- **Context sensitivity** - Previous conversation affects current responses
- **Time-dependent queries** - "What time is it?" should never return cached results
- **User-specific context** - Same question needs different answers for different users
- **Dynamic routing** - Plugin selection depends on conversation context and user state

**Example of why LLM caching would be problematic:**
```yaml
# Bad - this would be wrong
User: "What's the weather like?"
Cached LLM Response: "It's sunny and 75°F" (from yesterday)
Reality: "It's stormy and 45°F" (today)
```

**Request for LLM Caching:**
If you have a specific use case where LLM response caching would be beneficial, please [open an issue](https://github.com/anthropics/agentup/issues) with your requirements. We can discuss implementing configurable LLM caching with appropriate safeguards.

## Best Practices

### TTL Guidelines

- **API responses**: 1-10 minutes depending on data freshness requirements
- **Expensive calculations**: 10-60 minutes
- **Static data**: 1-24 hours
- **Real-time data**: Disable caching or use very short TTL (< 1 minute)

### Database Separation

When using Valkey, separate cache and state databases:

```yaml
# Cache configuration
cache:
  type: valkey
  config:
    db: 1  # Use DB 1 for cache

# State configuration
state_management:
  backend: valkey
  config:
    db: 0  # Use DB 0 for state
```

### Monitoring

Monitor cache performance:

```bash
# Check cache hit rates
redis-cli -n 1 INFO stats

# Monitor cache keys
redis-cli -n 1 KEYS "*" | wc -l

# Check memory usage
redis-cli -n 1 INFO memory
```

## Troubleshooting

### Common Issues

1. **Cache not working**: Verify middleware configuration includes `cached`
2. **TTL not applied**: Check TTL priority order (plugin > middleware > cache)
3. **Valkey connection errors**: Verify URL and ensure Valkey is running
4. **Memory cache full**: Increase `max_size` or use Valkey for larger datasets

### Debug Cache Behavior

Enable debug logging to see cache hits/misses:

```yaml
logging:
  level: "DEBUG"
```

Look for log messages:
- `Cache set for key: db7409832db5f29b50a5f1c249a4caf08af140e2d854ce77ccfb2d0ec7346ebd, TTL: 300s`
- `Cache hit for key: db7409832db5f29b50a5f1c249a4caf08af140e2d854ce77ccfb2d0ec7346ebd`
