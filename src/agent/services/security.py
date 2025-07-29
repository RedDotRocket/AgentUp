from .base import Service
from .config import ConfigurationManager


class SecurityService(Service):
    """Manages security and authentication for the agent.

    This service consolidates all security-related functionality,
    including authentication, authorization, and security context management.
    """

    def __init__(self, config_manager: ConfigurationManager):
        super().__init__(config_manager)
        self._security_manager = None

    async def initialize(self) -> None:
        self.logger.info("Initializing security service")

        try:
            # Create security manager using existing implementation
            from agent.config import Config
            from agent.security import create_security_manager, set_global_security_manager

            # Pass the full config as dictionary for backward compatibility
            config_dict = Config.model_dump()
            self._security_manager = create_security_manager(config_dict)
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
        self.logger.debug("Shutting down security service")
        self._security_manager = None

    @property
    def security_manager(self):
        return self._security_manager

    def is_enabled(self) -> bool:
        return self._security_manager is not None and self._security_manager.is_auth_enabled()
