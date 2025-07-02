from typing import Any

from a2a.types import TaskPushNotificationConfig
from pydantic import BaseModel


class listTaskPushNotificationConfigParams(BaseModel):
    """
    Parameters for the 'tasks/pushNotificationConfig/list' method.
    """

    id: str
    """
    The ID of the task.
    """
    metadata: dict[str, Any] | None = None
    """
    Request-specific metadata.
    """


class listTaskPushNotificationConfigRequest(BaseModel):
    """
    JSON-RPC request model for the 'tasks/pushNotificationConfig/list' method.
    """

    jsonrpc: str = "2.0"
    """
    JSON-RPC version.
    """
    id: str | int | None = None
    """
    Request identifier.
    """
    method: str = "tasks/pushNotificationConfig/list"
    """
    RPC method name.
    """
    params: listTaskPushNotificationConfigParams
    """
    Request parameters.
    """


class listTaskPushNotificationConfigResponse(BaseModel):
    """
    JSON-RPC response model for the 'tasks/pushNotificationConfig/list' method.
    """

    jsonrpc: str = "2.0"
    """
    JSON-RPC version.
    """
    id: str | int | None = None
    """
    Request identifier.
    """
    result: list[TaskPushNotificationConfig]
    """
    list of push notification configurations for the task.
    """


class DeleteTaskPushNotificationConfigParams(BaseModel):
    """
    Parameters for the 'tasks/pushNotificationConfig/delete' method.
    """

    id: str
    """
    The ID of the task.
    """
    pushNotificationConfigId: str
    """
    Push notification configuration ID to delete.
    """
    metadata: dict[str, Any] | None = None
    """
    Request-specific metadata.
    """


class DeleteTaskPushNotificationConfigRequest(BaseModel):
    """
    JSON-RPC request model for the 'tasks/pushNotificationConfig/delete' method.
    """

    jsonrpc: str = "2.0"
    """
    JSON-RPC version.
    """
    id: str | int | None = None
    """
    Request identifier.
    """
    method: str = "tasks/pushNotificationConfig/delete"
    """
    RPC method name.
    """
    params: DeleteTaskPushNotificationConfigParams
    """
    Request parameters.
    """


class DeleteTaskPushNotificationConfigResponse(BaseModel):
    """
    JSON-RPC response model for the 'tasks/pushNotificationConfig/delete' method.
    """

    jsonrpc: str = "2.0"
    """
    JSON-RPC version.
    """
    id: str | int | None = None
    """
    Request identifier.
    """
    result: None = None
    """
    Null result for successful deletion.
    """


class JSONRPCError(BaseModel):
    """
    JSON-RPC error object.
    """

    code: int
    """
    Error code.
    """
    message: str
    """
    Error message.
    """
    data: Any | None = None
    """
    Additional error data.
    """


class JSONRPCErrorResponse(BaseModel):
    """
    JSON-RPC error response.
    """

    jsonrpc: str = "2.0"
    """
    JSON-RPC version.
    """
    id: str | int | None = None
    """
    Request identifier.
    """
    error: JSONRPCError
    """
    Error object.
    """
