"""State management service for AgentUp framework."""

from typing import Any

from .base import Service
from .config import ConfigurationManager


class StateManager(Service):
    """Manages conversation and application state.

    This service provides centralized state management with support for:
    - Multiple backends (memory, file, valkey)
    - Context management
    - State persistence
    """

    def __init__(self, config_manager: ConfigurationManager):
        """Initialize the state manager."""
        super().__init__(config_manager)
        self._context_manager = None
        self._backend = None
        self._backend_config = {}

    async def initialize(self) -> None:
        """Initialize the state manager."""
        self.logger.info("Initializing state manager")

        state_config = self.config.get("state_management", {})
        if not state_config.get("enabled", False):
            self.logger.info("State management disabled")
            self._initialized = True
            return

        self._backend = state_config.get("backend", "memory")
        self._backend_config = self._prepare_backend_config(state_config)

        try:
            from agent.state.context import get_context_manager

            self._context_manager = get_context_manager(self._backend, **self._backend_config)

            self._initialized = True
            self.logger.info(f"State manager initialized with {self._backend} backend")

        except Exception as e:
            self.logger.error(f"Failed to initialize state manager: {e}")
            raise

    async def shutdown(self) -> None:
        """Cleanup state resources."""
        if self._context_manager:
            try:
                # Cleanup old contexts
                cleaned = await self._context_manager.cleanup_old_contexts(max_age_hours=24)
                if cleaned > 0:
                    self.logger.info(f"Cleaned up {cleaned} old conversation contexts")
            except Exception as e:
                self.logger.error(f"Error during state cleanup: {e}")

        self._context_manager = None

    def _prepare_backend_config(self, state_config: dict[str, Any]) -> dict[str, Any]:
        """Prepare backend-specific configuration."""
        backend_config = {}

        if self._backend == "valkey":
            # Get Valkey URL from services configuration or state config
            valkey_service = self.config.get("services.valkey.config", {})
            backend_config["url"] = valkey_service.get("url", "valkey://localhost:6379")
            backend_config["ttl"] = state_config.get("ttl", 3600)
        elif self._backend == "file":
            backend_config["storage_dir"] = state_config.get("storage_dir", "./conversation_states")

        # Add any additional config from state_config
        if "config" in state_config:
            backend_config.update(state_config["config"])

        return backend_config

    @property
    def context_manager(self):
        """Get the context manager instance."""
        return self._context_manager

    @property
    def backend_type(self) -> str:
        """Get the configured backend type."""
        return self._backend

    def is_enabled(self) -> bool:
        """Check if state management is enabled."""
        return self._context_manager is not None
