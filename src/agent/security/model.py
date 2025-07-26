"""
Pydantic models for AgentUp security module.

This module defines all security-related data structures including authentication,
authorization, and audit logging models.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from agent.types import (
    CookieName,
    HeaderName,
    IPAddress,
    JsonValue,
    QueryParam,
    ScopeName,
    Timestamp,
    UserId,
)


class AuthType(str, Enum):
    """Supported authentication types."""

    API_KEY = "api_key"
    BEARER = "bearer"
    JWT = "jwt"
    OAUTH2 = "oauth2"


class Scope(BaseModel):
    """Security scope definition with hierarchy support."""

    name: ScopeName = Field(..., description="Scope name")
    description: str | None = Field(None, description="Scope description")
    parent: ScopeName | None = Field(None, description="Parent scope name")

    @field_validator("name")
    @classmethod
    def validate_scope_format(cls, v: str) -> str:
        """Ensure scope follows naming convention."""
        import re

        # Scopes should be lowercase with colons for hierarchy
        # e.g., "read", "write", "admin:users", "api:v1:read"
        if not re.match(r"^[a-z0-9]+(?::[a-z0-9]+)*$", v):
            raise ValueError(f"Invalid scope format: {v}. Use lowercase alphanumeric with colons for hierarchy")
        return v

    def is_subscope_of(self, parent: Scope) -> bool:
        """Check if this scope is a subscope of parent."""
        return self.name.startswith(f"{parent.name}:")

    def __hash__(self) -> int:
        """Make Scope hashable for use in sets."""
        return hash(self.name)

    def __eq__(self, other) -> bool:
        """Compare scopes by name."""
        if isinstance(other, Scope):
            return self.name == other.name
        return False

    model_config = ConfigDict(frozen=True)  # Scopes are immutable


class APIKeyData(BaseModel):
    """API key with metadata and permissions."""

    key: SecretStr = Field(..., description="The API key value")
    name: str | None = Field(None, description="Human-readable key name")
    scopes: list[Scope] = Field(default_factory=list, description="Assigned scopes")
    description: str | None = Field(None, description="Key description")
    created_at: Timestamp = Field(default_factory=datetime.utcnow, description="Creation time")
    expires_at: Timestamp | None = Field(None, description="Expiration time")
    last_used: Timestamp | None = Field(None, description="Last usage time")
    usage_count: int = Field(0, description="Usage counter")

    @field_validator("key")
    @classmethod
    def validate_key_strength(cls, v: SecretStr) -> SecretStr:
        """Ensure API key meets security requirements."""
        key_str = v.get_secret_value()

        # Skip validation for env var placeholders
        if key_str.startswith("${") and key_str.endswith("}"):
            return v

        if len(key_str) < 32:
            raise ValueError("API key must be at least 32 characters")
        if len(key_str) > 128:
            raise ValueError("API key must be no more than 128 characters")

        # Check entropy (simplified)
        import string

        char_types = 0
        if any(c in string.ascii_lowercase for c in key_str):
            char_types += 1
        if any(c in string.ascii_uppercase for c in key_str):
            char_types += 1
        if any(c in string.digits for c in key_str):
            char_types += 1
        if any(c in string.punctuation for c in key_str):
            char_types += 1

        if char_types < 3:
            raise ValueError(
                "API key must contain at least 3 different character types (lowercase, uppercase, digits, special)"
            )

        return v

    @model_validator(mode="after")
    def validate_expiration(self) -> APIKeyData:
        """Ensure expiration is in the future."""
        if self.expires_at and self.created_at:
            if self.expires_at <= self.created_at:
                raise ValueError("Expiration must be after creation time")
        return self

    @computed_field  # Modern Pydantic v2 computed property
    @property
    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (not expired)."""
        return not self.is_expired

    @computed_field
    @property
    def scope_names(self) -> set[str]:
        """Get all scope names as a set for efficient lookup."""
        return {scope.name for scope in self.scopes}

    @computed_field
    @property
    def days_until_expiry(self) -> int | None:
        """Days until expiry, None if no expiration set."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    @computed_field
    @property
    def strength_score(self) -> float:
        """Calculate key strength score (0.0 to 1.0)."""
        key_str = self.key.get_secret_value()
        if key_str.startswith("${") and key_str.endswith("}"):
            return 1.0  # Assume env vars are strong

        score = 0.0
        # Length score (0.0 to 0.4)
        score += min(0.4, len(key_str) / 64 * 0.4)

        # Character diversity score (0.0 to 0.6)
        import string

        char_types = 0
        if any(c in string.ascii_lowercase for c in key_str):
            char_types += 1
        if any(c in string.ascii_uppercase for c in key_str):
            char_types += 1
        if any(c in string.digits for c in key_str):
            char_types += 1
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in key_str):
            char_types += 1
        score += (char_types / 4) * 0.6

        return min(1.0, score)

    def has_scope(self, scope: str | Scope) -> bool:
        """Check if key has a specific scope or any parent scope."""
        if isinstance(scope, str):
            scope = Scope(name=scope)

        for key_scope in self.scopes:
            if key_scope.name == scope.name:
                return True
            # Check if key has a parent scope
            if scope.is_subscope_of(key_scope):
                return True
        return False


class APIKeyConfig(BaseModel):
    """API key authentication configuration."""

    header_name: HeaderName = Field("X-API-Key", description="HTTP header name for API key")
    location: Literal["header", "query", "cookie"] = Field("header", description="Where to look for the API key")
    query_param: QueryParam = Field("api_key", description="Query parameter name if location is 'query'")
    cookie_name: CookieName = Field("api_key", description="Cookie name if location is 'cookie'")
    keys: list[APIKeyData] = Field(..., min_length=1, description="List of valid API keys")

    @field_validator("header_name")
    @classmethod
    def validate_header_name(cls, v: str) -> str:
        """Validate HTTP header name format."""
        import re

        if not re.match(r"^[!#$%&'*+\-.0-9A-Z^_`a-z|~]+$", v):
            raise ValueError(f"Invalid header name format: {v}")
        return v

    @field_validator("keys")
    @classmethod
    def validate_unique_keys(cls, v: list[APIKeyData]) -> list[APIKeyData]:
        """Ensure all API keys are unique."""
        seen = set()
        for key_data in v:
            key_value = key_data.key.get_secret_value()
            if key_value in seen:
                raise ValueError("Duplicate API keys are not allowed")
            seen.add(key_value)
        return v


class JWTAlgorithm(str, Enum):
    """Supported JWT algorithms."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    ES256 = "ES256"
    ES384 = "ES384"
    ES512 = "ES512"


class JWTConfig(BaseModel):
    """JWT authentication configuration."""

    secret_key: SecretStr = Field(..., description="JWT signing key")
    algorithm: JWTAlgorithm = Field(JWTAlgorithm.HS256, description="JWT signing algorithm")
    expiration: timedelta = Field(timedelta(hours=1), description="Token expiration time")
    issuer: str | None = Field(None, description="Expected token issuer")
    audience: str | None = Field(None, description="Expected token audience")

    # Public key for RS/ES algorithms
    public_key: SecretStr | None = Field(None, description="Public key for asymmetric algorithms")

    # Token claims
    required_claims: list[str] = Field(
        default_factory=lambda: ["sub", "exp"], description="Claims that must be present"
    )

    @model_validator(mode="after")
    def validate_algorithm_key_pair(self) -> JWTConfig:
        """Ensure proper keys for algorithm type."""
        if self.algorithm in [
            JWTAlgorithm.RS256,
            JWTAlgorithm.RS384,
            JWTAlgorithm.RS512,
            JWTAlgorithm.ES256,
            JWTAlgorithm.ES384,
            JWTAlgorithm.ES512,
        ]:
            if not self.public_key:
                raise ValueError(f"Public key required for {self.algorithm} algorithm")
        return self


class OAuth2Config(BaseModel):
    """OAuth2 authentication configuration."""

    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: SecretStr = Field(..., description="OAuth2 client secret")
    authorization_url: str = Field(..., description="Authorization endpoint URL")
    token_url: str = Field(..., description="Token endpoint URL")
    redirect_uri: str = Field(..., description="Redirect URI")
    scopes: list[str] = Field(default_factory=list, description="OAuth2 scopes")

    # Token validation strategy
    validation_strategy: Literal["jwt", "introspection", "both"] = Field("jwt", description="Token validation method")

    # JWT validation settings
    jwks_url: str | None = Field(None, description="JWKS endpoint URL")
    jwt_algorithm: JWTAlgorithm = Field(JWTAlgorithm.RS256, description="JWT algorithm for validation")
    jwt_audience: str | None = Field(None, description="Expected JWT audience")
    jwt_issuer: str | None = Field(None, description="Expected JWT issuer")

    # Introspection settings
    introspection_endpoint: str | None = Field(None, description="Token introspection endpoint")
    introspection_auth_method: Literal["client_secret_basic", "client_secret_post"] = Field(
        "client_secret_basic", description="Introspection authentication method"
    )

    # Advanced settings
    use_pkce: bool = Field(True, description="Use PKCE for authorization code flow")
    token_endpoint_auth_method: str = Field("client_secret_basic", description="Token endpoint authentication method")

    @field_validator("authorization_url", "token_url", "jwks_url", "introspection_endpoint")
    @classmethod
    def validate_urls(cls, v: str | None) -> str | None:
        """Validate URL format."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL: {v}")
        return v

    @model_validator(mode="after")
    def validate_strategy_config(self) -> OAuth2Config:
        """Ensure required fields for validation strategy."""
        if self.validation_strategy in ["jwt", "both"] and not self.jwks_url:
            raise ValueError("jwks_url required for JWT validation")
        if self.validation_strategy in ["introspection", "both"] and not self.introspection_endpoint:
            raise ValueError("introspection_endpoint required for introspection")
        return self


class SecurityConfig(BaseModel):
    """Complete security configuration."""

    enabled: bool = Field(True, description="Enable security features")

    # Authentication methods (at least one required)
    auth: dict[AuthType, APIKeyConfig | JWTConfig | OAuth2Config] = Field(
        ..., description="Authentication configurations by type"
    )

    # Global security settings
    require_https: bool = Field(True, description="Require HTTPS for all requests")
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"], description="CORS allowed origins")
    allowed_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"], description="Allowed HTTP methods"
    )

    # Security headers
    enable_hsts: bool = Field(True, description="Enable HSTS header")
    enable_csrf: bool = Field(True, description="Enable CSRF protection")

    # Audit logging
    audit_logging: bool = Field(True, description="Enable audit logging")
    audit_log_retention_days: int = Field(90, ge=1, le=365, description="Audit log retention")

    # Rate limiting
    enable_rate_limiting: bool = Field(True, description="Enable rate limiting")
    rate_limit_requests: int = Field(60, description="Requests per minute")

    @field_validator("auth")
    @classmethod
    def validate_auth_config(cls, v: dict) -> dict:
        """Ensure at least one auth method is configured."""
        if not v:
            raise ValueError("At least one authentication method must be configured")

        # Validate auth type matches config type
        for auth_type, config in v.items():
            expected_type = {
                AuthType.API_KEY: APIKeyConfig,
                AuthType.JWT: JWTConfig,
                AuthType.OAUTH2: OAuth2Config,
                AuthType.BEARER: JWTConfig,  # Bearer uses JWT config
            }

            if auth_type in expected_type:
                if not isinstance(config, expected_type[auth_type]):
                    raise ValueError(
                        f"Invalid config type for {auth_type}. Expected {expected_type[auth_type].__name__}"
                    )

        return v

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, v: list[str]) -> list[str]:
        """Validate CORS origins."""
        for origin in v:
            if origin != "*" and not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid origin: {origin}")
        return v


class AuthResult(str, Enum):
    """Authentication result status."""

    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    EXPIRED = "expired"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    DISABLED = "disabled"
    ERROR = "error"


class AuthContext(BaseModel):
    """Runtime authentication context."""

    authenticated: bool = Field(False, description="Whether request is authenticated")
    auth_type: AuthType | None = Field(None, description="Type of authentication used")
    auth_result: AuthResult | None = Field(None, description="Authentication result")

    # User information
    user_id: UserId | None = Field(None, description="User identifier")
    username: str | None = Field(None, description="Username")
    email: str | None = Field(None, description="User email")

    # Permissions
    scopes: set[Scope] = Field(default_factory=set, description="User scopes")
    roles: set[str] = Field(default_factory=set, description="User roles")

    # Request metadata
    ip_address: IPAddress | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="User agent string")
    request_id: str | None = Field(None, description="Request identifier")

    # Token/Key metadata
    token_id: str | None = Field(None, description="Token identifier")
    key_name: str | None = Field(None, description="API key name")
    expires_at: Timestamp | None = Field(None, description="Token expiration")

    # Additional context
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    def has_scope(self, scope: str | Scope) -> bool:
        """Check if context has a specific scope."""
        if isinstance(scope, str):
            scope = Scope(name=scope)

        for ctx_scope in self.scopes:
            if ctx_scope.name == scope.name:
                return True
            if scope.is_subscope_of(ctx_scope):
                return True
        return False

    def has_any_scope(self, scopes: list[str | Scope]) -> bool:
        """Check if context has any of the specified scopes."""
        return any(self.has_scope(scope) for scope in scopes)

    def has_all_scopes(self, scopes: list[str | Scope]) -> bool:
        """Check if context has all specified scopes."""
        return all(self.has_scope(scope) for scope in scopes)

    model_config = ConfigDict(
        arbitrary_types_allowed=True  # Allow set type for scopes
    )


class AuditAction(str, Enum):
    """Types of auditable actions."""

    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    GRANT = "grant"
    REVOKE = "revoke"
    EXPORT = "export"
    IMPORT = "import"


class AuditResult(str, Enum):
    """Result of an audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    BLOCKED = "blocked"


class AuditLogEntry(BaseModel):
    """Security audit log entry with comprehensive tracking."""

    # Timing
    timestamp: Timestamp = Field(default_factory=datetime.utcnow, description="Event timestamp")
    duration_ms: float | None = Field(None, description="Operation duration in milliseconds")

    # Event information
    event_type: str = Field(..., description="Type of event (e.g., 'auth', 'access')")
    action: AuditAction = Field(..., description="Action performed")
    result: AuditResult = Field(..., description="Action result")

    # Actor information
    user_id: UserId | None = Field(None, description="User identifier")
    username: str | None = Field(None, description="Username")
    auth_type: AuthType | None = Field(None, description="Authentication type used")

    # Resource information
    resource_type: str | None = Field(None, description="Type of resource accessed")
    resource_id: str | None = Field(None, description="Resource identifier")
    resource_name: str | None = Field(None, description="Resource name")

    # Request context
    ip_address: IPAddress | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="User agent string")
    request_id: str | None = Field(None, description="Request identifier")
    session_id: str | None = Field(None, description="Session identifier")

    # Details
    details: dict[str, str] = Field(default_factory=dict, description="Additional details")
    error_message: str | None = Field(None, description="Error message if applicable")

    # Compliance fields
    data_classification: str | None = Field(None, description="Data classification level")
    compliance_tags: list[str] = Field(default_factory=list, description="Compliance tags")

    def to_log_format(self) -> str:
        """Format entry for logging."""
        parts = [
            f"[{self.timestamp.isoformat()}]",
            f"EVENT={self.event_type}",
            f"ACTION={self.action.value}",
            f"RESULT={self.result.value}",
        ]

        if self.user_id:
            parts.append(f"USER={self.user_id}")
        if self.resource_type and self.resource_id:
            parts.append(f"RESOURCE={self.resource_type}:{self.resource_id}")
        if self.ip_address:
            parts.append(f"IP={self.ip_address}")
        if self.error_message:
            parts.append(f"ERROR={self.error_message}")

        return " ".join(parts)

    model_config = ConfigDict()

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize datetime to ISO format."""
        return value.isoformat()


class PermissionCheck(BaseModel):
    """Request for permission verification."""

    user_id: UserId = Field(..., description="User to check")
    resource_type: str = Field(..., description="Resource type")
    resource_id: str | None = Field(None, description="Specific resource ID")
    action: str = Field(..., description="Action to perform")
    context: dict[str, JsonValue] = Field(default_factory=dict, description="Additional context")


class PermissionResult(BaseModel):
    """Result of permission check."""

    granted: bool = Field(..., description="Whether permission is granted")
    reason: str | None = Field(None, description="Reason for denial")
    required_scopes: list[str] = Field(default_factory=list, description="Required scopes")
    missing_scopes: list[str] = Field(default_factory=list, description="Missing scopes")
    conditions: list[str] = Field(default_factory=list, description="Additional conditions")


class SecurityEvent(BaseModel):
    """Security event for monitoring and alerting."""

    event_id: str = Field(..., description="Unique event identifier")
    timestamp: Timestamp = Field(default_factory=datetime.utcnow, description="Event timestamp")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Event severity")
    category: str = Field(..., description="Event category")
    title: str = Field(..., description="Event title")
    description: str = Field(..., description="Event description")

    # Context
    user_id: UserId | None = Field(None, description="Associated user")
    ip_address: IPAddress | None = Field(None, description="Source IP")
    user_agent: str | None = Field(None, description="User agent")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Event tags")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Additional metadata")

    # Alerting
    alert_sent: bool = Field(False, description="Whether alert was sent")
    alert_recipients: list[str] = Field(default_factory=list, description="Alert recipients")


# Re-export commonly used models
__all__ = [
    "AuthType",
    "Scope",
    "APIKeyData",
    "APIKeyConfig",
    "JWTConfig",
    "JWTAlgorithm",
    "OAuth2Config",
    "SecurityConfig",
    "AuthResult",
    "AuthContext",
    "AuditAction",
    "AuditResult",
    "AuditLogEntry",
    "PermissionCheck",
    "PermissionResult",
    "SecurityEvent",
]
