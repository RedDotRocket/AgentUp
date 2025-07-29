import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# Import structlog lazily to avoid import-time configuration issues
def get_logger():
    try:
        import structlog

        return structlog.get_logger(__name__)
    except Exception:
        # Fallback to standard logging if structlog is not available/configured
        import logging

        return logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, log_requests: bool = True, log_responses: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        logger = get_logger()

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())[:8]

        # Add correlation ID to request state
        request.state.correlation_id = correlation_id

        # Try to bind correlation ID to logging context (structlog)
        try:
            import structlog

            context_manager = structlog.contextvars.bound_contextvars(
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params) if request.query_params else None,
            )
        except Exception:
            # Fallback for when structlog is not available
            from contextlib import nullcontext

            context_manager = nullcontext()

        with context_manager:
            start_time = time.time()

            # Log request if enabled
            if self.log_requests:
                try:
                    # Get authentication info if available
                    auth_user = None
                    auth_type = None
                    if (
                        hasattr(request, "state")
                        and hasattr(request.state, "auth_result")
                        and request.state.auth_result
                    ):
                        auth_user = request.state.auth_result.user_id
                        auth_type = request.state.auth_result.auth_type

                    logger.info(
                        "Request started",
                        method=request.method,
                        path=request.url.path,
                        query_params=str(request.query_params) if request.query_params else None,
                        client_host=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        authenticated_user=auth_user,
                        auth_type=auth_type,
                        forwarded_for=request.headers.get("X-Forwarded-For"),
                    )
                except Exception:
                    # Fallback logging
                    logger.info(f"Request started: {request.method} {request.url.path}")

            try:
                # Process request
                response = await call_next(request)

                # Calculate request duration
                duration = time.time() - start_time

                # Log response if enabled
                if self.log_responses:
                    try:
                        logger.info(
                            "Request completed",
                            status_code=response.status_code,
                            duration=round(duration, 3),
                        )
                    except Exception:
                        # Fallback logging
                        logger.info(f"Request completed: {response.status_code} in {duration:.3f}s")

                # Add correlation ID to response headers
                response.headers["X-Correlation-ID"] = correlation_id

                return response

            except Exception as e:
                # Calculate request duration for error case
                duration = time.time() - start_time

                # Log error
                try:
                    logger.error(
                        "Request failed",
                        error=str(e),
                        error_type=type(e).__name__,
                        duration=round(duration, 3),
                    )
                except Exception:
                    # Fallback logging
                    logger.error(f"Request failed: {type(e).__name__}: {e}")

                # Re-raise the exception
                raise


def add_correlation_id_to_logs(app):
    app.add_middleware(RequestLoggingMiddleware)


# Utility function to get correlation ID from request
def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")
