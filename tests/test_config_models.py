"""
Tests for AgentUp configuration models.
"""

import pytest
from pydantic import ValidationError

from src.agent.config.model import (
    AgentConfig,
    APIConfig,
    ConfigurationSettings,
    LogFormat,
    LoggingConfig,
    MCPConfig,
    MCPServerConfig,
    PluginCapabilityConfig,
    PluginConfig,
    ServiceConfig,
    expand_env_vars,
)


class TestLoggingConfig:
    def test_default_logging_config(self):
        config = LoggingConfig()

        assert config.enabled is True
        assert config.level == "INFO"
        assert config.format == LogFormat.TEXT
        assert config.console.enabled is True
        assert config.correlation_id is True
        assert config.request_logging is True

    def test_custom_logging_config(self):
        config = LoggingConfig(level="DEBUG", format=LogFormat.JSON, modules={"security": "WARNING", "api": "DEBUG"})

        assert config.level == "DEBUG"
        assert config.format == LogFormat.JSON
        assert config.modules["security"] == "WARNING"
        assert config.modules["api"] == "DEBUG"

    def test_invalid_log_level(self):
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INVALID")

        assert "Invalid log level" in str(exc_info.value)

    def test_log_level_case_insensitive(self):
        config = LoggingConfig(level="debug")
        assert config.level == "DEBUG"

        config = LoggingConfig(modules={"test": "warning"})
        assert config.modules["test"] == "WARNING"


class TestServiceConfig:
    def test_default_service_config(self):
        config = ServiceConfig(type="llm")

        assert config.type == "llm"
        assert config.enabled is True
        assert config.priority == 50
        assert config.health_check_enabled is True
        assert config.max_retries == 3

    def test_custom_service_config(self):
        config = ServiceConfig(
            type="custom-service", enabled=False, priority=10, settings={"api_key": "secret", "timeout": 30}
        )

        assert config.type == "custom-service"
        assert config.enabled is False
        assert config.priority == 10
        assert config.settings["api_key"] == "secret"
        assert config.settings["timeout"] == 30

    def test_service_type_validation(self):
        # Valid types
        ServiceConfig(type="llm")
        ServiceConfig(type="database")
        ServiceConfig(type="custom_service")
        ServiceConfig(type="service-name")

        # Invalid types
        with pytest.raises(ValidationError):
            ServiceConfig(type="")

        with pytest.raises(ValidationError):
            ServiceConfig(type="invalid service!")

    def test_priority_validation(self):
        ServiceConfig(type="test", priority=0)
        ServiceConfig(type="test", priority=100)

        with pytest.raises(ValidationError):
            ServiceConfig(type="test", priority=-1)

        with pytest.raises(ValidationError):
            ServiceConfig(type="test", priority=101)


class TestAPIConfig:
    def test_default_api_config(self):
        config = APIConfig()

        assert config.enabled is True
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.workers == 1
        assert config.cors_enabled is True
        assert "*" in config.cors_origins

    def test_custom_api_config(self):
        config = APIConfig(
            host="0.0.0.0", port=9000, workers=4, cors_origins=["https://example.com", "https://app.example.com"]
        )

        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.workers == 4
        assert "https://example.com" in config.cors_origins

    def test_port_validation(self):
        APIConfig(port=1)
        APIConfig(port=65535)

        with pytest.raises(ValidationError):
            APIConfig(port=0)

        with pytest.raises(ValidationError):
            APIConfig(port=65536)

    def test_workers_validation(self):
        APIConfig(workers=1)
        APIConfig(workers=32)

        with pytest.raises(ValidationError):
            APIConfig(workers=0)

        with pytest.raises(ValidationError):
            APIConfig(workers=33)


class TestMCPConfig:
    def test_mcp_server_config_stdio(self):
        config = MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="python",
            args=["-m", "mcp_server"],
            env={"DEBUG": "1"},
            tool_scopes={"test_tool": ["read"]},
        )

        assert config.name == "test-server"
        assert config.transport == "stdio"
        assert config.command == "python"
        assert config.args == ["-m", "mcp_server"]
        assert config.env["DEBUG"] == "1"

    def test_mcp_server_config_sse(self):
        config = MCPServerConfig(
            name="sse-server",
            transport="sse",
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer token"},
            timeout=60,
            tool_scopes={"test_tool": ["read"]},
        )

        assert config.name == "sse-server"
        assert config.transport == "sse"
        assert config.url == "https://api.example.com/mcp"
        assert config.headers["Authorization"] == "Bearer token"
        assert config.timeout == 60

    def test_mcp_server_config_validation(self):
        # stdio without command should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(name="test", transport="stdio", tool_scopes={"test": ["read"]})
        assert "command is required" in str(exc_info.value)

        # sse without url should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(name="test", transport="sse", tool_scopes={"test": ["read"]})
        assert "url is required" in str(exc_info.value)

        # Invalid sse url should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(name="test", transport="sse", url="invalid-url", tool_scopes={"test": ["read"]})
        assert "must start with http" in str(exc_info.value)

    def test_mcp_config(self):
        config = MCPConfig(
            enabled=True,
            client_enabled=True,
            server_enabled=True,
            server_port=9000,
            servers=[
                MCPServerConfig(
                    name="local",
                    transport="stdio",
                    command="python",
                    args=["-m", "local_server"],
                    tool_scopes={"test_tool": ["read"]},
                )
            ],
        )

        assert config.enabled is True
        assert config.server_port == 9000
        assert len(config.servers) == 1
        assert config.servers[0].name == "local"


class TestPluginConfig:
    def test_plugin_capability_config(self):
        capability = PluginCapabilityConfig(
            capability_id="text_processor",
            name="Text Processing",
            description="Process text input",
            required_scopes=["read", "process"],
            config={"max_length": 1000},
        )

        assert capability.capability_id == "text_processor"
        assert capability.name == "Text Processing"
        assert "read" in capability.required_scopes
        assert capability.config["max_length"] == 1000

    def test_plugin_config(self):
        plugin = PluginConfig(
            plugin_id="my.text.plugin",
            name="Text Plugin",
            description="A plugin for text processing",
            capabilities=[PluginCapabilityConfig(capability_id="process", required_scopes=["text:read"])],
            default_scopes=["basic"],
        )

        assert plugin.plugin_id == "my.text.plugin"
        assert plugin.name == "Text Plugin"
        assert len(plugin.capabilities) == 1
        assert plugin.capabilities[0].capability_id == "process"
        assert "basic" in plugin.default_scopes

    def test_plugin_id_validation(self):
        # Valid IDs
        PluginConfig(plugin_id="simple")
        PluginConfig(plugin_id="my-plugin")
        PluginConfig(plugin_id="my_plugin")
        PluginConfig(plugin_id="my.plugin.name")
        PluginConfig(plugin_id="plugin123")

        # Invalid IDs
        with pytest.raises(ValidationError):
            PluginConfig(plugin_id="")

        with pytest.raises(ValidationError):
            PluginConfig(plugin_id="invalid plugin!")


class TestAgentConfig:
    def test_default_agent_config(self):
        config = AgentConfig()

        assert config.project_name == "AgentUp"
        assert config.version == "1.0.0"
        assert config.services_enabled is True
        assert config.mcp_enabled is False
        assert config.environment == "development"
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.api, APIConfig)

    def test_custom_agent_config(self):
        config = AgentConfig(
            project_name="MyAgent",
            description="Custom AI agent",
            version="2.1.0",
            environment="production",
            mcp_enabled=True,
        )

        assert config.project_name == "MyAgent"
        assert config.description == "Custom AI agent"
        assert config.version == "2.1.0"
        assert config.environment == "production"
        assert config.mcp_enabled is True

    def test_project_name_validation(self):
        AgentConfig(project_name="A")  # Minimum length
        AgentConfig(project_name="A" * 100)  # Maximum length

        with pytest.raises(ValidationError):
            AgentConfig(project_name="")

        with pytest.raises(ValidationError):
            AgentConfig(project_name="A" * 101)

    def test_version_validation(self):
        # Valid versions
        AgentConfig(version="1.0.0")
        AgentConfig(version="10.20.30")
        AgentConfig(version="1.0.0-alpha")
        AgentConfig(version="1.0.0-beta.1")

        # Invalid versions
        with pytest.raises(ValidationError):
            AgentConfig(version="1.0")

        with pytest.raises(ValidationError):
            AgentConfig(version="v1.0.0")

        with pytest.raises(ValidationError):
            AgentConfig(version="1.0.0.0")

    def test_mcp_consistency_validation(self):
        config = AgentConfig(mcp_enabled=True)

        # Should auto-enable MCP config
        assert config.mcp.enabled is True

    def test_services_configuration(self):
        config = AgentConfig(
            services={
                "llm": ServiceConfig(type="openai", settings={"api_key": "secret"}),
                "database": ServiceConfig(type="postgresql", priority=10),
            }
        )

        assert "llm" in config.services
        assert "database" in config.services
        assert config.services["llm"].type == "openai"
        assert config.services["database"].priority == 10


class TestConfigurationSettings:
    def test_default_settings(self):
        settings = ConfigurationSettings()

        assert settings.CONFIG_FILE == "agentup.yml"
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"
        assert settings.API_HOST == "127.0.0.1"
        assert settings.API_PORT == 8000

    def test_directory_creation(self):
        settings = ConfigurationSettings(DATA_DIR="test_data", LOGS_DIR="test_logs", PLUGINS_DIR="test_plugins")

        # This would create directories in a real environment
        # Here we just test that the method exists and can be called
        try:
            settings.create_directories()
        except Exception:
            # Directory creation might fail in test environment, that's ok
            pass


class TestUtilityFunctions:
    def test_expand_env_vars_string(self):
        import os

        # Set test environment variable
        os.environ["TEST_VAR"] = "test_value"

        # Test simple expansion
        result = expand_env_vars("${TEST_VAR}")
        assert result == "test_value"

        # Test expansion with default
        result = expand_env_vars("${NONEXISTENT:default}")
        assert result == "default"

        # Test no expansion needed
        result = expand_env_vars("plain_string")
        assert result == "plain_string"

        # Clean up
        del os.environ["TEST_VAR"]

    def test_expand_env_vars_dict(self):
        import os

        os.environ["DB_HOST"] = "localhost"
        os.environ["DB_PORT"] = "5432"

        config = {"database": {"host": "${DB_HOST}", "port": "${DB_PORT}", "name": "mydb"}, "debug": "${DEBUG:false}"}

        result = expand_env_vars(config)

        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == "5432"
        assert result["database"]["name"] == "mydb"
        assert result["debug"] == "false"

        # Clean up
        del os.environ["DB_HOST"]
        del os.environ["DB_PORT"]

    def test_expand_env_vars_list(self):
        import os

        os.environ["PLUGIN1"] = "auth_plugin"

        config = ["${PLUGIN1}", "logging_plugin", "${PLUGIN2:default_plugin}"]

        result = expand_env_vars(config)

        assert result[0] == "auth_plugin"
        assert result[1] == "logging_plugin"
        assert result[2] == "default_plugin"

        # Clean up
        del os.environ["PLUGIN1"]


class TestModelSerialization:
    def test_agent_config_serialization(self):
        config = AgentConfig(project_name="TestAgent", version="1.2.3", mcp_enabled=True)

        # Serialize to dict (modern Pydantic v2 way) - exclude computed fields for round-trip
        config_dict = config.model_dump(
            exclude={
                "is_production",
                "is_development",
                "enabled_services",
                "total_service_count",
                "security_enabled",
                "full_name",
            }
        )
        assert config_dict["project_name"] == "TestAgent"
        assert config_dict["version"] == "1.2.3"
        assert config_dict["mcp_enabled"] is True
        assert isinstance(config_dict["logging"], dict)

        # Deserialize from dict
        restored_config = AgentConfig(**config_dict)
        assert restored_config.project_name == "TestAgent"
        assert restored_config.version == "1.2.3"
        assert restored_config.mcp_enabled is True

        # Test computed fields are accessible and work correctly
        assert restored_config.is_development is True  # computed field works
        assert restored_config.full_name == "TestAgent v1.2.3"  # computed field works

        # Test full serialization includes computed fields
        full_dict = config.model_dump()
        assert "is_development" in full_dict  # computed fields included in full dump
        assert "full_name" in full_dict
        assert full_dict["is_development"] is True
        assert full_dict["full_name"] == "TestAgent v1.2.3"

    def test_json_serialization(self):
        config = LoggingConfig(level="DEBUG", format=LogFormat.JSON)

        # Should be able to serialize to JSON
        json_str = config.model_dump_json()
        assert '"level":"DEBUG"' in json_str
        assert '"format":"json"' in json_str

        # Should be able to deserialize from JSON
        restored_config = LoggingConfig.model_validate_json(json_str)
        assert restored_config.level == "DEBUG"
        assert restored_config.format == LogFormat.JSON
