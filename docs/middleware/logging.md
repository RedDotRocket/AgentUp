# Logging Configuration Guide

AgentUp provides a structured logging system built on top of `structlog` that supports console output in multiple formats, with advanced features like correlation IDs and request tracing.

## Quick Start

Add logging configuration to your `agent_config.yaml`:

```yaml
# Basic logging configuration
logging:
  enabled: true
  level: "INFO"
  format: "text"  # Use "json" for production

  console:
    enabled: true
    colors: true

  correlation_id: true
  request_logging: true
```

## Configuration Options

### Basic Settings

- **`enabled`**: Enable/disable logging (default: `true`)
- **`level`**: Log level - `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (default: `INFO`)
- **`format`**: Output format - `text` or `json` (default: `text`)

### Console Output

```yaml
logging:
  console:
    enabled: true        # Enable console output
    colors: true         # Use colors (auto-disabled in production)
    show_path: false     # Show file paths in log messages
```


### Advanced Features

```yaml
logging:
  correlation_id: true        # Add correlation IDs to requests
  request_logging: true       # Log HTTP requests/responses

  # Module-specific log levels
  modules:
    uvicorn: "INFO"
    httpx: "WARNING"
    my_plugin: "DEBUG"

  # Uvicorn integration
  uvicorn:
    access_log: true
    disable_default_handlers: true
    use_colors: true
```

### Module-Specific Logging

You can set specific log levels for different modules:

```yaml
logging:
  modules:
    "a2a": "ERROR"                  # Suppress all a2a logs below ERROR level
    "a2a.utils": "ERROR"            # Specifically suppress a2a.utils logs
    "a2a.utils.telemetry": "ERROR"  # Specifically suppress telemetry logs
    "a2a.utils.telemetry": "CRITICAL" # Only critical errors from telemetry
    "uvicorn": "INFO"               # Uvicorn logs at INFO level
```


!!! note
    Module names should match the Python import paths, e.g., `a2a.utils.telemetry` you see in the logs:
    `2025-08-02T06:57:13.034656Z [DEBUG    ] Trace all class None, None [a2a.utils.telemetry]`

## Using Structured Logging in Code

### In Agent Handlers

```python
import structlog

# Get a structured logger (configured automatically by AgentUp)
logger = structlog.get_logger(__name__)

async def my_handler(task, context=None, context_id=None):
    logger.info("Processing task",
                skill="my_handler",
                task_id=task.id,
                user_id=context_id)

    try:
        result = await process_task(task)

        logger.info("Task completed successfully",
                   skill="my_handler",
                   task_id=task.id,
                   result_length=len(result))

        return result

    except Exception as e:
        logger.error("Task processing failed",
                    skill="my_handler",
                    task_id=task.id,
                    error=str(e),
                    error_type=type(e).__name__)
        raise
```

### In Plugins

```python
import structlog

logger = structlog.get_logger(__name__)

class MyPlugin:
    def execute_skill(self, context):
        logger.info("Plugin processing request",
                   plugin="my_plugin",
                   skill=context.skill_id,
                   correlation_id=context.correlation_id)

        # Your plugin logic here

        return SkillResult(content="Success", success=True)
```

### Context Variables

AgentUp automatically adds correlation IDs to log context for request tracing:

```python
import structlog
from structlog.contextvars import bind_contextvars

# Bind additional context
bind_contextvars(user_id="user123", session_id="session456")

logger = structlog.get_logger(__name__)
logger.info("Processing with context")  # Includes user_id and session_id
```

## Template Examples

### Development Configuration

```yaml
logging:
  enabled: true
  level: "DEBUG"
  format: "text"

  console:
    enabled: true
    colors: true
    show_path: true

  # File logging options available in configuration model

  correlation_id: true
  request_logging: true

  modules:
    uvicorn: "INFO"
    httpx: "WARNING"
```

### Production Configuration

```yaml
logging:
  enabled: true
  level: "INFO"
  format: "json"  # Structured JSON for log aggregation

  console:
    enabled: true
    colors: false  # Disable colors in production
    show_path: true

  # Currently console-only - file logging planned for future release

  correlation_id: true
  request_logging: true

  modules:
    uvicorn: "INFO"
    httpx: "WARNING"
    plugins: "INFO"

  uvicorn:
    access_log: true
    disable_default_handlers: true
    use_colors: false
```

## Log Output Examples

### Text Format (Development)

```
2024-01-15T10:30:45.123456Z [info     ] Request started [agent.api.request_logging] correlation_id=abc12345 method=POST path=/api/message
2024-01-15T10:30:45.124000Z [info     ] Processing task [agent.handlers.ai_assistant] correlation_id=abc12345 skill=ai_assistant task_id=task_001
2024-01-15T10:30:45.456789Z [info     ] Task completed [agent.handlers.ai_assistant] correlation_id=abc12345 duration=0.332 result_length=156
2024-01-15T10:30:45.457000Z [info     ] Request completed [agent.api.request_logging] correlation_id=abc12345 status_code=200 duration=0.334
```

### JSON Format (Production)

```json
{"timestamp": "2024-01-15T10:30:45.123456Z", "level": "info", "logger": "agent.api.request_logging", "message": "Request started", "correlation_id": "abc12345", "method": "POST", "path": "/api/message"}
{"timestamp": "2024-01-15T10:30:45.124000Z", "level": "info", "logger": "agent.handlers.ai_assistant", "message": "Processing task", "correlation_id": "abc12345", "skill": "ai_assistant", "task_id": "task_001"}
{"timestamp": "2024-01-15T10:30:45.456789Z", "level": "info", "logger": "agent.handlers.ai_assistant", "message": "Task completed", "correlation_id": "abc12345", "duration": 0.332, "result_length": 156}
{"timestamp": "2024-01-15T10:30:45.457000Z", "level": "info", "logger": "agent.api.request_logging", "message": "Request completed", "correlation_id": "abc12345", "status_code": 200, "duration": 0.334}
```

## Integration with Monitoring

### Log Aggregation

For production deployments, JSON format logs can be easily ingested by:

- **Elasticsearch + Kibana**
- **Fluentd/Fluent Bit**
- **Grafana Loki**
- **AWS CloudWatch**
- **GCP Cloud Logging**

### Correlation IDs

Correlation IDs enable distributed tracing across:
- HTTP requests
- Plugin executions
- External API calls
- Database operations

### Metrics and Alerting

Use structured fields for monitoring:
- Request duration
- Error rates
- Plugin performance
- Resource usage

## Environment Variables

AgentUp's logging system respects standard structlog environment variables:

- **`FORCE_COLOR=1`** - Force color output even in non-TTY environments
- **`NO_COLOR=1`** - Disable all color output completely
- **`PYTHONUNBUFFERED=1`** - Recommended for real-time log output

## Best Practices

1. **Use JSON format in production** for log aggregation
2. **Enable correlation IDs** for request tracing
3. **Set appropriate log levels** to avoid noise
4. **Use structured fields** instead of string interpolation
5. **Include context** (user_id, session_id, etc.)
6. **Log at boundaries** (requests, plugin calls, external APIs)
7. **Don't log sensitive data** (passwords, tokens, PII)
8. **Use environment variables** for deployment-specific settings

## Troubleshooting

### Common Issues

**Logs not appearing**:
- Check `logging.enabled: true` in config
- Verify log level settings
- Ensure console output is enabled

**Performance impact**:
- Use appropriate log levels
- Avoid debug logging in production
- Consider async logging for high-throughput

**Missing correlation IDs**:
- Ensure `correlation_id: true` in config
- Check middleware is properly configured

**Uvicorn logs not structured**:
- Verify `uvicorn.disable_default_handlers: true`
- Check logging configuration is loaded before uvicorn starts

**Multiple "Logging configured" messages**:
- This is normal during development/testing when modules are reloaded
- In production, you should see only one initialization message
- AgentUp prevents multiple configurations in the same process