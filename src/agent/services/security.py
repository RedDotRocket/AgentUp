"""Security service for AgentUp framework."""



from .base import Service
from .config import ConfigurationManager


class SecurityService(Service):
    """Manages security and authentication for the agent.

    This service consolidates all security-related functionality,
    including authentication, authorization, and security context management.
    """

    def __init__(self, config_manager: ConfigurationManager):
        """Initialize the security service."""
        super().__init__(config_manager)
        self._security_manager = None

    async def initialize(self) -> None:
        """Initialize the security service."""
        self.logger.info("Initializing security service")

        try:
            # Create security manager using existing implementation
            from agent.security import create_security_manager, set_global_security_manager

            self._security_manager = create_security_manager(self.config.config)
            set_global_security_manager(self._security_manager)

            if self._security_manager.is_auth_enabled():
                auth_type = self._security_manager.get_primary_auth_type()
                self.logger.info(f"Security enabled with {auth_type} authentication")
            else:
                self.logger.warning("Security disabled - all endpoints are UNPROTECTED")

            self._initialized = True

        except Exception as e:
            self.logger.error(f"Failed to initialize security service: {e}")
            raise

    async def shutdown(self) -> None:
        """Cleanup security resources."""
        self.logger.debug("Shutting down security service")
        self._security_manager = None

    @property
    def security_manager(self):
        """Get the underlying security manager."""
        return self._security_manager

    def is_enabled(self) -> bool:
        """Check if security is enabled."""
        return self._security_manager is not None and self._security_manager.is_auth_enabled()
