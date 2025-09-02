import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import httpx
import structlog
import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI

if TYPE_CHECKING:
    from a2a.server.tasks.push_notification_config_store import PushNotificationConfigStore
    from a2a.server.tasks.push_notification_sender import PushNotificationSender

from agent.a2a.agentcard import create_agent_card
from agent.config.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT
from agent.config.model import LogFormat
from agent.core.executor import AgentUpExecutor
from agent.dependencies import get_config
from agent.push.notifier import EnhancedPushNotifier
from agent.services import AgentBootstrapper

from .routes import router, set_request_handler_instance

# Configure logging
structlog.contextvars.clear_contextvars()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize services using bootstrapper
    # This is where we set up the agent's services and capabilities
    logger.debug("Starting application lifespan with services")
    bootstrapper = AgentBootstrapper()

    try:
        # Single line initialization!
        await bootstrapper.initialize_services(app)

        # Now that services (including MCP) are initialized, create the real agent card with MCP skills
        # Clear cache to force regeneration since services may have changed capabilities
        from agent.a2a.agentcard import clear_agent_card_cache

        clear_agent_card_cache()
        app.state.agent_card = create_agent_card()

        # Setup request handler with services
        _setup_request_handler(app)

        yield

    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise
    finally:
        # Cleanup services
        await bootstrapper.shutdown_services()


def _setup_request_handler(app: FastAPI) -> None:
    # Get services from app state
    services = app.state.services

    # Create request handler with appropriate push notifier
    client = httpx.AsyncClient()

    # Use push service if available
    push_service = services.get("pushnotificationservice")
    push_notifier: EnhancedPushNotifier

    if push_service and hasattr(push_service, "push_notifier") and push_service.push_notifier:
        # Ensure the service push notifier is compatible
        service_notifier = push_service.push_notifier
        if hasattr(service_notifier, "set_info") and hasattr(service_notifier, "send_notification"):
            # Type: ignore because we've verified it has the required methods
            push_notifier = service_notifier  # type: ignore[assignment]
            logger.debug("Using service-provided push notifier")
        else:
            push_notifier = EnhancedPushNotifier(client=client)
            logger.debug("Service push notifier not compatible, using default")
    else:
        push_notifier = EnhancedPushNotifier(client=client)
        logger.debug("Using default push notifier")

    # Use the agent_card from app.state (already created in create_app())
    agent_card = app.state.agent_card

    # Create request handler
    # Cast to protocol types since EnhancedPushNotifier implements both interfaces
    if TYPE_CHECKING:
        config_store = cast("PushNotificationConfigStore", push_notifier)
        sender = cast("PushNotificationSender", push_notifier)
    else:
        config_store = push_notifier
        sender = push_notifier

    # Load agent execution configuration
    config = get_config()
    agent_type = config.agent_type

    # Create agent configuration for executor
    from agent.config.model import AgentType
    from agent.core.models import AgentConfiguration

    if agent_type == AgentType.ITERATIVE:
        memory_config_data = config.memory_config
        iterative_config_data = config.iterative_config

        # Import memory and iterative config models
        from agent.config.model import IterativeConfig, MemoryConfig

        memory_config = MemoryConfig(**memory_config_data) if memory_config_data else MemoryConfig()
        iterative_config = IterativeConfig(**iterative_config_data) if iterative_config_data else IterativeConfig()

        agent_config = AgentConfiguration(
            agent_type=AgentType.ITERATIVE,
            memory=memory_config,
            iterative=iterative_config,
        )
    else:
        agent_config = AgentConfiguration(agent_type=AgentType.REACTIVE)

    request_handler = DefaultRequestHandler(
        agent_executor=AgentUpExecutor(agent=agent_card, config=agent_config),
        task_store=InMemoryTaskStore(),
        push_config_store=config_store,
        push_sender=sender,
    )

    # Set global request handler
    set_request_handler_instance(request_handler)


def create_app() -> FastAPI:
    # Create initial agent card for FastAPI metadata (before services are initialized)
    agent_card = create_agent_card()

    # Create FastAPI app
    app = FastAPI(
        title=agent_card.name,
        description=agent_card.description,
        version=agent_card.version,
        lifespan=lifespan,
    )

    # Agent card will be recreated after services initialize in lifespan()

    # Configure middleware
    _configure_middleware(app)

    # Add routes
    app.include_router(router)

    return app


def _configure_middleware(app: FastAPI) -> None:
    config = get_config()

    # CORS middleware
    if config.api.cors_enabled:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.api.cors_origins,
            allow_methods=config.api.cors_methods,
            allow_headers=["Content-Type", "X-API-Key"],
            allow_credentials=False,
            max_age=600,
        )

    # Network rate limiting middleware (applied to FastAPI Middleware)
    rate_limiting_enabled = getattr(config.middleware.rate_limiting, "enabled", True)
    if rate_limiting_enabled:
        from agent.api.rate_limiting import NetworkRateLimitMiddleware

        endpoint_limits = {
            "/": {
                "rpm": getattr(config.middleware.rate_limiting, "requests_per_minute", 60),
                "burst": getattr(config.middleware.rate_limiting, "burst_size", 72),
            },
            "/mcp": {"rpm": 50, "burst": 60},
            "/health": {"rpm": 200, "burst": 240},
        }
        app.add_middleware(NetworkRateLimitMiddleware, endpoint_limits=endpoint_limits)
        logger.debug("Network rate limiting middleware enabled")

    # Logging middleware
    if config.logging.correlation_id:
        try:
            from asgi_correlation_id import CorrelationIdMiddleware

            from agent.config.logging import LoggingConfig, create_structlog_middleware_with_config

            # Add correlation ID middleware
            app.add_middleware(CorrelationIdMiddleware)

            # Add structured logging middleware
            try:
                logging_cfg = config.logging
            except Exception:
                # Fallback with explicit defaults for type checker
                logging_cfg = LoggingConfig(
                    enabled=True,
                    level="INFO",
                    format=LogFormat.TEXT,
                    correlation_id=True,
                    request_logging=True,
                    structured_data=False,
                )
            StructLogMiddleware = create_structlog_middleware_with_config(logging_cfg)
            app.add_middleware(StructLogMiddleware)

            logger.debug("Structured logging middleware enabled")

        except ImportError:
            # Fallback to basic request logging
            if config.logging.request_logging:
                from .request_logging import add_correlation_id_to_logs

                add_correlation_id_to_logs(app)
                logger.debug("Basic request logging enabled")

    elif config.logging.request_logging:
        from .request_logging import add_correlation_id_to_logs

        add_correlation_id_to_logs(app)
        logger.debug("Basic request logging enabled")


# Create the app instance
app = create_app()


def main():
    host = os.getenv("SERVER_HOST", DEFAULT_SERVER_HOST)
    port = int(os.getenv("SERVER_PORT", DEFAULT_SERVER_PORT))

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
