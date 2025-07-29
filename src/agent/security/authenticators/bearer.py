import hashlib
import os
from typing import Any

from fastapi import Request

from agent.security.base import AuthenticationResult, BaseAuthenticator
from agent.security.exceptions import (
    InvalidCredentialsException,
    MissingCredentialsException,
    SecurityConfigurationException,
)
from agent.security.utils import (
    extract_bearer_token,
    get_request_info,
    log_security_event,
    secure_compare,
    validate_bearer_token_format,
)

# Optional JWT support
try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


class BearerTokenAuthenticator(BaseAuthenticator):
    def _resolve_env_var(self, value: str | None) -> str | None:
        if not value or not isinstance(value, str):
            return value

        if value.startswith("${") and value.endswith("}"):
            # Extract environment variable name and default value
            env_expr = value[2:-1]  # Remove ${ and }
            if ":" in env_expr:
                env_var, default_value = env_expr.split(":", 1)
                return os.getenv(env_var, default_value)
            else:
                return os.getenv(env_expr)

        return value

    def _validate_config(self) -> None:
        # Get bearer configuration from auth structure
        bearer_config = self.config.get("auth", {}).get("bearer", {})
        bearer_token = bearer_config.get("bearer_token")

        # JWT-specific configuration
        jwt_secret_raw = bearer_config.get("jwt_secret")
        self.jwt_algorithm = bearer_config.get("algorithm", "HS256")
        jwt_issuer_raw = bearer_config.get("issuer")
        jwt_audience_raw = bearer_config.get("audience")

        # Resolve JWT secret environment variable
        self.jwt_secret = self._resolve_env_var(jwt_secret_raw)
        self.jwt_issuer = self._resolve_env_var(jwt_issuer_raw)
        self.jwt_audience = self._resolve_env_var(jwt_audience_raw)

        # If JWT configuration is present, we're in JWT mode
        if self.jwt_secret:
            # JWT mode - no need for bearer_token
            self.bearer_token = None
            return

        # Otherwise, require a simple bearer token
        if not bearer_token:
            raise SecurityConfigurationException(
                "Bearer token is required for bearer authentication when not using JWT"
            )

        # Handle environment variable placeholders
        if isinstance(bearer_token, str) and bearer_token.startswith("${") and bearer_token.endswith("}"):
            self.bearer_token = bearer_token
            return

        if not isinstance(bearer_token, str):
            raise SecurityConfigurationException("Bearer token must be a string")

        if not validate_bearer_token_format(bearer_token):
            raise SecurityConfigurationException("Invalid bearer token format")

        self.bearer_token = bearer_token

    async def authenticate(self, request: Request) -> AuthenticationResult:
        """Authenticate request using Bearer token.

        Args:
            request: FastAPI request object

        Returns:
            AuthenticationResult: Authentication result

        Raises:
            MissingCredentialsException: If Bearer token is missing
            InvalidCredentialsException: If Bearer token is invalid
        """
        request_info = get_request_info(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            log_security_event("authentication", request_info, False, "Missing Authorization header")
            raise MissingCredentialsException("Unauthorized")

        # Extract Bearer token
        token = extract_bearer_token(auth_header)
        if not token:
            log_security_event("authentication", request_info, False, "Invalid Authorization header format")
            raise InvalidCredentialsException("Unauthorized")

        # Validate token format
        if not validate_bearer_token_format(token):
            log_security_event("authentication", request_info, False, "Invalid bearer token format")
            raise InvalidCredentialsException("Unauthorized")

        # If JWT secret is configured and JWT is available, validate as JWT
        if self.jwt_secret and JWT_AVAILABLE:
            return self._validate_jwt_token(token, request_info)

        # If we're in JWT-only mode but JWT is not available, error
        if self.jwt_secret and not JWT_AVAILABLE:
            log_security_event("authentication", request_info, False, "JWT mode configured but PyJWT not available")
            raise InvalidCredentialsException("JWT validation not available")

        # Otherwise, validate as simple bearer token
        return self._validate_bearer_token(token, request_info)

    def get_auth_type(self) -> str:
        return "bearer"

    def get_required_headers(self) -> set[str]:
        return {"Authorization"}

    def supports_scopes(self) -> bool:
        return True  # Could be extended to parse JWT scopes

    def _validate_bearer_token(self, token: str, request_info: dict[str, Any]) -> AuthenticationResult:
        """Validate simple bearer token against configured token.

        Args:
            token: The bearer token to validate
            request_info: Request information for logging

        Returns:
            AuthenticationResult: Authentication result
        """
        # If we're in JWT-only mode, this method shouldn't be called
        if self.bearer_token is None:
            log_security_event("authentication", request_info, False, "Bearer token validation called in JWT-only mode")
            raise InvalidCredentialsException("Unauthorized")

        configured_token = self.bearer_token

        # Handle environment variable placeholders
        if configured_token.startswith("${") and configured_token.endswith("}"):
            # Extract environment variable name and default value
            env_expr = configured_token[2:-1]  # Remove ${ and }
            if ":" in env_expr:
                env_var, default_value = env_expr.split(":", 1)
                configured_token = os.getenv(env_var, default_value)
            else:
                configured_token = os.getenv(env_expr)
                if not configured_token:
                    log_security_event(
                        "authentication", request_info, False, f"Bearer token environment variable {env_expr} not set"
                    )
                    raise InvalidCredentialsException("Unauthorized")

        if secure_compare(token, configured_token):
            log_security_event("authentication", request_info, True, "Bearer token authenticated")
            return AuthenticationResult(
                success=True,
                user_id=f"bearer_user_{hashlib.sha256(token.encode()).hexdigest()[:16]}",
                credentials=token,
            )

        log_security_event("authentication", request_info, False, "Bearer token does not match configured token")
        raise InvalidCredentialsException("Unauthorized")

    def _validate_jwt_token(self, token: str, request_info: dict[str, Any]) -> AuthenticationResult:
        """Validate JWT token with proper security checks.

        Args:
            token: The JWT token to validate
            request_info: Request information for logging

        Returns:
            AuthenticationResult: Authentication result with user info and scopes
        """
        if not JWT_AVAILABLE:
            log_security_event(
                "authentication", request_info, False, "JWT validation requested but PyJWT not available"
            )
            raise SecurityConfigurationException("JWT validation requires PyJWT library")

        try:
            # JWT secret should already be resolved in _validate_config
            jwt_secret = self.jwt_secret
            if not jwt_secret:
                log_security_event("authentication", request_info, False, "JWT secret not configured")
                raise InvalidCredentialsException("Unauthorized")

            # Decode and validate JWT
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=[self.jwt_algorithm],
                issuer=self.jwt_issuer,
                audience=self.jwt_audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": self.jwt_audience is not None,
                    "verify_iss": self.jwt_issuer is not None,
                    "require_exp": True,
                    "require_iat": True,
                },
            )

            # Extract user information from payload
            user_id = payload.get("sub") or payload.get("user_id") or "jwt_user"

            # Support both "scope" (string) and "scopes" (array) formats
            scopes = []
            if payload.get("scopes"):
                # Handle array format: "scopes": ["admin", "read"]
                scopes_value = payload.get("scopes")
                if isinstance(scopes_value, list):
                    scopes = scopes_value
                else:
                    scopes = [str(scopes_value)]
            elif payload.get("scope"):
                # Handle string format: "scope": "admin read write"
                scopes = payload.get("scope", "").split()
            else:
                scopes = []

            log_security_event("authentication", request_info, True, f"JWT token authenticated for user: {user_id}")

            return AuthenticationResult(
                success=True, user_id=user_id, credentials=token, scopes=set(scopes), metadata=payload
            )

        except jwt.ExpiredSignatureError as e:
            log_security_event("authentication", request_info, False, "JWT token has expired")
            raise InvalidCredentialsException("Token expired") from e

        except jwt.InvalidTokenError as e:
            log_security_event("authentication", request_info, False, f"Invalid JWT token: {str(e)}")
            raise InvalidCredentialsException("Invalid token") from e

        except Exception as e:
            log_security_event("authentication", request_info, False, f"JWT validation error: {str(e)}")
            raise InvalidCredentialsException("Authentication failed") from e
