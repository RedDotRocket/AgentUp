from typing import Any

import structlog
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from fastapi import Request

from agent.security.base import AuthenticationResult, BaseAuthenticator
from agent.security.exceptions import (
    InvalidCredentialsException,
    MissingCredentialsException,
    SecurityConfigurationException,
)
from agent.security.utils import extract_bearer_token, get_request_info, log_security_event

logger = structlog.get_logger(__name__)


class OAuth2Authenticator(BaseAuthenticator):
    """OAuth2 based authentication using Authlib."""

    def _validate_config(self) -> None:
        """Validate OAuth2 authenticator configuration."""
        # Get OAuth2 configuration from auth structure
        oauth2_config = self.config.get("auth", {}).get("oauth2", {})

        if not oauth2_config:
            raise SecurityConfigurationException("OAuth2 configuration is required for oauth2 authentication")

        # Required configuration
        self.client_id = oauth2_config.get("client_id")
        self.client_secret = oauth2_config.get("client_secret")
        self.token_endpoint = oauth2_config.get("token_endpoint")
        self.introspection_endpoint = oauth2_config.get("introspection_endpoint")

        # JWT validation configuration
        self.jwt_secret = oauth2_config.get("jwt_secret")
        self.jwt_algorithm = oauth2_config.get("jwt_algorithm", "RS256")
        self.jwt_issuer = oauth2_config.get("jwt_issuer")
        self.jwt_audience = oauth2_config.get("jwt_audience")
        self.jwks_url = oauth2_config.get("jwks_url")

        # Validation strategy: 'jwt', 'introspection', or 'both'
        self.validation_strategy = oauth2_config.get("validation_strategy", "jwt")

        # Validate required fields based on strategy
        if self.validation_strategy in ["jwt", "both"]:
            if not (self.jwt_secret or self.jwks_url):
                raise SecurityConfigurationException("JWT validation requires either jwt_secret or jwks_url")

        if self.validation_strategy in ["introspection", "both"]:
            if not self.introspection_endpoint:
                raise SecurityConfigurationException("Token introspection requires introspection_endpoint")
            if not (self.client_id and self.client_secret):
                raise SecurityConfigurationException("Token introspection requires client_id and client_secret")

        # Optional: Required scopes
        self.required_scopes = set(oauth2_config.get("required_scopes", []))

        # Cache JWKS keys if URL provided
        self._jwks_cache: dict[str, Any] | None = None

    async def authenticate(self, request: Request) -> AuthenticationResult:
        """Authenticate request using OAuth2 Bearer token.

        Args:
            request: FastAPI request object

        Returns:
            AuthenticationResult: Authentication result with user info and scopes

        Raises:
            MissingCredentialsException: If Bearer token is missing
            InvalidCredentialsException: If Bearer token is invalid
        """
        request_info = get_request_info(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            log_security_event("authentication", request_info, False, "Missing Authorization header for OAuth2")
            raise MissingCredentialsException("Unauthorized")

        # Extract Bearer token
        token = extract_bearer_token(auth_header)
        if not token:
            log_security_event("authentication", request_info, False, "Invalid Authorization header format for OAuth2")
            raise InvalidCredentialsException("Unauthorized")

        try:
            # Validate token based on configured strategy
            if self.validation_strategy == "jwt":
                result = await self._validate_jwt_token(token, request_info)
            elif self.validation_strategy == "introspection":
                result = await self._validate_via_introspection(token, request_info)
            elif self.validation_strategy == "both":
                # Try JWT first, fallback to introspection
                try:
                    result = await self._validate_jwt_token(token, request_info)
                except InvalidCredentialsException:
                    result = await self._validate_via_introspection(token, request_info)
            else:
                raise SecurityConfigurationException(f"Invalid validation strategy: {self.validation_strategy}")

            # Validate required scopes if configured
            if self.required_scopes and not self.required_scopes.issubset(result.scopes or set()):
                log_security_event(
                    "authorization", request_info, False, f"Required scopes not met: {self.required_scopes}"
                )
                raise InvalidCredentialsException("Unauthorized")

            log_security_event("authentication", request_info, True, "OAuth2 token authenticated")
            return result

        except (JoseError, ValueError, KeyError) as e:
            log_security_event("authentication", request_info, False, f"OAuth2 token validation failed: {str(e)}")
            raise InvalidCredentialsException("Unauthorized") from e

    async def _validate_jwt_token(self, token: str, request_info: dict[str, Any]) -> AuthenticationResult:
        """Validate JWT token using configured secret or JWKS.

        Args:
            token: The JWT token to validate
            request_info: Request information for logging

        Returns:
            AuthenticationResult: Authentication result with user info and scopes

        Raises:
            InvalidCredentialsException: If token is invalid
        """
        try:
            # Get signing key
            if self.jwks_url:
                key = await self._get_jwks_key(token)
            elif self.jwt_secret:
                key = self.jwt_secret
            else:
                raise InvalidCredentialsException("No JWT validation key available")

            # Validate JWT
            claims = jwt.decode(
                token,
                key,
                claims_options={
                    "iss": {"essential": bool(self.jwt_issuer), "value": self.jwt_issuer},
                    "aud": {"essential": bool(self.jwt_audience), "value": self.jwt_audience},
                },
            )

            # Extract user information
            user_id = claims.get("sub") or claims.get("user_id") or "unknown"
            email = claims.get("email")
            name = claims.get("name")

            # Extract scopes from standard claims
            scopes = set()
            if "scope" in claims:
                if isinstance(claims["scope"], str):
                    scopes = set(claims["scope"].split())
                elif isinstance(claims["scope"], list):
                    scopes = set(claims["scope"])
            elif "scopes" in claims:
                scopes = set(claims["scopes"]) if isinstance(claims["scopes"], list) else set()

            return AuthenticationResult(
                success=True,
                user_id=user_id,
                credentials=token,
                scopes=scopes,
                metadata={"email": email, "name": name, "claims": dict(claims)},
            )

        except JoseError as e:
            logger.debug(f"JWT validation failed: {e}")
            raise InvalidCredentialsException("Unauthorized") from e

    async def _validate_via_introspection(self, token: str, request_info: dict[str, Any]) -> AuthenticationResult:
        """Validate token via OAuth2 introspection endpoint.

        Args:
            token: The access token to introspect
            request_info: Request information for logging

        Returns:
            AuthenticationResult: Authentication result with user info and scopes

        Raises:
            InvalidCredentialsException: If token is invalid or introspection fails
        """
        try:
            # GitHub expects JSON payload with "access_token" field, not form data
            # Use basic auth with httpx directly instead of AsyncOAuth2Client
            import base64

            import httpx

            auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.introspection_endpoint,
                    headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                    json={"access_token": token},
                )
                response.raise_for_status()

                introspection_data = response.json()

                # Check if token is active
                # GitHub doesn't return 'active' field, but returns 200 status for valid tokens
                # For standard OAuth2 introspection, check 'active' field
                if "active" in introspection_data and not introspection_data.get("active", False):
                    raise InvalidCredentialsException("Unauthorized")

                # Extract user information
                user_id = (
                    introspection_data.get("sub")
                    or introspection_data.get("user_id")
                    or introspection_data.get("username")
                    or (introspection_data.get("user", {}).get("login") if introspection_data.get("user") else None)
                    or "unknown"
                )

                # Extract scopes
                scopes = set()
                if "scope" in introspection_data:
                    scope_value = introspection_data["scope"]
                    if isinstance(scope_value, str):
                        scopes = set(scope_value.split())
                    elif isinstance(scope_value, list):
                        scopes = set(scope_value)
                elif "scopes" in introspection_data:
                    # GitHub returns scopes as "scopes" field
                    scope_value = introspection_data["scopes"]
                    if isinstance(scope_value, list):
                        scopes = set(scope_value)
                    elif isinstance(scope_value, str):
                        scopes = set(scope_value.split())

                return AuthenticationResult(
                    success=True,
                    user_id=user_id,
                    credentials=token,
                    scopes=scopes,
                    metadata={
                        "client_id": introspection_data.get("client_id"),
                        "exp": introspection_data.get("exp"),
                        "iat": introspection_data.get("iat"),
                        "introspection": introspection_data,
                    },
                )

        except Exception as e:
            logger.debug(f"Token introspection failed: {e}")
            raise InvalidCredentialsException("Unauthorized") from e

    async def _get_jwks_key(self, token: str) -> JsonWebKey:
        """Get JWKS key for JWT validation.

        Args:
            token: JWT token to extract key ID from

        Returns:
            JsonWebKey: The public key for validation

        Raises:
            InvalidCredentialsException: If key cannot be found
        """
        try:
            # Decode token header to get key ID
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            if not kid:
                raise InvalidCredentialsException("No key ID in JWT header")

            # Fetch JWKS if not cached
            if self._jwks_cache is None:
                async with AsyncOAuth2Client() as client:
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    self._jwks_cache = response.json()

            # Find matching key
            for key_data in self._jwks_cache.get("keys", []):
                if key_data.get("kid") == kid:
                    return JsonWebKey.import_key(key_data)

            raise InvalidCredentialsException("JWT key not found in JWKS")

        except Exception as e:
            logger.debug(f"JWKS key retrieval failed: {e}")
            raise InvalidCredentialsException("Unauthorized") from e

    def get_auth_type(self) -> str:
        """Get authentication type identifier."""
        return "oauth2"

    def get_required_headers(self) -> set[str]:
        """Get required headers for OAuth2 authentication."""
        return {"Authorization"}

    def supports_scopes(self) -> bool:
        """OAuth2 supports scopes."""
        return True
