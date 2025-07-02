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

### Valkey Cache (Recommended)
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

### File Cache
- **Type**: `file`
- **Performance**: Good for small workloads
- **Persistence**: Yes (files on disk)
- **Scalability**: Limited (file locking issues)
- **Use case**: Single-instance deployments

## Configuration

### Cache vs State Configuration

AgentUp uses **two separate Valkey configurations** for different purposes:

```yaml
services:
  valkey:
    type: cache                           # Used for CACHING
    config:
      url: "valkey://localhost:6379"
      db: 1                              # Use different DB for cache

state:
  backend: valkey                        # Used for CONVERSATION MEMORY
  url: "valkey://localhost:6379"  
  key_prefix: "agentup:state:"
  ttl: 3600

cache:
  backend: valkey                        # Used for PERFORMANCE OPTIMIZATION
  key_prefix: "agentup:cache:"
  default_ttl: 1800
```

### Why Separate Cache and State?

| Purpose | Cache | State |
|---------|-------|-------|
| **Data Type** | API responses, computations | Conversation history, user context |
| **Failure Impact** | Slower performance | Lost memory |
| **TTL Policy** | Short (minutes) | Long (hours/days) |
| **Valkey DB** | Can use separate database | Typically DB 0 |
| **Cleanup** | Can clear anytime | Requires careful management |

### Valkey Cache Configuration

#### Basic Setup

```yaml
# External services - Valkey for caching
services:
  valkey:
    type: cache
    config:
      url: "valkey://localhost:6379"
      db: 1                    # Use DB 1 for cache (DB 0 for state)

# Cache system configuration
cache:
  backend: valkey
  default_ttl: 3600           # 1 hour default TTL
  key_prefix: "agentup:cache:"
  enabled: true
```

#### Production Configuration

```yaml
services:
  valkey:
    type: cache
    config:
      url: "${VALKEY_CACHE_URL:valkey://valkey-cache:6379}"
      db: 1
      max_connections: 20
      retry_on_timeout: true
      socket_keepalive: true

cache:
  backend: valkey
  default_ttl: 1800           # 30 minutes
  key_prefix: "${CACHE_PREFIX:agentup:cache:}"
  enabled: true
```

#### High-Performance Configuration

```yaml
services:
  valkey:
    type: cache
    config:
      url: "valkey://valkey-cluster:6379"
      db: 1
      max_connections: 50
      connection_pool_kwargs:
        retry_on_timeout: true
        socket_keepalive: true
        socket_connect_timeout: 5
        socket_timeout: 5

cache:
  backend: valkey
  default_ttl: 3600
  key_prefix: "agentup:cache:"
  enabled: true
```

### Memory Cache Configuration

For development and testing:

```yaml
cache:
  backend: memory
  default_ttl: 1800           # 30 minutes
  max_size: 1000              # Maximum cached items
  cleanup_interval: 300       # Cleanup every 5 minutes
  enabled: true
```

### File Cache Configuration

For single-instance deployments:

```yaml
cache:
  backend: file
  storage_dir: "./cache"      # Cache directory
  default_ttl: 7200          # 2 hours
  max_file_size: 1048576     # 1MB max per file
  cleanup_interval: 3600     # Cleanup every hour
  enabled: true
```

## Environment-Specific Configurations

### Development Environment

```yaml
# Fast development cycle with memory cache
cache:
  backend: memory
  default_ttl: 300            # 5 minutes - short for testing
  max_size: 100
  enabled: true
```

### Testing Environment

```yaml
# Disabled cache for consistent test results
cache:
  backend: memory
  default_ttl: 60             # 1 minute
  max_size: 50
  enabled: false              # Disable for testing
```

### Production Environment

```yaml
services:
  valkey:
    type: cache
    config:
      url: "${VALKEY_CACHE_URL}"
      db: "${VALKEY_CACHE_DB:1}"
      max_connections: 20
      retry_on_timeout: true

cache:
  backend: valkey
  default_ttl: 3600
  key_prefix: "${CACHE_KEY_PREFIX:prod:cache:}"
  enabled: true
```

### Multi-Valkey Setup

Using different Valkey instances for cache and state:

```yaml
services:
  # High-performance Valkey for caching
  valkey:
    type: cache
    config:
      url: "valkey://fast-valkey:6379"
      db: 0
      max_connections: 30

  # Persistent Valkey for state
  valkey_state:
    type: database
    config:
      url: "valkey://persistent-valkey:6379"
      db: 0

state:
  backend: valkey
  url: "valkey://persistent-valkey:6379"
  key_prefix: "agentup:state:"
  ttl: 86400                  # 24 hours

cache:
  backend: valkey
  key_prefix: "agentup:cache:"
  default_ttl: 1800           # 30 minutes
```

## Using Cache in Skills

### The @cached Decorator

Use the `@cached` decorator to automatically cache handler results:

```python
from src.agent.middleware import cached
from a2a.types import Task

@cached(ttl=1800, key_template="weather:{location}")
async def get_weather(task: Task, location: str):
    """Get weather data with caching."""
    # This will be cached for 30 minutes per location
    weather_data = await external_weather_api(location)
    return weather_data

@cached(ttl=3600, key_template="llm_response:{prompt_hash}")
async def generate_response(task: Task, prompt: str):
    """Generate LLM response with caching."""
    # Cache responses for 1 hour based on prompt hash
    response = await llm_service.generate(prompt)
    return response
```

### Manual Cache Operations

For more control, use the cache service directly:

```python
from src.agent.services import get_services

async def my_handler(task: Task):
    services = get_services()
    cache = services.get_cache()
    
    # Check cache first
    cache_key = f"user_data:{user_id}"
    cached_data = await cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    # Fetch from external service
    user_data = await fetch_user_data(user_id)
    
    # Store in cache for 1 hour
    await cache.set(cache_key, user_data, ttl=3600)
    
    return user_data
```

## Cache Operations

### Basic Operations

```python
from src.agent.services import get_services

async def cache_operations_example():
    services = get_services()
    cache = services.get_cache()
    
    # Set with default TTL
    await cache.set("key1", "value1")
    
    # Set with custom TTL (30 minutes)
    await cache.set("key2", {"data": "complex"}, ttl=1800)
    
    # Get value
    value = await cache.get("key1")
    
    # Get with default if not found
    value = await cache.get("key3", default="not found")
    
    # Check if key exists
    exists = await cache.exists("key1")
    
    # Delete key
    await cache.delete("key1")
    
    # Clear all cache (use with caution)
    await cache.clear()
```

### Batch Operations

```python
async def batch_cache_operations():
    cache = services.get_cache()
    
    # Set multiple keys
    data = {
        "user:123": {"name": "Alice", "role": "admin"},
        "user:456": {"name": "Bob", "role": "user"},
        "config:theme": {"mode": "dark", "color": "blue"}
    }
    await cache.set_many(data, ttl=3600)
    
    # Get multiple keys
    keys = ["user:123", "user:456", "user:789"]
    values = await cache.get_many(keys)
    # Returns: {"user:123": {...}, "user:456": {...}, "user:789": None}
    
    # Delete multiple keys
    await cache.delete_many(["user:123", "config:theme"])
```

### Cache Patterns

#### 1. API Response Caching

```python
@cached(ttl=1800, key_template="api_response:{endpoint}:{params_hash}")
async def fetch_external_api(endpoint: str, params: dict):
    """Cache external API responses."""
    response = await httpx.get(f"https://api.example.com/{endpoint}", params=params)
    return response.json()
```

#### 2. LLM Response Caching

```python
import hashlib

@cached(ttl=3600, key_template="llm:{model}:{prompt_hash}")
async def generate_llm_response(model: str, prompt: str, **kwargs):
    """Cache LLM responses based on prompt hash."""
    services = get_services()
    llm = services.get_llm(model)
    
    response = await llm.generate(prompt, **kwargs)
    return response.content
```

#### 3. Database Query Caching

```python
@cached(ttl=600, key_template="db_query:{table}:{query_hash}")
async def cached_database_query(table: str, query: str, params: list):
    """Cache database query results."""
    services = get_services()
    db = services.get_database()
    
    result = await db.execute(query, params)
    return result
```

#### 4. User-Specific Caching

```python
async def get_user_preferences(user_id: str):
    """Cache user preferences with user isolation."""
    cache = services.get_cache()
    cache_key = f"user_prefs:{user_id}"
    
    prefs = await cache.get(cache_key)
    if not prefs:
        prefs = await database.get_user_preferences(user_id)
        await cache.set(cache_key, prefs, ttl=1800)
    
    return prefs
```

## Cache Middleware

### Automatic Response Caching

Use middleware to automatically cache handler responses:

```python
from src.agent.middleware import cached

# Cache all responses from this handler for 10 minutes
@cached(ttl=600)
async def expensive_computation_handler(task: Task):
    # Expensive operation
    result = perform_complex_calculation(task.input)
    return result
```

### Conditional Caching

```python
@cached(ttl=1800, condition=lambda task: "cache" in task.input.lower())
async def conditional_cache_handler(task: Task):
    """Only cache responses when user requests caching."""
    if "no-cache" in task.input.lower():
        # Force fresh response
        return await fresh_computation(task)
    
    return await standard_response(task)
```

## Performance Optimization

### Cache Key Design

Good cache keys are:
- **Unique**: Avoid collisions between different data
- **Descriptive**: Easy to understand and debug
- **Hierarchical**: Use colons for namespacing

```python
# Good cache key patterns
"user:{user_id}:preferences"
"api:weather:{city}:{date}"
"llm:{model}:{prompt_hash}:{temperature}"
"db:query:{table}:{hash}"

# Poor cache key patterns
"data123"  # Not descriptive
"user_123_prefs"  # Hard to namespace
"cache_key"  # Too generic
```

### TTL Strategy

Choose appropriate TTL values:

```python
# Data freshness requirements
CACHE_TTL = {
    "static_data": 86400,      # 24 hours - rarely changes
    "user_prefs": 3600,        # 1 hour - changes occasionally
    "api_responses": 1800,     # 30 minutes - moderate freshness
    "real_time_data": 300,     # 5 minutes - needs freshness
    "computed_results": 600,   # 10 minutes - expensive to compute
}
```

### Cache Warming

Pre-populate cache with frequently accessed data:

```python
async def warm_cache():
    """Pre-populate cache with common data."""
    cache = services.get_cache()
    
    # Common user preferences
    common_users = await get_active_users()
    for user_id in common_users:
        prefs = await fetch_user_preferences(user_id)
        await cache.set(f"user_prefs:{user_id}", prefs, ttl=3600)
    
    # Frequently requested API data
    popular_locations = ["london", "paris", "tokyo"]
    for location in popular_locations:
        weather = await fetch_weather_data(location)
        await cache.set(f"weather:{location}", weather, ttl=1800)
```

## Monitoring and Debugging

### Cache Statistics

Monitor cache performance:

```python
async def get_cache_stats():
    """Get cache performance statistics."""
    cache = services.get_cache()
    
    if hasattr(cache, 'stats'):
        stats = await cache.stats()
        return {
            "hits": stats.get("hits", 0),
            "misses": stats.get("misses", 0),
            "hit_rate": stats.get("hit_rate", 0.0),
            "memory_usage": stats.get("memory_usage", 0),
            "key_count": stats.get("key_count", 0)
        }
    
    return {"message": "Stats not available for this cache backend"}
```

### Cache Debugging

Debug cache issues:

```python
async def debug_cache_key(key: str):
    """Debug specific cache key."""
    cache = services.get_cache()
    
    exists = await cache.exists(key)
    if exists:
        value = await cache.get(key)
        ttl = await cache.ttl(key) if hasattr(cache, 'ttl') else "unknown"
        
        return {
            "key": key,
            "exists": True,
            "value_type": type(value).__name__,
            "value_size": len(str(value)),
            "ttl": ttl
        }
    else:
        return {"key": key, "exists": False}
```

## Best Practices

### Performance

1. **Use appropriate TTL**: Balance freshness vs. performance
2. **Cache expensive operations**: API calls, database queries, computations
3. **Avoid caching small/cheap data**: Don't cache data faster to compute than retrieve
4. **Monitor hit rates**: Aim for >80% hit rate for effective caching

### Data Management

1. **Use meaningful key patterns**: Easy to debug and manage
2. **Implement cache invalidation**: Clear stale data when source changes
3. **Handle cache failures gracefully**: Always have fallback logic
4. **Set reasonable TTL limits**: Prevent unbounded cache growth

### Security

1. **Avoid caching sensitive data**: Or encrypt before caching
2. **User data isolation**: Ensure cache keys prevent cross-user access
3. **Sanitize cache keys**: Prevent injection attacks
4. **Monitor cache access**: Log unusual patterns

## Configuration Examples

### Development Environment

```yaml
cache:
  backend: memory
  default_ttl: 300      # 5 minutes - fast development cycle
  max_size: 100         # Small cache for testing
  enabled: true
```

### Production Environment

```yaml
services:
  valkey:
    type: cache
    config:
      url: "${VALKEY_CACHE_URL:valkey://valkey-cache:6379}"
      db: 1                    # Separate from state storage
      max_connections: 20

cache:
  backend: valkey
  default_ttl: 3600           # 1 hour default
  key_prefix: "${CACHE_PREFIX:agentup:cache:}"
  enabled: true
```

### High-Performance Setup

```yaml
services:
  valkey:
    type: cache
    config:
      url: "valkey://valkey-cluster:6379"
      db: 0
      max_connections: 50
      socket_keepalive: true
      retry_on_timeout: true

cache:
  backend: valkey
  default_ttl: 1800
  key_prefix: "agentup:cache:"
  enabled: true
  
  # Cache-specific optimizations
  compression: true           # Compress large values
  serialization: "pickle"     # Fast serialization
  pipeline_size: 100         # Batch Valkey operations
```

## Configuration Validation

### Manual Validation Script

```python
import yaml
import valkey

def validate_cache_config():
    """Validate cache configuration."""
    
    # Load config
    with open('agent_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    cache_cfg = config.get('cache', {})
    
    if not cache_cfg:
        print("❌ No cache configuration found")
        return False
    
    backend = cache_cfg.get('backend')
    print(f"✅ Cache backend: {backend}")
    
    if backend == 'valkey':
        # Check Valkey service config
        valkey_cfg = config.get('services', {}).get('valkey', {}).get('config', {})
        url = valkey_cfg.get('url', 'valkey://localhost:6379')
        
        try:
            # Test Valkey connection
            client = valkey.from_url(url)
            client.ping()
            print(f"✅ Valkey connection successful: {url}")
            
            # Test basic operations
            test_key = "agentup:cache:config_test"
            client.set(test_key, "test_value", ex=60)
            value = client.get(test_key)
            
            if value == b"test_value":
                print("✅ Cache operations working")
                client.delete(test_key)
                return True
            else:
                print("❌ Cache operations failed")
                return False
                
        except Exception as e:
            print(f"❌ Valkey connection failed: {e}")
            return False
    
    elif backend == 'memory':
        print("✅ Memory cache configured")
        return True
    
    elif backend == 'file':
        storage_dir = cache_cfg.get('storage_dir', './cache')
        print(f"✅ File cache configured: {storage_dir}")
        return True
    
    return False

if __name__ == "__main__":
    validate_cache_config()
```

## Configuration Issues and Solutions

### Issue 1: Cache Not Working

**Problem**: Cache operations fail silently

**Solution**: Check configuration and connections

```yaml
# Ensure cache is enabled
cache:
  enabled: true              # This must be true
  backend: valkey

# Verify Valkey service configuration
services:
  valkey:
    type: cache
    config:
      url: "valkey://localhost:6379"  # Verify URL is correct
```

### Issue 2: Valkey Connection Failed

**Problem**: Cannot connect to Valkey server

**Solution**: Verify Valkey configuration and server status

```bash
# Test Valkey connection manually
valkey-cli -h localhost -p 6379 ping

# Check Valkey server status
valkey-cli -h localhost -p 6379 info server
```

```yaml
# Update configuration with correct settings
services:
  valkey:
    type: cache
    config:
      url: "valkey://localhost:6379"
      db: 1                   # Use correct database
      socket_timeout: 10      # Increase timeout
```

### Issue 3: Cache and State Conflicts

**Problem**: Cache and state interfering with each other

**Solution**: Use separate Valkey databases or key prefixes

```yaml
services:
  valkey:
    type: cache
    config:
      url: "valkey://localhost:6379"
      db: 1                   # Cache uses DB 1

state:
  backend: valkey
  url: "valkey://localhost:6379"
  key_prefix: "agentup:state:"  # State uses DB 0 with prefix

cache:
  backend: valkey
  key_prefix: "agentup:cache:"  # Different prefix
```

### Issue 4: Poor Cache Performance

**Problem**: Cache operations are slow

**Solution**: Optimize Valkey configuration

```yaml
services:
  valkey:
    type: cache
    config:
      url: "valkey://localhost:6379"
      max_connections: 20     # Increase connection pool
      socket_keepalive: true  # Keep connections alive
      socket_timeout: 5       # Reduce timeout
```

## Troubleshooting

### Common Issues

1. **Cache Not Working**
   - Check `cache.enabled: true` in configuration
   - Verify Valkey connection settings
   - Ensure cache backend is properly configured

2. **Poor Hit Rates**
   - Review cache key patterns for consistency
   - Check TTL values aren't too short
   - Analyze cache usage patterns

3. **Memory Issues**
   - Set appropriate TTL values
   - Monitor cache size growth
   - Implement cache cleanup routines

4. **Performance Problems**
   - Check Valkey connection settings
   - Consider connection pooling
   - Monitor network latency to Valkey

### Debugging Commands

```bash
# Check Valkey cache data
valkey-cli -h localhost -p 6379
> SELECT 1                    # Switch to cache database
> KEYS agentup:cache:*        # list cache keys
> GET agentup:cache:some_key  # Examine cache value
> TTL agentup:cache:some_key  # Check remaining TTL

# Monitor Valkey operations
valkey-cli -h localhost -p 6379 MONITOR
```

## Migration Between Backends

### From Memory to Valkey

```yaml
# Update configuration
cache:
  backend: valkey      # Changed from memory
  default_ttl: 3600

services:
  valkey:              # Add Valkey service
    type: cache
    config:
      url: "valkey://localhost:6379"
```

### Cache Invalidation Strategies

```python
async def invalidate_user_cache(user_id: str):
    """Invalidate all cached data for a user."""
    cache = services.get_cache()
    
    # Pattern-based deletion (if supported)
    if hasattr(cache, 'delete_pattern'):
        await cache.delete_pattern(f"user:{user_id}:*")
    else:
        # Manual cleanup
        keys_to_delete = [
            f"user:{user_id}:preferences",
            f"user:{user_id}:history",
            f"user:{user_id}:settings"
        ]
        await cache.delete_many(keys_to_delete)
```

## Next Steps

1. **Configure caching** in your `agent_config.yaml`
2. **Apply @cached decorator** to expensive operations
3. **Monitor cache hit rates** to validate effectiveness
4. **Implement cache warming** for frequently accessed data
5. **Set up monitoring** for cache performance and health