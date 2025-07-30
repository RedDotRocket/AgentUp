# Plugin Testing Guide

Testing is crucial for building reliable plugins. This guide covers comprehensive testing strategies, from unit tests to integration testing, using AgentUp's built-in testing utilities and industry-standard tools.

## Testing Overview

AgentUp plugins should be tested at multiple levels:

1. **Unit Tests** - Test individual plugin methods and functions
2. **Integration Tests** - Test plugin interaction with AgentUp systems
3. **AI Function Tests** - Test LLM-callable functions specifically
4. **End-to-End Tests** - Test complete user workflows
5. **Performance Tests** - Ensure plugins meet performance requirements

## Setting Up Testing

### Basic Test Structure

When you create a plugin with `agentup plugin create`, you get a basic test structure:

```
my-plugin/
├── src/
│   └── my_plugin/
│       └── plugin.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Pytest configuration and fixtures
│   ├── test_plugin.py       # Main plugin tests
│   ├── test_ai_functions.py # AI function specific tests
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
pip install -e ".[test]"
```

## Unit Testing

### Basic Plugin Tests

Here's a comprehensive test suite for a weather plugin:

```python
"""Unit tests for weather plugin."""

import pytest
import datetime
from unittest.mock import Mock, AsyncMock, patch
import httpx
import responses

from weather_plugin.plugin import Plugin
from agent.plugins import CapabilityContext, CapabilityInfo, CapabilityResult


class TestWeatherPlugin:
    """Test suite for weather plugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance for testing."""
        plugin = Plugin()
        plugin.config = {
            "api_key": "test_api_key_12345",
            "default_units": "imperial",
            "cache_duration": 600,
        }
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()
        return plugin

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

    def test_plugin_registration(self, plugin):
        """Test that the plugin registers correctly."""
        capability_info = plugin.register_capability()

        assert isinstance(capability_info, CapabilityInfo)
        assert capability_info.id == "weather"
        assert capability_info.name == "Weather Information"
        assert skill_info.version == "1.0.0"
        assert "text" in [cap.value for cap in skill_info.capabilities]
        assert "ai_function" in [cap.value for cap in skill_info.capabilities]

    def test_configuration_validation(self, plugin):
        """Test configuration validation."""
        # Valid configuration
        valid_config = {
            "api_key": "valid_key_32_characters_long",
            "default_units": "metric",
            "cache_duration": 300
        }
        result = plugin.validate_config(valid_config)
        assert result.valid
        assert len(result.errors) == 0

        # Missing API key
        invalid_config = {"default_units": "metric"}
        result = plugin.validate_config(invalid_config)
        assert not result.valid
        assert any("api_key" in error for error in result.errors)

        # Invalid units
        invalid_units_config = {
            "api_key": "test_key",
            "default_units": "invalid_units"
        }
        result = plugin.validate_config(invalid_units_config)
        assert not result.valid

    def test_routing_confidence(self, plugin):
        """Test routing confidence calculation."""
        # High confidence weather queries
        high_confidence_queries = [
            "What's the weather like?",
            "How's the weather in New York?",
            "Will it rain today?",
            "What's the temperature outside?",
            "Weather forecast for tomorrow"
        ]

        for query in high_confidence_queries:
            task = self._create_mock_task(query)
            context = CapabilityContext(task=task)
            confidence = plugin.can_handle_task(context)
            assert confidence >= 0.8, f"Low confidence for: {query}"

        # Low confidence non-weather queries
        low_confidence_queries = [
            "What time is it?",
            "How do I cook pasta?",
            "What's the capital of France?",
            "Calculate 2 + 2"
        ]

        for query in low_confidence_queries:
            task = self._create_mock_task(query)
            context = CapabilityContext(task=task)
            confidence = plugin.can_handle_task(context)
            assert confidence < 0.3, f"High confidence for non-weather query: {query}"

    def test_location_extraction(self, plugin):
        """Test location parsing from user input."""
        test_cases = [
            ("Weather in New York", "New York"),
            ("What's the weather like in San Francisco?", "San Francisco"),
            ("How's the weather at Chicago today?", "Chicago"),
            ("Paris weather forecast", "Paris"),
            ("Weather for London, UK", "London, UK"),
            ("Tell me about weather in Los Angeles, CA", "Los Angeles, CA"),
        ]

        for user_input, expected_location in test_cases:
            location = plugin._extract_location(user_input)
            assert location == expected_location, f"Failed for: {user_input}"

    @pytest.mark.asyncio
    async def test_get_current_weather_success(self, plugin, mock_weather_data):
        """Test successful weather data retrieval."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = mock_weather_data
        mock_response.raise_for_status = Mock()
        plugin.http_client.get.return_value = mock_response

        # Mock cache miss
        plugin.cache.get.return_value = None

        result = await plugin._get_current_weather("New York", "imperial")

        assert result == mock_weather_data
        plugin.http_client.get.assert_called_once()
        plugin.cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_weather_cached(self, plugin, mock_weather_data):
        """Test weather data retrieval from cache."""
        # Mock cache hit
        plugin.cache.get.return_value = mock_weather_data

        result = await plugin._get_current_weather("New York", "imperial")

        assert result == mock_weather_data
        # Should not call API when cached
        plugin.http_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_weather_api_error(self, plugin):
        """Test handling of API errors."""
        # Mock API error
        plugin.http_client.get.side_effect = httpx.HTTPStatusError(
            "API Error",
            request=Mock(),
            response=Mock(status_code=401)
        )
        plugin.cache.get.return_value = None

        with pytest.raises(httpx.HTTPStatusError):
            await plugin._get_current_weather("Invalid", "imperial")

    def test_format_current_weather(self, plugin, mock_weather_data):
        """Test weather data formatting."""
        plugin.config = {"default_units": "imperial"}

        formatted = plugin._format_current_weather(mock_weather_data, "New York")

        assert "New York" in formatted
        assert "72.5°F" in formatted
        assert "partly cloudy" in formatted.lower()
        assert "65%" in formatted  # humidity
        assert "5.2 mph" in formatted  # wind speed

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

    @pytest.fixture
    def _create_mock_task(self):
        """Helper to create mock tasks."""
        def _create(user_input: str):
            task = Mock()
            task.history = [Mock()]
            task.history[0].parts = [Mock()]
            task.history[0].parts[0].text = user_input
            return task
        return _create

    @pytest.mark.asyncio
    async def test_execute_skill_success(self, plugin, mock_weather_data):
        """Test successful skill execution."""
        # Setup mocks
        task = self._create_mock_task("Weather in Boston")
        context = CapabilityContext(
            task=task,
            config=plugin.config,
            state={}
        )

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = mock_weather_data
        mock_response.raise_for_status = Mock()
        plugin.http_client.get.return_value = mock_response
        plugin.cache.get.return_value = None

        result = plugin.execute_capability(context)

        assert result.success
        assert "Boston" in result.content
        assert isinstance(result.state_updates, dict)
        assert "last_location" in result.state_updates

    @pytest.mark.asyncio
    async def test_execute_skill_missing_api_key(self, plugin):
        """Test skill execution without API key."""
        task = self._create_mock_task("Weather in Boston")
        context = CapabilityContext(
            task=task,
            config={},  # No API key
            state={}
        )

        result = plugin.execute_capability(context)

        assert not result.success
        assert "not configured" in result.content.lower()
        assert result.error == "Missing API key"
```

### Testing with Real HTTP Requests

Use the `responses` library to mock HTTP calls:

```python
import responses
import json

class TestWeatherAPIIntegration:
    """Test weather plugin with mocked HTTP responses."""

    @pytest.fixture
    def plugin(self):
        """Create plugin with real HTTP client."""
        import httpx
        plugin = Plugin()
        plugin.config = {"api_key": "test_key", "default_units": "imperial"}
        plugin.http_client = httpx.AsyncClient()
        plugin.cache = None  # Disable caching for tests
        return plugin

    @responses.activate
    @pytest.mark.asyncio
    async def test_real_api_call_success(self, plugin):
        """Test with mocked HTTP response."""
        # Mock the API endpoint
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            json={
                "main": {"temp": 68.0, "humidity": 70},
                "weather": [{"description": "clear sky"}],
                "name": "Boston"
            },
            status=200
        )

        result = await plugin._get_current_weather("Boston", "imperial")

        assert result["main"]["temp"] == 68.0
        assert result["name"] == "Boston"

    @responses.activate
    @pytest.mark.asyncio
    async def test_real_api_call_error(self, plugin):
        """Test API error handling."""
        responses.add(
            responses.GET,
            "https://api.openweathermap.org/data/2.5/weather",
            json={"cod": 401, "message": "Invalid API key"},
            status=401
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await plugin._get_current_weather("Boston", "imperial")

        assert exc_info.value.response.status_code == 401
```

## AI Function Testing

### Testing AI Function Registration

```python
class TestWeatherAIFunctions:
    """Test AI function capabilities."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return Plugin()

    def test_ai_function_registration(self, plugin):
        """Test that AI functions are properly registered."""
        ai_functions = plugin.get_ai_functions()

        # Check we have the expected functions
        function_names = [f.name for f in ai_functions]
        expected_functions = ["get_weather", "get_forecast"]

        for expected in expected_functions:
            assert expected in function_names

        # Validate function schemas
        for func in ai_functions:
            assert "name" in func.__dict__
            assert "description" in func.__dict__
            assert "parameters" in func.__dict__
            assert "handler" in func.__dict__

            # Validate OpenAI function calling schema
            params = func.parameters
            assert params["type"] == "object"
            assert "properties" in params
            assert isinstance(params.get("required", []), list)

    def test_function_parameter_validation(self, plugin):
        """Test AI function parameter schemas."""
        ai_functions = plugin.get_ai_functions()
        get_weather_func = next(f for f in ai_functions if f.name == "get_weather")

        params = get_weather_func.parameters
        properties = params["properties"]

        # Test location parameter
        assert "location" in properties
        assert properties["location"]["type"] == "string"
        assert "description" in properties["location"]

        # Test required fields
        assert "location" in params["required"]

    @pytest.mark.asyncio
    async def test_get_weather_function_execution(self, plugin):
        """Test AI function execution."""
        # Mock dependencies
        plugin.config = {"api_key": "test_key", "default_units": "imperial"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 75.0, "humidity": 60},
            "weather": [{"description": "sunny"}],
            "name": "Miami"
        }
        plugin.http_client.get.return_value = mock_response
        plugin.cache.get.return_value = None

        # Create test context
        task = Mock()
        context = CapabilityContext(
            task=task,
            metadata={
                "parameters": {
                    "location": "Miami",
                    "units": "imperial"
                }
            }
        )

        # Execute the AI function
        result = await plugin._get_weather_function(task, context)

        assert result.success
        assert "Miami" in result.content
        assert "75.0°F" in result.content
        assert result.metadata["function"] == "get_weather"

    @pytest.mark.asyncio
    async def test_ai_function_error_handling(self, plugin):
        """Test AI function error handling."""
        plugin.config = {}  # Missing API key

        task = Mock()
        context = CapabilityContext(
            task=task,
            metadata={"parameters": {"location": "Boston"}}
        )

        result = await plugin._get_weather_function(task, context)

        assert not result.success
        assert "Missing API key" in result.error
        assert "not configured" in result.content.lower()

    @pytest.mark.asyncio
    async def test_ai_function_missing_parameters(self, plugin):
        """Test AI function with missing required parameters."""
        plugin.config = {"api_key": "test_key"}

        task = Mock()
        context = CapabilityContext(
            task=task,
            metadata={"parameters": {}}  # Missing location
        )

        result = await plugin._get_weather_function(task, context)

        assert not result.success
        assert "location" in result.content.lower()
```

### Testing Function Parameter Schemas

```python
def test_function_schema_validation():
    """Test that function schemas are valid OpenAI format."""
    plugin = Plugin()
    ai_functions = plugin.get_ai_functions()

    for func in ai_functions:
        schema = func.parameters

        # Must be object type
        assert schema["type"] == "object"

        # Must have properties
        assert "properties" in schema
        assert isinstance(schema["properties"], dict)

        # Required must be a list
        if "required" in schema:
            assert isinstance(schema["required"], list)

        # Each property must have type and description
        for prop_name, prop_schema in schema["properties"].items():
            assert "type" in prop_schema
            assert "description" in prop_schema

            # Validate enum fields
            if "enum" in prop_schema:
                assert isinstance(prop_schema["enum"], list)
                assert len(prop_schema["enum"]) > 0
```

## Integration Testing

### Testing with AgentUp Components

```python
class TestWeatherPluginIntegration:
    """Test plugin integration with AgentUp systems."""

    @pytest.fixture
    def plugin_manager(self):
        """Create plugin manager with weather plugin."""
        from agent.plugins import PluginManager

        manager = PluginManager()
        plugin = Plugin()

        # Register plugin manually
        manager.pm.register(plugin, name="weather_plugin")

        # Register skill info
        capability_info = plugin.register_capability()
        manager.skills[skill_info.id] = skill_info
        manager.skill_to_plugin[skill_info.id] = "weather_plugin"
        manager.skill_hooks[skill_info.id] = plugin

        return manager

    def test_plugin_manager_integration(self, plugin_manager):
        """Test plugin works with plugin manager."""
        # Test skill is registered
        assert "weather" in plugin_manager.skills

        # Test skill retrieval
        skill = plugin_manager.get_skill("weather")
        assert skill is not None
        assert skill.name == "Weather Information"

    @pytest.mark.asyncio
    async def test_plugin_execution_via_manager(self, plugin_manager):
        """Test executing skill through plugin manager."""
        # Setup plugin dependencies
        weather_plugin = plugin_manager.skill_hooks["weather"]
        weather_plugin.config = {"api_key": "test_key"}
        weather_plugin.http_client = AsyncMock()
        weather_plugin.cache = AsyncMock()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 70.0},
            "weather": [{"description": "cloudy"}],
            "name": "Seattle"
        }
        weather_plugin.http_client.get.return_value = mock_response
        weather_plugin.cache.get.return_value = None

        # Create task context
        task = Mock()
        task.history = [Mock()]
        task.history[0].parts = [Mock()]
        task.history[0].parts[0].text = "Weather in Seattle"

        context = CapabilityContext(
            task=task,
            config={"api_key": "test_key"},
            state={}
        )

        # Execute through manager
        result = plugin_manager.execute_skill("weather", context)

        assert result.success
        assert "Seattle" in result.content

    def test_ai_function_registration_via_manager(self, plugin_manager):
        """Test AI functions are available through manager."""
        ai_functions = plugin_manager.get_ai_functions("weather")

        assert len(ai_functions) > 0
        function_names = [f.name for f in ai_functions]
        assert "get_weather" in function_names

    @pytest.mark.asyncio
    async def test_function_registry_integration(self):
        """Test integration with FunctionRegistry."""
        from agent.plugins.adapter import PluginAdapter
        from agentup.core.dispatcher import FunctionRegistry

        # Create adapter and registry
        adapter = PluginAdapter()
        registry = FunctionRegistry()

        # Integrate plugins
        adapter.integrate_with_function_registry(registry)

        # Test functions are registered
        schemas = registry.get_function_schemas()
        assert len(schemas) > 0

        # Test function names
        function_names = [s["name"] for s in schemas]
        # Should include any AI functions from discovered plugins
```

## Performance Testing

### Load Testing

```python
import asyncio
import time

class TestWeatherPluginPerformance:
    """Performance tests for weather plugin."""

    @pytest.fixture
    def plugin(self):
        """Create optimized plugin for performance testing."""
        plugin = Plugin()
        plugin.config = {"api_key": "test_key", "cache_duration": 300}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()
        return plugin

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, plugin):
        """Test plugin handles concurrent requests."""
        # Mock fast API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 72.0},
            "weather": [{"description": "clear"}],
        }
        plugin.http_client.get.return_value = mock_response
        plugin.cache.get.return_value = None

        # Create multiple concurrent requests
        tasks = []
        for i in range(50):
            task = asyncio.create_task(
                plugin._get_current_weather(f"City{i}", "imperial")
            )
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All requests should succeed
        assert len(results) == 50

        # Should complete within reasonable time (adjust based on expectations)
        assert end_time - start_time < 2.0

    @pytest.mark.asyncio
    async def test_caching_performance(self, plugin):
        """Test caching improves performance."""
        # First call - cache miss
        plugin.cache.get.return_value = None

        start_time = time.time()
        await plugin._get_current_weather("Boston", "imperial")
        first_call_time = time.time() - start_time

        # Second call - cache hit
        plugin.cache.get.return_value = {"cached": "data"}

        start_time = time.time()
        await plugin._get_current_weather("Boston", "imperial")
        second_call_time = time.time() - start_time

        # Cached call should be significantly faster
        assert second_call_time < first_call_time * 0.1

    def test_memory_usage(self, plugin):
        """Test plugin doesn't leak memory."""
        import tracemalloc

        tracemalloc.start()

        # Simulate many plugin operations
        for i in range(1000):
            task = Mock()
            task.history = [Mock()]
            task.history[0].parts = [Mock()]
            task.history[0].parts[0].text = f"Weather in City{i}"

            context = CapabilityContext(task=task)
            plugin.can_handle_task(context)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memory usage should be reasonable (adjust threshold as needed)
        assert peak < 10 * 1024 * 1024  # 10MB peak
```

## End-to-End Testing

### Full Workflow Tests

```python
class TestWeatherPluginE2E:
    """End-to-end tests for weather plugin."""

    @pytest.mark.asyncio
    async def test_complete_weather_workflow(self):
        """Test complete user interaction workflow."""
        # This test would require a running AgentUp agent
        # For demonstration, we'll simulate the key components

        # 1. User sends request
        user_request = "What's the weather like in Paris?"

        # 2. Plugin routing
        plugin = Plugin()
        task = Mock()
        task.history = [Mock()]
        task.history[0].parts = [Mock()]
        task.history[0].parts[0].text = user_request

        context = CapabilityContext(task=task)
        confidence = plugin.can_handle_task(context)
        assert confidence > 0.8  # Should be routed to weather plugin

        # 3. Plugin execution
        plugin.config = {"api_key": "test_key"}
        plugin.http_client = AsyncMock()
        plugin.cache = AsyncMock()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 18.0, "humidity": 65},
            "weather": [{"description": "light rain"}],
            "name": "Paris"
        }
        plugin.http_client.get.return_value = mock_response
        plugin.cache.get.return_value = None

        context.config = plugin.config
        context.state = {}

        result = plugin.execute_capability(context)

        # 4. Verify response
        assert result.success
        assert "Paris" in result.content
        assert "18.0°C" in result.content or "64.4°F" in result.content
        assert "rain" in result.content.lower()

    @pytest.mark.asyncio
    async def test_ai_function_workflow(self):
        """Test AI function calling workflow."""
        plugin = Plugin()
        plugin.config = {"api_key": "test_key"}
        plugin.http_client = AsyncMock()

        # Simulate LLM function call
        task = Mock()
        context = CapabilityContext(
            task=task,
            metadata={
                "parameters": {
                    "location": "Tokyo",
                    "units": "metric"
                }
            }
        )

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "main": {"temp": 25.0},
            "weather": [{"description": "sunny"}],
            "name": "Tokyo"
        }
        plugin.http_client.get.return_value = mock_response
        plugin.cache = AsyncMock()
        plugin.cache.get.return_value = None

        result = await plugin._get_weather_function(task, context)

        assert result.success
        assert "Tokyo" in result.content
        assert "25.0°C" in result.content
```

## Test Data Management

### Using Factory Boy for Test Data

```python
import factory
from datetime import datetime

class WeatherDataFactory(factory.Factory):
    """Factory for generating test weather data."""

    class Meta:
        model = dict

    main = factory.SubFactory('tests.factories.MainWeatherFactory')
    weather = factory.List([
        factory.SubFactory('tests.factories.WeatherDescriptionFactory')
    ])
    wind = factory.SubFactory('tests.factories.WindFactory')
    name = factory.Faker('city')

class MainWeatherFactory(factory.Factory):
    """Factory for main weather data."""

    class Meta:
        model = dict

    temp = factory.Faker('pyfloat', min_value=-30, max_value=45)
    feels_like = factory.LazyAttribute(lambda obj: obj.temp + factory.Faker('pyfloat', min_value=-5, max_value=5).generate())
    humidity = factory.Faker('pyint', min_value=20, max_value=100)
    pressure = factory.Faker('pyfloat', min_value=980, max_value=1050)

class WeatherDescriptionFactory(factory.Factory):
    """Factory for weather descriptions."""

    class Meta:
        model = dict

    main = factory.Faker('random_element', elements=['Clear', 'Clouds', 'Rain', 'Snow'])
    description = factory.LazyAttribute(lambda obj: f"{obj.main.lower()} sky")

# Usage in tests
def test_with_factory_data(plugin):
    """Test using factory-generated data."""
    weather_data = WeatherDataFactory()

    formatted = plugin._format_current_weather(weather_data, "Test City")

    assert "Test City" in formatted
    assert str(weather_data['main']['temp']) in formatted
```

### Test Configuration Management

```python
# conftest.py
import pytest
import os
from unittest.mock import Mock

@pytest.fixture
def test_config():
    """Provide test configuration."""
    return {
        "api_key": "test_key_32_characters_long_xxx",
        "default_units": "imperial",
        "cache_duration": 300,
        "include_forecast": True,
    }

@pytest.fixture
def mock_http_client():
    """Provide mocked HTTP client."""
    client = Mock()
    client.get = Mock()
    return client

@pytest.fixture
def mock_cache():
    """Provide mocked cache."""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock()
    return cache

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    os.environ['AGENTUP_TEST_MODE'] = 'true'
    os.environ['WEATHER_API_KEY'] = 'test_key'
    yield
    # Cleanup
    os.environ.pop('AGENTUP_TEST_MODE', None)
    os.environ.pop('WEATHER_API_KEY', None)
```

## Continuous Integration Testing

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Plugin

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[test]"

    - name: Run tests
      run: |
        pytest tests/ -v --cov=weather_plugin --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

## Best Practices

### 1. Test Organization

```python
# Organize tests by functionality
tests/
├── unit/
│   ├── test_plugin_core.py
│   ├── test_routing.py
│   └── test_formatting.py
├── integration/
│   ├── test_api_integration.py
│   └── test_plugin_manager.py
├── ai_functions/
│   ├── test_function_registration.py
│   └── test_function_execution.py
└── e2e/
    └── test_workflows.py
```

### 2. Mock Strategy

```python
# Use dependency injection for easier testing
class Plugin:
    def __init__(self, http_client=None, cache=None):
        self.http_client = http_client or httpx.AsyncClient()
        self.cache = cache

    # This makes testing easier:
    # plugin = Plugin(http_client=mock_client, cache=mock_cache)
```

### 3. Test Coverage

```bash
# Measure test coverage
pytest --cov=weather_plugin --cov-report=html tests/

# Enforce minimum coverage
pytest --cov=weather_plugin --cov-fail-under=90 tests/
```

### 4. Testing Configuration

```python
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --disable-warnings
    -ra
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

This comprehensive testing guide ensures your plugins are reliable, performant, and maintainable. Regular testing catches issues early and gives users confidence in your plugin's quality.