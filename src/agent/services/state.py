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
        super().__init__(config_manager)
        self._context_manager = None
        self._backend = None
        self._backend_config = {}

    async def initialize(self) -> None:
        self.logger.info("Initializing state manager")

        state_config = getattr(self.config, "state_management", None)
        if not state_config or not getattr(state_config, "enabled", False):
            self.logger.info("State management disabled")
            self._initialized = True
            return

        self._backend = getattr(state_config, "backend", "memory")
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
        backend_config = {}

        if self._backend == "valkey":
            # Get Valkey URL from services configuration or state config
            services = getattr(self.config, "services", None)
            valkey_service = {}
            if services:
                valkey_config = getattr(services, "valkey", None)
                if valkey_config:
                    valkey_service = getattr(valkey_config, "config", {})
                    if hasattr(valkey_service, "model_dump"):
                        valkey_service = valkey_service.model_dump()

            url = (
                valkey_service.get("url", "valkey://localhost:6379")
                if isinstance(valkey_service, dict)
                else getattr(valkey_service, "url", "valkey://localhost:6379")
            )
            backend_config["url"] = url
            backend_config["ttl"] = getattr(state_config, "ttl", 3600)
        elif self._backend == "file":
            backend_config["storage_dir"] = getattr(state_config, "storage_dir", "./conversation_states")

        # Add any additional config from state_config
        additional_config = getattr(state_config, "config", None)
        if additional_config:
            if hasattr(additional_config, "model_dump"):
                backend_config.update(additional_config.model_dump())
            elif isinstance(additional_config, dict):
                backend_config.update(additional_config)

        return backend_config

    @property
    def context_manager(self):
        return self._context_manager

    @property
    def backend_type(self) -> str:
        return self._backend

    def is_enabled(self) -> bool:
        return self._context_manager is not None
