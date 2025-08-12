import contextvars
from typing import Any

import structlog

from .base import AuthenticationResult

logger = structlog.get_logger(__name__)

# Context variable to store authentication information per request
_auth_context: contextvars.ContextVar[AuthenticationResult | None] = contextvars.ContextVar(
    "auth_context", default=None
)


class AuthContext:
    def __init__(self, auth_result: AuthenticationResult | None):
        self.auth_result = auth_result
        self.token = None

    def __enter__(self):
        self.token = _auth_context.set(self.auth_result)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _auth_context.reset(self.token)


def get_current_auth() -> AuthenticationResult | None:
    """
    Get the current authentication information for the request.

    Returns:
        AuthenticationResult or None: Authentication result if available
    """
    return _auth_context.get()


def get_current_user_id() -> str | None:
    """
    Get the current user ID from authentication context.

    Returns:
        str or None: User ID if authenticated, None otherwise
    """
    auth_result = get_current_auth()
    return auth_result.user_id if auth_result else None


def get_current_scopes() -> set[str]:
    """
    Get the current user's scopes from authentication context.

    Returns:
        set[str]: Set of scopes, empty if not authenticated
    """
    auth_result = get_current_auth()
    logger.debug(f"User scopes: {list(auth_result.scopes)}" if auth_result else "No user authenticated")
    return auth_result.scopes or set() if auth_result else set()


def has_scope(scope: str) -> bool:
    """
    Check if the current user has a specific scope.

    Args:
        scope: Scope to check for

    Returns:
        bool: True if user has the scope, False otherwise
    """
    return scope in get_current_scopes()


def requires_scopes(required_scopes: set[str]) -> bool:
    """
    Check if the current user has all required scopes.

    Args:
        required_scopes: Set of required scopes

    Returns:
        bool: True if user has all required scopes, False otherwise
    """
    user_scopes = get_current_scopes()
    return required_scopes.issubset(user_scopes)


def is_authenticated() -> bool:
    """
    Check if there is an authenticated user in the current context.

    Returns:
        bool: True if user is authenticated, False otherwise
    """
    return get_current_auth() is not None


class CapabilityContext:
    """
    Enhanced context object for capability handlers.

    This class provides capability handlers with access to authentication information,
    task data, and other contextual information needed for processing.
    """

    def __init__(self, task: Any, auth_result: AuthenticationResult | None = None):
        """
        Initialize capability context.

        Args:
            task: The A2A task being processed
            auth_result: Authentication result for the request
        """
        self.task = task
        self.auth_result = auth_result or get_current_auth()

    @property
    def user_id(self) -> str | None:
        return self.auth_result.user_id if self.auth_result else None

    @property
    def user_scopes(self) -> set[str]:
        return self.auth_result.scopes or set() if self.auth_result else set()

    @property
    def auth_metadata(self) -> dict[str, Any]:
        return self.auth_result.metadata or {} if self.auth_result else {}

    @property
    def is_authenticated(self) -> bool:
        return self.auth_result is not None

    def has_scope(self, scope: str) -> bool:
        try:
            # Try to use the unified auth manager's scope hierarchy
            from agent.security.unified_auth import get_unified_auth_manager

            auth_manager = get_unified_auth_manager()
            if auth_manager:
                logger.info(f"Checking if user has scope '{scope}'")
                logger.debug(f"User scopes: {list(self.user_scopes)}")
                return auth_manager.validate_scope_access(list(self.user_scopes), scope)
            else:
                # Fallback to simple scope checking if no auth manager available
                return scope in self.user_scopes
        except ImportError:
            # Fallback if unified auth not available
            return scope in self.user_scopes

    def requires_scopes(self, required_scopes: set[str]) -> bool:
        try:
            # Try to use the unified auth manager's scope hierarchy
            from agent.security.unified_auth import get_unified_auth_manager

            auth_manager = get_unified_auth_manager()
            if auth_manager:
                return all(
                    auth_manager.validate_scope_access(list(self.user_scopes), scope) for scope in required_scopes
                )
            else:
                # Fallback to simple scope checking if no auth manager available
                return required_scopes.issubset(self.user_scopes)
        except ImportError:
            # Fallback if unified auth not available
            return required_scopes.issubset(self.user_scopes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": getattr(self.task, "id", None),
            "user_id": self.user_id,
            "scopes": list(self.user_scopes),
            "is_authenticated": self.is_authenticated,
        }


def create_capability_context(task: Any, auth_result: AuthenticationResult | None = None) -> CapabilityContext:
    """
    Create a CapabilityContext for a task.

    Args:
        task: The A2A task being processed
        auth_result: Optional authentication result (will use current context if not provided)

    Returns:
        CapabilityContext: Context object for the capability handler
    """
    return CapabilityContext(task, auth_result)


# Logging utilities for security events
def log_auth_event(event_type: str, capability_id: str, success: bool, details: str = ""):
    """
    Log authentication-related events for capabilities.

    Args:
        event_type: Type of event (e.g., "authorization", "scope_check")
        capability_id: ID of the capability being accessed
        success: Whether the event was successful
        details: Additional details about the event
    """
    auth_result = get_current_auth()
    user_id = auth_result.user_id if auth_result else "anonymous"
    scopes = list(auth_result.scopes) if auth_result and auth_result.scopes else []

    log_data = {
        "event_type": event_type,
        "capability_id": capability_id,
        "user_id": user_id,
        "scopes": scopes,
        "success": success,
        "details": details,
    }

    if success:
        logger.info(f"Auth event: {event_type} for capability '{capability_id}' - {log_data}")
    else:
        logger.warning(f"Auth failure: {event_type} for capability '{capability_id}' - {log_data}")


def log_capability_access(
    capability_id: str,
    user_id: str,
    user_scopes: set[str],
    required_scopes: list[str],
    success: bool,
    execution_time_ms: int = None,
):
    """
    Comprehensive audit logging for capability access.

    This implements the audit trail requirement for all capability access,
    including scope checks and execution time. It logs both successful and failed
    capability accesses, providing a complete audit trail for security monitoring.

    Args:
        capability_id: ID of the capability being accessed
        user_id: ID of the user making the request
        user_scopes: Set of scopes the user possesses
        required_scopes: List of scopes required for the capability
        success: Whether the access was successful
        execution_time_ms: Optional execution time in milliseconds
    """
    import time

    audit_data = {
        "timestamp": time.time(),
        "capability_id": capability_id,
        "user_id": user_id,
        "user_scopes": sorted(list(user_scopes)),
        "required_scopes": required_scopes,
        "access_granted": success,
        "scope_check_passed": all(scope in user_scopes for scope in required_scopes),
        "execution_time_ms": execution_time_ms,
    }

    if success:
        logger.info(f"AUDIT: Capability access granted - {audit_data}")
    else:
        logger.warning(f"AUDIT: Capability access denied - {audit_data}")
