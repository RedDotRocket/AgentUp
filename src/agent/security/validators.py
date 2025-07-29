import os
import re

from agent.config import Config
from agent.config.model import ApiKeyConfig, BearerConfig, JWTConfig, OAuth2Config

from .exceptions import SecurityConfigurationException


class SecurityConfigValidator:
    def __init__(self):
        # This class does not need to maintain state, so no instance variables are needed
        self.security_config = Config.security

    # Cache for weak patterns to avoid reading file multiple times
    _weak_patterns_cache = None

    @classmethod
    def _load_weak_patterns(cls):
        """Load weak patterns from weak.txt file.

        Returns:
            list[str]: list of weak password patterns
        """
        if cls._weak_patterns_cache is not None:
            return cls._weak_patterns_cache

        weak_patterns = []

        try:
            # Get the directory of this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            passwords_file = os.path.join(current_dir, "weak.txt")

            if os.path.exists(passwords_file):
                with open(passwords_file) as f:
                    content = f.read().strip()
                    if content:
                        # Parse comma-separated passwords
                        all_passwords = [p.strip() for p in content.split(",") if p.strip()]
                        # Convert to lowercase for pattern matching
                        weak_patterns = [p.lower() for p in all_passwords]
        except Exception as e:
            # If file cannot be read, raise an exception
            raise SecurityConfigurationException(f"Failed to load weak patterns from weak.txt: {str(e)}") from e

        if not weak_patterns:
            raise SecurityConfigurationException("No weak patterns loaded from weak.txt")

        cls._weak_patterns_cache = weak_patterns
        return cls._weak_patterns_cache

    def validate_security_config(self) -> None:
        """Validate security-specific business rules that Pydantic can't handle.

        This focuses only on security validations like API key strength,
        URL formats, etc. Structure and type validation is handled by Pydantic.

        Raises:
            SecurityConfigurationException: If security rules are violated
        """
        if not self.security_config.enabled:
            return  # No validation needed if security is disabled

        # Business rule: if security is enabled, auth must be configured
        if not self.security_config.auth:
            raise SecurityConfigurationException("Security configuration must contain 'auth' section when enabled")

        # Validate security-specific rules for each auth type
        for auth_type, auth_config in self.security_config.auth.items():
            if auth_type == "api_key" and isinstance(auth_config, ApiKeyConfig):
                self._validate_api_key_security(auth_config)
            elif auth_type == "bearer" and isinstance(auth_config, BearerConfig):
                self._validate_bearer_security(auth_config)
            elif auth_type == "oauth2" and isinstance(auth_config, OAuth2Config):
                self._validate_oauth2_security(auth_config)
            elif auth_type == "jwt" and isinstance(auth_config, JWTConfig):
                self._validate_jwt_security(auth_config)

    def _validate_api_key_security(self, auth_config: ApiKeyConfig) -> None:
        for key_entry in auth_config.keys:
            if isinstance(key_entry, str):
                # Simple string format
                self._validate_api_key_value(key_entry)
            else:
                # ApiKeyEntry object with key and scopes
                self._validate_api_key_value(key_entry.key)

    def _validate_api_key_value(self, api_key: str) -> None:
        # Skip validation for environment variable placeholders
        if api_key.startswith("${") and api_key.endswith("}"):
            return

        # Security requirement: minimum length
        if len(api_key) < 8:
            raise SecurityConfigurationException("API key must be at least 8 characters long")

        # Security requirement: maximum length (prevent DoS)
        if len(api_key) > 128:
            raise SecurityConfigurationException("API key must be no more than 128 characters long")

        # Security requirement: not a weak password
        weak_patterns = self._load_weak_patterns()
        api_key_lower = api_key.lower()
        if api_key_lower in weak_patterns:
            raise SecurityConfigurationException(f"API key matches a known weak password: {api_key_lower}")

    def _validate_bearer_security(self, auth_config: BearerConfig) -> None:
        # Check JWT secret strength if present
        if auth_config.jwt_secret:
            # Skip validation for environment variable placeholders
            if not (auth_config.jwt_secret.startswith("${") and auth_config.jwt_secret.endswith("}")):
                if len(auth_config.jwt_secret) < 32:
                    raise SecurityConfigurationException("JWT secret should be at least 32 characters for security")

        # Check bearer token strength if present
        if auth_config.bearer_token:
            # Skip validation for environment variable placeholders
            if not (auth_config.bearer_token.startswith("${") and auth_config.bearer_token.endswith("}")):
                if len(auth_config.bearer_token) < 16:
                    raise SecurityConfigurationException("Bearer token should be at least 16 characters for security")

    def _validate_jwt_security(self, auth_config: JWTConfig) -> None:
        # Skip validation for environment variable placeholders
        if not (auth_config.secret_key.startswith("${") and auth_config.secret_key.endswith("}")):
            if len(auth_config.secret_key) < 32:
                raise SecurityConfigurationException("JWT secret key should be at least 32 characters for security")

    def _validate_oauth2_security(self, auth_config: OAuth2Config) -> None:
        # Validate URL formats for security (prevent SSRF, etc.)
        if auth_config.jwks_url:
            if not auth_config.jwks_url.startswith(("https://", "http://")):
                raise SecurityConfigurationException("OAuth2 JWKS URL must use HTTP/HTTPS protocol")
            # Security requirement: prefer HTTPS for production
            if auth_config.jwks_url.startswith("http://") and not auth_config.jwks_url.startswith("http://localhost"):
                raise SecurityConfigurationException("OAuth2 JWKS URL should use HTTPS for security")

        if auth_config.introspection_endpoint:
            if not auth_config.introspection_endpoint.startswith(("https://", "http://")):
                raise SecurityConfigurationException("OAuth2 introspection endpoint must use HTTP/HTTPS protocol")
            # Security requirement: prefer HTTPS for production
            if auth_config.introspection_endpoint.startswith(
                "http://"
            ) and not auth_config.introspection_endpoint.startswith("http://localhost"):
                raise SecurityConfigurationException("OAuth2 introspection endpoint should use HTTPS for security")

        # Validate client secret strength
        if auth_config.client_secret:
            # Skip validation for environment variable placeholders
            if not (auth_config.client_secret.startswith("${") and auth_config.client_secret.endswith("}")):
                if len(auth_config.client_secret) < 16:
                    raise SecurityConfigurationException(
                        "OAuth2 client secret should be at least 16 characters for security"
                    )


class InputValidator:
    @staticmethod
    def validate_header_name(header_name: str) -> bool:
        """Validate HTTP header name format.

        Args:
            header_name: The header name to validate

        Returns:
            bool: True if valid
        """
        if not header_name:
            return False

        # RFC 7230 compliant header name
        return bool(re.match(r"^[!#$%&\'*+\-.0-9A-Z^_`a-z|~]+$", header_name))

    @staticmethod
    def validate_scope_format(scope: str) -> bool:
        """Validate OAuth2 scope format.

        Args:
            scope: The scope to validate

        Returns:
            bool: True if valid
        """
        if not scope:
            return False

        # OAuth2 scope format: printable ASCII except space and quote
        return bool(re.match(r"^[!-~]+$", scope)) and " " not in scope and '"' not in scope

    @staticmethod
    def sanitize_scopes(scopes: list[str]) -> set[str]:
        """Sanitize and validate a list of scopes.

        Args:
            scopes: list of scope strings

        Returns:
            set[str]: set of valid, sanitized scopes
        """
        valid_scopes = set()

        for scope in scopes:
            if isinstance(scope, str) and InputValidator.validate_scope_format(scope):
                valid_scopes.add(scope.strip())

        return valid_scopes

    @staticmethod
    def validate_user_id_format(user_id: str) -> bool:
        """Validate user ID format.

        Args:
            user_id: The user ID to validate

        Returns:
            bool: True if valid
        """
        if not user_id:
            return False

        # Allow alphanumeric, hyphens, underscores, and at symbols
        return bool(re.match(r"^[a-zA-Z0-9._@-]+$", user_id)) and len(user_id) <= 256
