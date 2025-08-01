# Plugin Logging Guide

This guide explains how to use AgentUp's integrated logging system in your plugins. AgentUp provides structured logging with automatic plugin context annotation, making it easy to debug and monitor plugin behavior in production.

## Overview

AgentUp uses [structlog](https://www.structlog.org/) for structured logging, which provides:

- **Automatic plugin identification**: All plugin logs are automatically tagged with plugin metadata
- **Structured data**: Log entries can include key-value pairs for better searchability
- **Multiple output formats**: Text for development, JSON for production
- **Integration with server logs**: Plugin logs appear seamlessly in AgentUp server logs

## Quick Start

Every plugin automatically gets a pre-configured logger accessible via `self.logger`:

```python
from agent.plugins.base import Plugin
from agent.plugins.decorators import capability
from agent.plugins.models import CapabilityContext, CapabilityResult

class WeatherPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.name = "Weather Plugin"
        self.version = "1.0.0"
    
    @capability(id="get_weather", name="Get Weather")
    async def get_weather(self, context: CapabilityContext) -> CapabilityResult:
        # Plugin logs automatically include plugin context
        self.logger.info("Weather request started", location="New York")
        
        try:
            # Your plugin logic here
            result = await self._fetch_weather("New York")
            
            self.logger.info("Weather request completed", 
                           location="New York", 
                           temperature=result.temperature,
                           condition=result.condition)
            
            return CapabilityResult(
                content=f"Weather in New York: {result.temperature}°F, {result.condition}",
                success=True
            )
            
        except Exception as e:
            self.logger.error("Weather request failed", 
                            location="New York", 
                            error=str(e), 
                            exc_info=True)
            
            return CapabilityResult(
                content="Failed to fetch weather data",
                success=False,
                error=str(e)
            )
```

## Log Levels

AgentUp supports standard Python logging levels:

```python
# Debug: Detailed information for diagnosing problems
self.logger.debug("Processing user input", input_length=len(user_input))

# Info: General information about plugin operation
self.logger.info("API call successful", endpoint="/weather", status_code=200)

# Warning: Something unexpected happened but plugin continues
self.logger.warning("Rate limit approaching", requests_remaining=5)

# Error: Plugin encountered an error
self.logger.error("API request failed", endpoint="/weather", error="timeout")

# Critical: Serious error that may cause plugin to stop working
self.logger.critical("Configuration invalid", config_file="weather.yml")
```

## Structured Logging

The power of structlog comes from structured data. Instead of string formatting, use key-value pairs:

```python
# ❌ Don't do this - hard to search and parse
self.logger.info(f"Processing request for user {user_id} with {len(items)} items")

# ✅ Do this - structured and searchable
self.logger.info("Processing request", 
                user_id=user_id, 
                item_count=len(items),
                processing_mode="batch")
```

## Automatic Plugin Context

Every log entry from your plugin automatically includes:

- `plugin_id`: Your plugin's unique identifier
- `plugin_name`: Human-readable plugin name
- `plugin_version`: Plugin version (if specified)
- `logger`: Logger name (e.g., `agent.plugins.weather`)

Example log output:
```json
{
  "timestamp": "2025-08-01T10:30:45.123Z",
  "level": "INFO",
  "logger": "agent.plugins.weather",
  "event": "Weather request completed",
  "plugin_id": "weather",
  "plugin_name": "Weather Plugin",
  "plugin_version": "1.0.0",
  "location": "New York",
  "temperature": 72,
  "condition": "sunny"
}
```

## Error Logging

When logging errors, include the `exc_info=True` parameter to capture full stack traces:

```python
try:
    result = await self._risky_operation()
except ValueError as e:
    self.logger.error("Invalid input provided", 
                     input_value=user_input,
                     error=str(e),
                     exc_info=True)  # Captures full stack trace
except Exception as e:
    self.logger.critical("Unexpected error in plugin", 
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True)
```

## Performance Logging

Log performance metrics to help with optimization:

```python
import time

async def expensive_operation(self, data):
    start_time = time.time()
    
    self.logger.debug("Starting expensive operation", 
                     data_size=len(data),
                     operation="data_processing")
    
    try:
        result = await self._process_data(data)
        
        duration = time.time() - start_time
        self.logger.info("Operation completed", 
                        operation="data_processing",
                        duration_seconds=round(duration, 3),
                        data_size=len(data),
                        result_size=len(result))
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        self.logger.error("Operation failed", 
                         operation="data_processing",
                         duration_seconds=round(duration, 3),
                         error=str(e),
                         exc_info=True)
        raise
```

## Configuration and External Service Logging

Log configuration changes and external API calls:

```python
def configure(self, config: dict[str, Any]) -> None:
    """Configure the plugin with settings."""
    super().configure(config)
    
    self.logger.info("Plugin configured", 
                    api_endpoint=config.get("api_endpoint"),
                    timeout=config.get("timeout", 30),
                    retry_count=config.get("retries", 3))

async def _call_external_api(self, endpoint: str, params: dict):
    self.logger.debug("Calling external API", 
                     endpoint=endpoint,
                     params=params)
    
    try:
        response = await self.http_client.get(endpoint, params=params)
        
        self.logger.info("API call successful", 
                        endpoint=endpoint,
                        status_code=response.status_code,
                        response_size=len(response.text))
        
        return response.json()
        
    except Exception as e:
        self.logger.error("API call failed", 
                         endpoint=endpoint,
                         error=str(e),
                         exc_info=True)
        raise
```

## Security Considerations

Be careful not to log sensitive information:

```python
# ❌ Don't log sensitive data
self.logger.info("User authenticated", 
                password=user_password,  # Never log passwords!
                api_key=api_key)         # Never log API keys!

# ✅ Log safely
self.logger.info("User authenticated", 
                user_id=user_id,
                auth_method="api_key",
                api_key_prefix=api_key[:8] + "...",  # Only log prefix
                timestamp=datetime.now().isoformat())
```

## Development vs Production

AgentUp automatically configures logging based on the environment:

- **Development**: Text format with colors for easy reading
- **Production**: JSON format for structured log aggregation

You don't need to change your logging code - just use structured logging and AgentUp handles the formatting.

## Filtering and Searching Logs

In production, you can filter logs by plugin:

```bash
# Filter by plugin ID
grep '"plugin_id":"weather"' agentup.log

# Filter by plugin and log level
grep '"plugin_id":"weather"' agentup.log | grep '"level":"ERROR"'

# Using jq for JSON logs
cat agentup.log | jq 'select(.plugin_id == "weather" and .level == "ERROR")'
```

## Best Practices

### 1. Use Descriptive Event Names
```python
# ❌ Vague
self.logger.info("Done")

# ✅ Descriptive
self.logger.info("Weather data processing completed")
```

### 2. Include Relevant Context
```python
# ❌ Missing context
self.logger.error("Request failed")

# ✅ Rich context
self.logger.error("Weather API request failed", 
                 endpoint="api.weather.com",
                 status_code=429,
                 retry_attempt=3,
                 user_location="New York")
```

### 3. Use Consistent Field Names
```python
# Use consistent naming across your plugin
self.logger.info("Request started", request_id=req_id, user_id=user_id)
self.logger.info("Request completed", request_id=req_id, user_id=user_id, duration=0.5)
```

### 4. Log State Changes
```python
self.logger.info("Plugin state changed", 
                previous_state="idle",
                new_state="processing",
                trigger="user_request")
```

### 5. Don't Over-Log
```python
# ❌ Too verbose - will spam logs
for item in items:
    self.logger.debug("Processing item", item=item)

# ✅ Aggregate logging
self.logger.info("Processing batch", 
                batch_size=len(items),
                batch_id=batch_id)
```

## Troubleshooting

### Logger Not Available
If `self.logger` is not available, ensure you're calling `super().__init__()` in your plugin's `__init__` method:

```python
class MyPlugin(Plugin):
    def __init__(self):
        super().__init__()  # This creates self.logger
        # Your initialization code here
```

### Logs Not Appearing
1. Check that AgentUp logging is properly configured
2. Verify your log level - DEBUG messages won't appear if log level is INFO
3. Ensure your plugin is properly registered with AgentUp

### Missing Plugin Context
If logs don't show plugin information, verify:
1. You're using `self.logger` (not `print` or standard logging)
2. Your plugin inherits from the `Plugin` base class
3. You're calling `super().__init__()` in your plugin's constructor

## Advanced Usage

### Custom Logger Creation
If you need additional loggers for specific components:

```python
from agent.config.logging import get_plugin_logger

class MyPlugin(Plugin):
    def __init__(self):
        super().__init__()
        # Additional logger for database operations
        self.db_logger = get_plugin_logger(
            plugin_id=f"{self.plugin_id}.database",
            plugin_name=f"{self.name} - Database",
            plugin_version=self.version
        )
    
    async def _database_operation(self):
        self.db_logger.info("Database query started", table="users", operation="select")
```

### Correlation IDs
AgentUp automatically includes correlation IDs for request tracking. Your plugin logs will include these automatically when processing requests.

## Related Documentation

- [Plugin Development Guide](development.md)
- [Testing Plugins](testing.md)
- [Security and Scopes](scopes-and-security.md)
- [AgentUp Configuration](../configuration.md)