from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request


class AuthenticationResult:
    """
    Result of an authentication attempt. Allow the result to be used by various components.
    """

    def __init__(
        self,
        success: bool,
        user_id: str | None = None,
        credentials: str | None = None,
        scopes: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.user_id = user_id
        self.credentials = credentials  # Never log this
        self.scopes = scopes or set()
        self.metadata = metadata or {}


class BaseAuthenticator(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.auth_type = self.__class__.__name__.lower().replace("authenticator", "")
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate the authenticator configuration.

        Raises:
            SecurityConfigurationException: If configuration is invalid
        """
        pass

    @abstractmethod
    async def authenticate(self, request: Request) -> AuthenticationResult:
        """Authenticate a request.

        Args:
            request: The FastAPI request object

        Returns:
            AuthenticationResult: Result of authentication attempt

        Raises:
            AuthenticationFailedException: If authentication fails
            InvalidCredentialsException: If credentials are invalid
            MissingCredentialsException: If required credentials are missing
        """
        pass

    @abstractmethod
    def get_auth_type(self) -> str:
        pass

    def supports_scopes(self) -> bool:
        return False

    def get_required_headers(self) -> set[str]:
        return set()

    def get_optional_headers(self) -> set[str]:
        return set()


class SecurityPolicy:
    def __init__(
        self,
        require_authentication: bool = True,
        allowed_auth_types: set[str] | None = None,
        required_scopes: set[str] | None = None,
        allow_anonymous: bool = False,
    ):
        self.require_authentication = require_authentication
        self.allowed_auth_types = allowed_auth_types or set()
        self.required_scopes = required_scopes or set()
        self.allow_anonymous = allow_anonymous

    def is_auth_type_allowed(self, auth_type: str) -> bool:
        if not self.allowed_auth_types:
            return True  # No restrictions
        return auth_type in self.allowed_auth_types

    def has_required_scopes(self, user_scopes: set[str]) -> bool:
        if not self.required_scopes:
            return True  # No scope requirements
        return self.required_scopes.issubset(user_scopes)
