# Plugin Development Guide

This comprehensive guide covers everything you need to know about developing sophisticated AgentUp plugins, from basic concepts to advanced features like state management, external APIs, and custom middleware.

## Plugin Architecture Deep Dive

### Understanding the Hook System

AgentUp plugins use the pluggy library's hook system. Each hook represents a specific point where your plugin can extend the agent's behavior:

```python
import pluggy
from agent.plugins import SkillInfo, SkillContext, SkillResult

hookimpl = pluggy.HookimplMarker("agentup")

class MyPlugin:
    @hookimpl
    def register_skill(self) -> SkillInfo:
        """Called during plugin discovery to register your skill."""
        pass

    @hookimpl
    def can_handle_task(self, context: SkillContext) -> bool | float:
        """Called to determine if your plugin can handle a task."""
        pass

    @hookimpl
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """Called to execute your skill logic."""
        pass
```

The use of pluggy brings a lot of highly useful benefits. With pluggy's hook system,
AgentUp plugins are effectivly Python packages that can be easily installed, and
managed with tools such as `pip` and `uv` or `poetry`.

You can then do such things, as build your Agent with AgentUp and add your plugins
to the `requirements.txt` or `pyproject.toml` file, and they will be automatically
installed when you deploy your agent. 

This of course also makes it very easy for plugin developers to publish their plugins
to PyPI or other package repositories, allowing users to easily install and keep
them up to date using standard approaches such as dependabot etc.

### Core Hook Specifications

| Hook | Purpose | Return Type | Required |
|------|---------|-------------|----------|
| `register_skill` | Provide plugin metadata | `SkillInfo` | ✅ Yes |
| `can_handle_task` | Routing decision | `bool` or `float` | ✅ Yes |
| `execute_skill` | Main skill logic | `SkillResult` | ✅ Yes |
| `validate_config` | Config validation | `ValidationResult` | ❌ No |
| `get_ai_functions` | AI function definitions | `list[AIFunction]` | ❌ No |
| `configure_services` | Service injection | `None` | ❌ No |
| `get_middleware_config` | Middleware requests | `list[dict]` | ❌ No |
| `get_state_schema` | State schema definition | `dict` | ❌ No |

## Building a Weather Plugin

Let's build a comprehensive weather plugin that demonstrates all major features:

### Step 1: Project Setup

```bash
agentup plugin create weather-skill --template advanced
cd weather-skill
```

### Step 2: Configuration Schema

First, define what configuration your plugin needs:

```python
@hookimpl
def register_skill(self) -> SkillInfo:
    """Register the weather skill."""
    return SkillInfo(
        id="weather",
        name="Weather Information",
        version="1.0.0",
        description="Provides current weather and forecasts",
        capabilities=[SkillCapability.TEXT, SkillCapability.AI_FUNCTION, SkillCapability.STATEFUL],
        tags=["weather", "api", "forecast"],
        system_prompt="""You are a weather information assistant with access to current weather data and forecasts.

Your role:
- Provide accurate, current weather information for any location
- Explain weather patterns and conditions in clear, understandable terms
- Offer helpful recommendations based on weather conditions
- Use appropriate units (metric/imperial) based on user preference or location

When providing weather information:
1. Always include current temperature, conditions, and "feels like" temperature
2. Mention any significant weather warnings or alerts
3. Provide context about unusual weather patterns
4. Suggest appropriate clothing or activities based on conditions
5. Include humidity, wind speed, and visibility when relevant

Be helpful, accurate, and conversational in your responses.""",
        config_schema={
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "description": "OpenWeatherMap API key",
                },
                "default_units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "default": "imperial",
                    "description": "Default temperature units",
                },
                "cache_duration": {
                    "type": "integer",
                    "default": 600,
                    "description": "Cache weather data for this many seconds",
                },
                "include_forecast": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include 5-day forecast in responses",
                }
            },
            "required": ["api_key"],
        }
    )
```

### Step 3: Configuration Validation

Implement robust configuration validation:

```python
@hookimpl
def validate_config(self, config: dict) -> ValidationResult:
    """Validate weather plugin configuration."""
    errors = []
    warnings = []
    suggestions = []

    # Check required API key
    api_key = config.get("api_key")
    if not api_key:
        errors.append("api_key is required")
    elif len(api_key) != 32:
        warnings.append("API key should be 32 characters long")

    # Validate units
    units = config.get("default_units", "imperial")
    if units not in ["metric", "imperial", "kelvin"]:
        errors.append(f"Invalid units: {units}")

    # Check cache duration
    cache_duration = config.get("cache_duration", 600)
    if not isinstance(cache_duration, int) or cache_duration < 0:
        errors.append("cache_duration must be a non-negative integer")
    elif cache_duration < 60:
        warnings.append("Very short cache duration may cause rate limiting")
    elif cache_duration > 3600:
        suggestions.append("Consider shorter cache duration for more current data")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
    )
```

### Step 4: Service Injection

Use AgentUp's service registry for HTTP clients, caches, etc:

```python
def __init__(self):
    """Initialize the weather plugin."""
    self.name = "weather-skill"
    self.api_key = None
    self.http_client = None
    self.cache = None
    self.config = {}

@hookimpl
def configure_services(self, services: dict) -> None:
    """Configure services for the weather plugin."""
    # Get HTTP client for API calls
    self.http_client = services.get("http_client")
    if not self.http_client:
        import httpx
        self.http_client = httpx.AsyncClient()

    # Get cache service if available
    self.cache = services.get("cache")

    # Store other services
    self.services = services
```

### Step 5: Smart Routing

Implement intelligent task routing:

```python
@hookimpl
def can_handle_task(self, context: SkillContext) -> float:
    """Determine if this is a weather-related request."""
    user_input = self._extract_user_input(context).lower()

    # High confidence keywords
    weather_keywords = {
        'weather': 1.0,
        'temperature': 1.0,
        'forecast': 1.0,
        'rain': 0.9,
        'snow': 0.9,
        'sunny': 0.8,
        'cloudy': 0.8,
        'hot': 0.7,
        'cold': 0.7,
        'humid': 0.8,
        'wind': 0.8,
    }

    # Location keywords (boost confidence)
    location_keywords = ['in', 'at', 'for', 'near']

    # Question patterns
    weather_patterns = [
        r"what'?s? (?:the )?weather",
        r"how'?s? (?:the )?weather",
        r"weather (?:in|at|for)",
        r"(?:will it|is it going to) (?:rain|snow)",
        r"temperature (?:in|at|for)",
        r"(?:hot|cold|warm) (?:today|tomorrow)",
    ]

    confidence = 0.0

    # Check keyword matches
    for keyword, score in weather_keywords.items():
        if keyword in user_input:
            confidence = max(confidence, score)

    # Boost for location context
    if confidence > 0 and any(loc in user_input for loc in location_keywords):
        confidence = min(confidence + 0.2, 1.0)

    # Check patterns
    import re
    for pattern in weather_patterns:
        if re.search(pattern, user_input):
            confidence = 1.0
            break

    return confidence
```

### Step 6: Core Execution Logic

Implement the main skill functionality:

```python
@hookimpl
def execute_skill(self, context: SkillContext) -> SkillResult:
    """Execute weather skill logic."""
    try:
        # Extract location and query details
        user_input = self._extract_user_input(context)
        location = self._extract_location(user_input)
        query_type = self._determine_query_type(user_input)

        # Get configuration
        self.config = context.config
        self.api_key = self.config.get("api_key")
        units = self.config.get("default_units", "imperial")

        if not self.api_key:
            return SkillResult(
                content="Weather service is not configured. Please set an API key.",
                success=False,
                error="Missing API key",
            )

        # Get weather data
        if query_type == "current":
            weather_data = await self._get_current_weather(location, units)
            response = self._format_current_weather(weather_data, location)
        elif query_type == "forecast":
            forecast_data = await self._get_weather_forecast(location, units)
            response = self._format_forecast(forecast_data, location)
        else:
            # Default to current + short forecast
            weather_data = await self._get_current_weather(location, units)
            forecast_data = await self._get_weather_forecast(location, units, days=2)
            response = self._format_weather_summary(weather_data, forecast_data, location)

        # Update state with recent query
        state_updates = {
            "last_location": location,
            "last_query_time": datetime.datetime.now().isoformat(),
            "query_count": context.state.get("query_count", 0) + 1,
        }

        return SkillResult(
            content=response,
            success=True,
            metadata={
                "skill": "weather",
                "location": location,
                "query_type": query_type,
                "units": units,
            },
            state_updates=state_updates,
        )

    except Exception as e:
        logger.error(f"Weather skill error: {e}", exc_info=True)
        return SkillResult(
            content=f"Sorry, I couldn't get weather information: {str(e)}",
            success=False,
            error=str(e),
        )

async def _get_current_weather(self, location: str, units: str) -> dict:
    """Get current weather data from API."""
    # Check cache first
    cache_key = f"weather:current:{location}:{units}"
    if self.cache:
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data

    # API call
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": self.api_key,
        "units": units,
    }

    response = await self.http_client.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    # Cache the result
    if self.cache:
        cache_duration = self.config.get("cache_duration", 600)
        await self.cache.set(cache_key, data, ttl=cache_duration)

    return data

def _format_current_weather(self, data: dict, location: str) -> str:
    """Format current weather data into a readable response."""
    try:
        main = data["main"]
        weather = data["weather"][0]
        wind = data.get("wind", {})

        temp = main["temp"]
        feels_like = main["feels_like"]
        humidity = main["humidity"]
        description = weather["description"].title()

        # Determine unit symbol
        unit_symbol = "°F" if self.config.get("default_units") == "imperial" else "°C"

        response = f"🌤️ **Weather in {location}**\n\n"
        response += f"**Current:** {temp:.1f}{unit_symbol} ({description})\n"
        response += f"**Feels like:** {feels_like:.1f}{unit_symbol}\n"
        response += f"**Humidity:** {humidity}%\n"

        if wind.get("speed"):
            wind_speed = wind["speed"]
            wind_unit = "mph" if self.config.get("default_units") == "imperial" else "m/s"
            response += f"**Wind:** {wind_speed:.1f} {wind_unit}"

            if wind.get("deg"):
                direction = self._wind_direction(wind["deg"])
                response += f" {direction}"

        return response

    except KeyError as e:
        return f"Error formatting weather data: missing field {e}"

def _wind_direction(self, degrees: float) -> str:
    """Convert wind degrees to compass direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(degrees / 22.5) % 16
    return directions[index]
```

### Step 7: AI Function Integration

Make your plugin available to LLMs:

```python
@hookimpl
def get_ai_functions(self) -> list[AIFunction]:
    """Provide AI functions for LLM function calling."""
    return [
        AIFunction(
            name="get_weather",
            description="Get current weather information for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, state, or country (e.g., 'New York, NY')",
                    },
                    "units": {
                        "type": "string",
                        "enum": ["metric", "imperial", "kelvin"],
                        "description": "Temperature units",
                        "default": "imperial",
                    },
                },
                "required": ["location"],
            },
            handler=self._get_weather_function,
        ),

        AIFunction(
            name="get_weather_forecast",
            description="Get weather forecast for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, state, or country",
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Number of forecast days",
                        "default": 3,
                    },
                    "units": {
                        "type": "string",
                        "enum": ["metric", "imperial", "kelvin"],
                        "default": "imperial",
                    },
                },
                "required": ["location"],
            },
            handler=self._get_forecast_function,
        ),
    ]

async def _get_weather_function(self, task, context: SkillContext) -> SkillResult:
    """Handle the get_weather AI function."""
    params = context.metadata.get("parameters", {})
    location = params.get("location")
    units = params.get("units", self.config.get("default_units", "imperial"))

    if not location:
        return SkillResult(
            content="Please specify a location for weather information.",
            success=False,
            error="Missing location parameter",
        )

    try:
        weather_data = await self._get_current_weather(location, units)
        response = self._format_current_weather(weather_data, location)

        return SkillResult(
            content=response,
            success=True,
            metadata={"function": "get_weather", "location": location},
        )

    except Exception as e:
        return SkillResult(
            content=f"Error getting weather for {location}: {str(e)}",
            success=False,
            error=str(e),
        )
```

### Step 8: State Management

For stateful plugins, define your state schema:

```python
@hookimpl
def get_state_schema(self) -> dict:
    """Define state schema for weather plugin."""
    return {
        "type": "object",
        "properties": {
            "last_location": {
                "type": "string",
                "description": "Last queried location"
            },
            "last_query_time": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp of last query"
            },
            "query_count": {
                "type": "integer",
                "description": "Total number of queries"
            },
            "favorite_locations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "User's favorite locations"
            },
            "preferred_units": {
                "type": "string",
                "enum": ["metric", "imperial", "kelvin"],
                "description": "User's preferred units"
            },
        },
    }
```

Use state in your skill logic:

```python
def execute_skill(self, context: SkillContext) -> SkillResult:
    # Access previous state
    state = context.state
    last_location = state.get("last_location")
    query_count = state.get("query_count", 0)

    # If no location specified, use last location
    location = self._extract_location(user_input) or last_location

    # ... weather logic ...

    # Update state
    state_updates = {
        "last_location": location,
        "last_query_time": datetime.datetime.now().isoformat(),
        "query_count": query_count + 1,
    }

    return SkillResult(
        content=response,
        success=True,
        state_updates=state_updates,
    )
```

### Step 9: Middleware Configuration

Request middleware for your plugin:

```python
@hookimpl
def get_middleware_config(self) -> list[dict]:
    """Request middleware for weather plugin."""
    return [
        {
            "type": "rate_limit",
            "requests_per_minute": 30,  # API rate limits
        },
        {
            "type": "cache",
            "ttl": 600,  # Cache responses for 10 minutes
        },
        {
            "type": "retry",
            "max_retries": 3,
            "backoff_factor": 2,
        },
        {
            "type": "logging",
            "level": "INFO",
            "include_params": True,
        },
    ]
```

### Step 10: Health Monitoring

Implement health status reporting:

```python
@hookimpl
def get_health_status(self) -> dict:
    """Report health status of weather plugin."""
    status = {
        "status": "healthy",
        "version": "1.0.0",
        "api_configured": bool(self.api_key),
        "cache_available": self.cache is not None,
        "http_client_available": self.http_client is not None,
    }

    # Test API connectivity
    try:
        # Quick API test (cached)
        if self.api_key:
            # This would be a lightweight API call
            status["api_accessible"] = True
    except Exception:
        status["api_accessible"] = False
        status["status"] = "degraded"

    return status
```

## Advanced Features

### Custom Error Handling

```python
class WeatherAPIError(Exception):
    """Custom exception for weather API errors."""
    pass

class LocationNotFoundError(WeatherAPIError):
    """Raised when location cannot be found."""
    pass

def _handle_api_error(self, response) -> None:
    """Handle API error responses."""
    if response.status_code == 404:
        raise LocationNotFoundError("Location not found")
    elif response.status_code == 401:
        raise WeatherAPIError("Invalid API key")
    elif response.status_code == 429:
        raise WeatherAPIError("API rate limit exceeded")
    else:
        response.raise_for_status()
```

### Location Parsing

```python
import re

def _extract_location(self, text: str) -> str:
    """Extract location from user input."""
    # Common location patterns
    patterns = [
        r"(?:in|at|for|near)\s+([A-Za-z\s,]+?)(?:\s|$|[.!?])",
        r"weather\s+([A-Za-z\s,]+?)(?:\s|$|[.!?])",
        r"^([A-Za-z\s,]+?)\s+weather",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up common words
            location = re.sub(r'\b(the|weather|today|tomorrow)\b', '', location, flags=re.IGNORECASE)
            return location.strip()

    # Default fallback
    return "Current Location"
```

### Caching Strategy

```python
def _get_cache_key(self, location: str, data_type: str, units: str) -> str:
    """Generate consistent cache keys."""
    location_key = location.lower().replace(" ", "_")
    return f"weather:{data_type}:{location_key}:{units}"

async def _cached_api_call(self, cache_key: str, api_call_func, *args, **kwargs):
    """Generic cached API call wrapper."""
    # Check cache
    if self.cache:
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return cached_data

    # Make API call
    data = await api_call_func(*args, **kwargs)

    # Cache result
    if self.cache:
        cache_duration = self.config.get("cache_duration", 600)
        await self.cache.set(cache_key, data, ttl=cache_duration)

    return data
```

## Testing Your Plugin

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock
from weather_skill.plugin import Plugin

@pytest.fixture
def plugin():
    """Create a plugin instance for testing."""
    plugin = Plugin()
    plugin.api_key = "test_api_key"
    plugin.http_client = AsyncMock()
    plugin.config = {"default_units": "imperial", "cache_duration": 600}
    return plugin

@pytest.mark.asyncio
async def test_get_current_weather(plugin):
    """Test current weather retrieval."""
    # Mock API response
    mock_response = {
        "main": {"temp": 72.5, "feels_like": 75.0, "humidity": 65},
        "weather": [{"description": "partly cloudy"}],
        "wind": {"speed": 5.2, "deg": 180}
    }

    plugin.http_client.get.return_value.json.return_value = mock_response
    plugin.http_client.get.return_value.raise_for_status = Mock()

    result = await plugin._get_current_weather("New York", "imperial")

    assert result == mock_response
    plugin.http_client.get.assert_called_once()

def test_location_extraction(plugin):
    """Test location parsing from user input."""
    test_cases = [
        ("What's the weather in New York?", "New York"),
        ("Weather for San Francisco today", "San Francisco"),
        ("How's the weather at Chicago", "Chicago"),
        ("Tell me about London weather", "London"),
    ]

    for input_text, expected_location in test_cases:
        location = plugin._extract_location(input_text)
        assert location == expected_location
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_weather_flow(plugin):
    """Test complete weather request flow."""
    # Setup
    task = Mock()
    task.history = [Mock()]
    task.history[0].parts = [Mock()]
    task.history[0].parts[0].text = "What's the weather in Boston?"

    context = SkillContext(
        task=task,
        config={"api_key": "test_key", "default_units": "imperial"},
        state={}
    )

    # Mock API response
    plugin.http_client.get.return_value.json.return_value = {
        "main": {"temp": 68.0, "feels_like": 70.0, "humidity": 60},
        "weather": [{"description": "clear sky"}],
    }
    plugin.http_client.get.return_value.raise_for_status = Mock()

    # Execute
    result = plugin.execute_skill(context)

    # Verify
    assert result.success
    assert "Boston" in result.content
    assert "68.0°F" in result.content
    assert result.metadata["location"] == "Boston"
```

## Best Practices

### 1. Error Handling

Always provide graceful error handling:

```python
try:
    result = await self._api_call()
except LocationNotFoundError:
    return SkillResult(
        content="I couldn't find that location. Please check the spelling.",
        success=False,
        error="Location not found",
    )
except WeatherAPIError as e:
    return SkillResult(
        content=f"Weather service error: {str(e)}",
        success=False,
        error=str(e),
    )
```

### 2. Logging

Use structured logging:

```python
import logging

logger = logging.getLogger(__name__)

def execute_skill(self, context: SkillContext) -> SkillResult:
    logger.info("Processing weather request", extra={
        "user_input": self._extract_user_input(context),
        "skill": "weather",
    })

    try:
        # ... skill logic ...
        logger.info("Weather request completed successfully")
    except Exception as e:
        logger.error("Weather request failed", extra={
            "error": str(e),
            "skill": "weather",
        }, exc_info=True)
```

### 3. Configuration Management

Provide sensible defaults and validation:

```python
def _get_config_value(self, key: str, default=None, required=False):
    """Get configuration value with validation."""
    value = self.config.get(key, default)

    if required and value is None:
        raise ValueError(f"Required configuration '{key}' is missing")

    return value
```

### 4. Performance Optimization

Use async/await properly:

```python
async def execute_skill(self, context: SkillContext) -> SkillResult:
    """Execute with concurrent API calls where possible."""
    # Start multiple API calls concurrently
    current_task = asyncio.create_task(
        self._get_current_weather(location, units)
    )
    forecast_task = asyncio.create_task(
        self._get_weather_forecast(location, units)
    )

    # Wait for both to complete
    current_weather, forecast = await asyncio.gather(
        current_task, forecast_task
    )

    # Process results...
```

## Deployment and Distribution

### Package Structure

Organize your plugin for distribution:

```
weather-skill/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── weather_skill/
│       ├── __init__.py
│       ├── plugin.py
│       ├── api.py          # API client logic
│       ├── formatters.py   # Response formatting
│       └── utils.py        # Utility functions
├── tests/
│   ├── __init__.py
│   ├── test_plugin.py
│   ├── test_api.py
│   └── conftest.py
└── docs/
    ├── README.md
    ├── configuration.md
    └── examples.md
```

### Entry Points

Configure your entry point in `pyproject.toml`:

```toml
[project.entry-points."agentup.skills"]
weather = "weather_skill.plugin:Plugin"
```

### Documentation

Include comprehensive documentation:

```markdown
# Weather Skill Plugin

Provides weather information and forecasts for AgentUp agents.

## Installation

```bash
pip install weather-skill
```

## Configuration

Add to your `agent_config.yaml`:

```yaml
skills:
  - skill_id: weather
    config:
      api_key: "your-openweathermap-api-key"
      default_units: "imperial"  # or "metric"
      cache_duration: 600
```

## Features

- Current weather conditions
- 5-day weather forecast
- Multiple unit systems
- Location-aware queries
- Intelligent caching
- AI function calling support
```

This comprehensive development guide covers all aspects of building sophisticated AgentUp plugins. The weather plugin example demonstrates real-world patterns you can apply to any domain!