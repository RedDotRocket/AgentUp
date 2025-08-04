"""AgentUp Security Module - authentication and authorization system.

This module provides a comprehensive security framework for AgentUp agents,
supporting multiple authentication types, secure credential handling, and
flexible authorization policies.

Key Features:
- Multiple authentication types (API Key, Bearer Token, OAuth2)
- Secure credential comparison using constant-time algorithms
- Comprehensive input validation and sanitization
- Audit logging for security events
- architecture for custom authenticators
- Thread-safe operations
- Configuration-driven security policies

Security Best Practices:
- Never log credentials or sensitive data
- Use constant-time comparisons for all credential checks
- Validate all inputs rigorously
- Default to secure behavior (authentication required)
- Comprehensive error handling without information leakage
"""

from typing import Any

from .base import AuthenticationResult, SecurityPolicy
from .context import (
    AuthContext,
    CapabilityContext,
    create_capability_context,
    get_current_auth,
    get_current_scopes,
    is_authenticated,
    log_auth_event,
)
from .context import (
    get_current_user_id as get_context_user_id,
)
from .context import (
    has_scope as context_has_scope,
)
from .context import (
    requires_scopes as context_requires_scopes,
)
from .decorators import (
    always_protected,
    api_key_required,
    authenticated,  # Legacy alias
    bearer_token_required,
    get_auth_result,
    get_current_user_id,
    has_scope,
    protected,
    require_scopes,
)
from .exceptions import (
    AuthenticationFailedException,
    AuthenticatorNotFound,
    AuthorizationFailedException,
    InvalidAuthenticationTypeException,
    InvalidCredentialsException,
    MissingCredentialsException,
    SecurityConfigurationException,
    SecurityException,
)
from .manager import SecurityManager

# Global security manager instance (initialized during app startup)
_security_manager: SecurityManager = None


def create_security_manager(config: dict[str, Any] = None) -> SecurityManager:
    """Create and configure a SecurityManager instance.

    This function should be called during application startup to initialize
    the security system with the agent configuration.

    Args:
        config: Complete agent configuration dictionary

    Returns:
        SecurityManager: Configured security manager instance

    Raises:
        SecurityConfigurationException: If security configuration is invalid

    Example:
        # In main.py or application startup
        from .config import Config
        from .security import create_security_manager, set_global_security_manager

        config = Config.model_dump()
        security_manager = create_security_manager(config)
        set_global_security_manager(security_manager)
    """
    return SecurityManager()


def set_global_security_manager(security_manager: SecurityManager) -> None:
    """Set the global security manager instance.

    Args:
        security_manager: The security manager to set as global

    Note: This is used internally by the framework. Applications should use
    create_security_manager() during startup.
    """
    global _security_manager
    _security_manager = security_manager


def get_global_security_manager() -> SecurityManager:
    """Get the global security manager instance.

    Returns:
        SecurityManager: The global security manager

    Raises:
        RuntimeError: If security manager has not been initialized
    """
    if _security_manager is None:
        raise RuntimeError(
            "Security manager not initialized. Call create_security_manager() during application startup."
        )
    return _security_manager


def is_security_enabled() -> bool:
    """Check if security is enabled globally.

    Returns:
        bool: True if security is enabled and configured
    """
    try:
        manager = get_global_security_manager()
        return manager.is_auth_enabled()
    except RuntimeError:
        return False


# Convenience functions for common security operations
def validate_security_config() -> bool:
    """Validate security configuration without creating a manager.

    Args:
        config: Agent configuration dictionary

    Returns:
        bool: True if configuration is valid

    Raises:
        SecurityConfigurationException: If configuration is invalid
    """
    from .validators import SecurityConfigValidator

    SecurityConfigValidator().validate_security_config()

    return True


# Export all public components
__all__ = [
    # Core classes
    "SecurityManager",
    "AuthenticationResult",
    "SecurityPolicy",
    "CapabilityContext",
    # Decorators
    "protected",
    "require_scopes",
    "api_key_required",
    "bearer_token_required",
    "always_protected",
    "authenticated",  # Legacy
    # Utility functions
    "get_auth_result",
    "get_current_user_id",
    "has_scope",
    # Context functions
    "AuthContext",
    "create_capability_context",
    "get_current_auth",
    "get_current_scopes",
    "get_context_user_id",
    "context_has_scope",
    "is_authenticated",
    "context_requires_scopes",
    "log_auth_event",
    # Manager functions
    "create_security_manager",
    "set_global_security_manager",
    "get_global_security_manager",
    "is_security_enabled",
    "validate_security_config",
    # Exceptions
    "SecurityException",
    "AuthenticationFailedException",
    "AuthorizationFailedException",
    "InvalidCredentialsException",
    "MissingCredentialsException",
    "InvalidAuthenticationTypeException",
    "SecurityConfigurationException",
    "AuthenticatorNotFound",
]


# Version info
__version__ = "0.5.1"
__author__ = "AgentUp Team"
__description__ = "security module for AgentUp agents"
