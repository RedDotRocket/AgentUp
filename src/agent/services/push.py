from typing import Any

from .base import Service
from .config import ConfigurationManager


class PushNotificationService(Service):
    """Manages push notifications for the agent.

    This service handles:
    - Push notification configuration
    - Webhook management
    - Notification delivery
    """

    def __init__(self, config_manager: ConfigurationManager):
        super().__init__(config_manager)
        self._push_notifier = None
        self._backend = None

    async def initialize(self) -> None:
        self.logger.info("Initializing push notification service")

        push_config = self.config.get("push_notifications", {})
        if not push_config.get("enabled", True):
            self.logger.info("Push notifications disabled")
            self._initialized = True
            return

        self._backend = push_config.get("backend", "memory")

        try:
            if self._backend == "valkey":
                await self._setup_valkey_backend(push_config)
            else:
                await self._setup_memory_backend()

            self._initialized = True
            self.logger.info(f"Push notification service initialized with {self._backend} backend")

        except Exception as e:
            self.logger.error(f"Failed to initialize push notification service: {e}")
            raise

    async def shutdown(self) -> None:
        self.logger.debug("Shutting down push notification service")
        self._push_notifier = None

    async def _setup_memory_backend(self) -> None:
        import httpx

        from agent.push.notifier import EnhancedPushNotifier

        client = httpx.AsyncClient()
        self._push_notifier = EnhancedPushNotifier(client=client)
        self.logger.debug("Using memory push notifier")

    async def _setup_valkey_backend(self, push_config: dict[str, Any]) -> None:
        try:
            import httpx
            import valkey.asyncio as valkey

            from agent.push.notifier import ValkeyPushNotifier
            from agent.services import get_services

            # Get services and find cache service
            services = get_services()
            cache_service_name = None
            services_config = self.config.get("services", {})

            for service_name, service_config in services_config.items():
                if service_config.get("type") == "cache":
                    cache_service_name = service_name
                    break

            if cache_service_name:
                valkey_service = services.get_cache(cache_service_name)
                if valkey_service and hasattr(valkey_service, "url"):
                    valkey_url = valkey_service.url
                    valkey_client = valkey.from_url(valkey_url)

                    # Create Valkey push notifier
                    client = httpx.AsyncClient()
                    self._push_notifier = ValkeyPushNotifier(
                        client=client,
                        valkey_client=valkey_client,
                        key_prefix=push_config.get("key_prefix", "agentup:push:"),
                        validate_urls=push_config.get("validate_urls", True),
                    )
                    self.logger.debug("Using Valkey push notifier")
                    return

            # Fallback to memory if Valkey setup fails
            self.logger.warning("Valkey setup failed, falling back to memory push notifier")
            await self._setup_memory_backend()

        except Exception as e:
            self.logger.warning(f"Failed to setup Valkey backend: {e}, using memory backend")
            await self._setup_memory_backend()

    @property
    def push_notifier(self):
        return self._push_notifier
