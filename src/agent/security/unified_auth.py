from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog
from fastapi import HTTPException, Request

logger = structlog.get_logger(__name__)


class AuthType(str, Enum):
    """Supported authentication types."""

    OAUTH2 = "oauth2"
    JWT = "jwt"
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"


@dataclass
class AuthContext:
    """Enhanced authentication context with scope information."""

    user_id: str
    auth_type: AuthType
    scopes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    expires_at: float | None = None
    is_valid: bool = True

    def has_scope(self, scope: str) -> bool:
        """Check if this context has a specific scope."""
        return scope in self.scopes or "admin" in self.scopes

    def require_scope(self, scope: str) -> None:
        """Require a specific scope, raising exception if not present."""
        if not self.has_scope(scope):
            raise HTTPException(status_code=403, detail=f"Insufficient permissions. Required scope: {scope}")


class ScopeHierarchy:
    """Manages hierarchical scope inheritance."""

    def __init__(self):
        """
        Initialize scope hierarchy with explicit configuration only.
        This is put in as a safety measure to ensure all scope inheritance is explicit
        and somehow not injected by unexpected sources.
        """
        self.hierarchy = {}

    def add_scope_inheritance(self, parent_scope: str, child_scopes: list[str]) -> None:
        """Add custom scope inheritance."""
        self.hierarchy[parent_scope] = child_scopes
        logger.debug(f"Added scope inheritance: {parent_scope} -> {child_scopes}")

    def expand_scopes(self, user_scopes: list[str]) -> set[str]:
        """Expand user scopes based on hierarchy."""
        expanded = set(user_scopes)
        logger.info(
            f"Expanding scopes: initial={user_scopes}, hierarchy_size={len(self.hierarchy)}, hierarchy={self.hierarchy}"
        )

        if not self.hierarchy:
            logger.warning("No scope hierarchy available - scopes will not be expanded")

        # Keep expanding until no new scopes are added
        from collections import deque

        # Early wildcard check on initial scopes
        for scope in expanded:
            if scope in self.hierarchy and "*" in self.hierarchy.get(scope, []):
                logger.debug(f"Wildcard detected for scope '{scope}' - granting all permissions")
                return {"*"}

        # BFS expansion using queue
        to_process = deque(expanded)
        seen = expanded.copy()  # Track what we've already added

        while to_process:
            scope = to_process.popleft()

            if scope in self.hierarchy:
                inherited = self.hierarchy[scope]
                logger.debug(f"Scope '{scope}' inherits: {inherited}")

                if "*" in inherited:
                    logger.debug(f"Wildcard detected for scope '{scope}' - granting all permissions")
                    return {"*"}

                for inherited_scope in inherited:
                    if inherited_scope not in seen:
                        seen.add(inherited_scope)
                        expanded.add(inherited_scope)
                        to_process.append(inherited_scope)
                        logger.debug(f"Added inherited scope '{inherited_scope}' from '{scope}'")
            logger.debug(f"Final expanded scopes: {expanded}")
        return expanded

    def validate_scope(self, user_scopes: list[str], required_scope: str) -> bool:
        """Validate if user has required scope including hierarchy."""
        logger.debug(f"Validating scope: user_scopes={user_scopes}, required_scope={required_scope}")
        expanded_scopes = self.expand_scopes(user_scopes)
        logger.debug(f"Expanded scopes: {expanded_scopes}")
        logger.debug(f"Required scope: {required_scope}")
        result = required_scope in expanded_scopes or "*" in expanded_scopes
        logger.debug(f"Scope validation result: {result} (expanded_scopes={expanded_scopes})")
        return result


class AuthenticationProvider:
    """Base class for authentication providers."""

    async def authenticate(self, request: Request) -> AuthContext | None:
        """Authenticate a request and return auth context."""
        raise NotImplementedError

    def get_auth_type(self) -> AuthType:
        """Get the authentication type for this provider."""
        raise NotImplementedError


class JWTAuthProvider(AuthenticationProvider):
    """JWT authentication provider."""

    def __init__(self, secret_key: str, algorithm: str = "HS256", issuer: str | None = None):
        """Initialize JWT provider."""
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.issuer = issuer

    async def authenticate(self, request: Request) -> AuthContext | None:
        """Authenticate JWT token."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Import JWT library when needed
            import jwt

            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], issuer=self.issuer)

            user_id = payload.get("sub") or payload.get("user_id")
            if not user_id:
                logger.warning("JWT token missing user identifier")
                return None

            scopes = payload.get("scopes", [])
            if isinstance(scopes, str):
                scopes = scopes.split()

            return AuthContext(
                user_id=user_id, auth_type=AuthType.JWT, scopes=scopes, metadata=payload, expires_at=payload.get("exp")
            )

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except ImportError:
            logger.error("PyJWT not available for JWT authentication")
            return None

    def get_auth_type(self) -> AuthType:
        """Get auth type."""
        return AuthType.JWT


class BearerTokenAuthProvider(AuthenticationProvider):
    """Bearer token authentication provider."""

    def __init__(self, token_validation_url: str | None = None, valid_tokens: dict[str, dict[str, Any]] | None = None):
        """Initialize bearer token provider."""
        self.token_validation_url = token_validation_url
        self.valid_tokens = valid_tokens or {}

    async def authenticate(self, request: Request) -> AuthContext | None:
        """Authenticate bearer token."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Check against local token store first
        if token in self.valid_tokens:
            token_data = self.valid_tokens[token]
            return AuthContext(
                user_id=token_data.get("user_id", "unknown"),
                auth_type=AuthType.BEARER,
                scopes=token_data.get("scopes", []),
                metadata=token_data,
            )

        # Validate against external service if configured
        if self.token_validation_url:
            return await self._validate_token_externally(token)

        return None

    async def _validate_token_externally(self, token: str) -> AuthContext | None:
        """Validate token against external service."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(self.token_validation_url, headers={"Authorization": f"Bearer {token}"})

                if response.status_code == 200:
                    data = response.json()
                    return AuthContext(
                        user_id=data.get("user_id", "unknown"),
                        auth_type=AuthType.BEARER,
                        scopes=data.get("scopes", []),
                        metadata=data,
                    )
                else:
                    logger.warning(f"Token validation failed: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error validating token externally: {e}")
            return None

    def get_auth_type(self) -> AuthType:
        """Get auth type."""
        return AuthType.BEARER


class APIKeyAuthProvider(AuthenticationProvider):
    """API Key authentication provider."""

    def __init__(self, valid_keys: dict[str, dict[str, Any]], header_name: str = "X-API-Key"):
        """Initialize API key provider."""
        self.valid_keys = valid_keys
        self.header_name = header_name

    async def authenticate(self, request: Request) -> AuthContext | None:
        """Authenticate API key."""
        api_key = request.headers.get(self.header_name)
        if not api_key:
            return None

        if api_key in self.valid_keys:
            key_data = self.valid_keys[api_key]
            return AuthContext(
                user_id=key_data.get("user_id", "api_user"),
                auth_type=AuthType.API_KEY,
                scopes=key_data.get("scopes", []),
                metadata=key_data,
            )

        return None

    def get_auth_type(self) -> AuthType:
        """Get auth type."""
        return AuthType.API_KEY


class UnifiedAuthenticationManager:
    """Unified authentication supporting multiple auth types with granular scopes."""

    def __init__(self, config: dict[str, Any]):
        """Initialize unified authentication manager."""
        self.config = config
        self.scope_hierarchy = ScopeHierarchy()
        self.auth_providers: list[AuthenticationProvider] = []
        self.auth_enabled = config.get("enabled", True)

        # Build custom scope hierarchy if provided
        scope_hierarchy = config.get("scope_hierarchy", {})
        logger.info(f"Loading scope hierarchy from config: {scope_hierarchy}")
        logger.info(f"Config keys available: {list(config.keys())}")

        if scope_hierarchy:
            for parent, children in scope_hierarchy.items():
                self.scope_hierarchy.add_scope_inheritance(parent, children)
        else:
            logger.warning("No custom scope hierarchy found in config - scope inheritance disabled")

        logger.info(f"Scope hierarchy initialized with {len(self.scope_hierarchy.hierarchy)} entries")
        logger.debug(f"Scope hierarchy: {self.scope_hierarchy.hierarchy}")
        # Initialize authentication providers
        self._initialize_providers()

        logger.info(
            "ASF authentication manager initialized",
            enabled=self.auth_enabled,
            providers=[p.get_auth_type().value for p in self.auth_providers],
        )

    def _initialize_providers(self) -> None:
        """Initialize authentication providers based on configuration."""
        # Get auth configuration from auth: structure
        auth_config = self.config.get("auth", {})
        if not auth_config:
            logger.warning("No auth configuration found")
            return

        # Use the first auth type found, warn about others
        available_types = list(auth_config.keys())
        if len(available_types) > 1:
            logger.warning(f"Multiple auth types configured: {available_types}. Using {available_types[0]}, ignoring others.")

        if not available_types:
            logger.warning("No authentication types configured")
            return

        primary_type = available_types[0]
        auth_types = {primary_type: auth_config[primary_type]}

        # JWT provider
        if "jwt" in auth_types:
            jwt_config = auth_types["jwt"]
            provider = JWTAuthProvider(
                secret_key=jwt_config["secret_key"],
                algorithm=jwt_config.get("algorithm", "HS256"),
                issuer=jwt_config.get("issuer"),
            )
            self.auth_providers.append(provider)

        # Bearer token provider
        if "bearer" in auth_types:
            bearer_config = auth_types["bearer"]
            provider = BearerTokenAuthProvider(
                token_validation_url=bearer_config.get("token_validation_url"),
                valid_tokens=bearer_config.get("valid_tokens", {}),
            )
            self.auth_providers.append(provider)

        # API Key provider
        if "api_key" in auth_types:
            api_key_config = auth_types["api_key"]

            # Handle both simple keys array and complex valid_keys object
            valid_keys = {}

            if "valid_keys" in api_key_config:
                # New format: valid_keys already in correct format
                valid_keys = api_key_config["valid_keys"]
            elif "keys" in api_key_config:
                # Template format: convert keys array to valid_keys object
                keys_list = api_key_config["keys"]
                if isinstance(keys_list, list):
                    # Convert simple string array to dict format
                    for key in keys_list:
                        if isinstance(key, str):
                            valid_keys[key] = {
                                "user_id": "api_user",
                                "scopes": ["api:read", "api:write"]  # Default scopes
                            }
                        elif isinstance(key, dict) and "key" in key:
                            # Handle {key: "...", scopes: [...]} format
                            valid_keys[key["key"]] = {
                                "user_id": key.get("user_id", "api_user"),
                                "scopes": key.get("scopes", ["api:read"])
                            }

            provider = APIKeyAuthProvider(
                valid_keys=valid_keys,
                header_name=api_key_config.get("header_name", "X-API-Key"),
            )
            self.auth_providers.append(provider)

    def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.auth_enabled

    async def authenticate_request(self, request: Request, required_scopes: list[str] = None) -> AuthContext | None:
        """Authenticate request using any available provider."""
        if not self.auth_enabled:
            logger.error("Authentication disabled but request requires authentication - denying access")
            raise HTTPException(status_code=401, detail="Authentication is required but disabled in configuration")

        # Try each provider in order
        for provider in self.auth_providers:
            try:
                auth_context = await provider.authenticate(request)
                if auth_context and auth_context.is_valid:
                    # Expand scopes using hierarchy
                    expanded_scopes = self.scope_hierarchy.expand_scopes(auth_context.scopes)
                    auth_context.scopes = list(expanded_scopes)

                    # Validate required scopes if specified
                    if required_scopes:
                        for scope in required_scopes:
                            if not self.scope_hierarchy.validate_scope(auth_context.scopes, scope):
                                logger.warning(
                                    f"User '{auth_context.user_id}' lacks required scope '{scope}'",
                                    user_scopes=auth_context.scopes,
                                )
                                raise HTTPException(
                                    status_code=403, detail=f"Insufficient permissions. Required scope: {scope}"
                                )

                    logger.debug(
                        "Authentication successful",
                        user_id=auth_context.user_id,
                        auth_type=auth_context.auth_type.value,
                        scopes=auth_context.scopes,
                    )
                    return auth_context

            except HTTPException:
                # Re-raise HTTP exceptions (like permission denied)
                raise
            except Exception as e:
                logger.warning(f"Provider {provider.get_auth_type().value} failed: {e}")
                continue

        # No provider could authenticate the request
        logger.warning("Authentication failed for request", path=request.url.path)
        raise HTTPException(status_code=401, detail="Authentication required")

    def validate_scope_access(self, user_scopes: list[str], required_scope: str) -> bool:
        """Validate if user has access to required scope."""
        logger.info(f"Validating scope access for user. Required scope: {required_scope}")
        return self.scope_hierarchy.validate_scope(user_scopes, required_scope)

    def get_scope_summary(self) -> dict[str, Any]:
        """Get summary of scope hierarchy for debugging."""
        return {
            "hierarchy": self.scope_hierarchy.hierarchy,
            "total_scopes": len(self.scope_hierarchy.hierarchy),
            "wildcard_scopes": [scope for scope, children in self.scope_hierarchy.hierarchy.items() if "*" in children],
        }


# Global manager instance
_unified_auth_manager: UnifiedAuthenticationManager | None = None


def get_unified_auth_manager() -> UnifiedAuthenticationManager | None:
    """Get the global unified authentication manager instance."""
    return _unified_auth_manager


def create_unified_auth_manager(config: dict[str, Any]) -> UnifiedAuthenticationManager:
    """Create and set the global unified authentication manager."""
    global _unified_auth_manager
    _unified_auth_manager = UnifiedAuthenticationManager(config)
    return _unified_auth_manager
