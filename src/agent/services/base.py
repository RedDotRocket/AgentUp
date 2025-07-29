from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from .config import ConfigurationManager


class Service(ABC):
    """Base service class with lifecycle management.

    All services in the AgentUp framework should inherit from this class
    to ensure consistent lifecycle management and configuration access.
    """

    def __init__(self, config_manager: "ConfigurationManager"):
        """Initialize the service with configuration manager.

        Args:
            config_manager: Singleton configuration manager instance
        """
        self.config = config_manager
        self._initialized = False
        self.logger = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service.

        This method should be called once during application startup.
        Services should perform any necessary setup here, such as:
        - Loading configuration
        - Establishing connections
        - Registering handlers

        Raises:
            Exception: If initialization fails
        """
        pass

    async def shutdown(self) -> None:
        """Cleanup service resources.

        This method is called during application shutdown.
        Services should override this to clean up resources such as:
        - Closing connections
        - Flushing buffers
        - Releasing locks
        """
        # Base implementation does nothing - services override as needed
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value for this service.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
