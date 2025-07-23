"""Pytest configuration and shared fixtures for AgentUp tests."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import yaml

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_agent_config() -> dict[str, Any]:
    """Sample agent configuration for testing."""
    return {
        "agent": {"name": "test-agent", "description": "Test Agent for Unit Testing", "version": "0.3.0"},
        "plugins": [
            {
                "plugin_id": "ai_assistant",
                "name": "AI Assistant",
                "description": "General purpose AI assistant",
                "tags": ["ai", "assistant", "helper"],
                # No keywords or patterns defined, only available via AI routing
                "input_mode": "text",
                "output_mode": "text",
                "priority": 100,
            }
        ],
        "ai_provider": {
            "provider": "openai",
            "api_key": "${OPENAI_API_KEY}",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        },
        "services": {},
        "security": {"enabled": False, "type": "api_key"},
        "middleware": [{"name": "logged", "params": {"log_level": 20}}, {"name": "timed", "params": {}}],
        "push_notifications": {"enabled": True, "backend": "memory", "validate_urls": True},
        "cache": {"backend": "memory", "default_ttl": 1800, "max_size": 1000, "enabled": True},
        "state_management": {
            "enabled": True,
            "backend": "file",
            "ttl": 3600,
            "config": {"storage_dir": "./conversation_states"},
        },
    }


@pytest.fixture
def minimal_agent_config() -> dict[str, Any]:
    """Minimal agent configuration for testing."""
    return {
        "agent": {"name": "minimal-test", "description": "Minimal Test Agent", "version": "0.3.0"},
        "plugins": [
            {
                "plugin_id": "echo",
                "name": "Echo",
                "description": "Echo back the input text",
                "tags": ["echo", "basic", "simple"],
                "input_mode": "text",
                "output_mode": "text",
                "keywords": ["echo", "repeat", "say"],
                "patterns": [".*"],
                "priority": 50,
            }
        ],
    }


@pytest.fixture
def ollama_agent_config() -> dict[str, Any]:
    """Ollama-specific agent configuration for testing."""
    return {
        "agent": {"name": "ollama-test", "description": "Ollama Test Agent", "version": "0.3.0"},
        "ai_provider": {
            "provider": "ollama",
            "model": "qwen3:0.6b",
            "base_url": "${OLLAMA_BASE_URL:http://localhost:11434/v1}",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        },
        "services": {},
    }


@pytest.fixture
def anthropic_agent_config() -> dict[str, Any]:
    """Anthropic-specific agent configuration for testing."""
    return {
        "agent": {"name": "anthropic-test", "description": "Anthropic Test Agent", "version": "0.3.0"},
        "ai_provider": {
            "provider": "anthropic",
            "api_key": "${ANTHROPIC_API_KEY}",
            "model": "claude-3-haiku-20240307",
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 1.0,
        },
        "services": {},
    }


@pytest.fixture
def project_config() -> dict[str, Any]:
    """Sample project configuration for generator testing."""
    return {
        "name": "test-project",
        "description": "Test Project Description",
        "template": "standard",
        "features": ["services", "middleware", "auth", "ai_provider", "mcp"],
        "services": ["valkey"],
        "ai_provider_config": {"provider": "openai"},
        "feature_config": {"auth": "api_key", "middleware": ["rate_limit", "cache", "logging"]},
    }


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    mock_service = AsyncMock()
    mock_service.generate_response.return_value.content = "Mock response"
    mock_service.generate_response.return_value.usage = {"tokens": 100}
    return mock_service


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Mock OpenAI response"
    mock_response.usage.total_tokens = 100
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.content = [Mock()]
    mock_response.content[0].text = "Mock Anthropic response"
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    mock_client = AsyncMock()
    mock_response = {"message": {"content": "Mock Ollama response"}, "done": True}
    mock_client.chat.return_value = mock_response
    return mock_client


@pytest.fixture
def config_file(temp_dir: Path, sample_agent_config: dict[str, Any]) -> Path:
    """Create a temporary config file."""
    config_file = temp_dir / "agentup.yml"
    with open(config_file, "w") as f:
        yaml.dump(sample_agent_config, f, default_flow_style=False)
    return config_file


@pytest.fixture
def env_vars():
    """Set up test environment variables."""
    test_env = {
        "OPENAI_API_KEY": "test_openai_key",
        "ANTHROPIC_API_KEY": "test_anthropic_key",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "VALKEY_URL": "valkey://localhost:6379",
    }

    # Store original values
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield test_env

    # Restore original values
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_file_system(temp_dir: Path):
    """Mock file system operations for testing."""
    # Create mock directory structure
    src_dir = temp_dir / "src" / "agent"
    src_dir.mkdir(parents=True)

    # Create mock Python files
    for filename in ["__init__.py", "main.py", "config.py", "api.py"]:
        (src_dir / filename).write_text(f"# Mock {filename}\npass\n")

    return {"temp_dir": temp_dir, "src_dir": src_dir, "files": ["__init__.py", "main.py", "config.py", "api.py"]}


@pytest.fixture(scope="session")
def agent_templates():
    """Load agent template information for testing."""
    return {
        "minimal": {"features": [], "description": "Basic agent without AI or advanced features"},
        "standard": {
            "features": ["services", "middleware", "mcp"],
            "description": "AI-powered agent with MCP integration",
        },
        "full": {
            "features": ["services", "middleware", "auth", "state_management", "mcp", "monitoring"],
            "description": "All features enabled including database, cache, monitoring",
        },
        "demo": {
            "features": ["services", "middleware", "mcp"],
            "description": "Pre-configured demo plugins for testing",
        },
    }


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()


# Async test support
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Test markers
pytestmark = pytest.mark.asyncio
