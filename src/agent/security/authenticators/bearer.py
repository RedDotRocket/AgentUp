import os
from typing import Any

from fastapi import Request

from ..base import AuthenticationResult, BaseAuthenticator
from ..exceptions import InvalidCredentialsException, MissingCredentialsException, SecurityConfigurationException
from ..utils import (
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
    """Bearer Token based authentication."""

    def _validate_config(self) -> None:
        """Validate Bearer token authenticator configuration."""
        # Check for bearer token in config
        bearer_config = self.config.get("bearer", {})
        bearer_token = bearer_config.get("bearer_token") or self.config.get("bearer_token")

        if not bearer_token:
            raise SecurityConfigurationException("Bearer token is required for bearer authentication")

        # Handle environment variable placeholders
        if isinstance(bearer_token, str) and bearer_token.startswith("${") and bearer_token.endswith("}"):
            self.bearer_token = bearer_token
            return

        if not isinstance(bearer_token, str):
            raise SecurityConfigurationException("Bearer token must be a string")

        if not validate_bearer_token_format(bearer_token):
            raise SecurityConfigurationException("Invalid bearer token format")

        self.bearer_token = bearer_token

        # Additional JWT-specific configuration
        self.jwt_secret = bearer_config.get("jwt_secret")
        self.jwt_algorithm = bearer_config.get("algorithm", "HS256")
        self.jwt_issuer = bearer_config.get("issuer")
        self.jwt_audience = bearer_config.get("audience")

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

        # Otherwise, validate as simple bearer token
        return self._validate_bearer_token(token, request_info)

    def get_auth_type(self) -> str:
        """Get authentication type identifier."""
        return "bearer"

    def get_required_headers(self) -> set[str]:
        """Get required headers for Bearer authentication."""
        return {"Authorization"}

    def supports_scopes(self) -> bool:
        """Bearer tokens can support scopes (especially JWT)."""
        return True  # Could be extended to parse JWT scopes

    def _validate_bearer_token(self, token: str, request_info: dict[str, Any]) -> AuthenticationResult:
        """Validate simple bearer token against configured token.

        Args:
            token: The bearer token to validate
            request_info: Request information for logging

        Returns:
            AuthenticationResult: Authentication result
        """
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
            return AuthenticationResult(success=True, user_id=f"bearer_user_{hash(token) % 10000}", credentials=token)

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
            # Get JWT secret from environment if needed
            jwt_secret = self.jwt_secret
            if jwt_secret and jwt_secret.startswith("${") and jwt_secret.endswith("}"):
                env_expr = jwt_secret[2:-1]  # Remove ${ and }
                if ":" in env_expr:
                    env_var, default_value = env_expr.split(":", 1)
                    jwt_secret = os.getenv(env_var, default_value)
                else:
                    jwt_secret = os.getenv(env_expr)

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
                    "verify_iat": True,
                    "verify_aud": self.jwt_audience is not None,
                    "verify_iss": self.jwt_issuer is not None,
                },
            )

            # Extract user information from payload
            user_id = payload.get("sub") or payload.get("user_id") or "jwt_user"
            scopes = payload.get("scope", "").split() if payload.get("scope") else []

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
