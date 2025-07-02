import logging
from typing import Any

from fastapi import HTTPException, Request

from .authenticators import get_authenticator_class, list_authenticator_types  # noqa: F401
from .base import AuthenticationResult, BaseAuthenticator, SecurityPolicy
from .exceptions import (
    AuthenticationFailedException,
    AuthenticatorNotFound,  # noqa: F401
    AuthorizationFailedException,
    InvalidAuthenticationTypeException,  # noqa: F401
    SecurityConfigurationException,
)
from .utils import get_request_info, log_security_event
from .validators import SecurityConfigValidator

logger = logging.getLogger(__name__)


class SecurityManager:
    """Main security manager that orchestrates authentication and authorization.

    This class replaces the previous A2ASecurityHandler with a more robust,
    modular design that supports multiple authentication types and security policies.
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize security manager with configuration.

        Args:
            config: Complete agent configuration dictionary
        """
        self.config = config
        self.security_config = config.get("security", {})
        self.auth_enabled = self.security_config.get("enabled", False)

        # Validate configuration
        SecurityConfigValidator.validate_security_config(self.security_config)

        # Initialize authenticators
        self.authenticators: dict[str, BaseAuthenticator] = {}
        self._initialize_authenticators()

        # set primary authentication type
        self.primary_auth_type = self._determine_primary_auth_type()

        logger.info(
            f"Security manager initialized - enabled: {self.auth_enabled}, primary auth: {self.primary_auth_type}"
        )

    def _determine_primary_auth_type(self) -> str:
        """Determine the primary authentication type from configuration."""
        # Check for strategies (new format)
        strategies = self.security_config.get("strategies", [])
        if strategies:
            enabled_strategy = next((s for s in strategies if s.get("enabled", True)), None)
            if enabled_strategy:
                return enabled_strategy.get("type", "api_key")

        # Fall back to simple type (legacy format)
        return self.security_config.get("type", "api_key")

    def _initialize_authenticators(self) -> None:
        """Initialize available authenticators based on configuration."""
        if not self.auth_enabled:
            return

        # Get all configured authentication types
        auth_types = set()

        # Check strategies (new format)
        strategies = self.security_config.get("strategies", [])
        for strategy in strategies:
            if strategy.get("enabled", True):
                auth_types.add(strategy.get("type", "api_key"))

        # Add primary type (legacy format)
        auth_types.add(self.security_config.get("type", "api_key"))

        # Initialize authenticators for each type
        for auth_type in auth_types:
            try:
                authenticator_class = get_authenticator_class(auth_type)
                authenticator = authenticator_class(self.security_config)
                self.authenticators[auth_type] = authenticator
                logger.debug(f"Initialized {auth_type} authenticator")
            except Exception as e:
                logger.error(f"Failed to initialize {auth_type} authenticator: {e}")
                raise SecurityConfigurationException(f"Failed to initialize {auth_type} authenticator: {e}") from e

    async def authenticate_request(
        self, request: Request, auth_type: str | None = None, policy: SecurityPolicy | None = None
    ) -> AuthenticationResult | None:
        """Authenticate a request using the specified or configured authentication type.

        Args:
            request: FastAPI request object
            auth_type: Specific auth type to use (overrides configured type)
            policy: Security policy to apply (defaults to require auth)

        Returns:
            Optional[AuthenticationResult]: Authentication result, or None if auth disabled

        Raises:
            HTTPException: For authentication/authorization failures
        """
        request_info = get_request_info(request)

        # Apply default policy if none provided
        if policy is None:
            policy = SecurityPolicy(require_authentication=True)

        # Check if authentication is disabled
        if not self.auth_enabled:
            if policy.require_authentication:
                log_security_event(
                    "authentication", request_info, False, "Authentication required but security is disabled"
                )
                raise HTTPException(status_code=500, detail="Authentication required but security is not configured")
            return None

        # Allow anonymous access if policy permits
        if policy.allow_anonymous:
            try:
                # Try to authenticate, but don't fail if it doesn't work
                return await self._perform_authentication(request, auth_type, policy)
            except (AuthenticationFailedException, HTTPException):
                return None  # Anonymous access allowed

        # Perform required authentication
        return await self._perform_authentication(request, auth_type, policy)

    async def _perform_authentication(
        self, request: Request, auth_type: str | None, policy: SecurityPolicy
    ) -> AuthenticationResult:
        """Perform the actual authentication process.

        Args:
            request: FastAPI request object
            auth_type: Specific auth type to use
            policy: Security policy to apply

        Returns:
            AuthenticationResult: Authentication result

        Raises:
            HTTPException: For authentication/authorization failures
        """
        request_info = get_request_info(request)

        # Determine which authenticator to use
        target_auth_type = auth_type or self.primary_auth_type

        # Check if auth type is allowed by policy
        if not policy.is_auth_type_allowed(target_auth_type):
            log_security_event(
                "authorization", request_info, False, f"Auth type {target_auth_type} not allowed by policy"
            )
            raise HTTPException(status_code=403, detail=f"Authentication type '{target_auth_type}' not allowed")

        # Get authenticator
        authenticator = self.authenticators.get(target_auth_type)
        if not authenticator:
            available_types = list(self.authenticators.keys())
            log_security_event(
                "configuration",
                request_info,
                False,
                f"Authenticator {target_auth_type} not found. Available: {available_types}",
            )
            raise HTTPException(status_code=500, detail=f"Authenticator '{target_auth_type}' not available")

        # Perform authentication
        try:
            result = await authenticator.authenticate(request)

            # Check scope-based authorization if required
            if policy.required_scopes and not policy.has_required_scopes(result.scopes):
                log_security_event(
                    "authorization",
                    request_info,
                    False,
                    f"Insufficient scopes. Required: {policy.required_scopes}, User has: {result.scopes}",
                )
                raise HTTPException(status_code=403, detail="Insufficient permissions")

            return result

        except AuthenticationFailedException as e:
            # Convert to HTTP exception
            raise HTTPException(status_code=401, detail=str(e)) from e
        except AuthorizationFailedException as e:
            # Convert to HTTP exception
            raise HTTPException(status_code=403, detail=str(e)) from e

    def get_available_auth_types(self) -> set[str]:
        """Get set of available authentication types.

        Returns:
            set[str]: Available authentication types
        """
        return set(self.authenticators.keys())

    def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled.

        Returns:
            bool: True if authentication is enabled
        """
        return self.auth_enabled

    def get_primary_auth_type(self) -> str:
        """Get the primary authentication type.

        Returns:
            str: Primary authentication type
        """
        return self.primary_auth_type

    def get_required_headers(self, auth_type: str | None = None) -> set[str]:
        """Get required headers for authentication.

        Args:
            auth_type: Specific auth type (defaults to primary)

        Returns:
            set[str]: Required headers
        """
        target_auth_type = auth_type or self.primary_auth_type
        authenticator = self.authenticators.get(target_auth_type)
        if authenticator:
            return authenticator.get_required_headers()
        return set()

    def validate_configuration(self) -> bool:
        """Validate the security configuration.

        Returns:
            bool: True if configuration is valid

        Raises:
            SecurityConfigurationException: If configuration is invalid
        """
        try:
            SecurityConfigValidator.validate_security_config(self.security_config)
            return True
        except SecurityConfigurationException:
            raise
