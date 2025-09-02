"""
FastAPI dependency providers for AgentUp.

This module provides dependency injection functions for FastAPI routes,
enabling proper separation of concerns and testability.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from .config.settings import Settings, get_settings
from .security import AuthContext, AuthenticationResult, get_auth_result


@lru_cache
def get_config_dependency() -> Settings:
    """
    FastAPI dependency provider for configuration.

    Returns the cached global settings instance with full Pydantic validation.
    This replaces the need for ConfigurationManager or direct Config access.

    Usage in FastAPI routes:
        @router.get("/example")
        async def example(config: Settings = Depends(get_config_dependency)):
            return {"agent_name": config.project_name}

    Returns:
        Settings: The global configuration instance
    """
    return get_settings()


def get_auth_context_dependency(request: Request) -> AuthenticationResult | None:
    """
    FastAPI dependency provider for authentication context.

    Extracts the authentication result from the request state, which is
    set by the @protected decorator during request processing.

    Args:
        request: The FastAPI request object

    Returns:
        AuthResult | None: The authentication result if available
    """
    try:
        return get_auth_result(request)
    except Exception:
        return None


# Type aliases for cleaner dependency injection
ConfigDep = Annotated[Settings, Depends(get_config_dependency)]
AuthDep = Annotated[AuthenticationResult | None, Depends(get_auth_context_dependency)]


def create_auth_context(auth_result: AuthenticationResult | None) -> AuthContext | None:
    """
    Helper function to create AuthContext from AuthResult.

    Args:
        auth_result: The authentication result

    Returns:
        AuthContext | None: The auth context if auth_result is available
    """
    if auth_result is None:
        return None
    return AuthContext(auth_result)


# Utility functions for backward compatibility
def get_config() -> Settings:
    """
    Direct configuration access (for migration from ConfigurationManager).

    This provides a direct way to get configuration without FastAPI dependency
    injection, useful during migration from ConfigurationManager usage.

    Returns:
        Settings: The global configuration instance
    """
    return get_config_dependency()
