# Import the services to test
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.config import Config
from agent.services import CacheService, Service, ServiceError, ServiceRegistry, WebAPIService


class TestService:
    def test_service_initialization(self):
        # Create a concrete test service class that mimics other services
        class TestServiceImpl(Service):
            def __init__(self, name, config):
                # Fix: The base Service class only accepts 'config'.
                super().__init__(config)
                # The name is set on the instance after the base is initialized.
                self.name = name

            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

        config = {"test": "config"}
        service = TestServiceImpl("test_service", config)

        assert service.name == "test_service"
        assert service.config == config
        assert service.initialized is False

    @pytest.mark.asyncio
    async def test_service_abstract_methods(self):
        # Test that Service cannot be instantiated directly
        with pytest.raises(TypeError, match="Can't instantiate abstract class Service"):
            # This call should fail because Service is abstract
            # Fix: The constructor only takes one argument (config)
            Service({})

    @pytest.mark.asyncio
    async def test_service_health_check_default(self):
        # Create a concrete test service class
        class TestServiceImpl(Service):
            def __init__(self, name, config):
                # Fix: The base Service class only accepts 'config'.
                super().__init__(config)
                self.name = name

            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

            async def health_check(self):
                return {"status": "unknown"}

        service = TestServiceImpl("test_service", {})
        health = await service.health_check()

        assert health == {"status": "unknown"}


class TestCacheService:
    def test_cache_service_initialization(self):
        config = {"url": "valkey://localhost:6379/0", "ttl": 1800}

        cache_service = CacheService("test_cache", config)

        assert cache_service.name == "test_cache"
        assert cache_service.config == config
        assert cache_service.url == "valkey://localhost:6379/0"
        assert cache_service.ttl == 1800
        assert cache_service.is_initialized is False

    def test_cache_service_default_config(self):
        config = {}

        cache_service = CacheService("test_cache", config)

        assert cache_service.url == "valkey://localhost:6379"
        assert cache_service.ttl == 3600

    @pytest.mark.asyncio
    async def test_cache_service_initialize(self):
        config = {"url": "valkey://localhost:6379/0"}
        cache_service = CacheService("test_cache", config)

        await cache_service.initialize()

        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_close(self):
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)
        cache_service._initialized = True

        await cache_service.close()

        assert cache_service.is_initialized is False

    @pytest.mark.asyncio
    async def test_cache_service_health_check_healthy(self):
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        health = await cache_service.health_check()

        assert health["status"] == "healthy"
        assert health["url"] == "valkey://localhost:6379"

    @pytest.mark.asyncio
    async def test_cache_service_get_method(self):
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        value = await cache_service.get("test_key")

        assert value is None
        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_set_method(self):
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        await cache_service.set("test_key", "test_value", ttl=300)

        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_delete_method(self):
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        await cache_service.delete("test_key")

        assert cache_service.is_initialized is True


class TestWebAPIService:
    def test_web_api_service_initialization(self):
        config = {
            "base_url": "https://api.example.com",
            "api_key": "test_key",
            "headers": {"User-Agent": "AgentUp/1.0"},
            "timeout": 30.0,
        }

        web_service = WebAPIService("test_api", config)

        assert web_service.name == "test_api"
        assert web_service.config == config
        assert web_service.base_url == "https://api.example.com"
        assert web_service.api_key == "test_key"
        assert web_service.headers == {"User-Agent": "AgentUp/1.0"}
        assert web_service.timeout == 30.0
        assert web_service.is_initialized is False

    def test_web_api_service_default_config(self):
        config = {}

        web_service = WebAPIService("test_api", config)

        assert web_service.base_url == ""
        assert web_service.api_key == ""
        assert web_service.headers == {}
        assert web_service.timeout == 30.0

    @pytest.mark.asyncio
    async def test_web_api_service_initialize(self):
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        await web_service.initialize()

        assert web_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_web_api_service_close(self):
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)
        web_service._initialized = True

        await web_service.close()

        assert web_service.is_initialized is False

    @pytest.mark.asyncio
    async def test_web_api_service_health_check_healthy(self):
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        health = await web_service.health_check()

        assert health["status"] == "healthy"
        assert health["base_url"] == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_web_api_service_get_method(self):
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        result = await web_service.get("users")

        assert result == {"result": "api_response"}
        assert web_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_web_api_service_post_method(self):
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        result = await web_service.post("users", {"name": "test"})

        assert result == {"result": "api_response"}
        assert web_service.is_initialized is True


class TestServiceRegistry:
    def test_service_registry_initialization_empty(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            assert registry.config is not None
            assert registry._services == {}
            assert "openai" in registry._llm_providers
            assert "anthropic" in registry._llm_providers
            assert "ollama" in registry._llm_providers

    def test_service_registry_llm_provider_mapping(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            # Test that LLM providers are properly mapped
            from agent.llm_providers.anthropic import AnthropicProvider
            from agent.llm_providers.ollama import OllamaProvider
            from agent.llm_providers.openai import OpenAIProvider

            assert registry._llm_providers["openai"] == OpenAIProvider
            assert registry._llm_providers["anthropic"] == AnthropicProvider
            assert registry._llm_providers["ollama"] == OllamaProvider

    def test_register_service_type(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            class CustomService(Service):
                async def initialize(self):
                    pass

                async def close(self):
                    pass

            registry.register_service_type("custom", CustomService)

            assert "custom" in registry._service_types
            assert registry._service_types["custom"] == CustomService

    def test_create_llm_service_openai(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            config = {"provider": "openai", "api_key": "test_key", "model": "gpt-4"}

            service = registry._create_llm_service("openai", config)

            assert service.name == "openai"
            assert service.config == config

    def test_create_llm_service_missing_provider(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            config = {"api_key": "test_key"}

            with pytest.raises(ServiceError, match="missing 'provider' configuration"):
                registry._create_llm_service("openai", config)

    def test_create_llm_service_unknown_provider(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            config = {"provider": "unknown", "api_key": "test_key"}

            with pytest.raises(ServiceError, match="Unknown LLM provider"):
                registry._create_llm_service("unknown", config)

    def test_initialize_all_services(self):
        config_data = {
            "project_name": "test",
            "services": {
                "valkey": {"type": "cache", "settings": {"url": "valkey://localhost:6379"}},
            },
        }

        mock_config = Mock()
        mock_config.model_dump.return_value = config_data
        mock_config.project_name = "test-registry"
        mock_config.services = {"valkey": Mock(type="cache", settings={"url": "valkey://localhost:6379"})}

        with patch("agent.services.registry.Config", mock_config):
            registry = ServiceRegistry()

            # Initialize non-LLM services (which should work)
            registry.initialize_all()

            # Should have created services for configured items
            assert len(registry._services) == 1
            assert "valkey" in registry._services
            assert isinstance(registry._services["valkey"], CacheService)


class TestServiceRegistryIntegration:
    def test_full_service_registry_flow_with_mocks(self):
        config_data = {
            "project_name": "integration-test",
            "description": "Integration test agent",
            "version": "1.0.0",
            "services": {
                "valkey": {"type": "cache", "settings": {"url": "valkey://localhost:6379"}},
                "custom_api": {"type": "web_api", "settings": {"base_url": "https://api.example.com"}},
            },
        }

        mock_config = Mock()
        mock_config.model_dump.return_value = config_data
        mock_config.project_name = "integration-test"
        mock_config.services = config_data["services"]

        with patch("agent.services.registry.Config", mock_config):
            registry = ServiceRegistry()

            # Initialize all services
            registry.initialize_all()

            # Verify all services were created
            assert len(registry._services) == 2
            assert "valkey" in registry._services
            assert "custom_api" in registry._services

            # Verify service types
            assert isinstance(registry._services["valkey"], CacheService)
            assert isinstance(registry._services["custom_api"], WebAPIService)

    def test_llm_service_creation_separately(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            config = {"provider": "openai", "api_key": "test_key", "model": "gpt-4"}

            # Test creating LLM service directly
            service = registry._create_llm_service("openai", config)

            assert service.name == "openai"
            assert service.config == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
