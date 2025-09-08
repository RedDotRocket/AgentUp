"""
Test suite for src/agent/plugins/integration.py

This module tests the integration between the new decorator-based plugin system
and the capability registry, focusing on capability registration, scope enforcement,
and configuration management.
"""

from unittest.mock import Mock, call, patch

import pytest
from a2a.types import Task

from src.agent.plugins.adapter import PluginAdapter
from src.agent.plugins.integration import (
    create_plugin_capability_wrapper,
    enable_plugin_system,
    get_capability_info,
    get_plugin_adapter,
    get_plugin_registry_instance,
    integrate_plugins_with_capabilities,
    integrate_with_function_registry,
    list_all_capabilities,
)
from src.agent.plugins.models import CapabilityDefinition, CapabilityType


class TestPluginCapabilityIntegration:
    """Test integration of plugins with capability registry."""

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_basic_success(self, mock_get_registry):
        """Test basic successful plugin integration."""
        # Mock config
        mock_config = Mock()
        
        # Use dict format matching Settings model: plugins -> plugin_name -> capabilities -> capability_name -> config
        mock_config.plugins = {
            "test_plugin": {
                "capabilities": {
                    "test_capability": {
                        "required_scopes": ["test:read"],
                        "enabled": True
                    }
                }
            }
        }

        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        # Mock plugin instance
        mock_plugin = Mock()
        mock_capability_def = CapabilityDefinition(
            id="test_capability",
            name="Test Capability",
            version="1.0.0",
            description="Test capability",
            capabilities=[CapabilityType.TEXT],
            plugin_name="test_plugin",
            required_scopes=["test:read"],
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for capability 3",
        )
        mock_plugin.get_capability_definitions.return_value = [mock_capability_def]

        mock_registry.plugins = {"test_plugin": mock_plugin}
        mock_registry.get_plugin.return_value = mock_plugin
        mock_registry.discover_plugins.return_value = None
        mock_registry.configure_services.return_value = None

        with patch("src.agent.plugins.integration._capabilities", {}):
            with patch("agent.capabilities.manager.register_plugin_capability") as mock_register:
                with patch("src.agent.plugins.integration._get_available_services", return_value={}):
                    result = integrate_plugins_with_capabilities(mock_config)

                    # Verify plugin discovery was called
                    mock_registry.discover_plugins.assert_called_once()

                    # Verify plugin was configured
                    mock_plugin.configure.assert_called_once_with({})

                    # Verify capability was registered
                    mock_register.assert_called_once_with(
                        {"capability_id": "test_capability", "required_scopes": ["test:read"]}
                    )

                    # Verify return value
                    assert result == {"test_capability": ["test:read"]}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_with_config_loading(self, mock_get_registry):
        """Test integration when config needs to be loaded."""
        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.plugins = {}
        mock_registry.discover_plugins.return_value = None

        with patch("agent.config.Config") as mock_config_class:
            # The integration code does `config = Config` (not Config()), so we need to set attributes on the class
            mock_config_class.plugins = []

            # Should handle empty config gracefully
            result = integrate_plugins_with_capabilities(None)
            assert result == {}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_plugin_not_loaded(self, mock_get_registry):
        """Test integration when configured plugin is not loaded."""
        mock_config = Mock()
        
        # Use dict format matching Settings model
        mock_config.plugins = {
            "missing_plugin": {
                "capabilities": {
                    "missing_capability": {
                        "required_scopes": ["test:read"],
                        "enabled": True
                    }
                }
            }
        }

        # Mock plugin registry with no plugins loaded
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.plugins = {}  # No plugins loaded
        mock_registry.discover_plugins.return_value = None

        with patch("src.agent.plugins.integration._get_available_services", return_value={}):
            result = integrate_plugins_with_capabilities(mock_config)

            # Should return empty dict when no capabilities registered
            assert result == {}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_capability_not_provided_by_plugin(self, mock_get_registry):
        """Test integration when configured capability is not provided by plugin."""
        mock_config = Mock()

        # Use dict format matching Settings model: plugins -> plugin_name -> capabilities -> capability_name -> config
        mock_config.plugins = {
            "test_plugin": {"capabilities": {"missing_capability": {"required_scopes": ["test:read"], "enabled": True}}}
        }

        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        # Mock plugin that provides different capability
        mock_plugin = Mock()
        mock_capability_def = CapabilityDefinition(
            id="other_capability",  # Different capability
            name="Other Capability",
            version="1.0.0",
            description="Other capability",
            capabilities=[CapabilityType.TEXT],
            plugin_name="test_plugin",
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for other capability",
        )
        mock_plugin.get_capability_definitions.return_value = [mock_capability_def]

        mock_registry.plugins = {"test_plugin": mock_plugin}
        mock_registry.get_plugin.return_value = mock_plugin
        mock_registry.discover_plugins.return_value = None

        with patch("src.agent.plugins.integration._get_available_services", return_value={}):
            result = integrate_plugins_with_capabilities(mock_config)

            # Should return empty dict when configured capability not found
            assert result == {}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_multiple_capabilities(self, mock_get_registry):
        """Test integration with multiple capabilities."""
        mock_config = Mock()
        
        # Use dict format matching Settings model
        mock_config.plugins = {
            "multi_plugin": {
                "capabilities": {
                    "cap1": {
                        "required_scopes": ["read:files"],
                        "enabled": True
                    },
                    "cap2": {
                        "required_scopes": ["write:files"],
                        "enabled": False
                    },
                    "cap3": {
                        "required_scopes": ["admin"],
                        "enabled": True
                    }
                }
            }
        }

        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        # Mock plugin with multiple capabilities
        mock_plugin = Mock()
        mock_capability_defs = [
            CapabilityDefinition(
                id="cap1",
                name="Cap 1",
                version="1.0.0",
                description="Capability 1",
                capabilities=[CapabilityType.TEXT],
                plugin_name="multi_plugin",
                required_scopes=["read:files"],
                input_mode="text",
                output_mode="text",
                priority=1,
                system_prompt="System prompt for capability 1",
            ),
            CapabilityDefinition(
                id="cap2",
                name="Cap 2",
                version="1.0.0",
                description="Capability 2",
                capabilities=[CapabilityType.TEXT],
                plugin_name="multi_plugin",
                required_scopes=["write:files"],
                input_mode="text",
                output_mode="text",
                priority=1,
                system_prompt="System prompt for capability 2",
            ),
            CapabilityDefinition(
                id="cap3",
                name="Cap 3",
                version="1.0.0",
                description="Capability 3",
                capabilities=[CapabilityType.TEXT],
                plugin_name="multi_plugin",
                required_scopes=["admin"],
                input_mode="text",
                output_mode="text",
                priority=1,
                system_prompt="System prompt for capability 3",
            ),
        ]
        mock_plugin.get_capability_definitions.return_value = mock_capability_defs

        mock_registry.plugins = {"multi_plugin": mock_plugin}
        mock_registry.get_plugin.return_value = mock_plugin
        mock_registry.discover_plugins.return_value = None

        with patch("src.agent.plugins.integration._capabilities", {}):
            with patch("agent.capabilities.manager.register_plugin_capability") as mock_register:
                with patch("src.agent.plugins.integration._get_available_services", return_value={}):
                    result = integrate_plugins_with_capabilities(mock_config)

                    # New behavior: registers all capabilities from the plugin
                    expected_calls = [
                        call({"capability_id": "cap1", "required_scopes": ["read:files"]}),
                        call({"capability_id": "cap2", "required_scopes": ["write:files"]}),
                        call({"capability_id": "cap3", "required_scopes": ["admin"]}),
                    ]
                    mock_register.assert_has_calls(expected_calls, any_order=True)
                    assert mock_register.call_count == 3

                    # Return value includes all capabilities
                    assert result == {"cap1": ["read:files"], "cap2": ["write:files"], "cap3": ["admin"]}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_skips_existing_capabilities(self, mock_get_registry):
        """Test that integration skips capabilities already registered."""
        mock_config = Mock()
        
        # Use dict format matching Settings model
        mock_config.plugins = {
            "test_plugin": {
                "capabilities": {
                    "existing_capability": {
                        "required_scopes": ["test:read"],
                        "enabled": True
                    }
                }
            }
        }

        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        mock_plugin = Mock()
        mock_capability_def = CapabilityDefinition(
            id="existing_capability",
            name="Existing",
            version="1.0.0",
            description="Existing capability",
            capabilities=[CapabilityType.TEXT],
            plugin_name="test_plugin",
            required_scopes=["test:read"],
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for capability",
        )
        mock_plugin.get_capability_definitions.return_value = [mock_capability_def]

        mock_registry.plugins = {"test_plugin": mock_plugin}
        mock_registry.get_plugin.return_value = mock_plugin
        mock_registry.discover_plugins.return_value = None

        # Mock existing capability in registry
        existing_capabilities = {"existing_capability": Mock()}

        with patch("src.agent.plugins.integration._capabilities", existing_capabilities):
            with patch("agent.capabilities.manager.register_plugin_capability") as mock_register:
                with patch("src.agent.plugins.integration._get_available_services", return_value={}):
                    result = integrate_plugins_with_capabilities(mock_config)

                    # Should not register existing capability
                    mock_register.assert_not_called()

                    # Still return the capability mapping (skipped but added to return value)
                    assert result == {"existing_capability": ["test:read"]}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_integration_registration_failure(self, mock_get_registry):
        """Test integration when capability registration fails."""
        mock_config = Mock()
        
        # Use dict format matching Settings model
        mock_config.plugins = {
            "test_plugin": {
                "capabilities": {
                    "failing_capability": {
                        "required_scopes": ["test:read"],
                        "enabled": True
                    }
                }
            }
        }

        # Mock plugin registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        mock_plugin = Mock()
        mock_capability_def = CapabilityDefinition(
            id="failing_capability",
            name="Failing",
            version="1.0.0",
            description="Failing capability",
            capabilities=[CapabilityType.TEXT],
            plugin_name="test_plugin",
            required_scopes=["test:read"],
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for capability",
        )
        mock_plugin.get_capability_definitions.return_value = [mock_capability_def]

        mock_registry.plugins = {"test_plugin": mock_plugin}
        mock_registry.get_plugin.return_value = mock_plugin
        mock_registry.discover_plugins.return_value = None

        with patch("src.agent.plugins.integration._capabilities", {}):
            with patch("agent.capabilities.manager.register_plugin_capability") as mock_register:
                with patch("src.agent.plugins.integration._get_available_services", return_value={}):
                    mock_register.side_effect = Exception("Registration failed")

                    with pytest.raises(
                        ValueError, match="Plugin capability 'failing_capability' requires proper scope enforcement"
                    ):
                        integrate_plugins_with_capabilities(mock_config)


class TestPluginAdapter:
    """Test PluginAdapter functionality."""

    def test_plugin_adapter_initialization(self):
        """Test PluginAdapter initialization."""
        mock_config = Mock()
        adapter = PluginAdapter(mock_config)
        assert adapter is not None

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_get_capability_executor_success(self, mock_get_registry):
        """Test getting capability executor successfully."""
        # Mock registry and plugin
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        mock_plugin = Mock()
        mock_capability_def = CapabilityDefinition(
            id="test_capability",
            name="Test",
            version="1.0.0",
            description="Test capability",
            capabilities=[CapabilityType.TEXT],
            plugin_name="test_plugin",
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for capability",
        )
        mock_plugin.get_capability_definitions.return_value = [mock_capability_def]

        mock_registry.plugins = {"test_plugin": mock_plugin}

        mock_config = Mock()
        adapter = PluginAdapter(mock_config)
        executor = adapter.get_capability_executor_for_capability("test_capability")

        assert executor is not None
        assert callable(executor)

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_get_capability_executor_not_found(self, mock_get_registry):
        """Test getting capability executor when capability not found."""
        # Mock empty registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.plugins = {}

        mock_config = Mock()
        mock_config.plugins = {}  # Empty plugins dict
        adapter = PluginAdapter(mock_config)
        executor = adapter.get_capability_executor_for_capability("nonexistent")

        # Should return a function (executor)
        assert executor is not None
        assert callable(executor)

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_get_capability_executor_no_registry(self, mock_get_registry):
        """Test getting capability executor when registry not available."""
        mock_get_registry.return_value = None

        mock_config = Mock()
        mock_config.plugins = {}  # Empty plugins dict
        adapter = PluginAdapter(mock_config)
        executor = adapter.get_capability_executor_for_capability("test_capability")

        # Should return a function (executor)
        assert executor is not None
        assert callable(executor)


class TestPluginCapabilityWrapper:
    """Test plugin capability wrapper functionality."""

    @pytest.mark.asyncio
    async def test_create_plugin_capability_wrapper(self):
        """Test creation and execution of plugin capability wrapper."""
        mock_task = Mock(spec=Task)

        with patch("src.agent.plugins.integration.get_plugin_registry_instance") as mock_get_instance:
            # Mock registry with capability mapping
            mock_registry = Mock()
            mock_registry.capability_to_plugin = {"test_capability": "test_plugin"}
            mock_registry.plugins = {"test_plugin": Mock(_services={"llm": Mock()})}

            # Mock successful capability execution
            from src.agent.plugins.models import CapabilityResult

            mock_result = CapabilityResult(content="test result", success=True, error=None)

            # Make the async method return a coroutine
            async def mock_execute():
                return mock_result

            mock_registry.execute_capability.return_value = mock_execute()

            mock_get_instance.return_value = mock_registry

            # Create and test wrapper
            wrapper = create_plugin_capability_wrapper("test_capability")
            result = await wrapper(mock_task)

            assert result == "test result"
            mock_registry.execute_capability.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_plugin_capability_wrapper_no_registry(self):
        """Test wrapper when plugin system not initialized."""
        mock_task = Mock(spec=Task)

        with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=None):
            wrapper = create_plugin_capability_wrapper("test_capability")
            result = await wrapper(mock_task)

            assert result == "Plugin system not initialized"


class TestFunctionRegistryIntegration:
    """Test plugin integration with function registry."""

    @patch("src.agent.plugins.integration.get_plugin_registry_instance")
    def test_integrate_with_function_registry_success(self, mock_get_instance):
        """Test successful integration with function registry."""
        # Mock function registry
        mock_registry = Mock()

        # Mock plugin registry with AI function capabilities
        mock_plugin_registry = Mock()
        mock_plugin_registry.capabilities = {"ai_capability": Mock(ai_function=True, scopes=["test:read"])}
        mock_plugin_registry.capability_to_plugin = {"ai_capability": "test_plugin"}

        # Mock plugin with AI functions
        mock_plugin = Mock()
        from src.agent.plugins.models import AIFunction

        mock_ai_func = AIFunction(
            name="test_function",
            description="Test function",
            parameters={"type": "object", "properties": {}},
            handler=Mock(),  # Add required handler field
        )
        mock_plugin.get_ai_functions.return_value = [mock_ai_func]
        mock_plugin_registry.plugins = {"test_plugin": mock_plugin}

        mock_get_instance.return_value = mock_plugin_registry

        # Test integration
        enabled_capabilities = {"ai_capability": ["test:read"]}
        integrate_with_function_registry(mock_registry, enabled_capabilities)

        # Verify function was registered
        mock_registry.register_function.assert_called_once()
        call_args = mock_registry.register_function.call_args
        assert call_args[0][0] == "test_function"  # function name
        assert callable(call_args[0][1])  # handler
        assert call_args[0][2]["name"] == "test_function"  # schema

    @patch("src.agent.plugins.integration.get_plugin_registry_instance")
    def test_integrate_with_function_registry_no_registry(self, mock_get_instance):
        """Test integration when plugin registry not available."""
        mock_get_instance.return_value = None
        mock_function_registry = Mock()

        # Should not raise exception
        integrate_with_function_registry(mock_function_registry, {})

        # Should not register any functions
        mock_function_registry.register_function.assert_not_called()

    @patch("src.agent.plugins.integration.get_plugin_registry_instance")
    def test_integrate_with_function_registry_no_enabled_capabilities(self, mock_get_instance):
        """Test integration with auto-discovery when no enabled capabilities provided."""
        mock_plugin_registry = Mock()
        mock_plugin_registry.capabilities = {"ai_capability": Mock(ai_function=True, scopes=["test:read"])}
        mock_plugin_registry.capability_to_plugin = {"ai_capability": "test_plugin"}
        # Mock the plugin and its get_ai_functions method
        mock_plugin = Mock()
        mock_plugin.get_ai_functions.return_value = []  # Return empty list instead of Mock
        mock_plugin_registry.plugins = {"test_plugin": mock_plugin}
        mock_get_instance.return_value = mock_plugin_registry

        mock_function_registry = Mock()

        # Test with None (should auto-discover)
        integrate_with_function_registry(mock_function_registry, None)

        # Should have processed the AI function capability


class TestCapabilityListing:
    """Test capability listing and information retrieval."""

    def test_list_all_capabilities_no_plugins(self):
        """Test listing capabilities when no plugins are available."""
        mock_executor_capabilities = {"exec1": Mock(), "exec2": Mock()}

        with patch("src.agent.plugins.integration._capabilities", mock_executor_capabilities):
            with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=None):
                capabilities = list_all_capabilities()

                # Should return only executor capabilities
                assert set(capabilities) == {"exec1", "exec2"}

    def test_list_all_capabilities_with_plugins(self):
        """Test listing capabilities with plugins available."""
        mock_executor_capabilities = {"exec1": Mock(), "exec2": Mock()}

        mock_registry = Mock()
        mock_registry.capabilities = {"plugin1": Mock(), "plugin2": Mock(), "exec1": Mock()}  # exec1 overlap

        with patch("src.agent.plugins.integration._capabilities", mock_executor_capabilities):
            with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=mock_registry):
                capabilities = list_all_capabilities()

                # Should return combined and deduplicated capabilities
                assert set(capabilities) == {"exec1", "exec2", "plugin1", "plugin2"}

    def test_get_capability_info_from_plugin(self):
        """Test getting capability info from plugin."""
        mock_registry = Mock()
        mock_capability_def = CapabilityDefinition(
            id="plugin_cap",
            name="Plugin Capability",
            version="1.0.0",
            description="Test plugin capability",
            capabilities=[CapabilityType.TEXT, CapabilityType.AI_FUNCTION],
            plugin_name="test_plugin",
            required_scopes=["test:read"],
            tags=["test"],
            input_mode="text",
            output_mode="text",
            priority=1,
            system_prompt="System prompt for capability 3",
        )
        mock_registry.get_capability.return_value = mock_capability_def

        with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=mock_registry):
            info = get_capability_info("plugin_cap")

            expected = {
                "capability_id": "plugin_cap",
                "name": "Plugin Capability",
                "description": "Test plugin capability",
                "plugin_name": "test_plugin",
                "source": "plugin",
                "scopes": ["test:read"],  # From required_scopes field
                "ai_function": True,
                "tags": ["test"],
            }
            assert info == expected

    def test_get_capability_info_from_executor_fallback(self):
        """Test getting capability info from executor when plugin returns None."""
        mock_executor = Mock()
        mock_executor.__doc__ = "Test executor capability"
        mock_executor_capabilities = {"exec_cap": mock_executor}

        mock_registry = Mock()
        mock_registry.get_capability.return_value = None  # Plugin doesn't have it

        with patch("src.agent.plugins.integration._capabilities", mock_executor_capabilities):
            with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=mock_registry):
                info = get_capability_info("exec_cap")

                expected = {
                    "capability_id": "exec_cap",
                    "name": "Exec Cap",
                    "description": "Test executor capability",
                    "source": "executor",
                }
                assert info == expected

    def test_get_capability_info_not_found(self):
        """Test getting capability info when capability doesn't exist."""
        mock_registry = Mock()
        mock_registry.get_capability.return_value = None

        with patch("src.agent.plugins.integration._capabilities", {}):
            with patch("src.agent.plugins.integration.get_plugin_registry_instance", return_value=mock_registry):
                info = get_capability_info("nonexistent")

                assert info == {}


class TestPluginSystemEnable:
    """Test plugin system enablement and initialization."""

    @patch("src.agent.plugins.integration.integrate_plugins_with_capabilities")
    @patch("agent.core.dispatcher.get_function_registry")
    @patch("src.agent.plugins.integration.integrate_with_function_registry")
    def test_enable_plugin_system_success(self, mock_integrate_func_registry, mock_get_registry, mock_integrate):
        """Test successful plugin system enablement."""
        # Mock integration result
        mock_integrate.return_value = {"test_cap": ["test:read"]}

        # Mock function registry
        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        enable_plugin_system()

        # Verify integration was called
        mock_integrate.assert_called_once()

        # Verify function registry integration
        mock_integrate_func_registry.assert_called_once_with(mock_registry, {"test_cap": ["test:read"]})

    @patch("src.agent.plugins.integration.integrate_plugins_with_capabilities")
    def test_enable_plugin_system_integration_failure(self, mock_integrate):
        """Test plugin system enablement when integration fails."""
        mock_integrate.side_effect = Exception("Integration failed")

        # Should not raise exception (logs error and continues)
        enable_plugin_system()

        mock_integrate.assert_called_once()

    @patch("src.agent.plugins.integration.integrate_plugins_with_capabilities")
    @patch("agent.core.dispatcher.get_function_registry")
    def test_enable_plugin_system_function_registry_failure(self, mock_get_registry, mock_integrate):
        """Test plugin system enablement when function registry integration fails."""
        mock_integrate.return_value = {"test_cap": ["test:read"]}

        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry

        with patch("src.agent.plugins.integration.integrate_with_function_registry") as mock_integrate_func:
            mock_integrate_func.side_effect = Exception("Registry failed")

            # Should not raise exception (logs error and continues)
            enable_plugin_system()

            mock_integrate.assert_called_once()

    @patch("src.agent.plugins.integration.integrate_plugins_with_capabilities")
    def test_enable_plugin_system_multimodal_helper(self, mock_integrate):
        """Test plugin system enablement sets up multimodal helper."""
        mock_integrate.return_value = {}

        with patch("agent.core.dispatcher.get_function_registry", side_effect=Exception("No registry")):
            with patch("agent.utils.multimodal.MultiModalHelper") as mock_helper:
                import sys

                original_modules = sys.modules.copy()
                try:
                    # Clear agentup.multimodal from sys.modules if it exists
                    if "agentup.multimodal" in sys.modules:
                        del sys.modules["agentup.multimodal"]

                    with patch("types.ModuleType") as mock_module_type:
                        mock_module = Mock()
                        mock_module_type.return_value = mock_module

                        enable_plugin_system()

                        # Verify module was created and registered
                        mock_module_type.assert_called_once_with("agentup.multimodal")
                        assert mock_module.MultiModalHelper is mock_helper
                        assert sys.modules["agentup.multimodal"] is mock_module
                finally:
                    # Restore original sys.modules
                    sys.modules.clear()
                    sys.modules.update(original_modules)


class TestGlobalPluginState:
    """Test global plugin registry and adapter management."""

    def test_get_plugin_registry_instance_initially_none(self):
        """Test that plugin registry instance is initially None."""
        # Reset global state
        with patch("src.agent.plugins.integration._plugin_registry_instance", [None]):
            registry = get_plugin_registry_instance()
            assert registry is None

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_plugin_registry_stored_globally(self, mock_get_registry):
        """Test that plugin registry is stored globally after integration."""
        mock_config = Mock()
        mock_config.plugins = {}

        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.plugins = {}
        mock_registry.discover_plugins.return_value = None

        # Integration should store registry globally even with empty config
        with patch("src.agent.plugins.integration._plugin_registry_instance", [None]) as mock_global:
            result = integrate_plugins_with_capabilities(mock_config)

            # With empty config, should return empty dict but still store registry
            assert result == {}
            assert mock_global[0] == mock_registry  # Registry should be stored

    def test_get_plugin_adapter_singleton(self):
        """Test that plugin adapter follows singleton pattern."""
        adapter1 = get_plugin_adapter()
        adapter2 = get_plugin_adapter()

        assert adapter1 is adapter2
        assert isinstance(adapter1, PluginAdapter)


class TestServiceConfiguration:
    """Test service configuration for plugins."""

    def test_get_available_services(self):
        """Test getting available services."""
        with patch("agent.llm_providers.create_llm_provider") as mock_llm_factory:
            with patch("agent.utils.multimodal.MultiModalHelper") as _mock_multimodal:
                from src.agent.plugins.integration import _get_available_services

                services = _get_available_services()

                assert "llm_factory" in services
                assert services["llm_factory"] is mock_llm_factory
                assert "multimodal" in services
                assert isinstance(services["multimodal"], Mock)  # Mock of MultiModalHelper instance

    def test_get_available_services_import_failures(self):
        """Test service discovery with import failures."""
        # Store original import to avoid recursion
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name in ["agent.llm_providers", "agent.utils.multimodal"]:
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from src.agent.plugins.integration import _get_available_services

            services = _get_available_services()

            # Should return empty dict when imports fail
            assert services == {}


class TestConfigurationValidation:
    """Test configuration validation and error handling."""

    def test_no_plugin_configuration_returns_empty(self):
        """Test that missing plugin configuration returns empty dict."""
        mock_config = Mock()
        mock_config.plugins = {}

        with patch("src.agent.plugins.integration.get_plugin_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_get_registry.return_value = mock_registry
            mock_registry.plugins = {}
            mock_registry.discover_plugins.return_value = None

            result = integrate_plugins_with_capabilities(mock_config)
            assert result == {}

    def test_config_loading_failure(self):
        """Test handling of config loading failure."""
        mock_config = Mock()
        # Make plugins property raise exception
        type(mock_config).plugins = PropertyMock(side_effect=Exception("Config error"))

        with patch("src.agent.plugins.integration.get_plugin_registry") as mock_get_registry:
            mock_registry = Mock()
            mock_get_registry.return_value = mock_registry
            mock_registry.plugins = {}
            mock_registry.discover_plugins.return_value = None

            # Should handle config loading failure gracefully
            result = integrate_plugins_with_capabilities(mock_config)
            assert result == {}

    @patch("src.agent.plugins.integration.get_plugin_registry")
    def test_plugin_with_no_capabilities_skipped(self, mock_get_registry):
        """Test that plugin with no capabilities is skipped with warning."""
        mock_config = Mock()
        
        # Use dict format matching Settings model - empty capabilities
        mock_config.plugins = {
            "empty_plugin": {
                "capabilities": {}  # Empty capabilities dict
            }
        }

        mock_registry = Mock()
        mock_get_registry.return_value = mock_registry
        mock_registry.plugins = {"empty_plugin": Mock()}
        mock_registry.discover_plugins.return_value = None

        with patch("src.agent.plugins.integration._get_available_services", return_value={}):
            result = integrate_plugins_with_capabilities(mock_config)
            assert result == {}


# Add custom PropertyMock import for older Python versions
try:
    from unittest.mock import PropertyMock
except ImportError:

    class PropertyMock(Mock):
        def __get__(self, obj, obj_type=None):
            return self()

        def __set__(self, obj, val):
            self(val)
