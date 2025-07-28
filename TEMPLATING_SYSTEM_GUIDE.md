# AgentUp Templating System Guide

## Overview

AgentUp uses Jinja2 templating to generate project configuration files. The main template is `src/agent/templates/config/agentup.yml.j2` which generates the `agentup.yml` configuration file.

## Architecture

### Key Files:
- **Generator Logic**: `src/agent/generator.py` (line 227-345: `_render_template()`)
- **Main Template**: `src/agent/templates/config/agentup.yml.j2`
- **Configuration Model**: `src/agent/config/model.py` (computed fields)

### Template Context Creation

The template context is built in `ProjectGenerator._render_template()` method:

## Jinja2 Template Variables

### Core Project Variables
```python
# Basic project info
"project_name": self.project_name,
"project_name_snake": self._to_snake_case(self.project_name),
"project_name_title": self._to_title_case(self.project_name),
"description": self.config.get("description", ""),
```

### Feature Flags (Boolean)
```python
"features": self.features,  # List of enabled features
"has_middleware": "middleware" in self.features,
"has_state_management": "state_management" in self.features,
"has_auth": "auth" in self.features,
"has_mcp": "mcp" in self.features,
"has_push_notifications": "push_notifications" in self.features,
"has_development": "development" in self.features,
"has_deployment": "deployment" in self.features,
```

### AI Provider Configuration
```python
# When AI provider is configured:
"ai_provider_config": ai_provider_config,  # Dict with provider details
"llm_provider_config": True,
"ai_enabled": True,
"has_ai_provider": True,

# When no AI provider:
"ai_provider_config": None,
"llm_provider_config": False,
"ai_enabled": False,
"has_ai_provider": False,
```

### Authentication/Security Variables
```python
"asf_enabled": auth_enabled,  # AgentUp Security Framework enabled
"auth_type": auth_type,  # "api_key", "jwt", "oauth2"
"scope_hierarchy_enabled": bool(scope_config.get("scope_hierarchy")),
"has_enterprise_scopes": scope_config.get("security_level") == "enterprise",
"context_aware_middleware": "middleware" in self.features and auth_enabled,
```

### Configuration Variables
```python
"feature_config": self.config["feature_config"],  # All feature-specific config
"cache_backend": cache_backend,  # "memory", "valkey"
"state_backend": state_backend,  # "memory", "valkey", "file"
```

### Development Variables
```python
"development_enabled": feature_config.get("development_enabled", False),
"filesystem_plugins_enabled": feature_config.get("filesystem_plugins_enabled", False),
"plugin_directory": feature_config.get("plugin_directory"),
```

## Template Variables Used in agentup.yml.j2

### **ISSUE IDENTIFIED**: Variable Mismatch
The template uses `security_enabled` but the generator sets `asf_enabled`. This is the bug causing authentication to show as `False`.

### Direct Template Variables (from grep analysis):

#### Basic Variables:
- `{{ project_name }}` ✅
- `{{ description }}` ✅
- `{{ project_name_snake }}` ✅

#### **Problem Variables** (not set in generator):
- `{{ security_enabled }}` ❌ **NOT SET** (should be `asf_enabled`)
- `{{ auth_header_name }}` ❌ **NOT SET**
- `{{ auth_location }}` ❌ **NOT SET**
- `{{ generate_multiple_keys }}` ❌ **NOT SET**

#### AI Variables:
- `{{ ai_provider_config.provider }}` ✅
- `{{ ai_provider_config.model }}` ✅
- `{{ ai_temperature }}` ❌ **NOT SET**
- `{{ ai_max_tokens }}` ❌ **NOT SET**
- `{{ ai_top_p }}` ❌ **NOT SET**
- `{{ ai_enabled }}` ✅
- `{{ ai_system_prompt }}` ❌ **NOT SET**

#### MCP Variables:
- `{{ mcp_client_enabled }}` ❌ **NOT SET**
- `{{ mcp_filesystem_path }}` ❌ **NOT SET**
- `{{ mcp_custom_server }}` ❌ **NOT SET**
- `{{ mcp_server_enabled }}` ❌ **NOT SET**
- `{{ mcp_server_port }}` ❌ **NOT SET**

#### Middleware Variables:
- `{{ rate_limit_rpm }}` ❌ **NOT SET**
- `{{ rate_limit_burst }}` ❌ **NOT SET**
- `{{ cache_backend }}` ✅
- `{{ middleware_cache_ttl }}` ❌ **NOT SET**
- `{{ cache_max_size }}` ❌ **NOT SET**
- `{{ retry_max_attempts }}` ❌ **NOT SET**
- `{{ retry_initial_delay }}` ❌ **NOT SET**
- `{{ retry_max_delay }}` ❌ **NOT SET**

#### Push Notification Variables:
- `{{ push_enabled }}` ❌ **NOT SET**
- `{{ push_backend }}` ❌ **NOT SET**
- `{{ push_validate_urls }}` ❌ **NOT SET**
- `{{ push_retry_attempts }}` ❌ **NOT SET**
- `{{ push_timeout }}` ❌ **NOT SET**

#### State Variables:
- `{{ state_ttl }}` ❌ **NOT SET**
- `{{ state_storage_dir }}` ❌ **NOT SET**

#### Logging Variables:
- `{{ logging_enabled }}` ❌ **NOT SET**
- `{{ log_level }}` ❌ **NOT SET**
- `{{ log_format }}` ❌ **NOT SET**
- `{{ console_logging }}` ❌ **NOT SET**
- `{{ console_colors }}` ❌ **NOT SET**
- `{{ correlation_id }}` ❌ **NOT SET**
- `{{ request_logging }}` ❌ **NOT SET**
- `{{ uvicorn_access_log }}` ❌ **NOT SET**
- `{{ uvicorn_colors }}` ❌ **NOT SET**

### Conditional Variables ({% if %}):

#### Working Conditions:
- `{% if plugin == 'ai_assistant' %}` ✅
- `{% if ai_provider_config.provider == 'openai' %}` ✅
- `{% if has_middleware and 'rate_limit' in feature_config.get('middleware', []) %}` ✅
- `{% if development_enabled %}` ✅

#### **Problem Conditions** (use undefined variables):
- `{% if security_enabled %}` ❌ **UNDEFINED**
- `{% if generate_multiple_keys %}` ❌ **UNDEFINED**
- `{% if push_backend == 'valkey' %}` ❌ **UNDEFINED**

## Root Cause of Authentication Bug

The template expects `security_enabled` but the generator provides `asf_enabled`. This causes:
1. Security section shows `enabled: False` even when auth is selected
2. All auth configuration is skipped because `{% if security_enabled %}` fails

## Functions Available in Templates

### Jinja2 Global Functions (set in generator):
- `{{ generate_api_key() }}` - Generates random API key
- `{{ generate_jwt_secret() }}` - Generates JWT secret
- `{{ generate_client_secret() }}` - Generates OAuth client secret

## Template Structure

### Main Sections in agentup.yml.j2:
1. **Agent Information** - Basic project metadata
2. **Core plugins configuration** - Plugin definitions with loop over `selected_plugins`
3. **Unified Security Configuration** - Authentication and authorization
4. **AI Provider configuration** - AI service configuration (conditional)
5. **AI system prompt and configuration** - AI behavior settings (conditional)
6. **External services configuration** - Service definitions
7. **Model Context Protocol** - MCP configuration (conditional)
8. **Middleware configuration** - Rate limiting, caching, retry logic
9. **Push notifications configuration** - Notification settings
10. **State management configuration** - State persistence (conditional)
11. **Logging configuration** - Logging and monitoring
12. **Development configuration** - Development-only features (conditional)

## Variable Sources

### From `self.config`:
- Basic project info (`name`, `description`)
- Feature configuration (`feature_config`)
- AI provider settings (`ai_provider_config`)
- Services configuration (`services`)

### From `self.features`:
- Feature flags (list of enabled features)
- Converted to `has_*` boolean flags

### Missing/Undefined Variables:
Many template variables are not defined in the generator context, causing:
- Default values to be used (via `| default(...)`)
- Conditional sections to be skipped
- Incorrect configuration generation

## Fix Requirements

### Immediate Fixes Needed:

1. **Fix security_enabled mismatch**:
   ```python
   # In generator.py, change:
   "security_enabled": auth_enabled,  # Instead of "asf_enabled"
   ```

2. **Add missing authentication variables**:
   ```python
   "auth_header_name": feature_config.get("auth_header_name", "X-API-Key"),
   "auth_location": feature_config.get("auth_location", "header"),
   "generate_multiple_keys": feature_config.get("generate_multiple_keys", False),
   ```

3. **Add missing configuration variables for all sections**:
   - AI variables (`ai_temperature`, `ai_max_tokens`, etc.)
   - MCP variables (`mcp_client_enabled`, `mcp_server_port`, etc.)
   - Middleware variables (`rate_limit_rpm`, `middleware_cache_ttl`, etc.)
   - Push notification variables (`push_enabled`, `push_backend`, etc.)
   - State management variables (`state_ttl`, `state_storage_dir`, etc.)
   - Logging variables (`logging_enabled`, `log_level`, etc.)

### Long-term Improvements:

1. **Create comprehensive variable mapping** between CLI feature selection and template variables
2. **Add validation** to ensure all template variables are defined
3. **Create tests** to verify template variable availability
4. **Document variable dependencies** for each feature

## Current Status

- ✅ Template system consolidated to single `agentup.yml.j2`
- ✅ Whitespace formatting improved
- ❌ **Major bug**: Authentication always shows `enabled: False`
- ❌ **Missing variables**: Many template variables undefined in generator
- ❌ **Inconsistent defaults**: Template defaults don't match feature selections

The templating system works but has significant variable mapping issues that prevent proper configuration generation for many features.