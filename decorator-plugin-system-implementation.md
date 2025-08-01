# Decorator-Based Plugin System Implementation

## Overview

This document outlines a complete redesign of the AgentUp plugin system using decorators to replace the current 11-hook Pluggy-based approach. The new system prioritizes developer experience with intuitive decorators while maintaining all the power and flexibility of the current architecture.

## Core Architecture

### The @capability Decorator

The `@capability` decorator is the cornerstone of the new system. It collects metadata about plugin capabilities and automatically handles registration, routing, and execution.

```python
def capability(
    id: str,
    name: str | None = None,
    description: str | None = None,
    scopes: list[str] | None = None,
    ai_function: bool = False,
    ai_parameters: dict | None = None,
    input_mode: str = "text",
    output_mode: str = "text",
    tags: list[str] | None = None,
    priority: int = 50,
    middleware: list[dict] | None = None,
    config_schema: dict | None = None,
    state_schema: dict | None = None,
    streaming: bool = False,
    multimodal: bool = False
) -> Callable:
    """
    Decorator that marks a method as a plugin capability.
    
    This decorator replaces the need for manual hook implementations by
    automatically generating all necessary plugin metadata and handlers.
    """
```

### Internal Decorator Implementation

```python
import functools
from typing import Any, Callable, Dict, List
from dataclasses import dataclass, field

@dataclass
class CapabilityMetadata:
    """Stores all metadata for a capability"""
    id: str
    name: str
    description: str
    method_name: str
    scopes: list[str] = field(default_factory=list)
    ai_function: bool = False
    ai_parameters: dict = field(default_factory=dict)
    input_mode: str = "text"
    output_mode: str = "text"
    tags: list[str] = field(default_factory=list)
    priority: int = 50
    middleware: list[dict] = field(default_factory=list)
    config_schema: dict = field(default_factory=dict)
    state_schema: dict = field(default_factory=dict)
    streaming: bool = False
    multimodal: bool = False
    handler: Callable | None = None

def capability(
    id: str,
    name: str | None = None,
    description: str | None = None,
    scopes: list[str] | None = None,
    ai_function: bool = False,
    ai_parameters: dict | None = None,
    **kwargs
) -> Callable:
    def decorator(func: Callable) -> Callable:
        # Create metadata object
        metadata = CapabilityMetadata(
            id=id,
            name=name or id.replace("_", " ").title(),
            description=description or func.__doc__ or f"Capability {id}",
            method_name=func.__name__,
            scopes=scopes or [],
            ai_function=ai_function,
            ai_parameters=ai_parameters or {},
            handler=func,
            **kwargs
        )
        
        # Store metadata on the function
        if not hasattr(func, '_agentup_capabilities'):
            func._agentup_capabilities = []
        func._agentup_capabilities.append(metadata)
        
        # Mark the function as a capability handler
        func._is_agentup_capability = True
        
        return func
    return decorator
```

## New Plugin Base Classes

### Plugin Base Class

```python
from abc import ABC
from typing import Any, Dict, List
import inspect

class Plugin(ABC):
    """
    Base class for all AgentUp plugins.
    
    This class automatically discovers @capability decorated methods
    and handles all plugin registration and lifecycle management.
    """
    
    def __init__(self):
        self._capabilities: Dict[str, CapabilityMetadata] = {}
        self._services: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}
        self._state: Dict[str, Any] = {}
        
        # Auto-discover capabilities
        self._discover_capabilities()
    
    def _discover_capabilities(self):
        """Automatically discover all @capability decorated methods"""
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_is_agentup_capability'):
                for capability_meta in method._agentup_capabilities:
                    # Bind the handler to this instance
                    capability_meta.handler = method
                    self._capabilities[capability_meta.id] = capability_meta
    
    # === Core Plugin Interface ===
    
    async def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a specific capability by ID"""
        if capability_id not in self._capabilities:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found",
                success=False,
                error="Capability not found"
            )
        
        capability = self._capabilities[capability_id]
        try:
            # Call the decorated method
            result = await capability.handler(context)
            
            # Handle different return types
            if isinstance(result, CapabilityResult):
                return result
            elif isinstance(result, str):
                return CapabilityResult(content=result, success=True)
            else:
                return CapabilityResult(content=str(result), success=True)
                
        except Exception as e:
            logger.error(f"Error executing capability {capability_id}: {e}")
            return CapabilityResult(
                content=f"Error executing capability: {str(e)}",
                success=False,
                error=str(e)
            )
    
    def get_capability_definitions(self) -> List[CapabilityDefinition]:
        """Get all capability definitions for this plugin"""
        definitions = []
        for capability_meta in self._capabilities.values():
            # Convert metadata to CapabilityDefinition
            definition = CapabilityDefinition(
                id=capability_meta.id,
                name=capability_meta.name,
                version="1.0.0",  # TODO: Get from plugin metadata
                description=capability_meta.description,
                capabilities=self._determine_capability_types(capability_meta),
                input_mode=capability_meta.input_mode,
                output_mode=capability_meta.output_mode,
                tags=capability_meta.tags,
                priority=capability_meta.priority,
                config_schema=capability_meta.config_schema,
                required_scopes=capability_meta.scopes
            )
            definitions.append(definition)
        return definitions
    
    def _determine_capability_types(self, meta: CapabilityMetadata) -> List[CapabilityType]:
        """Determine capability types from metadata"""
        types = [CapabilityType.TEXT]  # Default
        
        if meta.ai_function:
            types.append(CapabilityType.AI_FUNCTION)
        if meta.streaming:
            types.append(CapabilityType.STREAMING)
        if meta.multimodal:
            types.append(CapabilityType.MULTIMODAL)
        if meta.state_schema:
            types.append(CapabilityType.STATEFUL)
            
        return types
    
    def get_ai_functions(self, capability_id: str | None = None) -> List[AIFunction]:
        """Get AI functions for capabilities"""
        functions = []
        
        capabilities = [self._capabilities[capability_id]] if capability_id else self._capabilities.values()
        
        for capability_meta in capabilities:
            if capability_meta.ai_function:
                ai_func = AIFunction(
                    name=capability_meta.id,
                    description=capability_meta.description,
                    parameters=capability_meta.ai_parameters,
                    handler=self._create_ai_function_wrapper(capability_meta)
                )
                functions.append(ai_func)
        
        return functions
    
    def _create_ai_function_wrapper(self, capability_meta: CapabilityMetadata):
        """Create wrapper for AI function calls"""
        async def wrapper(task, context: CapabilityContext):
            # Extract AI function parameters from context
            params = context.metadata.get("parameters", {})
            
            # Create new context with parameters
            ai_context = CapabilityContext(
                task=task,
                config=context.config,
                services=context.services,
                state=context.state,
                metadata={"parameters": params, "capability_id": capability_meta.id}
            )
            
            return await capability_meta.handler(ai_context)
        
        return wrapper
    
    # === Service and Configuration Management ===
    
    def configure_services(self, services: Dict[str, Any]):
        """Store services for use by capabilities"""
        self._services.update(services)
    
    def configure(self, config: Dict[str, Any]):
        """Configure the plugin"""
        self._config.update(config)
    
    def get_service(self, name: str) -> Any:
        """Get a service by name"""
        return self._services.get(name)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
```

## Hook System Replacement

### Current Hook Functions and Their Decorator Equivalents

Here's how each of the 11 current hook functions is replaced or simplified by the decorator system:

#### 1. `register_capability` → Automatic Discovery

**Old way:**
```python
@hookimpl
def register_capability(self) -> CapabilityDefinition:
    return CapabilityDefinition(id="weather", name="Weather", ...)
```

**New way:**
```python
@capability("weather", name="Weather Lookup", scopes=["web:search"])
async def get_weather(self, context: CapabilityContext) -> str:
    return "Sunny, 72°F"
```

The decorator automatically creates the `CapabilityDefinition` from metadata.

#### 2. `validate_config` → Schema-based Validation

**Old way:**
```python
@hookimpl
def validate_config(self, config: dict) -> PluginValidationResult:
    # Manual validation logic
    errors = []
    if "api_key" not in config:
        errors.append("API key required")
    return PluginValidationResult(valid=len(errors) == 0, errors=errors)
```

**New way:**
```python
@capability(
    "weather",
    config_schema={
        "type": "object",
        "properties": {
            "api_key": {"type": "string", "description": "Weather API key"}
        },
        "required": ["api_key"]
    }
)
async def get_weather(self, context: CapabilityContext) -> str:
    api_key = context.config["api_key"]  # Automatically validated
    return await self.fetch_weather(api_key)
```

The framework automatically validates configuration against the schema.

#### 3. `can_handle_task` → Automatic Routing

**Old way:**
```python
@hookimpl
def can_handle_task(self, context: CapabilityContext) -> float:
    content = self._extract_content(context)
    if "weather" in content.lower():
        return 0.8
    return 0.0
```

**New way:**
```python
@capability(
    "weather",
    tags=["weather", "forecast", "temperature"],
    priority=80  # High priority for weather queries
)
async def get_weather(self, context: CapabilityContext) -> str:
    # Framework handles routing based on tags and priority
    return await self.fetch_weather()
```

The framework uses tags, priority, and semantic matching for routing.

#### 4. `execute_capability` → Direct Method Execution

**Old way:**
```python
@hookimpl
def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
    # Manual routing to different handlers
    capability_id = context.metadata.get("capability_id")
    if capability_id == "weather":
        return self._handle_weather(context)
    elif capability_id == "forecast":
        return self._handle_forecast(context)
```

**New way:**
```python
@capability("weather")
async def get_weather(self, context: CapabilityContext) -> str:
    return "Current weather"

@capability("forecast")
async def get_forecast(self, context: CapabilityContext) -> str:
    return "Weather forecast"
```

Framework automatically routes to the correct method based on capability ID.

#### 5. `get_ai_functions` → Automatic AI Function Generation

**Old way:**
```python
@hookimpl
def get_ai_functions(self) -> List[AIFunction]:
    return [
        AIFunction(
            name="get_weather",
            description="Get current weather",
            parameters={"location": {"type": "string"}},
            handler=self._weather_handler
        )
    ]
```

**New way:**
```python
@capability(
    "weather",
    ai_function=True,
    ai_parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name"}
        }
    }
)
async def get_weather(self, context: CapabilityContext) -> str:
    location = context.metadata.get("parameters", {}).get("location")
    return f"Weather in {location}: Sunny"
```

The `ai_function=True` parameter automatically creates the AI function definition.

#### 6. `get_middleware_config` → Declarative Middleware

**Old way:**
```python
@hookimpl
def get_middleware_config(self) -> List[dict]:
    return [
        {"type": "rate_limit", "requests_per_minute": 100},
        {"type": "cache", "ttl": 300}
    ]
```

**New way:**
```python
@capability(
    "weather",
    middleware=[
        {"type": "rate_limit", "requests_per_minute": 100},
        {"type": "cache", "ttl": 300}
    ]
)
async def get_weather(self, context: CapabilityContext) -> str:
    return "Weather data"
```

Middleware is declared directly in the decorator.

#### 7. `get_state_schema` → Declarative State Management

**Old way:**
```python
@hookimpl
def get_state_schema(self) -> dict:
    return {
        "type": "object",
        "properties": {
            "last_location": {"type": "string"},
            "cache_timestamp": {"type": "number"}
        }
    }
```

**New way:**
```python
@capability(
    "weather",
    state_schema={
        "type": "object",
        "properties": {
            "last_location": {"type": "string"},
            "cache_timestamp": {"type": "number"}
        }
    }
)
async def get_weather(self, context: CapabilityContext) -> str:
    # Access state through context
    last_location = context.state.get("last_location")
    context.state_updates["last_location"] = "New York"
    return "Weather data"
```

State schema is declared in the decorator, and state is managed through the context.

#### 8. `configure_services` → Plugin-Level Configuration

**Old way:**
```python
@hookimpl
def configure_services(self, services: dict) -> None:
    self.llm_service = services.get("llm")
    self.cache_service = services.get("cache")
```

**New way:**
```python
class WeatherPlugin(Plugin):
    def configure_services(self, services: dict):
        super().configure_services(services)
        # Services automatically available via self.get_service()
    
    @capability("weather")
    async def get_weather(self, context: CapabilityContext) -> str:
        llm = self.get_service("llm")
        cache = self.get_service("cache")
        return "Weather data"
```

Services are managed at the plugin level and accessible in all capabilities.

#### 9. `wrap_execution` → Middleware Chain

**Old way:**
```python
@hookimpl
def wrap_execution(self, context: CapabilityContext, next_handler) -> CapabilityResult:
    # Pre-processing
    start_time = time.time()
    
    # Execute
    result = next_handler(context)
    
    # Post-processing
    execution_time = time.time() - start_time
    result.metadata["execution_time"] = execution_time
    
    return result
```

**New way:**
```python
@capability(
    "weather",
    middleware=[
        {"type": "timing", "enabled": True},
        {"type": "logging", "level": "info"}
    ]
)
async def get_weather(self, context: CapabilityContext) -> str:
    # Middleware automatically wraps execution
    return "Weather data"
```

Middleware is handled declaratively through the framework's middleware system.

#### 10. `on_install` → Plugin Lifecycle Hooks

**Old way:**
```python
@hookimpl
def on_install(self, install_path: str) -> None:
    # Setup logic
    self.download_models()
    self.create_directories()
```

**New way:**
```python
class WeatherPlugin(Plugin):
    async def on_install(self, install_path: str):
        """Called when plugin is installed"""
        await self.download_weather_models()
        await self.setup_cache_directory()
```

Lifecycle hooks are optional methods on the plugin class.

#### 11. `on_uninstall` → Plugin Lifecycle Hooks

**Old way:**
```python
@hookimpl
def on_uninstall(self) -> None:
    # Cleanup logic
    self.cleanup_temp_files()
```

**New way:**
```python
class WeatherPlugin(Plugin):
    async def on_uninstall(self):
        """Called when plugin is uninstalled"""
        await self.cleanup_weather_cache()
        await self.remove_temp_files()
```

#### 12. `get_health_status` → Plugin Health Monitoring

**Old way:**
```python
@hookimpl
def get_health_status(self) -> dict:
    return {
        "status": "healthy",
        "api_connected": self.api_client.is_connected(),
        "cache_size": len(self.cache)
    }
```

**New way:**
```python
class WeatherPlugin(Plugin):
    async def get_health_status(self) -> dict:
        """Return plugin health information"""
        return {
            "status": "healthy",
            "api_connected": await self.check_api_connection(),
            "capabilities_loaded": len(self._capabilities)
        }
```

## Complete Plugin Examples

### Simple Single-Capability Plugin

```python
from agentup.plugins import Plugin, capability, CapabilityContext

class GreetingPlugin(Plugin):
    """Simple greeting plugin with one capability"""
    
    @capability(
        "greet",
        name="Greeting",
        description="Generate personalized greetings",
        scopes=["api:read"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Person's name"},
                "style": {"type": "string", "enum": ["casual", "formal"], "description": "Greeting style"}
            },
            "required": ["name"]
        }
    )
    async def greet_person(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        name = params.get("name", "Friend")
        style = params.get("style", "casual")
        
        if style == "formal":
            return f"Good day, {name}. How may I assist you today?"
        else:
            return f"Hey {name}! How's it going?"
```

### Multi-Capability Plugin with Shared State

```python
from agentup.plugins import Plugin, capability, CapabilityContext
import aiohttp
import asyncio

class WeatherPlugin(Plugin):
    """Weather plugin with multiple related capabilities"""
    
    def __init__(self):
        super().__init__()
        self.api_client = None
    
    async def on_install(self, install_path: str):
        """Initialize API client"""
        self.api_client = aiohttp.ClientSession()
    
    async def on_uninstall(self):
        """Cleanup resources"""
        if self.api_client:
            await self.api_client.close()
    
    @capability(
        "current_weather",
        name="Current Weather",
        description="Get current weather conditions for a location",
        scopes=["web:search"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or coordinates"}
            },
            "required": ["location"]
        },
        middleware=[
            {"type": "cache", "ttl": 300},  # Cache for 5 minutes
            {"type": "rate_limit", "requests_per_minute": 60}
        ],
        state_schema={
            "type": "object",
            "properties": {
                "last_location": {"type": "string"},
                "last_update": {"type": "number"}
            }
        }
    )
    async def get_current_weather(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        location = params.get("location")
        
        # Update state
        context.state_updates["last_location"] = location
        context.state_updates["last_update"] = time.time()
        
        # Get API key from config
        api_key = self.get_config("api_key")
        if not api_key:
            return "Weather API key not configured"
        
        # Fetch weather data
        weather_data = await self._fetch_weather_data(location, api_key)
        return f"Current weather in {location}: {weather_data['description']}, {weather_data['temperature']}°F"
    
    @capability(
        "weather_forecast",
        name="Weather Forecast",
        description="Get weather forecast for a location",
        scopes=["web:search"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "days": {"type": "integer", "minimum": 1, "maximum": 7, "description": "Number of days"}
            },
            "required": ["location"]
        },
        middleware=[
            {"type": "cache", "ttl": 1800}  # Cache for 30 minutes
        ]
    )
    async def get_weather_forecast(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        location = params.get("location")
        days = params.get("days", 3)
        
        api_key = self.get_config("api_key")
        forecast_data = await self._fetch_forecast_data(location, days, api_key)
        
        # Format forecast
        forecast_text = f"{days}-day forecast for {location}:\n"
        for day in forecast_data:
            forecast_text += f"- {day['date']}: {day['description']}, High: {day['high']}°F, Low: {day['low']}°F\n"
        
        return forecast_text
    
    @capability(
        "weather_alerts",
        name="Weather Alerts",
        description="Get weather alerts for a location",
        scopes=["web:search"],
        tags=["weather", "alerts", "emergency"]
    )
    async def get_weather_alerts(self, context: CapabilityContext) -> str:
        # Get location from previous state if not provided
        last_location = context.state.get("last_location")
        if not last_location:
            return "No location specified and no previous location in state"
        
        api_key = self.get_config("api_key")
        alerts = await self._fetch_weather_alerts(last_location, api_key)
        
        if not alerts:
            return f"No weather alerts for {last_location}"
        
        alert_text = f"Weather alerts for {last_location}:\n"
        for alert in alerts:
            alert_text += f"- {alert['title']}: {alert['description']}\n"
        
        return alert_text
    
    # === Private Helper Methods ===
    
    async def _fetch_weather_data(self, location: str, api_key: str) -> dict:
        """Fetch current weather data from API"""
        # Implementation would make actual API call
        return {
            "description": "Partly cloudy",
            "temperature": 72
        }
    
    async def _fetch_forecast_data(self, location: str, days: int, api_key: str) -> list:
        """Fetch forecast data from API"""
        # Implementation would make actual API call
        return [
            {"date": "2024-01-01", "description": "Sunny", "high": 75, "low": 60},
            {"date": "2024-01-02", "description": "Cloudy", "high": 70, "low": 55}
        ]
    
    async def _fetch_weather_alerts(self, location: str, api_key: str) -> list:
        """Fetch weather alerts from API"""
        # Implementation would make actual API call
        return []
    
    async def get_health_status(self) -> dict:
        """Check plugin health"""
        health = {
            "status": "healthy",
            "capabilities": len(self._capabilities),
            "api_client": self.api_client is not None
        }
        
        # Test API connection
        try:
            api_key = self.get_config("api_key")
            if api_key:
                # Test API call
                await self._test_api_connection(api_key)
                health["api_connected"] = True
            else:
                health["api_connected"] = False
                health["status"] = "degraded"
                health["issues"] = ["API key not configured"]
        except Exception as e:
            health["api_connected"] = False
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
```

### AI-Powered Analysis Plugin

```python
from agentup.plugins import Plugin, capability, CapabilityContext
from agentup.multimodal import MultiModalHelper

class AnalysisPlugin(Plugin):
    """AI-powered content analysis plugin"""
    
    @capability(
        "analyze_text",
        name="Text Analysis",
        description="Analyze text content for sentiment, topics, and insights",
        scopes=["ai:analyze"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze"},
                "analysis_type": {
                    "type": "string",
                    "enum": ["sentiment", "topics", "summary", "all"],
                    "description": "Type of analysis to perform"
                }
            },
            "required": ["text"]
        },
        multimodal=False,
        streaming=False
    )
    async def analyze_text(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        text = params.get("text")
        analysis_type = params.get("analysis_type", "all")
        
        # Get LLM service
        llm = self.get_service("llm")
        if not llm:
            return "LLM service not available"
        
        # Create analysis prompt
        if analysis_type == "sentiment":
            prompt = f"Analyze the sentiment of this text: {text}"
        elif analysis_type == "topics":
            prompt = f"Extract the main topics from this text: {text}"
        elif analysis_type == "summary":
            prompt = f"Provide a concise summary of this text: {text}"
        else:
            prompt = f"Analyze this text for sentiment, main topics, and provide a summary: {text}"
        
        # Use LLM for analysis
        result = await llm.generate(prompt)
        return result
    
    @capability(
        "analyze_image",
        name="Image Analysis",
        description="Analyze images for content, objects, and text",
        scopes=["ai:analyze", "multimodal:read"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "image_data": {"type": "string", "description": "Base64 encoded image data"},
                "analysis_focus": {
                    "type": "string",
                    "enum": ["objects", "text", "scene", "all"],
                    "description": "What to focus on in the analysis"
                }
            },
            "required": ["image_data"]
        },
        multimodal=True
    )
    async def analyze_image(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        image_data = params.get("image_data")
        focus = params.get("analysis_focus", "all")
        
        # Get multimodal LLM service
        llm = self.get_service("multimodal_llm")
        if not llm:
            return "Multimodal LLM service not available"
        
        # Use multimodal helper to process image
        helper = MultiModalHelper()
        image_message = helper.create_image_message(image_data)
        
        # Create analysis prompt based on focus
        if focus == "objects":
            prompt = "Identify and describe the main objects in this image."
        elif focus == "text":
            prompt = "Extract and transcribe any text visible in this image."
        elif focus == "scene":
            prompt = "Describe the overall scene and setting in this image."
        else:
            prompt = "Analyze this image thoroughly, describing objects, text, scene, and any notable details."
        
        # Analyze image
        result = await llm.generate_multimodal([
            {"type": "text", "text": prompt},
            image_message
        ])
        
        return result
    
    @capability(
        "compare_documents",
        name="Document Comparison",
        description="Compare two documents and highlight differences",
        scopes=["ai:analyze", "files:read"],
        ai_function=True,
        ai_parameters={
            "type": "object",
            "properties": {
                "document1": {"type": "string", "description": "First document content"},
                "document2": {"type": "string", "description": "Second document content"},
                "comparison_type": {
                    "type": "string",
                    "enum": ["content", "structure", "sentiment", "comprehensive"],
                    "description": "Type of comparison to perform"
                }
            },
            "required": ["document1", "document2"]
        }
    )
    async def compare_documents(self, context: CapabilityContext) -> str:
        params = context.metadata.get("parameters", {})
        doc1 = params.get("document1")
        doc2 = params.get("document2")
        comparison_type = params.get("comparison_type", "comprehensive")
        
        llm = self.get_service("llm")
        
        if comparison_type == "content":
            prompt = f"""Compare the content of these two documents:

Document 1:
{doc1}

Document 2:
{doc2}

Focus on differences in information, facts, and key points."""
        
        elif comparison_type == "structure":
            prompt = f"""Compare the structure and organization of these two documents:

Document 1:
{doc1}

Document 2:
{doc2}

Focus on differences in formatting, sections, and organization."""
        
        elif comparison_type == "sentiment":
            prompt = f"""Compare the tone and sentiment of these two documents:

Document 1:
{doc1}

Document 2:
{doc2}

Focus on differences in tone, emotion, and perspective."""
        
        else:  # comprehensive
            prompt = f"""Perform a comprehensive comparison of these two documents:

Document 1:
{doc1}

Document 2:
{doc2}

Analyze differences in content, structure, tone, and any other notable aspects."""
        
        result = await llm.generate(prompt)
        return result
```

## Plugin Registration and Discovery

### Automatic Plugin Discovery

```python
class PluginRegistry:
    """
    New plugin registry that works with decorator-based plugins
    """
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.capabilities: Dict[str, CapabilityMetadata] = {}
        self.capability_to_plugin: Dict[str, str] = {}
    
    def register_plugin(self, plugin_id: str, plugin_instance: Plugin):
        """Register a plugin instance"""
        self.plugins[plugin_id] = plugin_instance
        
        # Register all capabilities from the plugin
        for capability_id, capability_meta in plugin_instance._capabilities.items():
            self.capabilities[capability_id] = capability_meta
            self.capability_to_plugin[capability_id] = plugin_id
    
    def discover_plugins(self):
        """Discover plugins from entry points"""
        import importlib.metadata
        
        # Get all entry points in the agentup.plugins group
        entry_points = importlib.metadata.entry_points()
        if hasattr(entry_points, "select"):
            plugin_entries = entry_points.select(group="agentup.plugins")
        else:
            plugin_entries = entry_points.get("agentup.plugins", [])
        
        for entry_point in plugin_entries:
            try:
                # Load plugin class
                plugin_class = entry_point.load()
                
                # Instantiate plugin
                plugin_instance = plugin_class()
                
                # Register plugin
                self.register_plugin(entry_point.name, plugin_instance)
                
                logger.info(f"Registered plugin '{entry_point.name}' with {len(plugin_instance._capabilities)} capabilities")
                
            except Exception as e:
                logger.error(f"Failed to load plugin {entry_point.name}: {e}")
    
    async def execute_capability(self, capability_id: str, context: CapabilityContext) -> CapabilityResult:
        """Execute a capability by ID"""
        if capability_id not in self.capabilities:
            return CapabilityResult(
                content=f"Capability '{capability_id}' not found",
                success=False,
                error="Capability not found"
            )
        
        plugin_id = self.capability_to_plugin[capability_id]
        plugin = self.plugins[plugin_id]
        
        return await plugin.execute_capability(capability_id, context)
    
    def get_ai_functions(self) -> List[AIFunction]:
        """Get all AI functions from all plugins"""
        ai_functions = []
        for plugin in self.plugins.values():
            ai_functions.extend(plugin.get_ai_functions())
        return ai_functions
```

### Plugin Configuration Generation

The new system can automatically generate YAML configuration from plugin metadata:

```python
def generate_plugin_config(plugin_instance: Plugin) -> dict:
    """Generate YAML configuration for a plugin"""
    capabilities_config = []
    
    for capability_id, capability_meta in plugin_instance._capabilities.items():
        cap_config = {
            "capability_id": capability_id,
            "name": capability_meta.name,
            "description": capability_meta.description,
            "required_scopes": capability_meta.scopes,
            "enabled": True
        }
        
        if capability_meta.config_schema:
            cap_config["config_schema"] = capability_meta.config_schema
        
        if capability_meta.middleware:
            cap_config["middleware_override"] = capability_meta.middleware
        
        capabilities_config.append(cap_config)
    
    return {
        "plugin_id": plugin_instance.__class__.__name__.lower().replace("plugin", ""),
        "name": plugin_instance.__class__.__name__,
        "description": plugin_instance.__class__.__doc__ or "Plugin description",
        "capabilities": capabilities_config
    }
```

## Migration from Current System

### No Backward Compatibility

The new decorator system completely replaces the current hook-based system. There is no backward compatibility layer. All existing plugins must be rewritten using the new decorator API.

### Migration Steps

1. **Replace Plugin Class**: Inherit from `Plugin` instead of implementing hooks
2. **Convert Hooks to Decorators**: Replace hook implementations with `@capability` decorators
3. **Update Method Signatures**: Use `CapabilityContext` instead of individual parameters
4. **Consolidate Configuration**: Move configuration schemas to decorator metadata
5. **Update Registration**: Use the new plugin registry system

### Migration Example

**Before:**
```python
class OldWeatherPlugin:
    @hookimpl
    def register_capability(self) -> CapabilityDefinition:
        return CapabilityDefinition(id="weather", name="Weather", ...)
    
    @hookimpl
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        # Manual routing and execution
        pass
    
    @hookimpl
    def get_ai_functions(self) -> List[AIFunction]:
        return [AIFunction(...)]
```

**After:**
```python
class WeatherPlugin(Plugin):
    @capability(
        "weather",
        name="Weather",
        ai_function=True,
        ai_parameters={...},
        scopes=["web:search"]
    )
    async def get_weather(self, context: CapabilityContext) -> str:
        # Direct implementation
        return "Weather data"
```

## Framework Integration

### Integration with Existing Systems

The decorator-based plugins integrate seamlessly with the existing AgentUp framework:

1. **Capability System**: Plugins register capabilities through the standard capability manager
2. **Security**: Scope-based security is enforced at the framework level
3. **Middleware**: Plugin middleware integrates with the global middleware system
4. **AI Functions**: AI functions are automatically registered with the function registry
5. **State Management**: Plugin state is managed through the standard state system

### Performance Considerations

The decorator system is designed for optimal performance:

1. **Lazy Loading**: Plugin capabilities are only loaded when needed
2. **Metadata Caching**: Capability metadata is cached at registration time
3. **Direct Routing**: No hook chain traversal - direct method calls
4. **Minimal Overhead**: Decorators add minimal runtime overhead

## Summary

The decorator-based plugin system provides a dramatic improvement in developer experience while maintaining all the power and flexibility of the current system. Key benefits:

1. **Intuitive API**: Simple decorators replace complex hook implementations
2. **Automatic Discovery**: No manual registration - capabilities are discovered automatically
3. **Type Safety**: Strong typing throughout the system
4. **Clear Separation**: Each capability is a separate method with clear boundaries
5. **Declarative Configuration**: Everything is declared in code, reducing YAML complexity
6. **Modern Python**: Uses modern Python features like async/await and type hints

The new system eliminates the confusion around multi-capability plugins, makes the relationship between plugins and capabilities explicit, and provides a much more intuitive development experience while maintaining all the advanced features needed for production use.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Create ultra-detailed decorator-based plugin implementation document", "status": "completed", "priority": "high"}]