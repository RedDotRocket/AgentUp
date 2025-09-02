from collections.abc import AsyncGenerator, AsyncIterable
from datetime import datetime
from typing import Any

import structlog
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.jsonrpc_handler import JSONRPCHandler
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    InternalError,
    JSONRPCErrorResponse,
    SendMessageRequest,
    SendStreamingMessageRequest,
    SetTaskPushNotificationConfigRequest,
    TaskResubscriptionRequest,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent.a2a.agentcard import create_agent_card
from agent.dependencies import ConfigDep
from agent.push.types import (
    DeleteTaskPushNotificationConfigRequest,
    DeleteTaskPushNotificationConfigResponse,
    listTaskPushNotificationConfigRequest,
    listTaskPushNotificationConfigResponse,
)
from agent.security import AuthContext, get_auth_result, protected

# Setup logger
logger = structlog.get_logger(__name__)

# Create router
router = APIRouter()


# Task storage
task_storage: dict[str, dict[str, Any]] = {}

# Request handler instance management
_request_handler: DefaultRequestHandler | None = None


def set_request_handler_instance(handler: DefaultRequestHandler):
    global _request_handler
    _request_handler = handler


def get_request_handler() -> DefaultRequestHandler:
    if _request_handler is None:
        raise RuntimeError("Request handler not initialized")
    return _request_handler


@router.get("/task/{task_id}/status")
@protected()
async def get_task_status(task_id: str, request: Request) -> JSONResponse:
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")

    task_data = task_storage[task_id]

    response = {
        "id": task_id,
        "status": task_data["status"].value,
        "created_at": task_data["created_at"].isoformat(),
        "updated_at": task_data["updated_at"].isoformat(),
    }

    if "result" in task_data:
        response["result"] = task_data["result"]

    if "error" in task_data:
        response["error"] = task_data["error"]

    return JSONResponse(status_code=200, content=response)


@router.get("/health")
async def health_check(config: ConfigDep) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "agent": config.project_name,
            "timestamp": datetime.now().isoformat(),
        },
    )


@router.get("/services/health")
async def services_health() -> JSONResponse:
    try:
        from agent.services import get_services

        services = get_services()
        health_results = await services.health_check_all()
    except ImportError:
        health_results = {"error": "Services module not available"}

    all_healthy = all(
        result.get("status") == "healthy" if isinstance(result, dict) else False for result in health_results.values()
    )

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "services": health_results,
            "timestamp": datetime.now().isoformat(),
        },
    )


# A2A AgentCard
@router.get("/.well-known/agent-card.json", response_model=AgentCard)
async def get_agent_discovery() -> AgentCard:
    return create_agent_card()


# A2A Authenticated Extended AgentCard
@router.get("/agent/authenticatedExtendedCard", response_model=AgentCard)
@protected()
async def get_authenticated_extended_card(request: Request) -> AgentCard:
    return create_agent_card(extended=True)


async def sse_generator(async_iterator: AsyncIterable[Any]) -> AsyncGenerator[str, None]:
    try:
        async for response in async_iterator:
            # Each response is a SendStreamingMessageResponse
            data = response.model_dump_json(by_alias=True)
            yield f"data: {data}\n\n"
    except Exception as e:
        # Send error event
        error_response = JSONRPCErrorResponse(id=None, error=InternalError(message=str(e)))
        yield f"data: {error_response.model_dump_json(by_alias=True)}\n\n"


@router.post("/", response_model=None)
@protected()
async def jsonrpc_endpoint(
    request: Request,
    handler: DefaultRequestHandler = Depends(get_request_handler),
) -> JSONResponse | StreamingResponse:
    try:
        # Parse JSON-RPC request
        body = await request.json()

        # Validate JSON-RPC structure
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request"},
                    "id": body.get("id") if isinstance(body, dict) else None,
                },
            )

        if body.get("jsonrpc") != "2.0":
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request"},
                    "id": body.get("id"),
                },
            )

        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        if not method:
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request"},
                    "id": request_id,
                },
            )

        # Get authentication result from request state (set by @protected decorator)
        auth_result = get_auth_result(request)

        # Get the agent_card from app.state (created once at startup)
        agent_card = request.app.state.agent_card
        jsonrpc_handler = JSONRPCHandler(agent_card, handler)

        # Route to appropriate handler based on method - wrapped with auth context
        if method == "message/send":
            # Non-streaming method
            rpc_request = SendMessageRequest(jsonrpc="2.0", id=request_id or "", method=method, params=params)
            # Set thread-local auth for executor access
            from agent.core.base import set_current_auth_for_executor

            set_current_auth_for_executor(auth_result)

            with AuthContext(auth_result):
                response = await jsonrpc_handler.on_message_send(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "message/stream":
            # Use JSONRPCHandler streaming to ensure iterative agent execution
            from agent.core.base import set_current_auth_for_executor

            # Set thread-local auth for executor access
            set_current_auth_for_executor(auth_result)

            # Create streaming message request
            rpc_request = SendStreamingMessageRequest(
                jsonrpc="2.0", id=request_id or "", method="message/stream", params=params
            )

            with AuthContext(auth_result):
                # Use JSONRPCHandler's streaming method which uses our configured AgentUpExecutor
                return StreamingResponse(
                    sse_generator(jsonrpc_handler.on_message_send_stream(rpc_request)),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

        elif method == "tasks/get":
            # Non-streaming method
            rpc_request = GetTaskRequest(jsonrpc="2.0", id=request_id or "", method=method, params=params)
            with AuthContext(auth_result):
                response = await jsonrpc_handler.on_get_task(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/cancel":
            # Non-streaming method
            rpc_request = CancelTaskRequest(jsonrpc="2.0", id=request_id or "", method=method, params=params)
            response = await jsonrpc_handler.on_cancel_task(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/resubscribe":
            # Streaming method - return SSE
            rpc_request = TaskResubscriptionRequest(jsonrpc="2.0", id=request_id or "", method=method, params=params)
            response_stream = jsonrpc_handler.on_resubscribe_to_task(rpc_request)
            return StreamingResponse(
                sse_generator(response_stream),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        elif method == "tasks/pushNotificationConfig/set":
            # Non-streaming method
            rpc_request = SetTaskPushNotificationConfigRequest(
                jsonrpc="2.0", id=request_id or "", method=method, params=params
            )
            response = await jsonrpc_handler.set_push_notification_config(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/pushNotificationConfig/get":
            # Get push notification configuration for a task
            try:
                rpc_request = GetTaskPushNotificationConfigRequest(
                    jsonrpc="2.0", id=request_id or "", method=method, params=params
                )
                response = await handle_get_push_notification_config(rpc_request)
                return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))
            except Exception as e:
                logger.error(f"Error in get push notification config: {e}")
                error_response = JSONRPCErrorResponse(id=request_id, error=InternalError(message=str(e)))
                return JSONResponse(status_code=200, content=error_response.model_dump(by_alias=True))

        elif method == "tasks/pushNotificationConfig/list":
            # list push notification configurations for a task
            try:
                rpc_request = listTaskPushNotificationConfigRequest(
                    jsonrpc="2.0", id=request_id or "", method=method, params=params
                )
                response = await handle_list_push_notification_configs(rpc_request)
                return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))
            except Exception as e:
                logger.error(f"Error handling list push notification configs: {e}")
                return JSONResponse(
                    status_code=200,
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                        "id": request_id,
                    },
                )

        elif method == "tasks/pushNotificationConfig/delete":
            # Delete push notification configuration for a task
            try:
                rpc_request = DeleteTaskPushNotificationConfigRequest(
                    jsonrpc="2.0", id=request_id or "", method=method, params=params
                )
                response = await handle_delete_push_notification_config(rpc_request)
                return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))
            except Exception as e:
                logger.error(f"Error handling delete push notification config: {e}")
                return JSONResponse(
                    status_code=200,
                    content={
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                        "id": request_id,
                    },
                )

        else:
            # Method not found
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Unknown method: {method}",
                    },
                    "id": request_id,
                },
            )

    except Exception as e:
        # Unexpected error
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                "id": locals().get("body", {}).get("id") if isinstance(locals().get("body"), dict) else None,
            },
        )


# Handler functions for new push notification methods
async def handle_get_push_notification_config(request: GetTaskPushNotificationConfigRequest):
    """
    Handle getting push notification configuration for a task.

    Args:
        request: Get push notification config request

    Returns:
        Push notification configuration or None
    """
    try:
        # Get the request handler instance
        handler = get_request_handler()
        if not handler or not hasattr(handler, "_push_notifier"):
            raise ValueError("Push notifier not available")

        # Get configuration using the enhanced push notifier
        push_notifier = getattr(handler, "_push_notifier", None)
        if not push_notifier:
            raise ValueError("Push notifier not properly configured")
        config = await push_notifier.get_info(request.params.id)

        # Create response - handle None result properly
        from a2a.types import (
            GetTaskPushNotificationConfigResponse,
            GetTaskPushNotificationConfigSuccessResponse,
            JSONRPCError,
            JSONRPCErrorResponse,
        )

        if config is None:
            # Return error response for not found
            return GetTaskPushNotificationConfigResponse(
                root=JSONRPCErrorResponse(
                    id=request.id,
                    error=JSONRPCError(
                        code=-32001,
                        message="Push notification configuration not found",
                        data=f"No configuration found for task {request.params.id}",
                    ),
                )
            )
        else:
            return GetTaskPushNotificationConfigResponse(
                root=GetTaskPushNotificationConfigSuccessResponse(jsonrpc="2.0", id=request.id, result=config)
            )

    except Exception as e:
        logger.error(f"Error getting push notification config: {e}")
        raise


async def handle_list_push_notification_configs(
    request: listTaskPushNotificationConfigRequest,
) -> listTaskPushNotificationConfigResponse:
    """
    Handle listing push notification configurations for a task.

    Args:
        request: list push notification config request

    Returns:
        list of push notification configurations
    """
    try:
        # Get the request handler instance
        handler = get_request_handler()
        if not handler or not hasattr(handler, "_push_notifier"):
            raise ValueError("Push notifier not available")

        # list configurations using the enhanced push notifier
        push_notifier = getattr(handler, "_push_notifier", None)
        if not push_notifier:
            raise ValueError("Push notifier not properly configured")
        configs = await push_notifier.list_info(request.params.id)

        return listTaskPushNotificationConfigResponse(jsonrpc="2.0", id=request.id, result=configs)

    except Exception as e:
        logger.error(f"Error listing push notification configs: {e}")
        raise


async def handle_delete_push_notification_config(
    request: DeleteTaskPushNotificationConfigRequest,
) -> DeleteTaskPushNotificationConfigResponse | JSONRPCErrorResponse:
    """
    Handle deleting a push notification configuration.

    Args:
        request: Delete push notification config request

    Returns:
        Success response
    """
    try:
        # Get the request handler instance
        handler = get_request_handler()
        if not handler or not hasattr(handler, "_push_notifier"):
            raise ValueError("Push notifier not available")

        # Delete configuration using the enhanced push notifier
        push_notifier = getattr(handler, "_push_notifier", None)
        if not push_notifier:
            raise ValueError("Push notifier not properly configured")
        success = await push_notifier.delete_info(request.params.id, request.params.pushNotificationConfigId)

        if not success:
            # Return JSON-RPC error for not found
            from a2a.types import JSONRPCError, JSONRPCErrorResponse

            return JSONRPCErrorResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32001,  # TaskNotFoundError
                    message="Push notification configuration not found",
                    data=f"No configuration found with ID {request.params.pushNotificationConfigId} for task {request.params.id}",
                ),
            )

        return DeleteTaskPushNotificationConfigResponse(jsonrpc="2.0", id=request.id, result=None)

    except Exception as e:
        logger.error(f"Error deleting push notification config: {e}")
        raise


# Export router and handlers
__all__ = [
    "router",
    "set_request_handler_instance",
    "get_request_handler",
    "handle_list_push_notification_configs",
    "handle_delete_push_notification_config",
]
