# Cache Management

AgentUp provides a comprehensive caching system to optimize performance by storing frequently accessed data,
API responses, and computed results. This reduces latency and external API costs while improving user experience.

## Overview

Caching in AgentUp allows agents to:

- **Cache API responses** from LLM providers, external APIs, and databases
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

## TTL Configuration

AgentUp supports hierarchical TTL configuration with the following priority order:

### 1. Cache-Level Default TTL (Global)

Set default TTL for all cached items in the cache configuration:

```yaml
cache:
  type: memory  # or valkey
  config:
    default_ttl: 600  # 10 minutes - applies to all cached operations
```

### 2. Middleware TTL Override (Per-Handler)

Override cache default TTL for specific middleware:

```yaml
middleware:
  - name: cached
    params:
      ttl: 30  # Override cache default_ttl to 30 seconds
```

### 3. Skill-Level TTL Override (Per-Skill)

Override both cache and middleware TTL for specific skills:

```yaml
skills:
  - skill_id: echo
    middleware_override:
      - name: cached
        params:
          ttl: 120  # Override all other TTL settings to 2 minutes
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
  - name: cached
    # No TTL specified - uses cache default_ttl (300s)

# Override for specific skill
skills:
  - skill_id: weather
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

# Per-skill overrides
skills:
  - skill_id: ai_assistant
    middleware_override:
      - name: cached
        params:
          ttl: 60  # AI responses cached for 1 minute
  
  - skill_id: weather
    middleware_override:
      - name: cached
        params:
          ttl: 900  # Weather data cached for 15 minutes
```

## Cache Management

### Disable Caching for Specific Skills

```yaml
skills:
  - skill_id: real_time_data
    middleware_override: []  # Disable all middleware including caching
```

Or disable only caching while keeping other middleware:

```yaml
skills:
  - skill_id: real_time_data
    middleware_override:
      - name: logged
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

### ✅ What AgentUp Caches

- **Handler/Skill responses** - Results from skill execution (e.g., weather data, calculations)
- **External API responses** - Third-party API calls (weather, stock prices, etc.)
- **Expensive computations** - Complex calculations, data processing
- **Database queries** - User preferences, configuration data
- **Static content** - Documentation, file contents, reference data

### ❌ What AgentUp Does NOT Cache

**LLM Calls and AI Routing** - AgentUp deliberately does **not** cache LLM API calls or AI routing decisions because:

1. **Non-deterministic responses** - Same input produces different outputs due to temperature, sampling
2. **Context sensitivity** - Previous conversation affects current responses
3. **Time-dependent queries** - "What time is it?" should never return cached results
4. **User-specific context** - Same question needs different answers for different users
5. **Dynamic routing** - Skill selection depends on conversation context and user state

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
2. **TTL not applied**: Check TTL priority order (skill > middleware > cache)
3. **Valkey connection errors**: Verify URL and ensure Valkey is running
4. **Memory cache full**: Increase `max_size` or use Valkey for larger datasets

### Debug Cache Behavior

Enable debug logging to see cache hits/misses:

```yaml
logging:
  level: "DEBUG"
```

Look for log messages:
- `Cache hit for key: abcd1234...`
- `Cache miss, stored result for key: abcd1234... TTL: 300s (default)`