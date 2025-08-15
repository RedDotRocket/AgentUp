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

## TTL Configuration

AgentUp supports hierarchical TTL configuration with the following priority order (each overwritten in sequence):

### 1. Middleware TTL Override (Per-Handler)

```yaml
middleware:
  - name: cached
    params:
      ttl: 350
```

### 2. Plugin-Level TTL Override (Per-Plugin)

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
plugins:
  - plugin_id: stock_prices
    middleware_override:
      - name: cached
        params:
          ttl: 30

  - plugin_id: weather
    middleware_override:  
      - name: cached
        params:
          ttl: 1800
```

### Different Backend Types per Plugin

```yaml
plugins:
  - plugin_id: calculations
    middleware_override:
      - name: cached
        params:
          backend_type: memory
          ttl: 300
          
  - plugin_id: user_preferences  
    middleware_override:
      - name: cached
        params:
          backend_type: valkey
          ttl: 3600
          valkey_url: "redis://localhost:6379"
          valkey_db: 2
```

## Complete Configuration Examples

### Development Setup (Memory Cache)

```yaml
middleware:
  caching:
    enabled: true
    backend: memory
    default_ttl: 300
    max_size: 1000

plugins:
  - plugin_id: weather
    middleware_override:
      - name: cached
        params:
          ttl: 600
```

### Production Setup (Valkey Cache)

```yaml
middleware:
  - name: cached
    params:
      ttl: 1800

plugins:
  - plugin_id: todays_date
    middleware_override:
      - name: cached
        params:
          ttl: 86400

  - plugin_id: bitcoin
    middleware_override:
      - name: cached
        params:
          ttl: 10
```

## Cache Management

### Disable Caching for Specific Plugins

```yaml
plugins:
  - plugin_id: real_time_data
    middleware_override: []
```

Or disable only caching while keeping other middleware:

```yaml
plugins:
  - plugin_id: real_time_data
    middleware_override:
      - name: timed
      - name: rate_limited
```

## What Gets Cached vs What Doesn't

### ✓ What AgentUp Caches

- **Handler/Plugin responses**
- **External API responses**
- **Expensive computations**
- **Database queries**
- **Static content**

### ✗ What AgentUp Does NOT Cache

- **Task UUIDs**  
- **Context objects**  
- **Timestamp data**  
- **LLM Calls** (non-deterministic, context-dependent, time-sensitive)

Example of why LLM caching would be problematic:

```yaml
User: "What's the weather like?"
Cached LLM Response: "It's sunny and 75°F" (from yesterday)
Reality: "It's stormy and 45°F" (today)
```

If you have a specific use case for LLM caching, please [open an issue](https://github.com/anthropics/agentup/issues).

## Best Practices

### TTL Guidelines

- **API responses**: 1–10 minutes
- **Expensive calculations**: 10–60 minutes
- **Static data**: 1–24 hours
- **Real-time data**: Disable or very short TTL (< 1 min)

### Database Separation

```yaml
state_management:
  backend: valkey
  config:
    db: 0
```

### Monitoring

```bash
redis-cli -n 1 INFO stats
redis-cli -n 1 KEYS "*" | wc -l
redis-cli -n 1 INFO memory
```

## Troubleshooting

### Common Issues

1. **Cache not working**: Verify middleware configuration includes `cached`
2. **TTL not applied**: Check TTL priority order (plugin > middleware > cache)
3. **Valkey connection errors**: Verify URL and ensure Valkey is running
4. **Memory cache full**: Increase `max_size` or use Valkey

### Debug Cache Behavior

```yaml
logging:
  level: "DEBUG"
```

Look for log messages:
- `Cache set for key: db7409832db5f29b50a5f1c249a4caf08af140e2d854ce77ccfb2d0ec7346ebd, TTL: 300s`
- `Cache hit for key: db7409832db5f29b50a5f1c249a4caf08af140e2d854ce77ccfb2d0ec7346ebd`
