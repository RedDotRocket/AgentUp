from fastapi import Request

from agent.security.base import AuthenticationResult, BaseAuthenticator
from agent.security.exceptions import (
    InvalidCredentialsException,
    MissingCredentialsException,
    SecurityConfigurationException,
)
from agent.security.utils import get_request_info, log_security_event, secure_compare, validate_api_key_format
from agent.security.validators import InputValidator


class ApiKeyAuthenticator(BaseAuthenticator):
    """API Key based authentication."""

    def _validate_config(self) -> None:
        """Validate API key authenticator configuration."""
        # Check for API key in various config locations
        api_key_config = self.config.get("api_key")

        # Simple string format
        if isinstance(api_key_config, str):
            if not validate_api_key_format(api_key_config):
                raise SecurityConfigurationException("API key format is invalid")
            self.api_keys = [api_key_config]
            self.header_name = "X-API-Key"
            self.location = "header"
            return

        # Complex object format
        if isinstance(api_key_config, dict):
            self.header_name = api_key_config.get("header_name", "X-API-Key")
            self.location = api_key_config.get("location", "header")
            keys = api_key_config.get("keys", [])

            if not InputValidator.validate_header_name(self.header_name):
                raise SecurityConfigurationException(f"Invalid header name: {self.header_name}")

            if self.location not in {"header", "query", "cookie"}:
                raise SecurityConfigurationException(f"Invalid location: {self.location}")

            if not keys:
                raise SecurityConfigurationException("No API keys configured")

            # Validate each key
            valid_keys = []
            for key in keys:
                if isinstance(key, str):
                    # Skip validation for environment variable placeholders
                    if key.startswith("${") and key.endswith("}"):
                        valid_keys.append(key)
                    elif validate_api_key_format(key):
                        valid_keys.append(key)
                    else:
                        raise SecurityConfigurationException(f"Invalid API key format: {key[:8]}...")

            self.api_keys = valid_keys
            return

        # Check for top-level api_key config
        global_api_key = self.config.get("api_key")
        if isinstance(global_api_key, str):
            if not validate_api_key_format(global_api_key):
                raise SecurityConfigurationException("Global API key format is invalid")
            self.api_keys = [global_api_key]
            self.header_name = "X-API-Key"
            self.location = "header"
            return

        raise SecurityConfigurationException("No valid API key configuration found")

    async def authenticate(self, request: Request) -> AuthenticationResult:
        """Authenticate request using API key.

        Args:
            request: FastAPI request object

        Returns:
            AuthenticationResult: Authentication result

        Raises:
            MissingCredentialsException: If API key is missing
            InvalidCredentialsException: If API key is invalid
        """
        request_info = get_request_info(request)

        # Extract API key based on location
        api_key = None
        if self.location == "header":
            api_key = request.headers.get(self.header_name)
        elif self.location == "query":
            api_key = request.query_params.get(self.header_name)
        elif self.location == "cookie":
            api_key = request.cookies.get(self.header_name)

        if not api_key:
            log_security_event("authentication", request_info, False, f"Missing API key in {self.location}")
            raise MissingCredentialsException("Unauthorized")

        # Validate format
        if not validate_api_key_format(api_key):
            log_security_event("authentication", request_info, False, "Invalid API key format")
            raise InvalidCredentialsException("Unauthorized")

        # Check against configured keys using secure comparison
        for configured_key in self.api_keys:
            # Handle environment variable placeholders
            if configured_key.startswith("${") and configured_key.endswith("}"):
                # Extract default value if provided
                if ":" in configured_key:
                    default_value = configured_key.split(":", 1)[1][:-1]  # Remove closing }
                    if secure_compare(api_key, default_value):
                        log_security_event("authentication", request_info, True, "API key authenticated")
                        return AuthenticationResult(
                            success=True, user_id=f"api_key_user_{hash(api_key) % 10000}", credentials=api_key
                        )
                continue

            if secure_compare(api_key, configured_key):
                log_security_event("authentication", request_info, True, "API key authenticated")
                return AuthenticationResult(
                    success=True, user_id=f"api_key_user_{hash(api_key) % 10000}", credentials=api_key
                )

        log_security_event("authentication", request_info, False, "API key does not match any configured keys")
        raise InvalidCredentialsException("Unauthorized")

    def get_auth_type(self) -> str:
        """Get authentication type identifier."""
        return "api_key"

    def get_required_headers(self) -> set[str]:
        """Get required headers for API key authentication."""
        if self.location == "header":
            return {self.header_name}
        return set()

    def supports_scopes(self) -> bool:
        """API key auth doesn't support scopes by default."""
        return False
