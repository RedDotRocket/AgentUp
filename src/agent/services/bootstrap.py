"""Bootstrap service for AgentUp application initialization.

This module handles all service initialization.
"""

import structlog
from fastapi import FastAPI

from .base import Service
from .capabilities import CapabilityRegistry
from .config import ConfigurationManager


class AgentBootstrapper:
    """Handles all agent initialization in proper order.

    This class orchestrates the initialization of all services,
    ensuring dependencies are resolved and services start in
    the correct order.
    """

    def __init__(self):
        """Initialize the bootstrapper."""
        self.logger = structlog.get_logger(__name__)
        self.config = ConfigurationManager()
        self.services: list[Service] = []
        self._service_map: dict[str, Service] = {}
        self._initialized = False

    async def initialize_services(self, app: FastAPI) -> None:
        """Initialize all services in dependency order.

        Args:
            app: FastAPI application instance to store services

        Raises:
            Exception: If any service fails to initialize
        """
        if self._initialized:
            self.logger.warning("Services already initialized, skipping")
            return

        self.logger.info("Starting service initialization")

        try:
            # Create services in dependency order
            services_to_init = await self._create_services()

            # Initialize each service
            for service in services_to_init:
                service_name = service.__class__.__name__
                try:
                    self.logger.debug(f"Initializing {service_name}")
                    await service.initialize()
                    self.services.append(service)
                    self._service_map[service_name.lower()] = service
                    self.logger.info(f"✓ Initialized {service_name}")
                except Exception as e:
                    self.logger.error(f"✗ Failed to initialize {service_name}: {e}")
                    # Cleanup any already initialized services
                    await self._cleanup_services()
                    raise

            # Store services in app state for access
            app.state.services = self._service_map
            app.state.config = self.config

            # Expose security manager directly on app state for @protected decorator compatibility
            security_service = self._service_map.get("securityservice")
            if security_service and hasattr(security_service, "security_manager"):
                app.state.security_manager = security_service.security_manager
                self.logger.debug("Security manager attached to app.state.security_manager")
            else:
                app.state.security_manager = None
                self.logger.debug("No security manager available")

            # Log summary
            self._log_initialization_summary()

            self._initialized = True

        except Exception as e:
            self.logger.error(f"Service initialization failed: {e}")
            raise

    async def shutdown_services(self) -> None:
        """Shutdown all services in reverse order."""
        if not self._initialized:
            return

        self.logger.info("Starting service shutdown")
        await self._cleanup_services()
        self._initialized = False

    async def _create_services(self) -> list[Service]:
        """Create all services in dependency order.

        Returns:
            List of services ready to be initialized
        """
        services = []

        # 1. Security Service (no dependencies)
        if self.config.is_feature_enabled("security"):
            try:
                security_service = await self._create_security_service()
                services.append(security_service)
            except Exception as e:
                self.logger.warning(f"Security service not available: {e}")

        # 2. Middleware Manager (no dependencies)
        try:
            middleware_manager = await self._create_middleware_manager()
            services.append(middleware_manager)
        except Exception as e:
            self.logger.warning(f"Middleware manager not available: {e}")

        # 3. State Manager (no dependencies)
        if self.config.is_feature_enabled("state_management"):
            try:
                state_manager = await self._create_state_manager()
                services.append(state_manager)
            except Exception as e:
                self.logger.warning(f"State manager not available: {e}")

        # 4. Capability Registry (no dependencies)
        capability_registry = CapabilityRegistry(self.config)
        services.append(capability_registry)

        # 5. Plugin Service (depends on CapabilityRegistry)
        if self.config.is_feature_enabled("plugins"):
            try:
                plugin_service = await self._create_plugin_service(capability_registry)
                services.append(plugin_service)
            except Exception as e:
                self.logger.warning(f"Plugin service not available: {e}")

        # 6. MCP Service (depends on CapabilityRegistry)
        if self.config.is_feature_enabled("mcp"):
            try:
                mcp_service = await self._create_mcp_service(capability_registry)
                services.append(mcp_service)
            except Exception as e:
                self.logger.warning(f"MCP service not available: {e}")

        # 7. Push Notification Service
        push_config = self.config.get("push_notifications", {})
        if push_config.get("enabled", True):
            try:
                push_service = await self._create_push_service()
                services.append(push_service)
            except Exception as e:
                self.logger.warning(f"Push notification service not available: {e}")

        return services

    async def _create_security_service(self) -> Service:
        """Create and return security service."""
        from .security import SecurityService

        return SecurityService(self.config)

    async def _create_middleware_manager(self) -> Service:
        """Create and return middleware manager."""
        from .middleware import MiddlewareManager

        return MiddlewareManager(self.config)

    async def _create_state_manager(self) -> Service:
        """Create and return state manager."""
        from .state import StateManager

        return StateManager(self.config)

    async def _create_plugin_service(self, capability_registry: CapabilityRegistry) -> Service:
        """Create and return plugin service."""
        from .plugins import PluginService

        return PluginService(self.config, capability_registry)

    async def _create_mcp_service(self, capability_registry: CapabilityRegistry) -> Service:
        """Create and return MCP service."""
        from .mcp import MCPService

        return MCPService(self.config, capability_registry)

    async def _create_push_service(self) -> Service:
        """Create and return push notification service."""
        from .push import PushNotificationService

        return PushNotificationService(self.config)

    async def _cleanup_services(self) -> None:
        """Cleanup all services in reverse initialization order."""
        for service in reversed(self.services):
            service_name = service.__class__.__name__
            try:
                await service.shutdown()
                self.logger.debug(f"Shut down {service_name}")
            except Exception as e:
                self.logger.error(f"Error shutting down {service_name}: {e}")

        self.services.clear()
        self._service_map.clear()

    def _log_initialization_summary(self) -> None:
        """Log a summary of initialized services and features."""
        agent_info = self.config.get_agent_info()

        self.logger.info("=" * 50)
        self.logger.info(f"{agent_info['name']} v{agent_info['version']} initialized")
        self.logger.info(f"{agent_info['description']}")
        self.logger.info("=" * 50)

        # Log active services
        self.logger.info(f"Active Services ({len(self.services)}):")
        for service in self.services:
            self.logger.info(f"  ✓ {service.__class__.__name__}")

        # Log enabled features
        features = []
        if self.config.is_feature_enabled("security"):
            auth_type = self.config.get("security.auth", {})
            if auth_type:
                auth_method = list(auth_type.keys())[0] if auth_type else "none"
                features.append(f"Security ({auth_method})")
            else:
                features.append("Security")

        if self.config.is_feature_enabled("state_management"):
            backend = self.config.get("state_management.backend", "memory")
            features.append(f"State Management ({backend})")

        if self.config.is_feature_enabled("mcp"):
            features.append("MCP Integration")

        capability_registry = self._service_map.get("capabilityregistry")
        if capability_registry:
            cap_count = len(capability_registry.list_capabilities())
            features.append(f"Capabilities ({cap_count})")

        if features:
            self.logger.info("Enabled Features:")
            for feature in features:
                self.logger.info(f"  ✓ {feature}")

        self.logger.info("=" * 50)

    def get_service(self, service_name: str) -> Service | None:
        """Get a service by name.

        Args:
            service_name: Name of the service (case-insensitive)

        Returns:
            Service instance or None if not found
        """
        return self._service_map.get(service_name.lower())

    @property
    def initialized(self) -> bool:
        """Check if services have been initialized."""
        return self._initialized
