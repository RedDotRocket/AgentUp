"""Tests for the service management system (src/agent/services.py)."""

# Import the services to test
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.services import CacheService, DatabaseService, Service, ServiceError, ServiceRegistry, WebAPIService


class TestService:
    """Test the Service base class."""

    def test_service_initialization(self):
        """Test Service initialization."""
        config = {"test": "config"}
        service = Service("test_service", config)

        assert service.name == "test_service"
        assert service.config == config
        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_service_abstract_methods(self):
        """Test that abstract methods raise NotImplementedError."""
        service = Service("test", {})

        with pytest.raises(NotImplementedError):
            await service.initialize()

        with pytest.raises(NotImplementedError):
            await service.close()

    @pytest.mark.asyncio
    async def test_service_health_check_default(self):
        """Test default health check implementation."""
        service = Service("test", {})
        health = await service.health_check()

        assert health == {"status": "unknown"}


class TestDatabaseService:
    """Test the DatabaseService implementation."""

    def test_database_service_initialization(self):
        """Test DatabaseService initialization."""
        config = {"url": "postgresql://user:pass@localhost/db", "pool_size": 10}

        db_service = DatabaseService("test_db", config)

        assert db_service.name == "test_db"
        assert db_service.config == config
        assert db_service.connection_url == "postgresql://user:pass@localhost/db"
        assert db_service.pool_size == 10
        assert db_service.is_initialized is False

    def test_database_service_default_config(self):
        """Test DatabaseService with default configuration."""
        config = {}

        db_service = DatabaseService("test_db", config)

        assert db_service.connection_url == "sqlite:///./agent.db"
        assert db_service.pool_size == 5

    @pytest.mark.asyncio
    async def test_database_service_initialize(self):
        """Test DatabaseService initialization."""
        config = {"url": "postgresql://user:pass@localhost/db"}
        db_service = DatabaseService("test_db", config)

        await db_service.initialize()

        assert db_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_database_service_close(self):
        """Test DatabaseService close method."""
        config = {"url": "sqlite:///test.db"}
        db_service = DatabaseService("test_db", config)
        db_service._initialized = True

        await db_service.close()

        assert db_service.is_initialized is False

    @pytest.mark.asyncio
    async def test_database_service_health_check_healthy(self):
        """Test DatabaseService health check when healthy."""
        config = {"url": "postgresql://user:pass@localhost/db"}
        db_service = DatabaseService("test_db", config)

        health = await db_service.health_check()

        assert health["status"] == "healthy"
        assert "connection_url" in health
        assert health["connection_url"] == "localhost/db"

    @pytest.mark.asyncio
    async def test_database_service_execute(self):
        """Test DatabaseService execute method."""
        config = {"url": "sqlite:///test.db"}
        db_service = DatabaseService("test_db", config)

        result = await db_service.execute("SELECT 1")

        assert result == {"result": "query_executed"}
        assert db_service.is_initialized is True


class TestCacheService:
    """Test the CacheService implementation."""

    def test_cache_service_initialization(self):
        """Test CacheService initialization."""
        config = {"url": "valkey://localhost:6379/0", "ttl": 1800}

        cache_service = CacheService("test_cache", config)

        assert cache_service.name == "test_cache"
        assert cache_service.config == config
        assert cache_service.url == "valkey://localhost:6379/0"
        assert cache_service.ttl == 1800
        assert cache_service.is_initialized is False

    def test_cache_service_default_config(self):
        """Test CacheService with default configuration."""
        config = {}

        cache_service = CacheService("test_cache", config)

        assert cache_service.url == "valkey://localhost:6379"
        assert cache_service.ttl == 3600

    @pytest.mark.asyncio
    async def test_cache_service_initialize(self):
        """Test CacheService initialization."""
        config = {"url": "valkey://localhost:6379/0"}
        cache_service = CacheService("test_cache", config)

        await cache_service.initialize()

        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_close(self):
        """Test CacheService close method."""
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)
        cache_service._initialized = True

        await cache_service.close()

        assert cache_service.is_initialized is False

    @pytest.mark.asyncio
    async def test_cache_service_health_check_healthy(self):
        """Test CacheService health check when healthy."""
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        health = await cache_service.health_check()

        assert health["status"] == "healthy"
        assert health["url"] == "valkey://localhost:6379"

    @pytest.mark.asyncio
    async def test_cache_service_get_method(self):
        """Test CacheService get method."""
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        value = await cache_service.get("test_key")

        assert value is None
        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_set_method(self):
        """Test CacheService set method."""
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        await cache_service.set("test_key", "test_value", ttl=300)

        assert cache_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_cache_service_delete_method(self):
        """Test CacheService delete method."""
        config = {"url": "valkey://localhost:6379"}
        cache_service = CacheService("test_cache", config)

        await cache_service.delete("test_key")

        assert cache_service.is_initialized is True


class TestWebAPIService:
    """Test the WebAPIService implementation."""

    def test_web_api_service_initialization(self):
        """Test WebAPIService initialization."""
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
        """Test WebAPIService with default configuration."""
        config = {}

        web_service = WebAPIService("test_api", config)

        assert web_service.base_url == ""
        assert web_service.api_key == ""
        assert web_service.headers == {}
        assert web_service.timeout == 30.0

    @pytest.mark.asyncio
    async def test_web_api_service_initialize(self):
        """Test WebAPIService initialization."""
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        await web_service.initialize()

        assert web_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_web_api_service_close(self):
        """Test WebAPIService close method."""
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)
        web_service._initialized = True

        await web_service.close()

        assert web_service.is_initialized is False

    @pytest.mark.asyncio
    async def test_web_api_service_health_check_healthy(self):
        """Test WebAPIService health check when healthy."""
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        health = await web_service.health_check()

        assert health["status"] == "healthy"
        assert health["base_url"] == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_web_api_service_get_method(self):
        """Test WebAPIService get method."""
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        result = await web_service.get("users")

        assert result == {"result": "api_response"}
        assert web_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_web_api_service_post_method(self):
        """Test WebAPIService post method."""
        config = {"base_url": "https://api.example.com"}
        web_service = WebAPIService("test_api", config)

        result = await web_service.post("users", {"name": "test"})

        assert result == {"result": "api_response"}
        assert web_service.is_initialized is True


class TestServiceRegistry:
    """Test the ServiceRegistry class."""

    def test_service_registry_initialization_empty(self):
        """Test ServiceRegistry initialization with empty config."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            assert registry.config is not None
            assert registry._services == {}
            assert "openai" in registry._llm_providers
            assert "anthropic" in registry._llm_providers
            assert "ollama" in registry._llm_providers

    def test_service_registry_llm_provider_mapping(self):
        """Test LLM provider mapping in ServiceRegistry."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            # Test that LLM providers are properly mapped
            from agent.llm_providers.anthropic import AnthropicProvider
            from agent.llm_providers.ollama import OllamaProvider
            from agent.llm_providers.openai import OpenAIProvider

            assert registry._llm_providers["openai"] == OpenAIProvider
            assert registry._llm_providers["anthropic"] == AnthropicProvider
            assert registry._llm_providers["ollama"] == OllamaProvider

    def test_register_service_type(self):
        """Test registering a custom service type."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

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
        """Test creating an OpenAI LLM service."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            config = {"provider": "openai", "api_key": "test_key", "model": "gpt-4"}

            service = registry._create_llm_service("openai", config)

            assert service.name == "openai"
            assert service.config == config

    def test_create_llm_service_missing_provider(self):
        """Test creating an LLM service without provider."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            config = {"api_key": "test_key"}

            with pytest.raises(ServiceError, match="missing 'provider' configuration"):
                registry._create_llm_service("openai", config)

    def test_create_llm_service_unknown_provider(self):
        """Test creating an LLM service with unknown provider."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            config = {"provider": "unknown", "api_key": "test_key"}

            with pytest.raises(ServiceError, match="Unknown LLM provider"):
                registry._create_llm_service("unknown", config)

    def test_initialize_all_services(self):
        """Test initializing all services from config."""
        config_data = {
            "agent": {"name": "test"},
            "services": {
                "valkey": {"type": "cache", "settings": {"url": "valkey://localhost:6379"}},
                "postgres": {"type": "database", "settings": {"url": "postgresql://user:pass@localhost/db"}},
            },
        }

        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = config_data

            registry = ServiceRegistry()

            # Initialize non-LLM services (which should work)
            registry.initialize_all()

            # Should have created services for configured items
            assert len(registry._services) == 2
            assert "valkey" in registry._services
            assert "postgres" in registry._services
            assert isinstance(registry._services["valkey"], CacheService)
            assert isinstance(registry._services["postgres"], DatabaseService)


class TestServiceRegistryIntegration:
    """Test ServiceRegistry integration scenarios."""

    def test_full_service_registry_flow_with_mocks(self):
        """Test complete service registry flow with mocked services."""
        config_data = {
            "agent": {"name": "integration-test"},
            "services": {
                "valkey": {"type": "cache", "settings": {"url": "valkey://localhost:6379"}},
                "postgres": {"type": "database", "settings": {"url": "postgresql://user:pass@localhost/db"}},
                "custom_api": {"type": "web_api", "settings": {"base_url": "https://api.example.com"}},
            },
        }

        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = config_data

            registry = ServiceRegistry()

            # Initialize all services
            registry.initialize_all()

            # Verify all services were created
            assert len(registry._services) == 3
            assert "valkey" in registry._services
            assert "postgres" in registry._services
            assert "custom_api" in registry._services

            # Verify service types
            assert isinstance(registry._services["valkey"], CacheService)
            assert isinstance(registry._services["postgres"], DatabaseService)
            assert isinstance(registry._services["custom_api"], WebAPIService)

    def test_llm_service_creation_separately(self):
        """Test LLM service creation using _create_llm_service method."""
        with patch("agent.services.load_config") as mock_load:
            mock_load.return_value = {"agent": {"name": "test"}, "services": {}}

            registry = ServiceRegistry()

            config = {"provider": "openai", "api_key": "test_key", "model": "gpt-4"}

            # Test creating LLM service directly
            service = registry._create_llm_service("openai", config)

            assert service.name == "openai"
            assert service.config == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
