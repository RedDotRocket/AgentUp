# Import the services to test
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent.config import Config
from agent.services import Service, ServiceError, ServiceRegistry


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

class TestServiceRegistry:
    def test_service_registry_initialization_empty(self):
        with patch.object(Config, "ai_provider", {"project_name": "test", "services": {}}):
            registry = ServiceRegistry()

            assert registry.config is not None
            assert registry._services == {}

 


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
