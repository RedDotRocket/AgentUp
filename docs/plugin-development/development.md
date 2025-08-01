# Plugin Development Guide

This comprehensive guide covers everything you need to know about developing AgentUp plugins using the new decorator-based system, from basic concepts to advanced features like trusted publishing, state management, and AI function integration.

## New Plugin Architecture Overview

### From Hooks to Decorators

AgentUp 2.0 introduces a revolutionary decorator-based plugin system that replaces the complex hook-based approach:

**Before (Hook-based):**
```python
import pluggy
from agent.plugins import CapabilityInfo, CapabilityContext, CapabilityResult

hookimpl = pluggy.HookimplMarker("agentup")

class MyPlugin:
    @hookimpl
    def register_capability(self) -> CapabilityInfo:
        """Called during plugin discovery to register your capability."""
        pass

    @hookimpl
    def can_handle_task(self, context: CapabilityContext) -> bool | float:
        """Called to determine if your plugin can handle a task."""
        pass

    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """Called to execute your capability logic."""
        pass
```

**After (Decorator-based):**
```python
from agent.plugins.base import Plugin
from agent.plugins.decorators import capability

class MyPlugin(Plugin):
    @capability(
        id="my_capability",
        name="My Capability",
        description="Does something useful",
        scopes=["my:read"],
        ai_function=True
    )
    async def my_capability(self, param: str = "default", **kwargs):
        """Execute capability logic directly."""
        return {
            "success": True,
            "content": f"Processed: {param}",
            "metadata": {"capability": "my_capability"}
        }
```

### Key Benefits of the New System

- **Simplicity**: One decorator replaces 11 different hooks
- **Type Safety**: Full typing support with IDE integration
- **Direct Method Calls**: No more complex hook chains
- **Automatic Discovery**: Capabilities auto-discovered from decorators
- **Built-in Security**: Scope-based permissions and trusted publishing
- **AI Integration**: Seamless LLM function calling support

## Building a Weather Plugin with the New System

Let's build a comprehensive weather plugin that demonstrates all major features:

### Step 1: Project Setup

```bash
agentup plugin create weather-plugin
cd weather-plugin
```

### Step 2: Plugin Structure

```python
"""
Weather Plugin for AgentUp.

Provides comprehensive weather information using the modern decorator system.
"""

import asyncio
import datetime
import re
from typing import Dict, Any, Optional
import aiohttp
import structlog

from agent.plugins.base import Plugin
from agent.plugins.decorators import capability

logger = structlog.get_logger(__name__)


class WeatherPlugin(Plugin):
    """Weather information plugin with advanced features."""

    def __init__(self):
        """Initialize the weather plugin."""
        super().__init__()
        self.name = "weather-plugin"
        self.version = "2.0.0"
        self.api_key = None
        self.http_client = None
        self.cache = None

    async def initialize(self, config: Dict[str, Any], services: Dict[str, Any]):
        """Initialize plugin with configuration and services."""
        self.config = config
        self.api_key = config.get("api_key")

        # Setup HTTP client
        if "http_client" in services:
            self.http_client = services["http_client"]
        else:
            self.http_client = aiohttp.ClientSession()

        # Setup cache if available
        self.cache = services.get("cache")

        logger.info("Weather plugin initialized", api_configured=bool(self.api_key))
```

### Step 3: Core Weather Capabilities

```python
    @capability(
        id="get_current_weather",
        name="Get Current Weather",
        description="Get current weather conditions for any location worldwide",
        scopes=["weather:read", "api:external"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, state, country (e.g., 'New York, NY' or 'London, UK')"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "description": "Temperature units",
                    "default": "imperial"
                },
                "include_details": {
                    "type": "boolean",
                    "description": "Include detailed weather information",
                    "default": True
                }
            },
            "required": ["location"]
        }
    )
    async def get_current_weather(
        self,
        location: str,
        units: str = "imperial",
        include_details: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Get current weather for a location."""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Weather API key not configured",
                    "content": "Weather service requires API key configuration"
                }

            # Check cache first
            cache_key = f"weather:current:{location.lower()}:{units}"
            if self.cache:
                cached_data = await self.cache.get(cache_key)
                if cached_data:
                    return self._format_weather_response(cached_data, location, "current")

            # Make API call
            weather_data = await self._fetch_current_weather(location, units)

            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, weather_data, ttl=600)  # 10 minutes

            return self._format_weather_response(weather_data, location, "current", include_details)

        except Exception as e:
            logger.error("Error fetching current weather", location=location, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "content": f"Sorry, I couldn't get weather information for {location}: {str(e)}"
            }

    @capability(
        id="get_weather_forecast",
        name="Get Weather Forecast",
        description="Get multi-day weather forecast for any location",
        scopes=["weather:read", "api:external"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, state, country"
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Number of forecast days (1-5)",
                    "default": 3
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "default": "imperial"
                }
            },
            "required": ["location"]
        }
    )
    async def get_weather_forecast(
        self,
        location: str,
        days: int = 3,
        units: str = "imperial",
        **kwargs
    ) -> Dict[str, Any]:
        """Get weather forecast for a location."""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Weather API key not configured",
                    "content": "Weather service requires API key configuration"
                }

            # Validate days parameter
            days = max(1, min(5, days))

            # Check cache
            cache_key = f"weather:forecast:{location.lower()}:{days}:{units}"
            if self.cache:
                cached_data = await self.cache.get(cache_key)
                if cached_data:
                    return self._format_forecast_response(cached_data, location, days)

            # Make API call
            forecast_data = await self._fetch_weather_forecast(location, units, days)

            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, forecast_data, ttl=1800)  # 30 minutes

            return self._format_forecast_response(forecast_data, location, days)

        except Exception as e:
            logger.error("Error fetching weather forecast", location=location, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "content": f"Sorry, I couldn't get forecast for {location}: {str(e)}"
            }

    @capability(
        id="get_weather_alerts",
        name="Get Weather Alerts",
        description="Get active weather alerts and warnings for a location",
        scopes=["weather:read", "api:external", "alerts:read"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, state, country"
                },
                "severity": {
                    "type": "string",
                    "enum": ["all", "minor", "moderate", "severe", "extreme"],
                    "description": "Minimum alert severity level",
                    "default": "moderate"
                }
            },
            "required": ["location"]
        }
    )
    async def get_weather_alerts(
        self,
        location: str,
        severity: str = "moderate",
        **kwargs
    ) -> Dict[str, Any]:
        """Get weather alerts for a location."""
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Weather API key not configured",
                    "content": "Weather service requires API key configuration"
                }

            # Fetch alerts data
            alerts_data = await self._fetch_weather_alerts(location, severity)

            if not alerts_data.get("alerts"):
                return {
                    "success": True,
                    "content": f"No active weather alerts for {location}",
                    "metadata": {
                        "location": location,
                        "alert_count": 0,
                        "severity": severity
                    }
                }

            return self._format_alerts_response(alerts_data, location)

        except Exception as e:
            logger.error("Error fetching weather alerts", location=location, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "content": f"Sorry, I couldn't get alerts for {location}: {str(e)}"
            }
```

### Step 4: API Integration Methods

```python
    async def _fetch_current_weather(self, location: str, units: str) -> dict:
        """Fetch current weather from OpenWeatherMap API."""
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": units
        }

        async with self.http_client.get(url, params=params) as response:
            if response.status == 404:
                raise ValueError(f"Location '{location}' not found")
            elif response.status == 401:
                raise ValueError("Invalid API key")
            elif response.status == 429:
                raise ValueError("API rate limit exceeded")

            response.raise_for_status()
            return await response.json()

    async def _fetch_weather_forecast(self, location: str, units: str, days: int) -> dict:
        """Fetch weather forecast from API."""
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": location,
            "appid": self.api_key,
            "units": units,
            "cnt": days * 8  # 8 forecasts per day (3-hour intervals)
        }

        async with self.http_client.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def _fetch_weather_alerts(self, location: str, severity: str) -> dict:
        """Fetch weather alerts from API."""
        # First get coordinates for the location
        geocoding_url = "https://api.openweathermap.org/geo/1.0/direct"
        params = {"q": location, "appid": self.api_key, "limit": 1}

        async with self.http_client.get(geocoding_url, params=params) as response:
            response.raise_for_status()
            geo_data = await response.json()

            if not geo_data:
                raise ValueError(f"Location '{location}' not found")

            lat, lon = geo_data[0]["lat"], geo_data[0]["lon"]

        # Get alerts using coordinates
        alerts_url = "https://api.openweathermap.org/data/3.0/onecall"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "exclude": "current,minutely,hourly,daily"
        }

        async with self.http_client.get(alerts_url, params=params) as response:
            response.raise_for_status()
            return await response.json()
```

### Step 5: Response Formatting

```python
    def _format_weather_response(
        self,
        data: dict,
        location: str,
        response_type: str,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """Format weather data into a readable response."""
        try:
            main = data["main"]
            weather = data["weather"][0]
            wind = data.get("wind", {})

            temp = main["temp"]
            feels_like = main["feels_like"]
            humidity = main["humidity"]
            pressure = main.get("pressure")
            description = weather["description"].title()

            # Determine units
            unit_symbol = self._get_unit_symbol(data.get("units", "imperial"))

            # Basic response
            response = f"**Current Weather in {location}**\n\n"
            response += f"🌡️ **Temperature**: {temp:.1f}{unit_symbol}\n"
            response += f"🤔 **Feels like**: {feels_like:.1f}{unit_symbol}\n"
            response += f"☁️ **Conditions**: {description}\n"
            response += f"💧 **Humidity**: {humidity}%\n"

            if include_details:
                if pressure:
                    response += f"📊 **Pressure**: {pressure} hPa\n"

                if wind.get("speed"):
                    wind_speed = wind["speed"]
                    wind_unit = "mph" if unit_symbol == "°F" else "m/s"
                    response += f"💨 **Wind**: {wind_speed:.1f} {wind_unit}"

                    if wind.get("deg"):
                        direction = self._wind_direction(wind["deg"])
                        response += f" {direction}"
                    response += "\n"

                # Add sunrise/sunset if available
                sys_data = data.get("sys", {})
                if sys_data.get("sunrise") and sys_data.get("sunset"):
                    sunrise = datetime.datetime.fromtimestamp(sys_data["sunrise"])
                    sunset = datetime.datetime.fromtimestamp(sys_data["sunset"])
                    response += f"🌅 **Sunrise**: {sunrise.strftime('%H:%M')}\n"
                    response += f"🌇 **Sunset**: {sunset.strftime('%H:%M')}\n"

            return {
                "success": True,
                "content": response.strip(),
                "metadata": {
                    "location": location,
                    "temperature": temp,
                    "conditions": description,
                    "units": unit_symbol,
                    "response_type": response_type,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }

        except KeyError as e:
            logger.error("Error formatting weather response", missing_field=str(e))
            return {
                "success": False,
                "error": f"Invalid weather data format: missing {e}",
                "content": f"Sorry, received incomplete weather data for {location}"
            }

    def _format_forecast_response(self, data: dict, location: str, days: int) -> Dict[str, Any]:
        """Format forecast data into a readable response."""
        try:
            forecasts = data["list"]
            response = f"**{days}-Day Weather Forecast for {location}**\n\n"

            # Group forecasts by day
            daily_forecasts = {}
            for forecast in forecasts:
                date = datetime.datetime.fromtimestamp(forecast["dt"]).date()
                if date not in daily_forecasts:
                    daily_forecasts[date] = []
                daily_forecasts[date].append(forecast)

            # Format each day
            for i, (date, day_forecasts) in enumerate(daily_forecasts.items()):
                if i >= days:
                    break

                # Get representative forecast (midday if available)
                midday_forecast = day_forecasts[len(day_forecasts)//2]

                temp = midday_forecast["main"]["temp"]
                conditions = midday_forecast["weather"][0]["description"].title()
                unit_symbol = self._get_unit_symbol("imperial")  # Default

                day_name = date.strftime("%A, %B %d")
                response += f"📅 **{day_name}**\n"
                response += f"   🌡️ {temp:.1f}{unit_symbol} - {conditions}\n\n"

            return {
                "success": True,
                "content": response.strip(),
                "metadata": {
                    "location": location,
                    "forecast_days": days,
                    "forecast_count": len(daily_forecasts),
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }

        except Exception as e:
            logger.error("Error formatting forecast response", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "content": f"Sorry, couldn't format forecast data for {location}"
            }

    def _format_alerts_response(self, data: dict, location: str) -> Dict[str, Any]:
        """Format weather alerts into a readable response."""
        alerts = data.get("alerts", [])

        if not alerts:
            return {
                "success": True,
                "content": f"No active weather alerts for {location}",
                "metadata": {"location": location, "alert_count": 0}
            }

        response = f"⚠️ **Weather Alerts for {location}**\n\n"

        for alert in alerts:
            event = alert.get("event", "Weather Alert")
            description = alert.get("description", "No details available")
            start = datetime.datetime.fromtimestamp(alert.get("start", 0))
            end = datetime.datetime.fromtimestamp(alert.get("end", 0))

            response += f"🚨 **{event}**\n"
            response += f"   📅 {start.strftime('%m/%d %H:%M')} - {end.strftime('%m/%d %H:%M')}\n"
            response += f"   📝 {description[:200]}{'...' if len(description) > 200 else ''}\n\n"

        return {
            "success": True,
            "content": response.strip(),
            "metadata": {
                "location": location,
                "alert_count": len(alerts),
                "alerts": [{"event": a.get("event"), "severity": a.get("severity")} for a in alerts]
            }
        }
```

### Step 6: Utility Methods

```python
    def _get_unit_symbol(self, units: str) -> str:
        """Get temperature unit symbol."""
        return {
            "imperial": "°F",
            "metric": "°C",
            "kelvin": "K"
        }.get(units, "°F")

    def _wind_direction(self, degrees: float) -> str:
        """Convert wind degrees to compass direction."""
        directions = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
        ]
        index = round(degrees / 22.5) % 16
        return directions[index]

    async def cleanup(self):
        """Cleanup resources when plugin is destroyed."""
        if self.http_client and not self.http_client.closed:
            await self.http_client.close()
```

### Step 7: Configuration and Validation

Create a comprehensive configuration system:

```python
    def get_config_schema(self) -> Dict[str, Any]:
        """Define configuration schema for the weather plugin."""
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "description": "OpenWeatherMap API key (required)",
                    "minLength": 32,
                    "maxLength": 32
                },
                "default_units": {
                    "type": "string",
                    "enum": ["metric", "imperial", "kelvin"],
                    "default": "imperial",
                    "description": "Default temperature units"
                },
                "cache_duration": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 600,
                    "description": "Cache weather data for this many seconds"
                },
                "max_forecast_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 5,
                    "description": "Maximum number of forecast days"
                },
                "enable_alerts": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable weather alerts capability"
                }
            },
            "required": ["api_key"],
            "additionalProperties": False
        }

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate weather plugin configuration."""
        errors = []
        warnings = []

        # Check API key
        api_key = config.get("api_key")
        if not api_key:
            errors.append("api_key is required for weather functionality")
        elif len(api_key) != 32:
            warnings.append("OpenWeatherMap API keys are typically 32 characters")

        # Validate cache duration
        cache_duration = config.get("cache_duration", 600)
        if cache_duration < 60:
            warnings.append("Very short cache duration may cause API rate limiting")
        elif cache_duration > 3600:
            warnings.append("Long cache duration may provide stale weather data")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
```

### Step 8: Advanced Features

#### State Management

```python
    def get_state_schema(self) -> Dict[str, Any]:
        """Define state schema for weather plugin."""
        return {
            "type": "object",
            "properties": {
                "recent_locations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                    "description": "Recently queried locations"
                },
                "user_preferences": {
                    "type": "object",
                    "properties": {
                        "preferred_units": {
                            "type": "string",
                            "enum": ["metric", "imperial", "kelvin"]
                        },
                        "default_location": {"type": "string"},
                        "include_details": {"type": "boolean", "default": True}
                    }
                },
                "query_stats": {
                    "type": "object",
                    "properties": {
                        "total_queries": {"type": "integer", "default": 0},
                        "last_query_time": {"type": "string", "format": "date-time"},
                        "favorite_location": {"type": "string"}
                    }
                }
            }
        }

    def update_state(self, current_state: Dict[str, Any], location: str) -> Dict[str, Any]:
        """Update plugin state after a weather query."""
        # Update recent locations
        recent = current_state.get("recent_locations", [])
        if location not in recent:
            recent.insert(0, location)
            recent = recent[:10]  # Keep only last 10

        # Update stats
        stats = current_state.get("query_stats", {})
        stats["total_queries"] = stats.get("total_queries", 0) + 1
        stats["last_query_time"] = datetime.datetime.now().isoformat()

        return {
            **current_state,
            "recent_locations": recent,
            "query_stats": stats
        }
```

#### Health Monitoring

```python
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of weather plugin."""
        status = {
            "plugin": "weather",
            "version": self.version,
            "status": "healthy",
            "checks": {}
        }

        # Check API key configuration
        status["checks"]["api_configured"] = bool(self.api_key)

        # Check HTTP client
        status["checks"]["http_client"] = self.http_client is not None

        # Check cache availability
        status["checks"]["cache_available"] = self.cache is not None

        # Test API connectivity (lightweight)
        try:
            if self.api_key:
                # Quick API test with minimal data
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {"q": "London", "appid": self.api_key}

                async with self.http_client.get(url, params=params, timeout=5) as response:
                    status["checks"]["api_accessible"] = response.status == 200
        except Exception as e:
            status["checks"]["api_accessible"] = False
            status["status"] = "degraded"
            status["api_error"] = str(e)

        return status
```

## Testing Your Plugin

### Unit Tests with Pytest

```python
"""Tests for Weather Plugin."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import datetime
from weather_plugin.plugin import WeatherPlugin


@pytest.fixture
async def weather_plugin():
    """Create a configured weather plugin for testing."""
    plugin = WeatherPlugin()
    await plugin.initialize(
        config={
            "api_key": "test_api_key_12345678901234567890",
            "default_units": "imperial",
            "cache_duration": 600
        },
        services={
            "http_client": AsyncMock(),
            "cache": AsyncMock()
        }
    )
    return plugin


@pytest.mark.asyncio
async def test_get_current_weather_success(weather_plugin):
    """Test successful current weather retrieval."""
    # Mock API response
    mock_response = {
        "main": {
            "temp": 72.5,
            "feels_like": 75.0,
            "humidity": 65,
            "pressure": 1013
        },
        "weather": [{"description": "partly cloudy"}],
        "wind": {"speed": 5.2, "deg": 180},
        "sys": {"sunrise": 1609459200, "sunset": 1609495200}
    }

    # Mock HTTP client
    weather_plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_response
    weather_plugin.http_client.get.return_value.__aenter__.return_value.status = 200
    weather_plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()

    # Test the capability
    result = await weather_plugin.get_current_weather("New York", "imperial", True)

    assert result["success"] is True
    assert "New York" in result["content"]
    assert "72.5°F" in result["content"]
    assert "Partly Cloudy" in result["content"]
    assert result["metadata"]["location"] == "New York"
    assert result["metadata"]["temperature"] == 72.5


@pytest.mark.asyncio
async def test_get_current_weather_api_error(weather_plugin):
    """Test handling of API errors."""
    # Mock API error
    weather_plugin.http_client.get.return_value.__aenter__.return_value.status = 404

    result = await weather_plugin.get_current_weather("NonexistentCity")

    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_get_weather_forecast(weather_plugin):
    """Test weather forecast capability."""
    # Mock forecast API response
    mock_response = {
        "list": [
            {
                "dt": 1609459200,
                "main": {"temp": 70.0},
                "weather": [{"description": "sunny"}]
            },
            {
                "dt": 1609545600,
                "main": {"temp": 68.0},
                "weather": [{"description": "cloudy"}]
            }
        ]
    }

    weather_plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_response
    weather_plugin.http_client.get.return_value.__aenter__.return_value.status = 200
    weather_plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()

    result = await weather_plugin.get_weather_forecast("Boston", 2, "imperial")

    assert result["success"] is True
    assert "Boston" in result["content"]
    assert "Forecast" in result["content"]
    assert result["metadata"]["forecast_days"] == 2


def test_config_validation(weather_plugin):
    """Test configuration validation."""
    # Valid config
    valid_config = {
        "api_key": "12345678901234567890123456789012",
        "default_units": "metric",
        "cache_duration": 300
    }

    result = weather_plugin.validate_config(valid_config)
    assert result["valid"] is True
    assert len(result["errors"]) == 0

    # Invalid config - missing API key
    invalid_config = {"default_units": "metric"}

    result = weather_plugin.validate_config(invalid_config)
    assert result["valid"] is False
    assert "api_key is required" in result["errors"][0]


def test_wind_direction_conversion(weather_plugin):
    """Test wind direction conversion."""
    assert weather_plugin._wind_direction(0) == "N"
    assert weather_plugin._wind_direction(90) == "E"
    assert weather_plugin._wind_direction(180) == "S"
    assert weather_plugin._wind_direction(270) == "W"
    assert weather_plugin._wind_direction(45) == "NE"


def test_unit_symbol_mapping(weather_plugin):
    """Test temperature unit symbol mapping."""
    assert weather_plugin._get_unit_symbol("imperial") == "°F"
    assert weather_plugin._get_unit_symbol("metric") == "°C"
    assert weather_plugin._get_unit_symbol("kelvin") == "K"
    assert weather_plugin._get_unit_symbol("unknown") == "°F"  # default


@pytest.mark.asyncio
async def test_caching_behavior(weather_plugin):
    """Test that caching works correctly."""
    # Mock cache hit
    cached_data = {
        "main": {"temp": 75.0, "feels_like": 78.0, "humidity": 60},
        "weather": [{"description": "sunny"}]
    }
    weather_plugin.cache.get.return_value = cached_data

    result = await weather_plugin.get_current_weather("Miami")

    # Should use cached data, not make HTTP request
    weather_plugin.http_client.get.assert_not_called()
    assert result["success"] is True
    assert "75.0°F" in result["content"]


@pytest.mark.asyncio
async def test_plugin_cleanup(weather_plugin):
    """Test plugin cleanup."""
    weather_plugin.http_client.closed = False

    await weather_plugin.cleanup()

    weather_plugin.http_client.close.assert_called_once()
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_weather_api():
    """Test against real weather API (requires valid API key)."""
    import os

    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        pytest.skip("No API key provided for integration test")

    plugin = WeatherPlugin()
    await plugin.initialize(
        config={"api_key": api_key, "default_units": "imperial"},
        services={}
    )

    # Test real API call
    result = await plugin.get_current_weather("London")

    assert result["success"] is True
    assert "London" in result["content"]
    assert "°F" in result["content"]

    await plugin.cleanup()
```

## Trusted Publishing and Security

### Setting Up Trusted Publishing

Your plugin's `pyproject.toml` should include trusted publishing configuration:

```toml
[project.entry-points."agentup.plugins"]
weather = "weather_plugin.plugin:WeatherPlugin"

# Trusted publishing configuration
[tool.agentup.trusted-publishing]
publisher = "your-github-username"
repository = "your-username/weather-plugin"
workflow = "publish.yml"
trust_level = "community"

[tool.agentup.plugin]
capabilities = [
    "weather:current",
    "weather:forecast",
    "weather:alerts"
]
scopes = [
    "weather:read",
    "api:external",
    "alerts:read"
]
min_agentup_version = "2.0.0"
plugin_api_version = "1.0"

# Security hash for integrity verification
security_hash = "sha256:abc123def456..."
```

### Security Best Practices

1. **Scope Isolation**: Use specific scopes for each capability
2. **Input Validation**: Validate all user inputs and API responses
3. **Error Handling**: Never expose internal errors or API keys
4. **Rate Limiting**: Respect API rate limits and implement backoff
5. **Data Sanitization**: Clean user inputs before API calls

```python
def _sanitize_location(self, location: str) -> str:
    """Sanitize location input to prevent injection attacks."""
    # Remove potentially harmful characters
    sanitized = re.sub(r'[<>"\'\(\)\[\]\{\}]', '', location)
    # Limit length
    sanitized = sanitized[:100]
    # Remove extra whitespace
    sanitized = ' '.join(sanitized.split())
    return sanitized
```

## Best Practices

### 1. Error Handling
Always provide informative error messages:

```python
try:
    result = await self._api_call()
except aiohttp.ClientError as e:
    return {
        "success": False,
        "error": "Network error",
        "content": "Weather service is temporarily unavailable. Please try again later."
    }
except ValueError as e:
    return {
        "success": False,
        "error": str(e),
        "content": f"Invalid request: {str(e)}"
    }
```

### 2. Logging
Use structured logging throughout:

```python
logger.info(
    "Weather request processed",
    location=location,
    units=units,
    success=result["success"],
    duration=time.time() - start_time
)
```

### 3. Performance
- Use async/await for all I/O operations
- Implement intelligent caching
- Make concurrent API calls when possible
- Set appropriate timeouts

### 4. Configuration
- Provide sensible defaults
- Validate all configuration values
- Support environment variable overrides
- Document all configuration options

## Deployment and Distribution

### Package Structure
```
weather-plugin/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── weather_plugin/
│       ├── __init__.py
│       ├── plugin.py
│       ├── api_client.py
│       ├── formatters.py
│       └── utils.py
├── tests/
│   ├── __init__.py
│   ├── test_plugin.py
│   ├── test_integration.py
│   └── conftest.py
├── docs/
│   ├── README.md
│   ├── configuration.md
│   └── examples.md
└── .github/
    └── workflows/
        └── publish.yml
```

### GitHub Actions Workflow
```yaml
name: Publish Weather Plugin

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

This comprehensive guide covers everything needed to build production-ready AgentUp plugins using the new decorator system. The weather plugin example demonstrates real-world patterns that can be applied to any domain!