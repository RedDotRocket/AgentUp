import importlib.metadata
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import structlog
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.jsonrpc_handler import JSONRPCHandler
from a2a.types import (
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

from agent.config.a2a import (
    AgentCapabilities,
    AgentCard,
    AgentCardSignature,
    AgentExtension,
    AgentProvider,
    AgentSkill,
    APIKeySecurityScheme,
    HTTPAuthSecurityScheme,
    JSONRPCError,
)
from agent.push.types import (
    DeleteTaskPushNotificationConfigRequest,
    DeleteTaskPushNotificationConfigResponse,
    listTaskPushNotificationConfigRequest,
    listTaskPushNotificationConfigResponse,
)
from agent.security import AuthContext, get_auth_result, protected
from agent.services.config import ConfigurationManager

# Setup logger
logger = structlog.get_logger(__name__)

# Create router
router = APIRouter()

# Configuration will be loaded when needed

# Agent card caching - Force cache invalidation for debugging
_cached_agent_card: AgentCard | None = None
_cached_extended_agent_card: AgentCard | None = None
_cached_config_hash: str | None = None

# Task storage
task_storage: dict[str, dict[str, Any]] = {}

# Request handler instance management
_request_handler: DefaultRequestHandler | None = None


def _get_package_version(package_name: str) -> str:
    """Get the version of a package from metadata.

    Args:
        package_name: Name of the package to get version for

    Returns:
        Package version string or "0.0.0" if not found
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        logger.warning(f"Package '{package_name}' not found in metadata")
        return "0.0.0"
    except Exception as e:
        logger.warning(f"Failed to get version for package '{package_name}': {e}")
        return "0.0.0"


def set_request_handler_instance(handler: DefaultRequestHandler):
    global _request_handler
    _request_handler = handler


def get_request_handler() -> DefaultRequestHandler:
    if _request_handler is None:
        raise RuntimeError("Request handler not initialized")
    return _request_handler


def _get_mcp_skills_for_agent_card() -> list[AgentSkill]:
    """Convert registered MCP capabilities to AgentSkill objects.

    Only includes MCP tools from servers with expose_as_skills: true.

    Returns:
        List of AgentSkill objects representing MCP tools
    """
    from agent.capabilities.manager import get_mcp_capabilities
    from agent.services.config import ConfigurationManager

    mcp_skills = []
    try:
        # Get MCP server configuration to check expose_as_skills flags
        config_manager = ConfigurationManager()
        config = config_manager.config

        mcp_config = config.get("mcp", {})
        if not mcp_config.get("enabled"):
            return mcp_skills
        servers = mcp_config.get("servers", [])

        # Create a mapping of server names to expose_as_skills setting
        server_expose_flags = {}
        for server in servers:
            # TODO: Pydantic validation for server config
            server_name = server.get("name")
            expose_flag = server.get("expose_as_skills", False)

            server_expose_flags[server_name] = expose_flag

        mcp_capabilities = get_mcp_capabilities()

        for capability_id, capability_info in mcp_capabilities.items():
            # Only include capabilities from servers with expose_as_skills: true
            server_name = capability_info.server_name

            # Add server name to capability ID for uniqueness
            name = f"{server_name}:{capability_id}" if server_name else capability_id

            if server_expose_flags.get(server_name, False):
                logger.debug(
                    f"Including capability '{capability_id}' in AgentCard (server '{server_name}' has expose_as_skills=true)"
                )

                # Convert MCPCapabilityInfo to AgentSkill
                skill = AgentSkill(
                    id=capability_id,
                    name=name,
                    description=capability_info.description,
                    inputModes=["text"],
                    outputModes=["text"],
                    tags=["mcp", capability_info.server_name] if capability_info.server_name else ["mcp"],
                )
                mcp_skills.append(skill)
            else:
                logger.debug(
                    f"Skipping capability '{capability_id}' (server '{server_name}' has expose_as_skills={server_expose_flags.get(server_name, False)})"
                )

        logger.debug(f"Added {len(mcp_skills)} MCP tools as AgentCard skills from servers with expose_as_skills=true")

    except Exception as e:
        logger.error(f"Failed to get MCP capabilities for AgentCard: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

    return mcp_skills


def create_agent_card(extended: bool = False) -> AgentCard:
    """Create agent card with current configuration.

    Args:
        extended: If True, include plugins with visibility="extended" in addition to public plugins
    """
    import hashlib

    global _cached_agent_card, _cached_extended_agent_card, _cached_config_hash

    # Get configuration from the cached ConfigurationManager
    config_manager = ConfigurationManager()
    config = config_manager.config

    # Create a hash of the configuration to detect changes
    config_str = str(sorted(config.items()))
    # Bandit issue: B324 - Using hashlib.md5() is acceptable here for caching purposes
    current_config_hash = hashlib.md5(config_str.encode()).hexdigest()  # nosec

    logger.info(
        f"DEBUG: create_agent_card called, current_hash: {current_config_hash[:8]}, cached_hash: {_cached_config_hash[:8] if _cached_config_hash else 'None'}"
    )

    # Temporarily disable caching for debugging MCP skills
    # Check if we can use cached version
    # if _cached_config_hash == current_config_hash:
    #     logger.info("DEBUG: Using cached AgentCard")
    #     if extended and _cached_extended_agent_card is not None:
    #         return _cached_extended_agent_card
    #     elif not extended and _cached_agent_card is not None:
    #         return _cached_agent_card
    # else:
    logger.info("DEBUG: Cache disabled - regenerating AgentCard")

    # Cache miss - regenerate agent card
    agent_info = config.get("agent", {})
    plugins = config.get("plugins", [])

    # Only log plugins when actually regenerating (cache miss)
    logger.debug(f"Regenerating agent card - loaded {len(plugins)} plugins from config")

    # Convert plugins to A2A Skill format based on visibility
    agent_skills = []
    has_extended_plugins = False

    # Add MCP tools as skills
    agent_skills.extend(_get_mcp_skills_for_agent_card())

    # Get plugin information from the plugin registry
    from agent.plugins.manager import get_plugin_registry

    registry = get_plugin_registry()
    if registry and registry.plugins:
        # Get loaded plugins from the registry's plugins attribute
        for plugin_id, _plugin_instance in registry.plugins.items():
            # Find corresponding config
            plugin_config = None
            for p in plugins:
                if p.get("plugin_id") == plugin_id:
                    plugin_config = p
                    break

            if plugin_config:
                plugin_visibility = plugin_config.get("visibility", "public")

                # Track if any extended plugins exist
                if plugin_visibility == "extended":
                    has_extended_plugins = True

                # Include plugin in card based on visibility and card type
                if plugin_visibility == "public" or (extended and plugin_visibility == "extended"):
                    agent_skill = AgentSkill(
                        id=plugin_id,
                        name=plugin_config.get("name") or plugin_id,
                        description=plugin_config.get("description") or f"Plugin {plugin_id}",
                        inputModes=[plugin_config.get("input_mode", "text")],
                        outputModes=[plugin_config.get("output_mode", "text")],
                        tags=plugin_config.get("tags", ["general"]),
                    )
                    agent_skills.append(agent_skill)

    # Create capabilities object with extensions
    extensions = []

    # Add MCP extension if enabled
    mcp_config = config.get("mcp", {})
    if mcp_config.get("enabled") and mcp_config.get("server", {}).get("enabled"):
        mcp_extension = AgentExtension(
            uri="https://modelcontextprotocol.io/mcp/1.0",
            description="Agent supports MCP for tool sharing and collaboration",
            params={
                "endpoint": "/mcp",
                "transport": "http",
                "authentication": "api_key",
            },
            required=False,
        )
        extensions.append(mcp_extension)

    pushNotifications = config.get("push_notifications", {})
    state_management = config.get("state_management", {})

    capabilities = AgentCapabilities(
        streaming=True,  # this is always true, as we support non-streaming and streaming methods
        push_notifications=pushNotifications.get("enabled", False),
        state_transition_history=state_management.get("enabled", False),
        extensions=extensions if extensions else None,
    )

    # Create security schemes based on configuration
    security_config = config.get("security", {})
    security_schemes = {}
    security_requirements = []

    # Get protocol version from a2a-sdk package
    protocol_version = _get_package_version("a2a-sdk")
    if security_config.get("enabled", False):
        auth_type = security_config.get("type", "api_key")

        if auth_type == "api_key":
            # API Key authentication
            api_key_scheme = APIKeySecurityScheme.model_validate(
                {
                    "name": "X-API-Key",
                    "description": "API key for authentication",
                    "in": "header",  # <- use the JSON alias
                    "type": "apiKey",
                }
            )
            security_schemes["X-API-Key"] = api_key_scheme.model_dump(by_alias=True)
            security_requirements.append({"X-API-Key": []})

        elif auth_type == "bearer":
            # Bearer Token authentication
            bearer_scheme = HTTPAuthSecurityScheme(
                scheme="bearer", description="Bearer token for authentication", type="http"
            )
            security_schemes["BearerAuth"] = bearer_scheme.model_dump(by_alias=True)
            security_requirements.append({"BearerAuth": []})

        elif auth_type == "oauth2":
            # OAuth2 Bearer Token authentication
            oauth2_config = security_config.get("oauth2", {})
            required_scopes = oauth2_config.get("required_scopes", [])

            oauth2_scheme = HTTPAuthSecurityScheme(
                scheme="bearer",
                description="OAuth2 Bearer token for authentication",
                type="http",
                bearerFormat="JWT",  # Indicate JWT format for OAuth2
            )
            security_schemes["OAuth2"] = oauth2_scheme.model_dump(by_alias=True)
            security_requirements.append({"OAuth2": required_scopes})

    # Create the official AgentCard
    # Get version from package metadata, fallback to default
    package_version = _get_package_version("agentup")

    # Create signatures object only if we have actual signature data
    signatures = None
    signature_header = agent_info.get("signature_header")
    signature_protected = agent_info.get("signature_protected")
    signature_value = agent_info.get("signature")

    if signature_header and signature_protected and signature_value:
        signatures = AgentCardSignature(
            header=signature_header,
            protected=signature_protected,
            signature=signature_value,
        )

    agent_card = AgentCard(
        protocol_version=protocol_version,
        name=agent_info.get("name", config.get("project_name", "Agent")),
        description=agent_info.get("description", config.get("description", "AI Agent")),
        url=agent_info.get("url", config.get("url", "http://localhost:8000")),
        preferred_transport="JSONRPC!",
        provider=AgentProvider(
            organization=agent_info.get("provider_organization", "AgentUp"),
            url=agent_info.get("provider_url", "http://localhost:8000"),
        ),
        icon_url=agent_info.get(
            "icon_url",
            config.get(
                "icon_url", "https://raw.githubusercontent.com/RedDotRocket/AgentUp/refs/heads/main/assets/icon.png"
            ),
        ),
        version=agent_info.get("version", package_version),
        documentationUrl=agent_info.get(
            "documentation_url",
            config.get("documentation_url", "https://docs.agentup.dev"),
        ),
        capabilities=capabilities,
        security=security_requirements if security_requirements else None,
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=agent_skills,
        securitySchemes=security_schemes if security_schemes else None,
        signatures=signatures,
        supportsAuthenticatedExtendedCard=has_extended_plugins,
    )

    # Update cache
    _cached_config_hash = current_config_hash
    if extended:
        _cached_extended_agent_card = agent_card
    else:
        _cached_agent_card = agent_card

    return agent_card


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
async def health_check() -> JSONResponse:
    config_manager = ConfigurationManager()
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "agent": config_manager.get("project_name", "Agent"),
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

    all_healthy = all(result.get("status") == "healthy" for result in health_results.values())

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


async def sse_generator(async_iterator: AsyncGenerator) -> AsyncGenerator[str, None]:
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
                content={"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": request_id},
            )

        # Get authentication result from request state (set by @protected decorator)
        auth_result = get_auth_result(request)

        # Get the agent_card from app.state (created once at startup)
        agent_card = request.app.state.agent_card
        jsonrpc_handler = JSONRPCHandler(agent_card, handler)

        # Route to appropriate handler based on method - wrapped with auth context
        if method == "message/send":
            # Non-streaming method
            rpc_request = SendMessageRequest(jsonrpc="2.0", id=request_id, method=method, params=params)
            with AuthContext(auth_result):
                response = await jsonrpc_handler.on_message_send(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "message/stream":
            # Streaming method - return SSE
            rpc_request = SendStreamingMessageRequest(jsonrpc="2.0", id=request_id, method=method, params=params)
            with AuthContext(auth_result):
                response_stream = jsonrpc_handler.on_message_send_stream(rpc_request)
            return StreamingResponse(
                sse_generator(response_stream),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        elif method == "tasks/get":
            # Non-streaming method
            rpc_request = GetTaskRequest(jsonrpc="2.0", id=request_id, method=method, params=params)
            with AuthContext(auth_result):
                response = await jsonrpc_handler.on_get_task(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/cancel":
            # Non-streaming method
            rpc_request = CancelTaskRequest(jsonrpc="2.0", id=request_id, method=method, params=params)
            response = await jsonrpc_handler.on_cancel_task(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/resubscribe":
            # Streaming method - return SSE
            rpc_request = TaskResubscriptionRequest(jsonrpc="2.0", id=request_id, method=method, params=params)
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
                jsonrpc="2.0", id=request_id, method=method, params=params
            )
            response = await jsonrpc_handler.set_push_notification_config(rpc_request)
            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))

        elif method == "tasks/pushNotificationConfig/get":
            # Get push notification configuration for a task
            try:
                rpc_request = GetTaskPushNotificationConfigRequest(
                    jsonrpc="2.0", id=request_id, method=method, params=params
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
                    jsonrpc="2.0", id=request_id, method=method, params=params
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
                    jsonrpc="2.0", id=request_id, method=method, params=params
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
                    "error": {"code": -32601, "message": "Method not found", "data": f"Unknown method: {method}"},
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
                "id": body.get("id") if "body" in locals() else None,
            },
        )


# Error handlers (to be registered with FastAPI app)
async def jsonrpc_error_handler(request: Request, exc: JSONRPCError):
    return JSONResponse(
        status_code=400, content={"error": {"code": exc.code, "message": exc.message, "data": exc.data}}
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
        config = await handler._push_notifier.get_info(request.params.id)

        # Create response - handle None result properly
        from a2a.types import GetTaskPushNotificationConfigResponse

        if config is None:
            return GetTaskPushNotificationConfigResponse(jsonrpc="2.0", id=request.id, result=None)
        else:
            return GetTaskPushNotificationConfigResponse(jsonrpc="2.0", id=request.id, result=config)

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
        configs = await handler._push_notifier.list_info(request.params.id)

        return listTaskPushNotificationConfigResponse(jsonrpc="2.0", id=request.id, result=configs)

    except Exception as e:
        logger.error(f"Error listing push notification configs: {e}")
        raise


async def handle_delete_push_notification_config(
    request: DeleteTaskPushNotificationConfigRequest,
) -> DeleteTaskPushNotificationConfigResponse:
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
        success = await handler._push_notifier.delete_info(request.params.id, request.params.pushNotificationConfigId)

        if not success:
            # Return JSON-RPC error for not found
            from agent.push.types import JSONRPCErrorResponse

            return JSONRPCErrorResponse(
                jsonrpc="2.0",
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
    "jsonrpc_error_handler",
    "set_request_handler_instance",
    "get_request_handler",
    "handle_list_push_notification_configs",
    "handle_delete_push_notification_config",
]
