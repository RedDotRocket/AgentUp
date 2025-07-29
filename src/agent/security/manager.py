import structlog
from fastapi import HTTPException, Request

from .authenticators import get_authenticator_class, list_authenticator_types  # noqa: F401
from .base import AuthenticationResult, BaseAuthenticator, SecurityPolicy
from .exceptions import (
    AuthenticationFailedException,
    AuthorizationFailedException,
    SecurityConfigurationException,
)
from .utils import get_request_info, log_security_event
from .validators import SecurityConfigValidator

logger = structlog.get_logger(__name__)


class SecurityManager:
    """
    Main security manager that manages authentication and authorization.
    """

    def __init__(self):
        from agent.config import Config

        # Store config references
        self.config = Config.model_dump()
        self.security_config = self.config.get("security", {})
        self.auth_enabled = self.security_config.get("enabled", False)

        # Validate configuration
        SecurityConfigValidator().validate_security_config()

        # Determine primary authentication type first!
        self.primary_auth_type = self._determine_primary_auth_type()

        # Initialize authenticators
        self.authenticators: dict[str, BaseAuthenticator] = {}
        self._initialize_authenticators()

        # Initialize unified authentication manager for scope hierarchy
        self._initialize_unified_auth_manager()

        logger.info(
            f"Security manager initialized - enabled: {self.auth_enabled}, primary auth: {self.primary_auth_type}"
        )

    def _determine_primary_auth_type(self) -> str:
        # Get auth type from auth: structure
        auth_config = self.security_config.get("auth", {})
        if not auth_config:
            raise SecurityConfigurationException(
                "No auth configuration found. Expected 'auth' section with authentication type."
            )

        available_types = list(auth_config.keys())
        if not available_types:
            raise SecurityConfigurationException("No authentication types configured in 'auth' section.")

        if len(available_types) > 1:
            logger.warning(
                f"Multiple auth types configured: {available_types}. Using {available_types[0]}, ignoring others."
            )

        return available_types[0]

    def _initialize_authenticators(self) -> None:
        if not self.auth_enabled:
            return

        # Get the primary auth type from auth: structure
        auth_types = {self.primary_auth_type}

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

    def _initialize_unified_auth_manager(self) -> None:
        try:
            from .unified_auth import create_unified_auth_manager

            # Debug: Check what's in the security config
            logger.debug(f"Security config keys: {list(self.security_config.keys())}")
            logger.debug(f"Security config scope_hierarchy: {self.security_config.get('scope_hierarchy', {})}")

            # Create unified auth manager with security config
            unified_auth_manager = create_unified_auth_manager(self.security_config)
            logger.debug(
                f"Unified authentication manager initialized with {len(unified_auth_manager.scope_hierarchy.hierarchy)} scope hierarchy rules"
            )
        except Exception as e:
            # TODO: Maybe raise a specific exception here?
            logger.warning(f"Failed to initialize unified authentication manager: {e}")

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
                # Try to authenticate, but don't fail if it doesn't work (as we need to return a code
                # or auth maybe disabled)
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
