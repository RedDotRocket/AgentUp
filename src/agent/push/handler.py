import structlog
from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import (
    Message,
    MessageSendParams,
    Task,
)

logger = structlog.get_logger(__name__)


class CustomRequestHandler(DefaultRequestHandler):
    """
    Enhanced request handler that fixes push notification storage for non-streaming endpoints.

    The default a2a-sdk DefaultRequestHandler only stores push notification configs
    for existing tasks in non-streaming mode, not for new tasks. This fixes that, but
    we should eventually upstream this change to the a2a-sdk, or find out why it
    has not been done already.
    """

    async def on_message_send(
        self,
        params: MessageSendParams,
        context: ServerCallContext | None = None,
    ) -> Message | Task:
        """
        Override to ensure push notification configs are saved for new tasks.
        """
        # Call parent implementation
        result = await super().on_message_send(params, context)

        # If we got a task back and have push notification config, save it
        if (
            isinstance(result, Task)
            and self._push_config_store
            and self._push_sender
            and params.configuration
            and params.configuration.pushNotificationConfig
        ):
            logger.info(f"Saving push notification config for new task {result.id}")
            
            # Store the configuration
            await self._push_config_store.set_task_push_notification_config(
                result.id,
                params.configuration.pushNotificationConfig,
            )

            # Also send the initial notification until upsteam fixes this
            await self._push_sender.send_notification(result)

        return result
