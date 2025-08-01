# Plugin Testing Guide

Testing is crucial for building reliable plugins. This guide covers comprehensive testing strategies for the new decorator-based plugin system, from unit tests to integration testing, using AgentUp's built-in testing utilities and industry-standard tools.

## Testing Overview

AgentUp plugins using the new decorator-based system should be tested at multiple levels:

1. **Unit Tests** - Test individual capabilities and plugin methods
2. **Capability Tests** - Test @capability decorated methods specifically
3. **Integration Tests** - Test plugin interaction with AgentUp systems
4. **AI Function Tests** - Test LLM-callable functions specifically
5. **End-to-End Tests** - Test complete user workflows
6. **Security Tests** - Test scope-based permissions and trust verification
7. **Performance Tests** - Ensure plugins meet performance requirements

## Setting Up Testing

### Basic Test Structure

When you create a plugin with `agentup plugin create`, you get a comprehensive test structure:

```
my-plugin/
├── src/
│   └── my_plugin/
│       └── plugin.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration and fixtures
│   ├── test_plugin.py       # Main plugin tests
│   ├── test_capabilities.py # Capability-specific tests
│   ├── test_ai_functions.py # AI function specific tests
│   ├── test_security.py     # Security and scope tests
│   └── test_integration.py  # Integration tests
└── pyproject.toml
```

### Test Dependencies

Add testing dependencies to your `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-mock>=3.10.0",
    "httpx>=0.24.0",
    "responses>=0.23.0",  # For mocking HTTP requests
    "freezegun>=1.2.0",   # For mocking time
    "factory-boy>=3.2.0", # For test data generation
]
```

Install test dependencies:

```bash
uv add --group test pytest pytest-asyncio pytest-mock httpx responses freezegun factory-boy
# or pip install -e ".[test]"
```

## Unit Testing Decorator-Based Plugins

### Basic Plugin Tests

Here's a comprehensive test suite for a weather plugin using the new decorator system:

```python
"""Unit tests for weather plugin with decorator system."""

import pytest
import datetime
from unittest.mock import Mock, AsyncMock, patch
import httpx
import responses

from weather_plugin.plugin import WeatherPlugin
from agent.plugins.base import Plugin


class TestWeatherPlugin:
    """Test suite for decorator-based weather plugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance for testing."""
        plugin = WeatherPlugin()
        plugin.config = {
            "api_key": "test_api_key_12345",
            "default_units": "imperial",
            "cache_duration": 600,
        }
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()
        return plugin

    def test_plugin_inheritance(self, plugin):
        """Test that the plugin properly inherits from Plugin base."""
        assert isinstance(plugin, Plugin)
        assert hasattr(plugin, '_capabilities')
        assert hasattr(plugin, '_discover_capabilities')

    def test_capabilities_auto_discovery(self, plugin):
        """Test that capabilities are automatically discovered from decorators."""
        # Capabilities should be auto-discovered from @capability decorators
        assert len(plugin._capabilities) >= 2  # get_weather, get_forecast at minimum
        
        capability_ids = list(plugin._capabilities.keys())
        assert "get_current_weather" in capability_ids
        assert "get_weather_forecast" in capability_ids

    def test_capability_metadata(self, plugin):
        """Test capability metadata from decorators."""
        get_weather_cap = plugin._capabilities["get_current_weather"]
        
        assert get_weather_cap.id == "get_current_weather"
        assert get_weather_cap.name == "Get Current Weather"
        assert "weather" in get_weather_cap.description.lower()
        assert "weather:read" in get_weather_cap.scopes
        assert "api:external" in get_weather_cap.scopes
        assert get_weather_cap.ai_function is True

    def test_ai_function_parameters(self, plugin):
        """Test AI function parameters from decorators."""
        get_weather_cap = plugin._capabilities["get_current_weather"]
        
        params = get_weather_cap.ai_parameters
        assert params["type"] == "object"
        assert "properties" in params
        assert "location" in params["properties"]
        assert "location" in params.get("required", [])
        
        # Validate parameter schema
        location_param = params["properties"]["location"]
        assert location_param["type"] == "string"
        assert "description" in location_param

    @pytest.fixture
    def mock_weather_data(self):
        """Mock weather API response data."""
        return {
            "main": {
                "temp": 72.5,
                "feels_like": 75.0,
                "humidity": 65,
                "pressure": 1013.25
            },
            "weather": [
                {
                    "main": "Clouds",
                    "description": "partly cloudy",
                    "icon": "02d"
                }
            ],
            "wind": {
                "speed": 5.2,
                "deg": 180,
                "gust": 7.1
            },
            "name": "New York",
            "sys": {"country": "US"}
        }

    def test_configuration_validation(self, plugin):
        """Test configuration validation."""
        # Valid configuration
        valid_config = {
            "api_key": "valid_key_32_characters_long",
            "default_units": "metric",
            "cache_duration": 300
        }
        result = plugin.validate_config(valid_config)
        assert result["valid"]
        assert len(result["errors"]) == 0

        # Missing API key
        invalid_config = {"default_units": "metric"}
        result = plugin.validate_config(invalid_config)
        assert not result["valid"]
        assert any("api_key" in error for error in result["errors"])

    @pytest.mark.asyncio
    async def test_get_current_weather_capability(self, plugin, mock_weather_data):
        """Test the get_current_weather capability directly."""
        # Mock API response
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_weather_data
        plugin.http_client.get.return_value.__aenter__.return_value.status = 200
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()
        
        # Mock cache miss
        plugin.cache.get.return_value = None

        # Call capability directly
        result = await plugin.get_current_weather("New York", "imperial", True)

        assert result["success"] is True
        assert "New York" in result["content"]
        assert "72.5°F" in result["content"]
        assert result["metadata"]["location"] == "New York"

    @pytest.mark.asyncio
    async def test_capability_error_handling(self, plugin):
        """Test capability error handling."""
        # Mock API error
        plugin.http_client.get.side_effect = httpx.HTTPStatusError(
            "API Error",
            request=Mock(),
            response=Mock(status_code=401)
        )
        plugin.cache.get.return_value = None

        result = await plugin.get_current_weather("Invalid", "imperial")

        assert result["success"] is False
        assert "error" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_capability_with_missing_config(self, plugin):
        """Test capability when API key is missing."""
        plugin.api_key = None  # Simulate missing API key

        result = await plugin.get_current_weather("Boston")

        assert result["success"] is False
        assert "api key" in result["error"].lower()

    def test_wind_direction_conversion(self, plugin):
        """Test wind direction degree to compass conversion."""
        test_cases = [
            (0, "N"), (45, "NE"), (90, "E"), (135, "SE"),
            (180, "S"), (225, "SW"), (270, "W"), (315, "NW"),
            (360, "N")  # Full circle
        ]

        for degrees, expected in test_cases:
            direction = plugin._wind_direction(degrees)
            assert direction == expected

    @pytest.mark.asyncio
    async def test_caching_behavior(self, plugin, mock_weather_data):
        """Test that caching works correctly."""
        # Mock cache hit
        plugin.cache.get.return_value = mock_weather_data
        
        result = await plugin.get_current_weather("Miami")
        
        # Should use cached data, not make HTTP request
        plugin.http_client.get.assert_not_called()
        assert result["success"] is True

    @pytest.mark.asyncio 
    async def test_state_updates(self, plugin, mock_weather_data):
        """Test that capabilities can update plugin state."""
        plugin.cache.get.return_value = None
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_weather_data
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()

        # Mock the update_state method
        initial_state = {"recent_locations": []}
        updated_state = plugin.update_state(initial_state, "Miami")
        
        assert "recent_locations" in updated_state
        assert "Miami" in updated_state["recent_locations"]
        assert "query_stats" in updated_state

    def test_config_schema_validation(self, plugin):
        """Test configuration schema."""
        schema = plugin.get_config_schema()
        
        assert schema["type"] == "object"
        assert "api_key" in schema["properties"]
        assert "api_key" in schema["required"]
        assert schema["properties"]["api_key"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_health_check(self, plugin):
        """Test plugin health check."""
        plugin.api_key = "test_key"
        plugin.http_client.get.return_value.__aenter__.return_value.status = 200
        
        health = await plugin.health_check()
        
        assert health["plugin"] == "weather"
        assert "checks" in health
        assert health["checks"]["api_configured"] is True
```

## Testing Capability Decorators

### Decorator Functionality Tests

```python
"""Tests for @capability decorator functionality."""

import pytest
from unittest.mock import Mock

from agent.plugins.decorators import capability
from agent.plugins.base import Plugin


class TestCapabilityDecorators:
    """Test capability decorator system."""

    def test_capability_decorator_basic(self):
        """Test basic capability decorator functionality."""
        
        class TestPlugin(Plugin):
            @capability(
                id="test_capability",
                name="Test Capability",
                description="A test capability"
            )
            async def test_method(self, param: str = "default"):
                return {"result": f"processed {param}"}
        
        plugin = TestPlugin()
        
        # Check capability was registered
        assert "test_capability" in plugin._capabilities
        cap = plugin._capabilities["test_capability"]
        assert cap.id == "test_capability"
        assert cap.name == "Test Capability"

    def test_capability_decorator_with_scopes(self):
        """Test capability decorator with scopes."""
        
        class TestPlugin(Plugin):
            @capability(
                id="secure_capability",
                name="Secure Capability",
                description="A secure capability",
                scopes=["test:read", "test:write"]
            )
            async def secure_method(self):
                return {"result": "secure operation"}
        
        plugin = TestPlugin()
        cap = plugin._capabilities["secure_capability"]
        
        assert "test:read" in cap.scopes
        assert "test:write" in cap.scopes

    def test_capability_decorator_ai_function(self):
        """Test capability decorator with AI function parameters."""
        
        class TestPlugin(Plugin):
            @capability(
                id="ai_capability",
                name="AI Capability",
                description="An AI-enabled capability",
                ai_function=True,
                ai_parameters={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input text"}
                    },
                    "required": ["input"]
                }
            )
            async def ai_method(self, input: str):
                return {"result": f"AI processed: {input}"}
        
        plugin = TestPlugin()
        cap = plugin._capabilities["ai_capability"]
        
        assert cap.ai_function is True
        assert cap.ai_parameters["type"] == "object"
        assert "input" in cap.ai_parameters["properties"]

    def test_capability_method_binding(self):
        """Test that capabilities are properly bound to methods."""
        
        class TestPlugin(Plugin):
            @capability(id="test", name="Test", description="Test")
            async def test_method(self, value: int):
                return {"doubled": value * 2}
        
        plugin = TestPlugin()
        cap = plugin._capabilities["test"]
        
        # The method should be bound to the capability
        assert hasattr(cap, 'method')
        assert callable(cap.method)

    def test_multiple_capabilities_single_plugin(self):
        """Test plugin with multiple capabilities."""
        
        class MultiCapabilityPlugin(Plugin):
            @capability(id="cap1", name="Cap 1", description="First capability")
            async def first_capability(self):
                return {"result": "first"}
            
            @capability(id="cap2", name="Cap 2", description="Second capability")
            async def second_capability(self):
                return {"result": "second"}
            
            @capability(id="cap3", name="Cap 3", description="Third capability")
            async def third_capability(self):
                return {"result": "third"}
        
        plugin = MultiCapabilityPlugin()
        
        assert len(plugin._capabilities) == 3
        assert "cap1" in plugin._capabilities
        assert "cap2" in plugin._capabilities
        assert "cap3" in plugin._capabilities

    def test_capability_inheritance(self):
        """Test capability inheritance from parent classes."""
        
        class ParentPlugin(Plugin):
            @capability(id="parent_cap", name="Parent Cap", description="Parent capability")
            async def parent_method(self):
                return {"result": "parent"}
        
        class ChildPlugin(ParentPlugin):
            @capability(id="child_cap", name="Child Cap", description="Child capability")
            async def child_method(self):
                return {"result": "child"}
        
        child_plugin = ChildPlugin()
        
        # Should have both parent and child capabilities
        assert len(child_plugin._capabilities) == 2
        assert "parent_cap" in child_plugin._capabilities
        assert "child_cap" in child_plugin._capabilities
```

## AI Function Testing

### Testing AI Function Integration

```python
"""Tests for AI function capabilities."""

import pytest
from unittest.mock import Mock, AsyncMock

from weather_plugin.plugin import WeatherPlugin


class TestWeatherAIFunctions:
    """Test AI function capabilities in decorator system."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        plugin = WeatherPlugin()
        plugin.config = {"api_key": "test_key", "default_units": "imperial"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()
        return plugin

    def test_ai_function_discovery(self, plugin):
        """Test that AI functions are automatically discovered."""
        # Find capabilities marked as AI functions
        ai_capabilities = [
            cap for cap in plugin._capabilities.values() 
            if cap.ai_function
        ]
        
        assert len(ai_capabilities) >= 2  # get_weather, get_forecast
        
        # Check specific AI function
        weather_cap = next(
            (cap for cap in ai_capabilities if cap.id == "get_current_weather"),
            None
        )
        assert weather_cap is not None
        assert weather_cap.ai_function is True

    def test_ai_function_schemas(self, plugin):
        """Test AI function parameter schemas."""
        weather_cap = plugin._capabilities["get_current_weather"]
        
        # Validate OpenAI function schema format
        params = weather_cap.ai_parameters
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
        
        # Check location parameter
        location_prop = params["properties"]["location"]
        assert location_prop["type"] == "string"
        assert "description" in location_prop
        
        # Check units parameter
        if "units" in params["properties"]:
            units_prop = params["properties"]["units"]
            assert units_prop["type"] == "string"
            assert "enum" in units_prop
            assert "imperial" in units_prop["enum"]

    @pytest.mark.asyncio
    async def test_ai_function_execution(self, plugin):
        """Test AI function execution via capability."""
        # Mock API response
        mock_response = {
            "main": {"temp": 75.0, "humidity": 60},
            "weather": [{"description": "sunny"}],
            "name": "Miami"
        }
        
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_response
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()
        plugin.cache.get.return_value = None

        # Execute capability directly (simulating AI function call)
        result = await plugin.get_current_weather(
            location="Miami",
            units="imperial",
            include_details=True
        )

        assert result["success"] is True
        assert "Miami" in result["content"]
        assert "75.0°F" in result["content"]
        assert result["metadata"]["location"] == "Miami"

    def test_ai_parameter_validation(self, plugin):
        """Test AI function parameter validation."""
        weather_cap = plugin._capabilities["get_current_weather"]
        params = weather_cap.ai_parameters
        
        # Validate parameter types and constraints
        for prop_name, prop_schema in params["properties"].items():
            assert "type" in prop_schema
            assert "description" in prop_schema
            
            # Check enum constraints
            if "enum" in prop_schema:
                assert isinstance(prop_schema["enum"], list)
                assert len(prop_schema["enum"]) > 0

    @pytest.mark.asyncio
    async def test_ai_function_error_handling(self, plugin):
        """Test AI function error responses."""
        # Remove API key to simulate configuration error
        plugin.api_key = None
        
        result = await plugin.get_current_weather("Boston")
        
        assert result["success"] is False
        assert "error" in result
        assert "api key" in result["error"].lower()
        
        # Result should still be properly formatted for AI consumption
        assert "content" in result
        assert isinstance(result["content"], str)

    def test_function_schema_openai_compatibility(self, plugin):
        """Test that function schemas are OpenAI compatible."""
        ai_capabilities = [
            cap for cap in plugin._capabilities.values() 
            if cap.ai_function
        ]
        
        for cap in ai_capabilities:
            schema = cap.ai_parameters
            
            # Must follow OpenAI function calling schema
            assert schema["type"] == "object"
            assert "properties" in schema
            
            # Required must be array of strings
            if "required" in schema:
                assert isinstance(schema["required"], list)
                for req in schema["required"]:
                    assert isinstance(req, str)
                    assert req in schema["properties"]
            
            # Each property must have type and description
            for prop_name, prop_def in schema["properties"].items():
                assert "type" in prop_def
                assert "description" in prop_def
                assert isinstance(prop_def["description"], str)
```

## Security and Scope Testing

### Testing Permission System

```python
"""Tests for security and scope-based permissions."""

import pytest
from unittest.mock import Mock

from weather_plugin.plugin import WeatherPlugin


class TestWeatherPluginSecurity:
    """Test security features of decorator-based plugins."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return WeatherPlugin()

    def test_capability_scopes_defined(self, plugin):
        """Test that capabilities have proper scopes defined."""
        for cap_id, capability in plugin._capabilities.items():
            # All capabilities should have scopes defined
            assert hasattr(capability, 'scopes')
            assert isinstance(capability.scopes, list)
            assert len(capability.scopes) > 0
            
            # Weather capabilities should have weather:read scope
            if "weather" in cap_id:
                assert "weather:read" in capability.scopes

    def test_external_api_scopes(self, plugin):
        """Test that external API capabilities have proper scopes."""
        api_capabilities = [
            cap for cap in plugin._capabilities.values()
            if any("api" in scope for scope in cap.scopes)
        ]
        
        assert len(api_capabilities) > 0
        
        for cap in api_capabilities:
            # Should have api:external scope for external API calls
            assert "api:external" in cap.scopes

    def test_scope_hierarchy_validation(self, plugin):
        """Test scope hierarchy validation."""
        # This would test the scope validation logic
        # when it's implemented in the security system
        
        capability = plugin._capabilities["get_current_weather"]
        
        # Basic scopes should be present
        assert "weather:read" in capability.scopes
        
        # No admin scopes unless specifically needed
        admin_scopes = [scope for scope in capability.scopes if "admin" in scope]
        assert len(admin_scopes) == 0  # Weather plugin shouldn't need admin

    def test_capability_isolation(self, plugin):
        """Test that capabilities are properly isolated."""
        # Each capability should have distinct, appropriate scopes
        weather_cap = plugin._capabilities.get("get_current_weather")
        forecast_cap = plugin._capabilities.get("get_weather_forecast")
        
        if weather_cap and forecast_cap:
            # Both should have weather:read
            assert "weather:read" in weather_cap.scopes
            assert "weather:read" in forecast_cap.scopes
            
            # Both should have api:external for API calls
            assert "api:external" in weather_cap.scopes
            assert "api:external" in forecast_cap.scopes

    def test_no_excessive_permissions(self, plugin):
        """Test that capabilities don't request excessive permissions."""
        for capability in plugin._capabilities.values():
            # No capability should request system-level permissions
            system_scopes = [
                scope for scope in capability.scopes 
                if scope.startswith(("system:", "admin", "root:"))
            ]
            assert len(system_scopes) == 0
            
            # No wildcard permissions
            wildcard_scopes = [scope for scope in capability.scopes if "*" in scope]
            assert len(wildcard_scopes) == 0

    def test_trusted_publishing_metadata(self, plugin):
        """Test plugin has trusted publishing metadata."""
        # This would check the plugin's metadata for trusted publishing info
        # if it's available at runtime
        
        # Plugin should have name and version
        assert hasattr(plugin, 'name')
        assert hasattr(plugin, 'version')
        assert plugin.name is not None
        assert plugin.version is not None

    @pytest.mark.asyncio
    async def test_capability_security_validation(self, plugin):
        """Test that capabilities validate security context."""
        # This would test the security validation when it's implemented
        # For now, we test that the capability returns proper error messages
        
        plugin.api_key = None  # Simulate missing API key
        
        result = await plugin.get_current_weather("Boston")
        
        # Should fail securely with appropriate error message
        assert result["success"] is False
        assert "error" in result
        
        # Error message shouldn't expose internal details
        error_msg = result["error"].lower()
        assert "api key" in error_msg
        # Should not expose internal paths, tokens, etc.
        assert "/" not in result["error"]
        assert "token" not in error_msg
```

## Integration Testing

### Plugin Registry Integration

```python
"""Integration tests with AgentUp plugin system."""

import pytest
from unittest.mock import Mock, AsyncMock

from weather_plugin.plugin import WeatherPlugin
from agent.plugins.manager import PluginRegistry


class TestPluginIntegration:
    """Test plugin integration with AgentUp systems."""

    @pytest.fixture
    def plugin_registry(self):
        """Create plugin registry with weather plugin."""
        registry = PluginRegistry({})
        plugin = WeatherPlugin()
        
        # Register plugin
        registry.register_plugin("weather_plugin", plugin)
        
        return registry, plugin

    def test_plugin_registration(self, plugin_registry):
        """Test plugin registration with registry."""
        registry, plugin = plugin_registry
        
        # Plugin should be registered
        assert "weather_plugin" in registry.plugins
        
        # Capabilities should be available
        capabilities = registry.get_capabilities("weather_plugin")
        assert len(capabilities) > 0
        
        capability_ids = [cap.id for cap in capabilities]
        assert "get_current_weather" in capability_ids

    @pytest.mark.asyncio
    async def test_capability_execution_via_registry(self, plugin_registry):
        """Test executing capability through registry."""
        registry, plugin = plugin_registry
        
        # Setup plugin dependencies
        plugin.config = {"api_key": "test_key"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 70.0},
            "weather": [{"description": "cloudy"}],
            "name": "Seattle"
        }
        plugin.http_client.get.return_value.__aenter__.return_value = mock_response
        plugin.cache.get.return_value = None

        # Execute capability through registry
        result = await registry.execute_capability(
            "weather_plugin",
            "get_current_weather",
            location="Seattle",
            units="imperial"
        )

        assert result["success"] is True
        assert "Seattle" in result["content"]

    def test_ai_function_registration_via_registry(self, plugin_registry):
        """Test AI functions are available through registry."""
        registry, plugin = plugin_registry
        
        ai_functions = registry.get_ai_functions("weather_plugin")
        
        assert len(ai_functions) > 0
        function_ids = [func.id for func in ai_functions]
        assert "get_current_weather" in function_ids

    def test_plugin_metadata_via_registry(self, plugin_registry):
        """Test plugin metadata is accessible through registry."""
        registry, plugin = plugin_registry
        
        metadata = registry.get_plugin_metadata("weather_plugin")
        
        assert metadata is not None
        assert "name" in metadata
        assert "version" in metadata
        assert metadata["capabilities_count"] > 0

    @pytest.mark.asyncio
    async def test_plugin_health_check_via_registry(self, plugin_registry):
        """Test plugin health check through registry."""
        registry, plugin = plugin_registry
        
        # Setup plugin for health check
        plugin.api_key = "test_key"
        plugin.http_client = AsyncMock()
        
        health = await registry.check_plugin_health("weather_plugin")
        
        assert "status" in health
        assert "checks" in health
        assert health["checks"]["api_configured"] is True
```

## Performance Testing

### Load and Concurrency Tests

```python
"""Performance tests for decorator-based plugins."""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock

from weather_plugin.plugin import WeatherPlugin


class TestWeatherPluginPerformance:
    """Performance tests for weather plugin."""

    @pytest.fixture
    def plugin(self):
        """Create optimized plugin for performance testing."""
        plugin = WeatherPlugin()
        plugin.config = {"api_key": "test_key", "cache_duration": 300}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()
        return plugin

    @pytest.mark.asyncio
    async def test_concurrent_capability_execution(self, plugin):
        """Test plugin handles concurrent capability executions."""
        # Mock fast API response
        mock_response = {
            "main": {"temp": 72.0},
            "weather": [{"description": "clear"}],
            "name": "TestCity"
        }
        
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_response
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()
        plugin.cache.get.return_value = None

        # Create multiple concurrent capability calls
        tasks = []
        for i in range(50):
            task = asyncio.create_task(
                plugin.get_current_weather(f"City{i}", "imperial")
            )
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All requests should succeed
        assert len(results) == 50
        for result in results:
            assert result["success"] is True

        # Should complete within reasonable time
        assert end_time - start_time < 3.0

    @pytest.mark.asyncio
    async def test_caching_performance_benefit(self, plugin):
        """Test caching improves performance."""
        # First call - cache miss
        plugin.cache.get.return_value = None
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = {
            "main": {"temp": 75.0}, "weather": [{"description": "sunny"}]
        }
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()

        start_time = time.time()
        await plugin.get_current_weather("Boston", "imperial")
        first_call_time = time.time() - start_time

        # Second call - cache hit
        plugin.cache.get.return_value = {
            "main": {"temp": 75.0}, "weather": [{"description": "sunny"}]
        }

        start_time = time.time()
        await plugin.get_current_weather("Boston", "imperial")
        second_call_time = time.time() - start_time

        # Cached call should be significantly faster
        assert second_call_time < first_call_time * 0.2

    def test_capability_discovery_performance(self, plugin):
        """Test capability discovery doesn't impact performance."""
        # Capability discovery should be fast
        start_time = time.time()
        
        # Multiple capability lookups
        for _ in range(1000):
            capabilities = plugin._capabilities
            assert len(capabilities) > 0
        
        end_time = time.time()
        
        # Should be very fast (under 100ms for 1000 lookups)
        assert end_time - start_time < 0.1

    def test_memory_usage_capabilities(self, plugin):
        """Test capabilities don't cause memory leaks."""
        import tracemalloc
        
        tracemalloc.start()
        
        # Simulate many capability metadata accesses
        for i in range(1000):
            for cap_id, capability in plugin._capabilities.items():
                _ = capability.name
                _ = capability.description
                _ = capability.scopes
                _ = capability.ai_parameters
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Memory usage should be reasonable
        assert peak < 5 * 1024 * 1024  # 5MB peak
```

## End-to-End Testing

### Complete Workflow Tests

```python
"""End-to-end tests for decorator-based plugin workflows."""

import pytest
from unittest.mock import Mock, AsyncMock

from weather_plugin.plugin import WeatherPlugin


class TestWeatherPluginE2E:
    """End-to-end tests for weather plugin workflows."""

    @pytest.mark.asyncio
    async def test_complete_ai_function_workflow(self):
        """Test complete AI function calling workflow."""
        plugin = WeatherPlugin()
        plugin.config = {"api_key": "test_key", "default_units": "imperial"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # Mock API response
        mock_response = {
            "main": {"temp": 18.0, "humidity": 65},
            "weather": [{"description": "light rain"}],
            "name": "Paris"
        }
        plugin.http_client.get.return_value.__aenter__.return_value.json.return_value = mock_response
        plugin.http_client.get.return_value.__aenter__.return_value.raise_for_status = Mock()
        plugin.cache.get.return_value = None

        # Simulate AI function call with parameters
        result = await plugin.get_current_weather(
            location="Paris",
            units="metric",
            include_details=True
        )

        # Verify complete response
        assert result["success"] is True
        assert "Paris" in result["content"]
        assert "18.0°C" in result["content"]
        assert "rain" in result["content"].lower()
        assert result["metadata"]["location"] == "Paris"
        assert "timestamp" in result["metadata"]

    @pytest.mark.asyncio
    async def test_capability_chaining_workflow(self):
        """Test chaining multiple capabilities."""
        plugin = WeatherPlugin()
        plugin.config = {"api_key": "test_key"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # Mock current weather response
        current_weather_response = {
            "main": {"temp": 25.0},
            "weather": [{"description": "sunny"}],
            "name": "Tokyo"
        }
        
        # Mock forecast response
        forecast_response = {
            "list": [
                {
                    "dt": 1609459200,
                    "main": {"temp": 23.0},
                    "weather": [{"description": "cloudy"}]
                },
                {
                    "dt": 1609545600,
                    "main": {"temp": 21.0},
                    "weather": [{"description": "rainy"}]
                }
            ]
        }

        # Setup mocks for different API calls
        def mock_api_response(*args, **kwargs):
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            
            # Return different responses based on URL
            url = args[0] if args else kwargs.get('url', '')
            if 'forecast' in url:
                mock_resp.json.return_value = forecast_response
            else:
                mock_resp.json.return_value = current_weather_response
            
            mock_context = Mock()
            mock_context.__aenter__ = Mock(return_value=mock_resp)
            return mock_context

        plugin.http_client.get = Mock(side_effect=mock_api_response)
        plugin.cache.get.return_value = None

        # Execute current weather capability
        current_result = await plugin.get_current_weather("Tokyo", "metric")
        assert current_result["success"] is True
        assert "Tokyo" in current_result["content"]

        # Execute forecast capability
        forecast_result = await plugin.get_weather_forecast("Tokyo", 2, "metric")
        assert forecast_result["success"] is True
        assert "Tokyo" in forecast_result["content"]

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """Test error recovery and graceful degradation."""
        plugin = WeatherPlugin()
        plugin.config = {"api_key": "test_key"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # First attempt fails with network error
        plugin.http_client.get.side_effect = Exception("Network error")
        plugin.cache.get.return_value = None

        result = await plugin.get_current_weather("London")

        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result
        assert "content" in result
        assert "Network error" in result["error"]

        # Error message should be user-friendly
        assert "sorry" in result["content"].lower() or "error" in result["content"].lower()

    def test_plugin_lifecycle_workflow(self):
        """Test complete plugin lifecycle."""
        # 1. Plugin creation
        plugin = WeatherPlugin()
        assert isinstance(plugin, WeatherPlugin)

        # 2. Capability discovery
        assert len(plugin._capabilities) > 0

        # 3. Configuration validation
        config = {"api_key": "test_key", "default_units": "metric"}
        validation_result = plugin.validate_config(config)
        assert validation_result["valid"]

        # 4. Plugin initialization
        plugin.config = config
        assert plugin.config["api_key"] == "test_key"

        # 5. Health check
        # Note: In a real scenario, this would be async and check actual services
        assert hasattr(plugin, 'health_check')
```

## Testing Best Practices for Decorator-Based Plugins

### 1. Test Structure Organization

```python
# Organize tests by functionality
tests/
├── unit/
│   ├── test_plugin_base.py         # Base plugin functionality
│   ├── test_capabilities.py        # @capability decorator tests
│   ├── test_ai_functions.py        # AI function specific tests
│   └── test_security.py            # Scope and permission tests
├── integration/
│   ├── test_registry_integration.py # Plugin registry integration
│   └── test_api_integration.py      # External API integration
├── performance/
│   ├── test_concurrency.py         # Concurrent execution tests
│   └── test_memory_usage.py        # Memory and resource usage
└── e2e/
    └── test_workflows.py            # Complete user workflows
```

### 2. Fixture Management

```python
# conftest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock

@pytest.fixture
def base_plugin_config():
    """Standard plugin configuration for tests."""
    return {
        "api_key": "test_api_key_32_characters_long",
        "default_units": "imperial",
        "cache_duration": 300,
        "timeout": 30,
    }

@pytest.fixture
def mock_http_client():
    """Mock HTTP client with common response patterns."""
    client = AsyncMock()
    
    # Default success response
    mock_response = Mock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "main": {"temp": 72.0},
        "weather": [{"description": "clear"}]
    }
    mock_response.raise_for_status = Mock()
    
    client.get.return_value.__aenter__.return_value = mock_response
    return client

@pytest.fixture
def mock_cache():
    """Mock cache with helper methods."""
    cache = AsyncMock()
    cache.get.return_value = None  # Default cache miss
    cache.set.return_value = True
    return cache

@pytest.fixture
def weather_plugin(base_plugin_config, mock_http_client, mock_cache):
    """Fully configured weather plugin for testing."""
    from weather_plugin.plugin import WeatherPlugin
    
    plugin = WeatherPlugin()
    plugin.config = base_plugin_config
    plugin.http_client = mock_http_client
    plugin.cache = mock_cache
    return plugin
```

### 3. Test Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/test_*.py",
    "*/__pycache__/*",
    "*/site-packages/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
show_missing = true
fail_under = 85

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
    "--cov",
    "--cov-report=term-missing",
    "--cov-report=html",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests", 
    "e2e: End-to-end tests",
    "performance: Performance tests",
    "security: Security tests",
    "slow: Slow tests",
]
```

### 4. CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Test Plugin

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install UV
      run: curl -LsSf https://astral.sh/uv/install.sh | sh

    - name: Install dependencies
      run: |
        uv sync --all-extras --dev

    - name: Run linting
      run: |
        uv run ruff check src/ tests/
        uv run ruff format --check src/ tests/

    - name: Run type checking
      run: |
        uv run mypy src/

    - name: Run security scan
      run: |
        uv run bandit -r src/ -ll

    - name: Run unit tests
      run: |
        uv run pytest tests/unit/ -v -m "not slow"

    - name: Run integration tests
      run: |
        uv run pytest tests/integration/ -v

    - name: Run performance tests
      run: |
        uv run pytest tests/performance/ -v -m "not slow"

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

This comprehensive testing guide ensures your decorator-based AgentUp plugins are reliable, secure, performant, and maintainable. The new decorator system simplifies testing while providing powerful capabilities for building robust plugins.