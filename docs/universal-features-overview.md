# Universal Features Overview

This document provides an overview of AgentUp's universal features that are automatically applied to all handlers and plugins based on configuration.

## Architecture Philosophy

AgentUp follows a **configuration-driven, universal application** approach where:

- **Agents are pure configuration** - No source code, just `agent_config.yaml`
- **Features are universally applied** - Based on configuration, not manual integration
- **Plugins inherit everything** - Automatic access to all framework features

## Universal Features

### 1. Middleware System ✅

**Status:** Fully implemented and auto-applied

**What it does:**
- Automatically applies middleware (logging, caching, rate limiting, etc.) to ALL handlers
- No manual decorators needed
- Configured through `agent_config.yaml`

**Configuration:**
```yaml
middleware:
  - name: logged
    params: {log_level: 20}
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 60}
```

**Documentation:** See `docs/middleware-auto-application.md`

### 2. Multi-modal Processing ✅

**Status:** Fully implemented with universal helpers

**What it does:**
- Provides image and document processing capabilities
- Available to all handlers and plugins through helper utilities
- Built-in handlers: `analyze_image`, `process_document`, `transform_image`, `multimodal_chat`

**Configuration:**
```yaml
services:
  multimodal:
    type: multimodal
    enabled: true
    config:
      max_image_size_mb: 10
      max_document_size_mb: 50

skills:
  - skill_id: analyze_image
    input_mode: multimodal
    output_mode: text
```

**Documentation:** See `docs/multimodal-usage-examples.md`

### 3. Authentication 🔒

**Status:** Fully implemented at API level

**What it does:**
- Protects all endpoints before requests reach handlers
- Multiple auth types: API Key, JWT, OAuth2
- Plugins automatically protected

**Configuration:**
```yaml
security:
  enabled: true
  type: api_key
  api_key:
    header_name: X-API-Key
    keys: ["your-api-key"]
```

### 4. Service Registry 🔧

**Status:** Fully implemented

**What it does:**
- Provides access to external services (LLM, database, cache)
- Available to all handlers and plugins
- Centralized connection management

**Usage in handlers/plugins:**
```python
from agentup.services.registry import get_services
services = get_services()
llm = services.get_llm('openai')
cache = services.get_cache('valkey')
```

### 5. AI Provider Integration 🤖

**Status:** Fully implemented

**What it does:**
- Configures LLM provider globally
- All AI-enabled features use the same provider
- Supports OpenAI, Anthropic, Ollama

**Configuration:**
```yaml
ai_provider:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini
  temperature: 0.7
```

## How Universal Features Work

### During Agent Creation

When you run `agentup agent create`:

```
? Select features to include:
 ● Middleware System (auto-applied to all handlers)
 ● Multi-modal Processing (images, documents)
 ● External Services (Database, Cache)
 ● AI Provider
 ● Authentication
```

These features are:
- **Configured** in `agent_config.yaml`
- **Enabled** automatically by the framework
- **Applied** universally to all handlers and plugins

### At Runtime

1. **Agent starts** → Loads `agent_config.yaml`
2. **Framework initializes** → Sets up all configured features
3. **Middleware applied** → All handlers wrapped automatically
4. **Services registered** → Available through registry
5. **Plugins loaded** → Inherit all features automatically

## Benefits

1. **No Code Duplication** - Features configured once, applied everywhere
2. **Consistent Behavior** - All handlers behave the same way
3. **Easy Updates** - Change config, restart agent
4. **Plugin Simplicity** - Plugins focus on business logic
5. **Framework Evolution** - New features automatically available

## Example: Complete Agent Configuration

```yaml
# agent_config.yaml - Everything configured, nothing coded

agent:
  name: MySmartAgent
  version: 1.0.0

# Universal middleware - applied to ALL handlers
middleware:
  - name: logged
    params: {log_level: 20}
  - name: timed
    params: {}
  - name: cached
    params: {ttl: 300}
  - name: rate_limited
    params: {requests_per_minute: 100}

# Multi-modal service - enables image/document processing
services:
  multimodal:
    type: multimodal
    enabled: true
  valkey:
    type: cache
    config:
      url: ${VALKEY_URL:valkey://localhost:6379}

# Global AI provider
ai_provider:
  provider: openai
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o-mini

# API protection
security:
  enabled: true
  type: api_key
  api_key:
    header_name: X-API-Key
    keys: ["${API_KEY}"]

# Skills to enable
skills:
  - skill_id: ai_assistant
    name: AI Assistant
    input_mode: text
    output_mode: text
    
  - skill_id: analyze_image
    name: Image Analysis
    input_mode: multimodal
    output_mode: text
```

## Plugin Developer Perspective

As a plugin developer, you get all these features for free:

```python
class MyPlugin:
    def execute_skill(self, context):
        # This method automatically has:
        # - All configured middleware applied
        # - Access to multi-modal helpers
        # - Protection from authentication
        # - Access to all services
        
        # Use multi-modal helpers
        from agentup.multimodal import MultiModalHelper
        if MultiModalHelper.has_images(context.task):
            # Process images...
        
        # Access services
        from agentup.services.registry import get_services
        services = get_services()
        cache = services.get_cache()
        
        return SkillResult(content="Done!", success=True)
```

## Summary

AgentUp's universal features architecture ensures:

- ✅ **Configuration over code** - Change behavior through YAML
- ✅ **Universal application** - Features apply to everything
- ✅ **Automatic inheritance** - Plugins get features for free
- ✅ **Consistent behavior** - All handlers work the same way
- ✅ **Future-proof** - New features automatically available

This approach makes AgentUp agents powerful yet simple, with complex functionality available through configuration rather than coding.