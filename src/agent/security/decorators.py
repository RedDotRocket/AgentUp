from collections.abc import Callable
from functools import wraps

import structlog
from fastapi import HTTPException, Request

from .base import SecurityPolicy


def protected(
    auth_type: str | None = None,
    required: bool = True,
    scopes: set[str] | None = None,
    allow_anonymous: bool = False,
    force_auth: bool = False,
):
    """
    Decorator to protect AgentUp endpoints with authentication and authorization.

    This decorator provides a clean, declarative way to add security to endpoints
    without cluttering the endpoint logic with authentication code. It respects
    the global security configuration while providing override options.

    Args:
        auth_type: Specific authentication type to use (overrides configured default)
        required: Whether authentication is required (default True)
        scopes: Required scopes/permissions for access
        allow_anonymous: Allow anonymous access when auth fails (default False)
        force_auth: Force authentication even when global security is disabled (default False)

    Behavior:
        - When security.enabled = false: Allows access by default (logs warning)
        - When security.enabled = true: Requires authentication as normal
        - force_auth = true: Always requires auth regardless of global setting

    Usage:
        @protected()  # Respects global security setting
        async def my_endpoint(request: Request):
            return {"message": "Context-aware protection"}

        @protected(auth_type="api_key")  # Specific auth type
        async def api_endpoint(request: Request):
            return {"message": "API key protected"}

        @protected(required=False)  # Never requires auth
        async def optional_endpoint(request: Request):
            return {"message": "Always accessible"}

        @protected(force_auth=True)  # Always requires auth
        async def secure_endpoint(request: Request):
            return {"message": "Always protected"}

        @protected(scopes={"read", "write"})  # Scope-based
        async def scoped_endpoint(request: Request):
            return {"message": "Scope-protected endpoint"}

        @protected(allow_anonymous=True)  # Mixed access
        async def mixed_endpoint(request: Request):
            # Check if user is authenticated
            return {"message": "Mixed endpoint"}

    The decorator will:
    1. Automatically find the Request object in function parameters
    2. Respect global security configuration unless overridden
    3. Apply authentication using the specified or configured auth type
    4. Check required scopes if specified
    5. Store authentication result in request.state.auth_result
    6. Log security bypass events when global security is disabled
    7. Handle errors gracefully with proper HTTP exceptions

    Note: This decorator requires a SecurityManager instance when authentication
    is actually needed (global security enabled or force_auth=True).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find the Request object in the arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if not request:
                # Check kwargs for request
                request = kwargs.get("request")

            if not request:
                raise HTTPException(
                    status_code=500, detail="@protected decorator requires Request parameter in endpoint function"
                )

            # Get security manager from application state
            security_manager = getattr(request.app.state, "security_manager", None)

            # Determine if authentication should be enforced
            should_authenticate = required and (force_auth or (security_manager and security_manager.is_auth_enabled()))

            # Handle case where authentication is required but security manager not available
            if should_authenticate and not security_manager:
                raise HTTPException(status_code=500, detail="Security manager not initialized")

            # If authentication not required or global security disabled, allow access with logging
            if not should_authenticate:
                # Log security bypass for audit purposes
                if required and not force_auth:
                    logger = structlog.get_logger(__name__)
                    endpoint = str(request.url.path) if request.url else "unknown"
                    logger.warning(
                        f"Security bypass: {endpoint} - Global security disabled, "
                        f"@protected() allowing access. Use force_auth=True to override."
                    )

                # Store None auth result and proceed
                if not hasattr(request, "state"):
                    request.state = type("State", (), {})()
                request.state.auth_result = None
                return await func(*args, **kwargs)

            # Create security policy
            policy = SecurityPolicy(
                require_authentication=required,
                allowed_auth_types={auth_type} if auth_type else None,
                required_scopes=scopes,
                allow_anonymous=allow_anonymous,
            )

            # Perform authentication
            auth_result = None
            try:
                auth_result = await security_manager.authenticate_request(request, auth_type=auth_type, policy=policy)
            except HTTPException:
                if not required or allow_anonymous:
                    # Authentication failed but it's optional or anonymous is allowed
                    auth_result = None
                else:
                    # Re-raise the HTTP exception for required authentication
                    raise

            # Store authentication result in request state for endpoint use
            if not hasattr(request, "state"):
                request.state = type("State", (), {})()
            request.state.auth_result = auth_result

            # Call the original function
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_scopes(*required_scopes: str):
    """
    Decorator to require specific scopes for endpoint access.

    This is a convenience decorator that combines @protected with scope requirements.

    Args:
        *required_scopes: Required scopes for access

    Usage:
        @require_scopes("read", "write")
        async def admin_endpoint(request: Request):
            return {"message": "Admin endpoint"}
    """
    return protected(scopes=set(required_scopes))


def api_key_required(required: bool = True):
    """
    Decorator to specifically require API key authentication.

    Args:
        required: Whether API key is required (default True)

    Usage:
        @api_key_required()
        async def api_endpoint(request: Request):
            return {"message": "API key required"}

        @api_key_required(required=False)
        async def optional_api_endpoint(request: Request):
            return {"message": "API key optional"}
    """
    return protected(auth_type="api_key", required=required)


def bearer_token_required(required: bool = True):
    """
    Decorator to specifically require Bearer token authentication.

    Args:
        required: Whether Bearer token is required (default True)

    Usage:
        @bearer_token_required()
        async def jwt_endpoint(request: Request):
            return {"message": "Bearer token required"}
    """
    return protected(auth_type="bearer", required=required)


# Legacy alias for backward compatibility
def always_protected(auth_type: str | None = None, scopes: set[str] | None = None):
    """
    Decorator to always require authentication regardless of global security setting.

    This is equivalent to @protected(force_auth=True) and ensures the endpoint
    is always protected even when global security is disabled.

    Args:
        auth_type: Specific authentication type to use
        scopes: Required scopes/permissions for access

    Usage:
        @always_protected()
        async def admin_endpoint(request: Request):
            return {"message": "Always requires auth"}

        @always_protected(auth_type="api_key", scopes={"admin"})
        async def super_secure_endpoint(request: Request):
            return {"message": "Always requires API key + admin scope"}
    """
    return protected(force_auth=True, auth_type=auth_type, scopes=scopes)


def authenticated(auth_type: str | None = None, required: bool = True):
    """Legacy alias for @protected decorator.

    Args:
        auth_type: Authentication type to use
        required: Whether authentication is required

    Note: This is provided for backward compatibility. Use @protected instead.
    """
    return protected(auth_type=auth_type, required=required)


# Utility function to get authentication result from request
def get_auth_result(request: Request):
    """Get authentication result from request state.

    Args:
        request: FastAPI request object

    Returns:
        AuthenticationResult or None: Authentication result if available

    Usage:
        @protected()
        async def my_endpoint(request: Request):
            auth_result = get_auth_result(request)
            if auth_result:
                user_id = auth_result.user_id
                scopes = auth_result.scopes
            return {"user": user_id}
    """
    if hasattr(request, "state") and hasattr(request.state, "auth_result"):
        return request.state.auth_result
    return None


def get_current_user_id(request: Request) -> str | None:
    """Get current user ID from authentication result.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: User ID if authenticated, None otherwise
    """
    auth_result = get_auth_result(request)
    return auth_result.user_id if auth_result else None


def has_scope(request: Request, scope: str) -> bool:
    """Check if current user has a specific scope.

    Args:
        request: FastAPI request object
        scope: Scope to check

    Returns:
        bool: True if user has the scope
    """
    auth_result = get_auth_result(request)
    return scope in auth_result.scopes if auth_result else False
