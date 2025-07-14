"""Input validation and sanitization for security components."""

import os
import re
from typing import Any

from .exceptions import SecurityConfigurationException


class SecurityConfigValidator:
    """Validator for security configuration."""

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

    @staticmethod
    def validate_security_config(config: dict[str, Any]) -> None:
        """Validate the main security configuration.

        Args:
            config: Security configuration dictionary

        Raises:
            SecurityConfigurationException: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise SecurityConfigurationException("Security config must be a dictionary")

        # Validate enabled flag
        enabled = config.get("enabled", False)
        if not isinstance(enabled, bool):
            raise SecurityConfigurationException("Security 'enabled' must be a boolean")

        if not enabled:
            return  # No further validation needed if security is disabled

        # Validate auth: structure
        auth_config = config.get("auth", {})
        if not auth_config:
            raise SecurityConfigurationException("Security configuration must contain 'auth' section")

        if not isinstance(auth_config, dict):
            raise SecurityConfigurationException("Security 'auth' must be a dictionary")

        available_types = list(auth_config.keys())
        if not available_types:
            raise SecurityConfigurationException("Security 'auth' must contain at least one authentication type")

        # Validate each auth type
        valid_auth_types = {"api_key", "bearer", "oauth2", "jwt"}
        for auth_type in available_types:
            if auth_type not in valid_auth_types:
                raise SecurityConfigurationException(f"Invalid auth type '{auth_type}'. Must be one of: {valid_auth_types}")

        # Validate the first (primary) auth type configuration
        primary_auth_type = available_types[0]
        primary_config = auth_config[primary_auth_type]

        if primary_auth_type == "api_key":
            SecurityConfigValidator._validate_api_key_config_new(primary_config)
        elif primary_auth_type == "bearer":
            SecurityConfigValidator._validate_bearer_config(primary_config)
        elif primary_auth_type == "oauth2":
            SecurityConfigValidator._validate_oauth2_config(primary_config)
        elif primary_auth_type == "jwt":
            SecurityConfigValidator._validate_jwt_config(primary_config)

    @staticmethod
    def _validate_api_key_config_new(config: dict[str, Any]) -> None:
        """Validate API key configuration in new auth: structure."""
        # Config should contain the api_key configuration directly
        header_name = config.get("header_name", "X-API-Key")
        if not isinstance(header_name, str) or not header_name.strip():
            raise SecurityConfigurationException("API key header_name must be a non-empty string")

        location = config.get("location", "header")
        if location not in {"header", "query", "cookie"}:
            raise SecurityConfigurationException("API key location must be 'header', 'query', or 'cookie'")

        keys = config.get("keys", [])
        if not isinstance(keys, list) or not keys:
            raise SecurityConfigurationException("API key 'keys' must be a non-empty list")

        for key in keys:
            if isinstance(key, str):
                # Simple string format
                SecurityConfigValidator._validate_api_key_value(key)
            elif isinstance(key, dict):
                # Complex object format with key and scopes
                if "key" not in key:
                    raise SecurityConfigurationException("API key object must contain 'key' field")

                key_value = key["key"]
                if not isinstance(key_value, str):
                    raise SecurityConfigurationException("API key 'key' field must be a string")

                SecurityConfigValidator._validate_api_key_value(key_value)

                # Validate scopes if provided
                scopes = key.get("scopes", [])
                if not isinstance(scopes, list):
                    raise SecurityConfigurationException("API key 'scopes' must be a list")

                for scope in scopes:
                    if not isinstance(scope, str):
                        raise SecurityConfigurationException("All scopes must be strings")
            else:
                raise SecurityConfigurationException("API keys must be strings or objects with 'key' field")

    @staticmethod
    def _validate_api_key_config(config: dict[str, Any]) -> None:
        """Validate API key configuration."""
        api_key_config = config.get("api_key")

        # Simple string format
        if isinstance(api_key_config, str):
            SecurityConfigValidator._validate_api_key_value(api_key_config)
            return

        # Complex object format
        if isinstance(api_key_config, dict):
            header_name = api_key_config.get("header_name", "X-API-Key")
            if not isinstance(header_name, str) or not header_name.strip():
                raise SecurityConfigurationException("API key header_name must be a non-empty string")

            location = api_key_config.get("location", "header")
            if location not in {"header", "query", "cookie"}:
                raise SecurityConfigurationException("API key location must be 'header', 'query', or 'cookie'")

            keys = api_key_config.get("keys", [])
            if not isinstance(keys, list) or not keys:
                raise SecurityConfigurationException("API key 'keys' must be a non-empty list")

            for key in keys:
                if isinstance(key, str):
                    # Simple string format
                    SecurityConfigValidator._validate_api_key_value(key)
                elif isinstance(key, dict):
                    # Complex object format with key and scopes
                    if "key" not in key:
                        raise SecurityConfigurationException("API key object must contain 'key' field")

                    key_value = key["key"]
                    if not isinstance(key_value, str):
                        raise SecurityConfigurationException("API key 'key' field must be a string")

                    SecurityConfigValidator._validate_api_key_value(key_value)

                    # Validate scopes if provided
                    scopes = key.get("scopes", [])
                    if not isinstance(scopes, list):
                        raise SecurityConfigurationException("API key 'scopes' must be a list")

                    for scope in scopes:
                        if not isinstance(scope, str):
                            raise SecurityConfigurationException("All scopes must be strings")
                else:
                    raise SecurityConfigurationException("API keys must be strings or objects with 'key' field")
            return

        # Check for top-level api_key
        global_api_key = config.get("api_key")
        if global_api_key:
            SecurityConfigValidator._validate_api_key_value(global_api_key)
        else:
            raise SecurityConfigurationException("API key configuration is required when using api_key auth type")

    @staticmethod
    def _validate_api_key_value(api_key: str) -> None:
        """Validate a single API key value."""
        if not isinstance(api_key, str):
            raise SecurityConfigurationException("API key must be a string")

        # Skip validation for environment variable placeholders
        if api_key.startswith("${") and api_key.endswith("}"):
            return

        if len(api_key) < 8:
            raise SecurityConfigurationException("API key must be at least 8 characters long")

        if len(api_key) > 128:
            raise SecurityConfigurationException("API key must be no more than 128 characters long")

        # Check for exact match against weak passwords list
        weak_patterns = SecurityConfigValidator._load_weak_patterns()
        api_key_lower = api_key.lower()
        if api_key_lower in weak_patterns:
            raise SecurityConfigurationException(f"API key matches a known weak password: {api_key_lower}")

    @staticmethod
    def _validate_bearer_config(config: dict[str, Any]) -> None:
        """Validate Bearer token configuration."""

        if not isinstance(config, dict):
            raise SecurityConfigurationException("Bearer config must be a dictionary")

        # Check for JWT configuration first
        jwt_secret = config.get("jwt_secret")
        if jwt_secret:
            # JWT mode - validate JWT config
            if not isinstance(jwt_secret, str):
                raise SecurityConfigurationException("JWT secret must be a string")
            return
        # Check for required bearer token (non-JWT mode)
        bearer_token = config.get("bearer_token") or config.get("bearer_token")
        if not bearer_token:
            raise SecurityConfigurationException("Bearer token or JWT secret is required when using bearer auth type")

        # Skip validation for environment variable placeholders
        if isinstance(bearer_token, str) and bearer_token.startswith("${") and bearer_token.endswith("}"):
            return

        if not isinstance(bearer_token, str):
            raise SecurityConfigurationException("Bearer token must be a string")

    @staticmethod
    def _validate_jwt_config(config: dict[str, Any]) -> None:
        """Validate JWT configuration."""
        secret_key = config.get("secret_key")
        if not secret_key:
            raise SecurityConfigurationException("JWT secret_key is required")

        if not isinstance(secret_key, str):
            raise SecurityConfigurationException("JWT secret_key must be a string")

        # Validate algorithm if provided
        algorithm = config.get("algorithm", "HS256")
        if not isinstance(algorithm, str):
            raise SecurityConfigurationException("JWT algorithm must be a string")

        valid_algorithms = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if algorithm not in valid_algorithms:
            raise SecurityConfigurationException(f"Invalid JWT algorithm '{algorithm}'. Must be one of: {valid_algorithms}")

    @staticmethod
    def _validate_oauth2_config(config: dict[str, Any]) -> None:
        """Validate OAuth2 configuration."""
        oauth2_config = config.get("oauth2", {})

        if not isinstance(oauth2_config, dict):
            raise SecurityConfigurationException("OAuth2 config must be a dictionary")

        # Validation strategy: 'jwt', 'introspection', or 'both'
        validation_strategy = oauth2_config.get("validation_strategy", "jwt")
        if validation_strategy not in ["jwt", "introspection", "both"]:
            raise SecurityConfigurationException("OAuth2 validation_strategy must be 'jwt', 'introspection', or 'both'")

        # Validate JWT-specific configuration
        if validation_strategy in ["jwt", "both"]:
            jwt_secret = oauth2_config.get("jwt_secret")
            jwks_url = oauth2_config.get("jwks_url")

            if not (jwt_secret or jwks_url):
                raise SecurityConfigurationException("JWT validation requires either jwt_secret or jwks_url")

            if jwks_url and not isinstance(jwks_url, str):
                raise SecurityConfigurationException("OAuth2 jwks_url must be a string")

            if jwks_url and not jwks_url.startswith(("http://", "https://")):
                raise SecurityConfigurationException("OAuth2 jwks_url must be a valid HTTP/HTTPS URL")

            jwt_algorithm = oauth2_config.get("jwt_algorithm", "RS256")
            valid_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"]
            if jwt_algorithm not in valid_algorithms:
                raise SecurityConfigurationException(f"OAuth2 jwt_algorithm must be one of: {valid_algorithms}")

        # Validate introspection-specific configuration
        if validation_strategy in ["introspection", "both"]:
            introspection_endpoint = oauth2_config.get("introspection_endpoint")
            if not introspection_endpoint:
                raise SecurityConfigurationException("Token introspection requires introspection_endpoint")

            if not isinstance(introspection_endpoint, str):
                raise SecurityConfigurationException("OAuth2 introspection_endpoint must be a string")

            if not introspection_endpoint.startswith(("http://", "https://")):
                raise SecurityConfigurationException("OAuth2 introspection_endpoint must be a valid HTTP/HTTPS URL")

            # Client credentials required for introspection
            required_fields = ["client_id", "client_secret"]
            for field in required_fields:
                value = oauth2_config.get(field)
                if not value:
                    raise SecurityConfigurationException(f"OAuth2 {field} is required for introspection")

                # Skip validation for environment variable placeholders
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    continue

                if not isinstance(value, str) or len(value) < 8:
                    raise SecurityConfigurationException(f"OAuth2 {field} must be a string with at least 8 characters")

        # Validate optional scope configuration
        required_scopes = oauth2_config.get("required_scopes", [])
        if not isinstance(required_scopes, list):
            raise SecurityConfigurationException("OAuth2 required_scopes must be a list")

        for scope in required_scopes:
            if not isinstance(scope, str):
                raise SecurityConfigurationException("All OAuth2 required_scopes must be strings")
            if not InputValidator.validate_scope_format(scope):
                raise SecurityConfigurationException(f"Invalid OAuth2 scope format: {scope}")


class InputValidator:
    """Validator for runtime input validation."""

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
