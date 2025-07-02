from .api_key import ApiKeyAuthenticator
from .base import BaseAuthenticator
from .bearer import BearerTokenAuthenticator
from .oauth2 import OAuth2Authenticator

# Registry of available authenticators
AUTHENTICATOR_REGISTRY: dict[str, type[BaseAuthenticator]] = {
    "api_key": ApiKeyAuthenticator,
    "bearer": BearerTokenAuthenticator,
    "oauth2": OAuth2Authenticator,
}


def get_authenticator_class(auth_type: str) -> type[BaseAuthenticator]:
    """Get authenticator class by type name.

    Args:
        auth_type: The authentication type

    Returns:
        Type[BaseAuthenticator]: The authenticator class

    Raises:
        KeyError: If authenticator type is not found
    """
    if auth_type not in AUTHENTICATOR_REGISTRY:
        available = ", ".join(AUTHENTICATOR_REGISTRY.keys())
        raise KeyError(f"Unknown authenticator type '{auth_type}'. Available: {available}")

    return AUTHENTICATOR_REGISTRY[auth_type]


def list_authenticator_types() -> list[str]:
    """Get list of available authenticator types.

    Returns:
        list[str]: list of available authenticator type names
    """
    return list(AUTHENTICATOR_REGISTRY.keys())


__all__ = [
    "AUTHENTICATOR_REGISTRY",
    "get_authenticator_class",
    "list_authenticator_types",
    "BaseAuthenticator",
    "ApiKeyAuthenticator",
    "BearerTokenAuthenticator",
    "OAuth2Authenticator",
]
