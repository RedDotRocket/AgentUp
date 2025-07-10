from unittest.mock import AsyncMock, Mock, patch

import pytest
from a2a.types import Task

from src.agent.handlers.handlers import (
    _apply_state_to_handler,
    _get_plugin_config,
    _handlers,
    _load_state_config,
    _resolve_state_config,
    apply_global_state,
    get_handler,
    get_state_info,
    register_handler,
    register_handler_function,
    reset_state_cache,
)


class TestStateConfigResolution:
    """Test state configuration resolution logic."""

    def test_load_state_config_success(self):
        """Test successful loading of state configuration."""
        mock_config = {
            "state_management": {"enabled": True, "backend": "valkey", "config": {"url": "valkey://localhost:6379"}}
        }

        with patch("src.agent.handlers.handlers.load_config", return_value=mock_config):
            # Reset cache first
            reset_state_cache()

            result = _load_state_config()

            assert result == mock_config["state_management"]
            assert result["enabled"] is True
            assert result["backend"] == "valkey"

    def test_load_state_config_missing(self):
        """Test loading state configuration when not present."""
        mock_config = {"plugins": []}  # No state_management section

        with patch("src.agent.handlers.handlers.load_config", return_value=mock_config):
            # Reset cache first
            reset_state_cache()

            result = _load_state_config()

            assert result == {}

    def test_load_state_config_exception(self):
        """Test loading state configuration when exception occurs."""
        with patch("src.agent.handlers.handlers.load_config", side_effect=Exception("Config error")):
            # Reset cache first
            reset_state_cache()

            result = _load_state_config()

            assert result == {}

    def test_get_skill_config_found(self):
        """Test getting skill configuration when skill exists."""
        mock_config = {
            "plugins": [
                {"plugin_id": "test_skill", "name": "Test Skill", "state_override": {"backend": "memory"}},
                {"plugin_id": "other_skill", "name": "Other Skill"},
            ]
        }

        with patch("src.agent.handlers.handlers.load_config", return_value=mock_config):
            result = _get_plugin_config("test_skill")

            assert result is not None
            assert result["plugin_id"] == "test_skill"
            assert result["name"] == "Test Skill"
            assert "state_override" in result

    def test_get_plugin_config_not_found(self):
        """Test getting plugin configuration when plugin doesn't exist."""
        mock_config = {"plugins": [{"plugin_id": "other_skill", "name": "Other Skill"}]}

        with patch("src.agent.handlers.handlers.load_config", return_value=mock_config):
            result = _get_plugin_config("nonexistent_skill")

            assert result is None

    def test_resolve_state_config_global(self):
        """Test resolving state configuration uses global config."""
        global_config = {"enabled": True, "backend": "memory"}
        skill_config = {"skill_id": "test_skill", "name": "Test Skill"}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=global_config):
            with patch("src.agent.handlers.handlers._get_plugin_config", return_value=skill_config):
                result = _resolve_state_config("test_skill")

                assert result == global_config

    def test_resolve_state_config_skill_override(self):
        """Test resolving state configuration uses skill-specific override."""
        global_config = {"enabled": True, "backend": "memory"}
        skill_config = {
            "skill_id": "test_skill",
            "name": "Test Skill",
            "state_override": {"enabled": True, "backend": "file", "config": {"storage_dir": "/tmp"}},
        }

        with patch("src.agent.handlers.handlers._load_state_config", return_value=global_config):
            with patch("src.agent.handlers.handlers._get_plugin_config", return_value=skill_config):
                result = _resolve_state_config("test_skill")

                assert result == skill_config["state_override"]
                assert result["backend"] == "file"


class TestStateApplication:
    """Test state application to handlers."""

    def test_apply_state_to_handler_enabled(self):
        """Test applying state to handler when enabled."""

        # Create a mock handler
        async def mock_handler(task: Task):
            return "test result"

        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            with patch("src.agent.state.decorators.with_state") as mock_with_state:
                mock_decorator = Mock()
                mock_decorator.return_value = mock_handler
                mock_with_state.return_value = mock_decorator

                result = _apply_state_to_handler(mock_handler, "test_skill")

                assert result == mock_handler
                mock_with_state.assert_called_once_with([state_config])

    def test_apply_state_to_handler_disabled(self):
        """Test applying state to handler when disabled."""

        # Create a mock handler
        async def mock_handler(task: Task):
            return "test result"

        state_config = {"enabled": False, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            result = _apply_state_to_handler(mock_handler, "test_skill")

            # Should return original handler unchanged
            assert result == mock_handler

    def test_apply_state_to_handler_exception(self):
        """Test applying state to handler when exception occurs."""

        # Create a mock handler
        async def mock_handler(task: Task):
            return "test result"

        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            with patch("src.agent.state.decorators.with_state", side_effect=Exception("State error")):
                result = _apply_state_to_handler(mock_handler, "test_skill")

                # Should return original handler on error
                assert result == mock_handler


class TestHandlerRegistration:
    """Test handler registration with automatic state application."""

    def setup_method(self):
        """Clear handler registry before each test."""
        _handlers.clear()

    def test_register_handler_decorator_with_state(self):
        """Test register_handler decorator applies state automatically."""
        # Mock state configuration
        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            with patch("src.agent.state.decorators.with_state") as mock_with_state:
                with patch("src.agent.handlers.handlers._apply_middleware_to_handler") as mock_middleware:
                    # Mock middleware to return the original function
                    mock_middleware.side_effect = lambda f, s: f

                    # Mock state decorator
                    mock_state_decorator = Mock()
                    mock_state_decorator.return_value = lambda f: f  # Return function unchanged
                    mock_with_state.return_value = mock_state_decorator

                    # Register handler
                    @register_handler("test_skill")
                    async def test_handler(task: Task):
                        return "test result"

                    # Verify handler was registered
                    assert "test_skill" in _handlers
                    assert _handlers["test_skill"] == test_handler

                    # Verify state was applied
                    mock_with_state.assert_called_once_with([state_config])

    def test_register_handler_function_with_state(self):
        """Test register_handler_function applies state automatically."""

        # Create a mock handler
        async def mock_handler(task: Task):
            return "test result"

        # Mock state configuration
        state_config = {"enabled": True, "backend": "file", "config": {"storage_dir": "/tmp"}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            with patch("src.agent.state.decorators.with_state") as mock_with_state:
                with patch("src.agent.handlers.handlers._apply_middleware_to_handler") as mock_middleware:
                    # Mock middleware to return the original function
                    mock_middleware.side_effect = lambda f, s: f

                    # Mock state decorator
                    mock_state_decorator = Mock()
                    mock_state_decorator.return_value = lambda f: f  # Return function unchanged
                    mock_with_state.return_value = mock_state_decorator

                    # Register handler function
                    register_handler_function("test_skill", mock_handler)

                    # Verify handler was registered
                    assert "test_skill" in _handlers
                    assert _handlers["test_skill"] == mock_handler

                    # Verify state was applied
                    mock_with_state.assert_called_once_with([state_config])

    def test_get_handler_returns_stateful_handler(self):
        """Test get_handler returns the state-wrapped handler."""

        # Create a mock handler
        async def mock_handler(task: Task):
            return "test result"

        # Mock state configuration
        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._resolve_state_config", return_value=state_config):
            with patch("src.agent.state.decorators.with_state") as mock_with_state:
                with patch("src.agent.handlers.handlers._apply_middleware_to_handler") as mock_middleware:
                    # Mock middleware to return the original function
                    mock_middleware.side_effect = lambda f, s: f

                    # Mock state decorator
                    mock_state_decorator = Mock()
                    mock_state_decorator.return_value = lambda f: f  # Return function unchanged
                    mock_with_state.return_value = mock_state_decorator

                    # Register handler
                    register_handler_function("test_skill", mock_handler)

                    # Get handler
                    retrieved_handler = get_handler("test_skill")

                    # Verify correct handler was returned
                    assert retrieved_handler == mock_handler


class TestGlobalStateApplication:
    """Test global state application functionality."""

    def setup_method(self):
        """Clear handler registry and reset state cache before each test."""
        _handlers.clear()
        reset_state_cache()

    def test_apply_global_state_enabled(self):
        """Test applying global state when enabled."""

        # Add some handlers to the registry
        async def handler1(task: Task):
            return "handler1"

        async def handler2(task: Task):
            return "handler2"

        _handlers["skill1"] = handler1
        _handlers["skill2"] = handler2

        # Mock state configuration
        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            with patch("src.agent.handlers.handlers._apply_state_to_handler") as mock_apply_state:
                # Mock apply_state to return a "wrapped" version
                def mock_apply(handler, skill_id):
                    wrapped = AsyncMock()
                    wrapped._agentup_state_applied = True
                    return wrapped

                mock_apply_state.side_effect = mock_apply

                # Apply global state
                apply_global_state()

                # Verify apply_state was called for each handler
                assert mock_apply_state.call_count == 2
                mock_apply_state.assert_any_call(handler1, "skill1")
                mock_apply_state.assert_any_call(handler2, "skill2")

                # Verify handlers were replaced with wrapped versions
                assert hasattr(_handlers["skill1"], "_agentup_state_applied")
                assert hasattr(_handlers["skill2"], "_agentup_state_applied")

    def test_apply_global_state_disabled(self):
        """Test applying global state when disabled."""

        # Add some handlers to the registry
        async def handler1(task: Task):
            return "handler1"

        _handlers["skill1"] = handler1

        # Mock state configuration (disabled)
        state_config = {"enabled": False, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            with patch("src.agent.handlers.handlers._apply_state_to_handler") as mock_apply_state:
                # Apply global state
                apply_global_state()

                # Verify apply_state was not called
                mock_apply_state.assert_not_called()

                # Verify handlers remain unchanged
                assert _handlers["skill1"] == handler1

    def test_apply_global_state_already_applied(self):
        """Test applying global state when already applied."""

        # Add some handlers to the registry
        async def handler1(task: Task):
            return "handler1"

        _handlers["skill1"] = handler1

        # Mock state configuration
        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            with patch("src.agent.handlers.handlers._apply_state_to_handler") as mock_apply_state:
                # Apply global state first time
                apply_global_state()

                # Reset mock and apply again
                mock_apply_state.reset_mock()
                apply_global_state()

                # Verify apply_state was not called second time
                mock_apply_state.assert_not_called()

    def test_apply_global_state_skip_already_wrapped(self):
        """Test applying global state skips already wrapped handlers."""

        # Add handlers, one already wrapped
        async def handler1(task: Task):
            return "handler1"

        async def handler2(task: Task):
            return "handler2"

        handler2._agentup_state_applied = True  # Mark as already wrapped

        _handlers["skill1"] = handler1
        _handlers["skill2"] = handler2

        # Mock state configuration
        state_config = {"enabled": True, "backend": "memory", "config": {}}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            with patch("src.agent.handlers.handlers._apply_state_to_handler") as mock_apply_state:
                # Mock apply_state to return a "wrapped" version
                def mock_apply(handler, skill_id):
                    wrapped = AsyncMock()
                    wrapped._agentup_state_applied = True
                    return wrapped

                mock_apply_state.side_effect = mock_apply

                # Apply global state
                apply_global_state()

                # Verify apply_state was called only for handler1
                mock_apply_state.assert_called_once_with(handler1, "skill1")

                # Verify handler2 remained unchanged
                assert _handlers["skill2"] == handler2


class TestStateInfoAndUtilities:
    """Test state information and utility functions."""

    def test_get_state_info_enabled(self):
        """Test get_state_info when state is enabled."""
        # Mock state configuration
        state_config = {"enabled": True, "backend": "valkey", "config": {"url": "valkey://localhost:6379"}}

        # Add some handlers
        _handlers["skill1"] = Mock()
        _handlers["skill2"] = Mock()

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            info = get_state_info()

            assert info["config"] == state_config
            assert info["enabled"] is True
            assert info["backend"] == "valkey"
            assert info["total_handlers"] == 2

    def test_get_state_info_disabled(self):
        """Test get_state_info when state is disabled."""
        # Mock state configuration
        state_config = {"enabled": False, "backend": "memory"}

        with patch("src.agent.handlers.handlers._load_state_config", return_value=state_config):
            info = get_state_info()

            assert info["enabled"] is False
            assert info["backend"] == "memory"

    def test_reset_state_cache(self):
        """Test reset_state_cache functionality."""
        # Mock some state to be cached
        with patch("src.agent.handlers.handlers._load_state_config") as mock_load_config:
            mock_load_config.return_value = {"enabled": True}

            # Load config to cache it
            _load_state_config()

            # Verify it was called
            assert mock_load_config.call_count == 1

            # Reset cache
            reset_state_cache()

            # Load config again
            _load_state_config()

            # Verify it was called again (cache was reset)
            assert mock_load_config.call_count == 2


class TestIntegrationWithRealScenarios:
    """Test integration scenarios with realistic configurations."""

    def setup_method(self):
        """Clear handler registry and reset caches before each test."""
        _handlers.clear()
        reset_state_cache()

    @pytest.mark.asyncio
    async def test_full_state_application_workflow(self):
        """Test complete state application workflow."""
        # Create a realistic agent configuration
        agent_config = {
            "plugins": [
                {
                    "plugin_id": "ai_assistant",
                    "name": "AI Assistant",
                    "description": "AI-powered assistant",
                    "tags": ["ai", "assistant"],
                },
                {
                    "plugin_id": "stateful_echo",
                    "name": "Stateful Echo",
                    "description": "Echo with state",
                    "tags": ["echo", "stateful"],
                    "state_override": {"enabled": True, "backend": "file", "config": {"storage_dir": "/tmp/test"}},
                },
            ],
            "state_management": {"enabled": True, "backend": "memory", "config": {}},
            "middleware": [],
        }

        with patch("src.agent.handlers.handlers.load_config", return_value=agent_config):
            with patch("src.agent.state.decorators.with_state") as mock_with_state:
                with patch("src.agent.handlers.handlers.with_middleware") as mock_with_middleware:
                    # Mock middleware to return original function
                    mock_with_middleware.return_value = lambda f: f

                    # Mock state decorator
                    mock_state_decorator = Mock()
                    mock_state_decorator.return_value = lambda f: f
                    mock_with_state.return_value = mock_state_decorator

                    # Register handlers
                    @register_handler("ai_assistant")
                    async def ai_handler(task: Task):
                        return "AI response"

                    @register_handler("stateful_echo")
                    async def echo_handler(task: Task):
                        return "Echo response"

                    # Verify both handlers were registered
                    assert "ai_assistant" in _handlers
                    assert "stateful_echo" in _handlers

                    # Verify state was applied with correct configurations
                    assert mock_with_state.call_count == 2

                    # Check that ai_assistant used global config
                    calls = mock_with_state.call_args_list
                    ai_call = next(call for call in calls if call[0][0][0]["backend"] == "memory")
                    assert ai_call[0][0][0]["enabled"] is True
                    assert ai_call[0][0][0]["backend"] == "memory"

                    # Check that stateful_echo used override config
                    echo_call = next(call for call in calls if call[0][0][0]["backend"] == "file")
                    assert echo_call[0][0][0]["enabled"] is True
                    assert echo_call[0][0][0]["backend"] == "file"
                    assert echo_call[0][0][0]["config"]["storage_dir"] == "/tmp/test"
