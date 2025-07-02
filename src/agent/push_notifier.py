"""
Enhanced push notification system for AgentUp.

Extends the a2a-sdk InMemoryPushNotifier to support:
- Multiple configurations per task
- list and delete operations
- Security validation
- Persistent storage backends
"""

import json
import logging
import uuid
from urllib.parse import urlparse

import httpx
from a2a.types import PushNotificationAuthenticationInfo, PushNotificationConfig, Task, TaskPushNotificationConfig

logger = logging.getLogger(__name__)


class EnhancedPushNotifier:
    """
    Enhanced push notifier supporting multiple configurations per task.

    This extends the functionality of the a2a-sdk InMemoryPushNotifier
    to support the full A2A specification for push notifications.
    """

    def __init__(self, client: httpx.AsyncClient, validate_urls: bool = True):
        self.client = client
        self.validate_urls = validate_urls
        # Storage: task_id -> {config_id: TaskPushNotificationConfig}
        self._configs: dict[str, dict[str, TaskPushNotificationConfig]] = {}

    async def set_info(self, task_id: str, push_config: PushNotificationConfig) -> TaskPushNotificationConfig:
        """
        Set push notification configuration for a task.

        This method is compatible with a2a-sdk's PushNotifier interface.

        Args:
            task_id: Task identifier
            push_config: Push notification configuration

        Returns:
            The stored configuration (may mask sensitive details)
        """
        # Create TaskPushNotificationConfig wrapper
        config = TaskPushNotificationConfig(taskId=task_id, pushNotificationConfig=push_config)

        # Generate unique config ID if not provided
        config_id = getattr(push_config, "id", None)
        if not config_id:
            config_id = str(uuid.uuid4())
            # Note: We can't modify the config object directly since it's immutable
            # The config_id will be tracked internally

        # Validate webhook URL for security
        if self.validate_urls:
            await self._validate_webhook_url(push_config.url)

        # Store configuration
        if task_id not in self._configs:
            self._configs[task_id] = {}

        # Create internal tracking with config_id
        self._configs[task_id][config_id] = config

        logger.info(f"Set push notification config {config_id} for task {task_id}")

        # Return configuration (potentially masking sensitive data)
        return self._mask_sensitive_data(config)

    async def get_info(self, task_id: str, config_id: str | None = None) -> TaskPushNotificationConfig | None:
        """
        Get push notification configuration for a task.

        Args:
            task_id: Task identifier
            config_id: Optional specific configuration ID

        Returns:
            Push notification configuration or None if not found
        """
        if task_id not in self._configs:
            return None

        task_configs = self._configs[task_id]

        if config_id:
            # Get specific configuration
            config = task_configs.get(config_id)
            return self._mask_sensitive_data(config) if config else None
        else:
            # Get first/default configuration (for backward compatibility)
            if task_configs:
                config = next(iter(task_configs.values()))
                return self._mask_sensitive_data(config)
            return None

    async def list_info(self, task_id: str) -> list[TaskPushNotificationConfig]:
        """
        list all push notification configurations for a task.

        Args:
            task_id: Task identifier

        Returns:
            list of push notification configurations
        """
        if task_id not in self._configs:
            return []

        configs = list(self._configs[task_id].values())
        return [self._mask_sensitive_data(config) for config in configs]

    async def delete_info(self, task_id: str, config_id: str) -> bool:
        """
        Delete a specific push notification configuration.

        Args:
            task_id: Task identifier
            config_id: Configuration identifier

        Returns:
            True if deleted, False if not found
        """
        if task_id not in self._configs:
            return False

        task_configs = self._configs[task_id]
        if config_id in task_configs:
            del task_configs[config_id]
            logger.info(f"Deleted push notification config {config_id} for task {task_id}")

            # Clean up empty task entries
            if not task_configs:
                del self._configs[task_id]

            return True

        return False

    async def send_notification(self, task: Task) -> None:
        """
        Send push notifications to all registered webhooks for the task.

        Args:
            task: Task object to send in notification
        """
        task_id = task.id

        if task_id not in self._configs:
            logger.debug(f"No push notification configs for task {task_id}")
            return

        # Send to all registered configurations for this task
        for config_id, config in self._configs[task_id].items():
            try:
                await self._send_single_notification(task, config)
                logger.info(f"Sent push notification for task {task_id} to config {config_id}")
            except Exception as e:
                logger.error(f"Failed to send push notification for task {task_id} to config {config_id}: {e}")

    async def _send_single_notification(self, task: Task, config: TaskPushNotificationConfig) -> None:
        """
        Send notification to a single webhook endpoint.

        Args:
            task: Task object to send
            config: Push notification configuration
        """
        push_config = config.pushNotificationConfig

        # Prepare headers
        headers = {"Content-Type": "application/json", "User-Agent": "AgentUp-PushNotifier/1.0"}

        # Add client token if provided
        if push_config.token:
            headers["X-A2A-Notification-Token"] = push_config.token

        # Add authentication headers if configured
        if push_config.authentication:
            await self._add_authentication_headers(headers, push_config.authentication)

        # Serialize task to JSON
        payload = task.model_dump(by_alias=True)

        # Send webhook request
        try:
            response = await self.client.post(
                push_config.url,
                json=payload,
                headers=headers,
                timeout=30.0,  # 30 second timeout
            )
            response.raise_for_status()
            logger.debug(f"Successfully sent push notification to {push_config.url}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending push notification to {push_config.url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending push notification to {push_config.url}: {e}")
            raise

    async def _validate_webhook_url(self, url: str) -> None:
        """
        Validate webhook URL for security (SSRF prevention).

        Args:
            url: Webhook URL to validate

        Raises:
            ValueError: If URL is invalid or unsafe
        """
        try:
            parsed = urlparse(url)

            # Must be HTTPS in production (allow HTTP for development)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

            # Must have a valid hostname
            if not parsed.hostname:
                raise ValueError("URL must have a valid hostname")

            # Prevent localhost/private IP access (basic SSRF protection)
            hostname = parsed.hostname.lower()
            if hostname in ("localhost", "127.0.0.1", "::1"):
                logger.warning(f"Webhook URL points to localhost: {url}")
                # Allow for development but log warning

            # Check for private IP ranges (simplified check)
            if hostname.startswith(("10.", "172.", "192.168.")):
                logger.warning(f"Webhook URL points to private IP: {url}")
                # Allow for development but log warning

        except Exception as e:
            raise ValueError(f"Invalid webhook URL: {e}") from e

    async def _add_authentication_headers(
        self, headers: dict[str, str], auth_info: PushNotificationAuthenticationInfo
    ) -> None:
        """
        Add authentication headers based on configuration.

        Args:
            headers: Headers dictionary to modify
            auth_info: Authentication information
        """
        for scheme in auth_info.schemes:
            if scheme.lower() == "bearer":
                if auth_info.credentials:
                    headers["Authorization"] = f"Bearer {auth_info.credentials}"
                else:
                    logger.warning("Bearer authentication requested but no credentials provided")
            elif scheme.lower() == "apikey":
                if auth_info.credentials:
                    headers["X-API-Key"] = auth_info.credentials
                else:
                    logger.warning("API key authentication requested but no credentials provided")
            else:
                logger.warning(f"Unsupported authentication scheme: {scheme}")

    def _mask_sensitive_data(self, config: TaskPushNotificationConfig | None) -> TaskPushNotificationConfig | None:
        """
        Mask sensitive data in configuration for safe return.

        Args:
            config: Configuration to mask

        Returns:
            Configuration with sensitive data masked
        """
        if not config:
            return None

        # For now, return as-is. In production, you might want to mask
        # authentication credentials or other sensitive information
        return config


class ValkeyPushNotifier(EnhancedPushNotifier):
    """
    Valkey-backed push notifier for persistent storage.

    This stores push notification configurations in Valkey for persistence
    across agent restarts.
    """

    def __init__(
        self, client: httpx.AsyncClient, valkey_client, key_prefix: str = "agentup:push:", validate_urls: bool = True
    ):
        super().__init__(client, validate_urls)
        self.valkey = valkey_client
        self.key_prefix = key_prefix

    async def set_info(self, task_id: str, push_config: PushNotificationConfig) -> TaskPushNotificationConfig:
        """Store configuration in Valkey."""
        # Create TaskPushNotificationConfig wrapper
        config = TaskPushNotificationConfig(taskId=task_id, pushNotificationConfig=push_config)

        config_id = getattr(push_config, "id", str(uuid.uuid4()))

        # Validate webhook URL
        if self.validate_urls:
            await self._validate_webhook_url(push_config.url)

        # Store in Valkey
        key = f"{self.key_prefix}{task_id}:{config_id}"
        value = config.model_dump_json(by_alias=True)

        await self.valkey.set(key, value, ex=7200)  # 2 hour expiration

        logger.info(f"Stored push notification config {config_id} for task {task_id} in Valkey")

        return self._mask_sensitive_data(config)

    async def get_info(self, task_id: str, config_id: str | None = None) -> TaskPushNotificationConfig | None:
        """Get configuration from Valkey."""
        if config_id:
            # Get specific configuration
            key = f"{self.key_prefix}{task_id}:{config_id}"
            value = await self.valkey.get(key)
            if value:
                config_data = json.loads(value)
                config = TaskPushNotificationConfig(**config_data)
                return self._mask_sensitive_data(config)
        else:
            # Get first available configuration
            pattern = f"{self.key_prefix}{task_id}:*"
            keys = await self.valkey.keys(pattern)
            if keys:
                value = await self.valkey.get(keys[0])
                if value:
                    config_data = json.loads(value)
                    config = TaskPushNotificationConfig(**config_data)
                    return self._mask_sensitive_data(config)

        return None

    async def list_info(self, task_id: str) -> list[TaskPushNotificationConfig]:
        """list all configurations for task from Valkey."""
        pattern = f"{self.key_prefix}{task_id}:*"
        keys = await self.valkey.keys(pattern)

        configs = []
        for key in keys:
            value = await self.valkey.get(key)
            if value:
                config_data = json.loads(value)
                config = TaskPushNotificationConfig(**config_data)
                configs.append(self._mask_sensitive_data(config))

        return configs

    async def delete_info(self, task_id: str, config_id: str) -> bool:
        """Delete configuration from Valkey."""
        key = f"{self.key_prefix}{task_id}:{config_id}"
        result = await self.valkey.delete(key)

        if result:
            logger.info(f"Deleted push notification config {config_id} for task {task_id} from Valkey")

        return bool(result)

    async def send_notification(self, task: Task) -> None:
        """Send notifications using configurations from Valkey."""
        task_id = task.id
        configs = await self.list_info(task_id)

        if not configs:
            logger.debug(f"No push notification configs for task {task_id}")
            return

        # Send to all registered configurations
        for config in configs:
            try:
                await self._send_single_notification(task, config)
                logger.info(f"Sent push notification for task {task_id}")
            except Exception as e:
                logger.error(f"Failed to send push notification for task {task_id}: {e}")
