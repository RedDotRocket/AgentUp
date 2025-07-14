import os
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

from agent.api.rate_limiting import NetworkRateLimitMiddleware
from agent.capabilities.executors import apply_global_middleware, apply_global_state_management
from agent.config import load_config
from agent.config.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from agent.config.logging import create_structlog_middleware_with_config
from agent.config.models import JSONRPCError, PluginsConfig
from agent.core.executor import GenericAgentExecutor as AgentExecutorImpl
from agent.mcp_support.mcp_integration import initialize_mcp_integration, shutdown_mcp_integration
from agent.push.notifier import EnhancedPushNotifier, ValkeyPushNotifier
from agent.security import create_security_manager

# from agent.services import initialize_services_from_config
from .routes import create_agent_card, jsonrpc_error_handler, router, set_request_handler_instance

structlog.contextvars.clear_contextvars()
logger = structlog.get_logger()

config = load_config(configure_logging=False)

initialize_mcp_integration = initialize_mcp_integration
shutdown_mcp_integration = shutdown_mcp_integration


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for the FastAPI application."""

    app.state.config = config

    agent_cfg = config.get("agent", {})
    name = agent_cfg.get("name", "Agent")
    version = agent_cfg.get("version", "0.1.0")

    # Log startup with structured logging already configured
    logger.info(f"Starting {name} v{version}", structured_logging=True, uvicorn_integration=True)

    # Initialize security manager
    try:
        logger.debug("Step 1: Initializing security manager")
        security_manager = create_security_manager(config)
        app.state.security_manager = security_manager

        # Set as global security manager so unified auth is available
        from agent.security import set_global_security_manager

        logger.debug("Step 2: Setting global security manager")
        set_global_security_manager(security_manager)

        # Check if security is enabled and log accordingly
        logger.debug("Step 3: Checking security status")
        if security_manager.is_auth_enabled():
            logger.info(f"Security enabled with {security_manager.get_primary_auth_type()} authentication")
        else:
            logger.warning("WARNING: Security disabled - all endpoints are UNPROTECTED")
    except Exception as e:
        logger.error(f"WARNING: Failed to initialize security manager: {e}")
        # TODO: Handle security manager initialization failure, better. I feel like this should be a hard failure
        app.state.security_manager = None
        logger.warning("Continuing without security manager - all endpoints will be UNPROTECTED")
        app.state.security_manager = None

    # Apply global middleware to existing handlers
    logger.debug("Step 4: Applying global middleware to existing handlers")
    try:
        apply_global_middleware()
        logger.info("Global middleware applied to available handlers")
    except Exception as e:
        # TODO: Handle security manager initialization failure, better. I feel like this should be a hard failure
        logger.error(f"Failed to apply global middleware: {e}")

    # Apply global state management to existing handlers
    logger.debug("Step 5: Applying global state management to existing handlers")
    try:
        apply_global_state_management()
        logger.info("Global state management applied to existing handlers")
    except Exception as e:
        logger.error(f"Failed to apply global state management: {e}")

    # Initialize plugin system if available
    logger.debug("Step 6: Initializing plugin system if available")
    plugin_cfg = config.get("plugins", {})
    print(f"Plugin configuration: {plugin_cfg}")

    try:
        plugins_config = PluginsConfig.from_config_value(plugin_cfg)

        if plugins_config.enabled:
            try:
                from agent.plugins.integration import enable_plugin_system

                enable_plugin_system()
                logger.debug("Plugin system completed")
                logger.debug("Plugin AI functions will be provided through runtime scope filtering only")

                if plugins_config.plugins:
                    logger.info(f"Loaded {len(plugins_config.plugins)} plugin configurations")

            except ImportError:
                logger.debug("Plugin system not available")
            except Exception as e:
                logger.error(f"Failed to initialize plugin system: {e}")
        else:
            logger.debug("Plugin system disabled by configuration")
    except Exception as e:
        logger.error(f"Invalid plugin configuration: {e}")
        logger.debug("Plugin system disabled due to configuration error")

    routing_cfg = config.get("routing", {})
    default_mode = routing_cfg.get("default_mode", "ai")
    logger.debug(f"Global / fallback routing mode set to: {default_mode}")

    # Initialize state management if configured
    state_cfg = config.get("state_management", {})
    if state_cfg:
        try:
            from agent.state.context import get_context_manager

            backend = state_cfg.get("backend", "memory")
            backend_config = {}

            if backend == "valkey":
                # Get Valkey URL from services configuration or state config
                valkey_service = config.get("services", {}).get("valkey", {}).get("config", {})
                backend_config["url"] = valkey_service.get("url", "valkey://localhost:6379")
                backend_config["ttl"] = state_cfg.get("ttl", 3600)
            elif backend == "file":
                backend_config["storage_dir"] = state_cfg.get("storage_dir", "./conversation_states")

            # Initialize global state manager
            context_manager = get_context_manager(backend, **backend_config)
            app.state.context_manager = context_manager

            logger.info(f"State management initialized with {backend} backend")

            logger.info(f"Ahoy captain! {name} v{version} is ready to sail the seas!")

        except Exception as e:
            logger.error(f"Failed to initialize state management: {e}")
            # Continue without state management
            app.state.context_manager = None

    # Initialize MCP integration if available & enabled
    mcp_cfg = config.get("mcp", {})
    if initialize_mcp_integration and mcp_cfg.get("enabled", False):
        try:
            await initialize_mcp_integration(config)
            logger.info("MCP integration initialized successfully")

            # Add MCP HTTP endpoint if server is enabled
            if mcp_cfg.get("server", {}).get("enabled", False):
                try:
                    from agent.mcp_support.mcp_http_server import MCPHTTPServer, create_mcp_router

                    # Create MCP HTTP server with configuration
                    server_cfg = mcp_cfg.get("server", {})
                    mcp_http_server = MCPHTTPServer(
                        agent_name=server_cfg.get("name", agent_cfg.get("name", "Agent")),
                        agent_version=agent_cfg.get("version", "0.1.0"),
                        expose_handlers=server_cfg.get("expose_handlers", True),
                        expose_resources=server_cfg.get("expose_resources", []),
                    )
                    await mcp_http_server.initialize()

                    # Store in app state for later access
                    app.state.mcp_http_server = mcp_http_server

                    # Create and mount MCP router
                    mcp_router = create_mcp_router(mcp_http_server)
                    app.include_router(mcp_router)

                    logger.info("MCP HTTP endpoint added at /mcp")
                except Exception as e:
                    logger.error(f"Failed to add MCP HTTP endpoint: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize MCP integration: {e}")
        logger.debug("MCP integration initialization complete")

    # Initialize push notifier with Valkey if configured
    push_config = config.get("push_notifications", {})
    if push_config.get("backend") == "valkey" and push_config.get("enabled", True):
        try:
            from agent.services import get_services

            services = get_services()

            # Find the cache service name from config
            cache_service_name = None
            services_config = config.get("services", {})
            for service_name, service_config in services_config.items():
                if service_config.get("type") == "cache":
                    cache_service_name = service_name
                    break

            if cache_service_name:
                valkey_service = services.get_cache(cache_service_name)
            else:
                valkey_service = None
                logger.warning("No cache service found in configuration")

            # Create Valkey client from service URL
            if valkey_service and hasattr(valkey_service, "url"):
                import valkey.asyncio as valkey

                valkey_url = valkey_service.url
                valkey_client = valkey.from_url(valkey_url)
            else:
                valkey_client = None
                logger.warning("Cannot create Valkey client - no URL available")

            if valkey_client:
                # Create new Valkey push notifier
                client = httpx.AsyncClient()
                valkey_push_notifier = ValkeyPushNotifier(
                    client=client,
                    valkey_client=valkey_client,
                    key_prefix=push_config.get("key_prefix", "agentup:push:"),
                    validate_urls=push_config.get("validate_urls", True),
                )
                # Update the request handler to use Valkey push notifier
                from .routes import get_request_handler

                handler = get_request_handler()
                handler._push_config_store = valkey_push_notifier
                handler._push_sender = valkey_push_notifier

                logger.info("Updated to Valkey-backed push notifier")
            else:
                logger.warning("Valkey service available but no client found, using memory push notifier")
        except Exception as e:
            logger.error(f"Failed to initialize Valkey push notifier: {e}")
            logger.info("Using memory push notifier")

    yield

    # Shutdown hooks
    logger.info("Shutting down...")

    # State management cleanup
    if hasattr(app.state, "context_manager") and app.state.context_manager:
        try:
            # Cleanup old contexts (optional)
            cleaned = await app.state.context_manager.cleanup_old_contexts(max_age_hours=24)
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old conversation contexts")
        except Exception as e:
            logger.error(f"Error during state cleanup: {e}")

    if shutdown_mcp_integration and mcp_cfg.get("enabled", False):
        try:
            await shutdown_mcp_integration()
            logger.info("MCP integration shut down successfully")
        except Exception as e:
            logger.error(f"Failed to shutdown MCP integration: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    agent_card = create_agent_card()

    # Create basic request handler with memory push notifier
    client = httpx.AsyncClient()
    push_notifier = EnhancedPushNotifier(client=client)

    request_handler = DefaultRequestHandler(
        agent_executor=AgentExecutorImpl(agent=create_agent_card()),
        task_store=InMemoryTaskStore(),
        push_config_store=push_notifier,
        push_sender=push_notifier,
    )
    set_request_handler_instance(request_handler)

    # Create FastAPI app
    app = FastAPI(
        title=agent_card.name,
        description=agent_card.description,
        version=agent_card.version,
        lifespan=lifespan,
    )

    # Configure logging middleware during app creation (logging already configured at module level)
    config = load_config(configure_logging=False)  # Don't reconfigure logging
    logging_config = config.get("logging", {})

    # Add network-level rate limiting middleware (early in stack for security)
    rate_limit_config = config.get("rate_limiting", {})
    if rate_limit_config.get("enabled", True):  # Enabled by default
        endpoint_limits = rate_limit_config.get(
            "endpoint_limits",
            {
                "/": {"rpm": 100, "burst": 120},  # Main JSON-RPC endpoint
                "/mcp": {"rpm": 50, "burst": 60},  # MCP endpoints (more restrictive)
                "/health": {"rpm": 200, "burst": 240},  # Health check (more permissive)
                "/status": {"rpm": 60, "burst": 72},  # Status endpoint
                "default": {"rpm": 60, "burst": 72},  # Default for other endpoints
            },
        )
        app.add_middleware(NetworkRateLimitMiddleware, endpoint_limits=endpoint_limits)
        logger.debug("Network rate limiting middleware enabled", endpoint_limits=endpoint_limits)

    # Add structured logging middleware if correlation ID is enabled
    if logging_config.get("correlation_id", True):
        try:
            # Optional import for correlation ID middleware
            from asgi_correlation_id import CorrelationIdMiddleware

            # Add correlation ID middleware first (order matters - this is the outer middleware)
            app.add_middleware(CorrelationIdMiddleware)

            # Add structured logging middleware (this is the inner middleware)
            from agent.config.logging import LoggingConfig

            try:
                logging_cfg = LoggingConfig(**logging_config)
            except Exception:
                # Use defaults if config is invalid
                logging_cfg = LoggingConfig()

            StructLogMiddleware = create_structlog_middleware_with_config(logging_cfg)
            app.add_middleware(StructLogMiddleware)

        except ImportError:
            # Fall back to basic request logging if asgi-correlation-id not available
            if logging_config.get("request_logging", True):
                from .request_logging import add_correlation_id_to_logs

                add_correlation_id_to_logs(app)
    elif logging_config.get("request_logging", True):
        from .request_logging import add_correlation_id_to_logs

        add_correlation_id_to_logs(app)

    # Add default routes and exception handlers
    app.include_router(router)
    app.add_exception_handler(JSONRPCError, jsonrpc_error_handler)

    return app


app = create_app()


def main():
    """Main function to set up and run the agent."""
    host = os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)
    port = int(os.getenv("SERVER_PORT", DEFAULT_SERVER_PORT))

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
