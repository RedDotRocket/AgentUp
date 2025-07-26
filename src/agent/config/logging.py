"""
Logging configuration module for AgentUp.

This module provides centralized logging configuration using structlog for structured logging
with support for multiple output formats (text, JSON), console output,
and integration with FastAPI/uvicorn.
"""

import logging
import re
import time
from typing import Any, TypedDict

import structlog
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from structlog.types import EventDict, Processor
from uvicorn.protocols.utils import get_path_with_query_string

from .model import LoggingConfig

# Optional import for correlation ID support
try:
    from asgi_correlation_id import correlation_id

    CORRELATION_ID_AVAILABLE = True
except ImportError:
    CORRELATION_ID_AVAILABLE = False
    correlation_id = None

# Global logger instance for this module - will be configured later
logger = None
_logging_configured = False


def configure_logging_from_config(config: dict | None) -> LoggingConfig:
    """Configure logging from agent configuration.

    Args:
        config: Agent configuration dictionary or None

    Returns:
        LoggingConfig instance
    """
    # Handle None or empty config
    if config is None:
        config = {}

    logging_config_dict = config.get("logging", {})
    logging_config = LoggingConfig(**logging_config_dict)

    # Setup logging with the configuration
    setup_logging(logging_config)

    return logging_config


def drop_color_message_key(_logger, _method_name, event_dict: EventDict) -> EventDict:
    """
    Uvicorn logs the message a second time in the extra `color_message`, but we don't
    need it. This processor drops the key from the event dict if it exists.
    """
    event_dict.pop("color_message", None)
    return event_dict


def uppercase_log_level(_logger, _method_name, event_dict: EventDict) -> EventDict:
    """
    Convert log level to uppercase for consistent formatting.
    """
    if "level" in event_dict:
        event_dict["level"] = event_dict["level"].upper()
    return event_dict


def setup_logging(config: LoggingConfig | None = None, json_logs: bool | None = None, log_level: str | None = None):
    """Setup structured logging with optional configuration.

    Args:
        config: LoggingConfig object with full configuration
        json_logs: Override for JSON format (backwards compatibility)
        log_level: Override for log level (backwards compatibility)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Use config if provided, otherwise use defaults with overrides
    if config is None:
        config = LoggingConfig()

    # Apply overrides for backwards compatibility
    if json_logs is not None:
        config.format = "json" if json_logs else "text"
    if log_level is not None:
        config.level = log_level
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        uppercase_log_level,  # Convert log level to uppercase
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        drop_color_message_key,
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if config.format == "json":
        # Format the exception only for JSON logs, as we want to pretty-print them when
        # using the ConsoleRenderer
        shared_processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log_renderer: structlog.types.Processor
    if config.format == "json":
        log_renderer = structlog.processors.JSONRenderer()
    else:
        # Use default ConsoleRenderer with standard structlog colors
        log_renderer = structlog.dev.ConsoleRenderer(
            colors=config.console.colors,
            pad_event=25,  # Consistent padding``
        )

    formatter = structlog.stdlib.ProcessorFormatter(
        # These run ONLY on `logging` entries that do NOT originate within
        # structlog.
        foreign_pre_chain=shared_processors,
        # These run on ALL entries after the pre_chain is done.
        processors=[
            # Remove _record & _from_structlog.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ],
    )

    # Reconfigure the root logger to use our structlog formatter, effectively emitting the logs via structlog
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(config.level.upper())

    # Apply module-specific log levels
    for module_name, module_level in config.modules.items():
        logging.getLogger(module_name).setLevel(module_level.upper())

    # Configure uvicorn loggers to use our structured logging
    for _log in ["uvicorn", "uvicorn.error"]:
        # Make sure the logs are handled by the root logger
        logging.getLogger(_log).handlers.clear()
        logging.getLogger(_log).propagate = True

    # Uvicorn logs are re-emitted with more context. We effectively silence them here
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False

    _logging_configured = True


def _get_module_logger():
    """Get logger for this module, initializing if needed."""
    global logger
    if logger is None:
        try:
            logger = structlog.get_logger(__name__)
        except Exception:
            import logging

            logger = logging.getLogger(__name__)
    return logger


def create_structlog_middleware_with_config(config: LoggingConfig | None = None):
    """Create a StructLogMiddleware instance with proper configuration.

    Args:
        config: LoggingConfig to use, or None to use defaults

    Returns:
        Configured StructLogMiddleware class (not instance)
    """
    if config is None:
        config = LoggingConfig()

    # Configure loggers with the provided config
    app_logger_name = "agentup.app"
    access_logger_name = "agentup.access"

    class ConfiguredStructLogMiddleware(StructLogMiddleware):
        def __init__(self, app):
            super().__init__(app)
            # Use configured logger names
            global app_logger, access_logger
            app_logger = structlog.stdlib.get_logger(app_logger_name)
            access_logger = structlog.stdlib.get_logger(access_logger_name)

    return ConfiguredStructLogMiddleware


class FastAPIStructLogger:
    def __init__(self, log_name: str = "agentup.app"):
        self.logger = structlog.stdlib.get_logger(log_name)

    @staticmethod
    def _to_snake_case(name):
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def bind(self, *args, **new_values: Any):
        # For AgentUp, we'll focus on key-value binding rather than SQLAlchemy models
        # If you need model binding, implement a protocol for model objects
        for arg in args:
            if hasattr(arg, "id") and hasattr(arg, "__class__"):
                key = self._to_snake_case(type(arg).__name__)
                structlog.contextvars.bind_contextvars(**{key: arg.id})
            else:
                self.logger.error(
                    "Unsupported argument when trying to log. "
                    f"Argument must have 'id' attribute. Invalid argument: {type(arg).__name__}"
                )
                continue

        structlog.contextvars.bind_contextvars(**new_values)

    @staticmethod
    def unbind(*keys: str):
        structlog.contextvars.unbind_contextvars(*keys)

    def debug(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.debug(event, *args, **kw)

    def info(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.info(event, *args, **kw)

    def warning(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.warning(event, *args, **kw)

    warn = warning

    def error(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.error(event, *args, **kw)

    def critical(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.critical(event, *args, **kw)

    def exception(self, event: str | None = None, *args: Any, **kw: Any):
        self.logger.exception(event, *args, **kw)


# Create default loggers - will be reconfigured when settings are available
app_logger = structlog.stdlib.get_logger("agentup.app")
access_logger = structlog.stdlib.get_logger("agentup.access")


class AccessInfo(TypedDict, total=False):
    status_code: int
    start_time: float


class StructLogMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # If the request is not an HTTP request, we don't need to do anything special
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        structlog.contextvars.clear_contextvars()
        if CORRELATION_ID_AVAILABLE and correlation_id:
            structlog.contextvars.bind_contextvars(request_id=correlation_id.get())
        else:
            # Generate a simple request ID if correlation_id is not available
            import uuid

            structlog.contextvars.bind_contextvars(request_id=str(uuid.uuid4())[:8])

        info = AccessInfo()

        # Inner send function
        async def inner_send(message):
            if message["type"] == "http.response.start":
                info["status_code"] = message["status"]
            await send(message)

        try:
            info["start_time"] = time.perf_counter_ns()
            await self.app(scope, receive, inner_send)
        except Exception as e:
            app_logger.exception(
                "An unhandled exception was caught by last resort middleware",
                exception_class=e.__class__.__name__,
                exc_info=e,
            )
            info["status_code"] = 500
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                },
            )
            await response(scope, receive, send)
        finally:
            process_time = time.perf_counter_ns() - info["start_time"]
            client_host, client_port = scope["client"]
            http_method = scope["method"]
            http_version = scope["http_version"]
            url = get_path_with_query_string(scope)

            # Recreate the Uvicorn access log format, but add all parameters as structured information
            request_id = correlation_id.get() if CORRELATION_ID_AVAILABLE and correlation_id else "unknown"
            access_logger.info(
                f"""{client_host}:{client_port} - "{http_method} {scope["path"]} HTTP/{http_version}" {info["status_code"]}""",
                http={
                    "url": str(url),
                    "status_code": info["status_code"],
                    "method": http_method,
                    "request_id": request_id,
                    "version": http_version,
                },
                network={"client": {"ip": client_host, "port": client_port}},
                duration=process_time,
            )
