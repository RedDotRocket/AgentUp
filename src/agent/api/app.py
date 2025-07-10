import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
import uvicorn
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

# Load .env file if it exists
try:
    from dotenv import load_dotenv

    # Look for .env file in current directory and parent directories
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Check parent directory (for development)
        parent_env = Path.cwd().parent / ".env"
        if parent_env.exists():
            load_dotenv(parent_env)
except ImportError:
    pass  # python-dotenv not available

from ..config import load_config
from ..config.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from ..config.logging import configure_logging_from_config, create_structlog_middleware_with_config
from ..config.models import JSONRPCError
from ..core.executor import GenericAgentExecutor as AgentExecutorImpl
from ..push.handler import CustomRequestHandler
from ..push.notifier import EnhancedPushNotifier, ValkeyPushNotifier
from ..security import create_security_manager
from .routes import create_agent_card, jsonrpc_error_handler, router, set_request_handler_instance

# Optional imports; fall back to None if the module isn't present
try:
    from ..services import initialize_services_from_config
except ImportError:
    initialize_services_from_config = None

try:
    from ..core.dispatcher import register_ai_functions_from_handlers
except ImportError:
    register_ai_functions_from_handlers = None

# Configure structured logging at module level (before uvicorn configures its loggers)
try:
    # Load config early to configure logging
    early_config = load_config(configure_logging=False)  # Don't configure yet

    # Configure structured logging early
    configure_logging_from_config(early_config)

    # Clear context vars and get logger
    structlog.contextvars.clear_contextvars()
    logger = structlog.get_logger()

    logger.info("Structured logging configured at module level")
except Exception as e:
    # Fallback to basic logging if structlog setup fails
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to configure structured logging: {e}")

try:
    from ..mcp_support.mcp_integration import initialize_mcp_integration, shutdown_mcp_integration

    logger.debug("MCP support available")
    initialize_mcp_integration = initialize_mcp_integration
    shutdown_mcp_integration = shutdown_mcp_integration
except ImportError as e:
    logger.debug(f"MCP import failed: {e}")
    initialize_mcp_integration = None
    shutdown_mcp_integration = None
except Exception as e:
    logger.warning(f"MCP import failed with unexpected error: {e}")
    initialize_mcp_integration = None
    shutdown_mcp_integration = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for the FastAPI application."""
    # Load configuration and attach to app.state (logging already configured at module level)
    config = load_config(configure_logging=False)
    app.state.config = config

    # Structured logging is now configured at module level, before uvicorn starts

    agent_cfg = config.get("agent", {})
    name = agent_cfg.get("name", "Agent")
    version = agent_cfg.get("version", "0.1.0")

    # Log startup with structured logging already configured
    logger.info(f"Starting {name} v{version}", structured_logging=True, uvicorn_integration=True)

    # Initialize security manager
    try:
        security_manager = create_security_manager(config)
        app.state.security_manager = security_manager
        if security_manager.is_auth_enabled():
            logger.info(f"Security enabled with {security_manager.get_primary_auth_type()} authentication")
        else:
            logger.info("Security disabled - all endpoints will be public")
    except Exception as e:
        logger.error(f"Failed to initialize security manager: {e}")
        # Continue without security for now, but log the error
        app.state.security_manager = None

    # Initialize services if available & enabled
    svc_cfg = config.get("services", {})

    if initialize_services_from_config and svc_cfg.get("enabled", True):
        try:
            await initialize_services_from_config(config)
            logger.info("Services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
    else:
        logger.warning("Services initialization skipped")

    # Apply global middleware to existing handlers
    try:
        from ..handlers.handlers import apply_global_middleware

        apply_global_middleware()
        logger.info("Global middleware applied to existing handlers")
    except Exception as e:
        logger.error(f"Failed to apply global middleware: {e}")

    # Apply global state management to existing handlers
    try:
        from ..handlers.handlers import apply_global_state

        apply_global_state()
        logger.info("Global state management applied to existing handlers")
    except Exception as e:
        logger.error(f"Failed to apply global state management: {e}")

    # Initialize plugin system if available
    def _is_plugin_enabled(plugin_cfg) -> bool:
        """Check if plugin system is enabled based on configuration type."""
        if isinstance(plugin_cfg, dict):
            return plugin_cfg.get("enabled", True)
        elif isinstance(plugin_cfg, list):
            return bool(plugin_cfg)  # Enabled if not empty
        return True  # Default enabled for other types

    plugin_cfg = config.get("plugins", {})
    if _is_plugin_enabled(plugin_cfg):
        try:
            from ..plugins.integration import enable_plugin_system

            enable_plugin_system()
            logger.info("Plugin system initialized successfully")
        except ImportError:
            logger.debug("Plugin system not available")
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")

    # Register AI functions if available & requested
    routing_cfg = config.get("routing", {})
    default_mode = routing_cfg.get("default_mode", "ai")
    logger.info(f"Routing default mode set to: {default_mode}")

    # Register AI functions if any plugins might use AI routing
    # Note: In mixed routing, plugins can override the default mode
    plugins = config.get("plugins", [])
    needs_ai = any(plugin.get("routing_mode", default_mode) == "ai" for plugin in plugins)

    if register_ai_functions_from_handlers and needs_ai and svc_cfg.get("ai_functions", True):
        try:
            register_ai_functions_from_handlers()
            logger.info("AI functions registered successfully")
        except Exception as e:
            logger.error(f"Failed to register AI functions: {e}")
    elif not needs_ai:
        logger.info("No AI routing plugins found - skipping AI function registration")

    # Initialize state management if configured
    state_cfg = config.get("state", {})
    if state_cfg:
        try:
            from ..state.context import get_context_manager

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

        except Exception as e:
            logger.error(f"Failed to initialize state management: {e}")
            # Continue without state management
            app.state.context_manager = None

    # Initialize MCP integration if available & enabled
    mcp_cfg = config.get("mcp", {})
    logger.info(f"MCP debug: initialize_mcp_integration is None!: {initialize_mcp_integration is None}")
    if initialize_mcp_integration and mcp_cfg.get("enabled", False):
        try:
            await initialize_mcp_integration(config)
            logger.info("MCP integration initialized successfully")

            # Add MCP HTTP endpoint if server is enabled
            if mcp_cfg.get("server", {}).get("enabled", False):
                try:
                    from ..mcp_support.mcp_http_server import MCPHTTPServer, create_mcp_router

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

    # Initialize push notifier with Valkey if configured
    push_config = config.get("push_notifications", {})
    if push_config.get("backend") == "valkey" and push_config.get("enabled", True):
        try:
            from ..services import get_services

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
                handler._push_notifier = valkey_push_notifier

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

    request_handler = CustomRequestHandler(
        agent_executor=AgentExecutorImpl(agent=create_agent_card()),
        task_store=InMemoryTaskStore(),
        push_notifier=push_notifier,
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

    # Add structured logging middleware if correlation ID is enabled
    if logging_config.get("correlation_id", True):
        try:
            # Optional import for correlation ID middleware
            from asgi_correlation_id import CorrelationIdMiddleware

            # Add correlation ID middleware first (order matters - this is the outer middleware)
            app.add_middleware(CorrelationIdMiddleware)

            # Add structured logging middleware (this is the inner middleware)
            from ..config.logging import LoggingConfig

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
