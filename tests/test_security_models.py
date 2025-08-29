"""
Tests for AgentUp security models.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr, ValidationError

from src.agent.security.model import (
    APIKeyConfig,
    APIKeyData,
    AuditAction,
    AuditLogEntry,
    AuditResult,
    AuthContext,
    AuthResult,
    AuthType,
    JWTAlgorithm,
    JWTConfig,
    OAuth2Config,
    PermissionCheck,
    PermissionResult,
    Scope,
    SecurityConfig,
)


class TestScope:
    def test_valid_scope_creation(self):
        scope = Scope(name="read")
        assert scope.name == "read"
        assert scope.description is None
        assert scope.parent is None

        scope_with_desc = Scope(name="api:v1:read", description="Read API v1 resources", parent="api:v1")
        assert scope_with_desc.name == "api:v1:read"
        assert scope_with_desc.description == "Read API v1 resources"
        assert scope_with_desc.parent == "api:v1"

    def test_scope_validation(self):
        # Valid scope names
        Scope(name="read")
        Scope(name="write")
        Scope(name="admin")
        Scope(name="api:read")
        Scope(name="api:v1:read")
        Scope(name="user123:read")

        # Invalid scope names
        with pytest.raises(ValidationError):
            Scope(name="Read")  # Uppercase not allowed

        with pytest.raises(ValidationError):
            Scope(name="read write")  # Spaces not allowed

        with pytest.raises(ValidationError):
            Scope(name="read-write")  # Hyphens not allowed

        with pytest.raises(ValidationError):
            Scope(name="read_write")  # Underscores not allowed

        with pytest.raises(ValidationError):
            Scope(name="")  # Empty not allowed

    def test_scope_hierarchy(self):
        parent_scope = Scope(name="api")
        child_scope = Scope(name="api:read")
        grandchild_scope = Scope(name="api:read:user")
        unrelated_scope = Scope(name="admin")

        assert child_scope.is_subscope_of(parent_scope)
        assert grandchild_scope.is_subscope_of(parent_scope)
        assert grandchild_scope.is_subscope_of(child_scope)
        assert not parent_scope.is_subscope_of(child_scope)
        assert not unrelated_scope.is_subscope_of(parent_scope)

    def test_scope_equality_and_hashing(self):
        scope1 = Scope(name="read")
        scope2 = Scope(name="read")
        scope3 = Scope(name="write")

        assert scope1 == scope2
        assert scope1 != scope3

        # Test in sets
        scope_set = {scope1, scope2, scope3}
        assert len(scope_set) == 2  # scope1 and scope2 are the same
        assert scope1 in scope_set
        assert scope3 in scope_set

    def test_scope_immutability(self):
        scope = Scope(name="read")

        # Should not be able to modify the scope
        with pytest.raises(ValidationError):
            scope.name = "write"


class TestAPIKeyData:
    def test_valid_api_key(self):
        # Key with 3+ character types: lowercase, uppercase, digits, special
        test_key = "Aa1!" + "x" * 28  # 32 chars total with required diversity
        key = APIKeyData(
            key=SecretStr(test_key),
            name="Test Key",
            scopes=[Scope(name="read"), Scope(name="write")],
            description="Test API key",
        )

        assert key.key.get_secret_value() == test_key
        assert key.name == "Test Key"
        assert len(key.scopes) == 2
        assert not key.is_expired
        assert key.usage_count == 0

    def test_api_key_validation(self):
        # Too short
        with pytest.raises(ValidationError) as exc_info:
            APIKeyData(key=SecretStr("short"))
        assert "at least 32 characters" in str(exc_info.value)

        # Too long
        with pytest.raises(ValidationError):
            APIKeyData(key=SecretStr("a" * 129))

        # Insufficient character types
        with pytest.raises(ValidationError) as exc_info:
            APIKeyData(key=SecretStr("a" * 32))  # Only lowercase
        assert "at least 3 different character types" in str(exc_info.value)

        # Valid key with mixed character types
        APIKeyData(key=SecretStr("Aa1!" * 8))  # 32 chars with 4 types

    def test_api_key_env_var_skip(self):
        # Should not raise validation error
        key = APIKeyData(key=SecretStr("${API_KEY}"))
        assert key.key.get_secret_value() == "${API_KEY}"

    def test_api_key_expiration(self):
        now = datetime.now(timezone.utc)

        # Valid expiration (in future)
        key = APIKeyData(key=SecretStr("Aa1!" * 8), created_at=now, expires_at=now + timedelta(days=30))
        assert not key.is_expired

        # Invalid expiration (in past)
        with pytest.raises(ValidationError):
            APIKeyData(key=SecretStr("Aa1!" * 8), created_at=now, expires_at=now - timedelta(days=1))

        # Test expired key
        past_time = now - timedelta(days=2)
        expired_key = APIKeyData(
            key=SecretStr("Aa1!" * 8),
            created_at=past_time,
            expires_at=past_time + timedelta(seconds=1),  # Expires 1 second after creation, but still in the past
        )
        assert expired_key.is_expired

    def test_scope_checking(self):
        key = APIKeyData(
            key=SecretStr("Aa1!" * 8),
            scopes=[Scope(name="api"), Scope(name="read"), Scope(name="user:profile")],
        )

        # Direct scope match
        assert key.has_scope("read")
        assert key.has_scope(Scope(name="api"))

        # Subscope match
        assert key.has_scope("api:v1")
        assert key.has_scope("api:v1:read")
        assert key.has_scope("user:profile:view")

        # No match
        assert not key.has_scope("write")
        assert not key.has_scope("admin")


class TestAPIKeyConfig:
    def test_valid_api_key_config(self):
        config = APIKeyConfig(
            header_name="X-Custom-Key",
            location="header",
            keys=[
                APIKeyData(key=SecretStr("Aa1!" * 8), name="Key 1"),
                APIKeyData(key=SecretStr("Bb2@" * 8), name="Key 2"),
            ],
        )

        assert config.header_name == "X-Custom-Key"
        assert config.location == "header"
        assert len(config.keys) == 2

    def test_header_name_validation(self):
        # Valid header names
        APIKeyConfig(header_name="X-API-Key", keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])
        APIKeyConfig(header_name="Authorization", keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])

        # Invalid header names
        with pytest.raises(ValidationError):
            APIKeyConfig(
                header_name="Invalid Header Name",  # Spaces not allowed
                keys=[APIKeyData(key=SecretStr("Aa1!" * 8))],
            )

    def test_unique_keys_validation(self):
        same_key = SecretStr("Aa1!" * 8)

        with pytest.raises(ValidationError) as exc_info:
            APIKeyConfig(
                keys=[
                    APIKeyData(key=same_key, name="Key 1"),
                    APIKeyData(key=same_key, name="Key 2"),  # Duplicate
                ]
            )
        assert "Duplicate API keys" in str(exc_info.value)

    def test_location_validation(self):
        valid_locations = ["header", "query", "cookie"]

        for location in valid_locations:
            APIKeyConfig(location=location, keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])

        # Invalid location should be caught by Literal type


class TestJWTConfig:
    def test_default_jwt_config(self):
        config = JWTConfig(secret_key=SecretStr("my-secret-key-32-chars-long!!"))

        assert config.algorithm == JWTAlgorithm.HS256
        assert config.expiration == timedelta(hours=1)
        assert config.issuer is None
        assert config.audience is None
        assert "sub" in config.required_claims
        assert "exp" in config.required_claims

    def test_asymmetric_jwt_config(self):
        # Should require public key for RS/ES algorithms
        with pytest.raises(ValidationError) as exc_info:
            JWTConfig(secret_key=SecretStr("private-key"), algorithm=JWTAlgorithm.RS256)
        assert "Public key required" in str(exc_info.value)

        # Valid asymmetric config
        config = JWTConfig(
            secret_key=SecretStr("private-key"),
            algorithm=JWTAlgorithm.RS256,
            public_key=SecretStr("public-key"),
        )
        assert config.algorithm == JWTAlgorithm.RS256
        assert config.public_key is not None

    def test_custom_jwt_config(self):
        config = JWTConfig(
            secret_key=SecretStr("custom-secret-key-32-chars!!!"),
            algorithm=JWTAlgorithm.HS512,
            expiration=timedelta(minutes=30),
            issuer="agentup",
            audience="api",
            required_claims=["sub", "exp", "iat", "custom"],
        )

        assert config.algorithm == JWTAlgorithm.HS512
        assert config.expiration == timedelta(minutes=30)
        assert config.issuer == "agentup"
        assert config.audience == "api"
        assert "custom" in config.required_claims


class TestOAuth2Config:
    def test_valid_oauth2_config(self):
        config = OAuth2Config(
            client_id="client123",
            client_secret=SecretStr("secret123"),
            authorization_url="https://auth.example.com/oauth/authorize",
            token_url="https://auth.example.com/oauth/token",
            redirect_uri="https://app.example.com/callback",
            scopes=["read", "write"],
            jwks_url="https://auth.example.com/.well-known/jwks.json",
        )

        assert config.client_id == "client123"
        assert config.validation_strategy == "jwt"
        assert config.use_pkce is True
        assert "read" in config.scopes

    def test_oauth2_url_validation(self):
        # Valid URLs
        OAuth2Config(
            client_id="client",
            client_secret=SecretStr("secret"),
            authorization_url="https://example.com/auth",
            token_url="https://example.com/token",
            redirect_uri="https://app.com/callback",
            jwks_url="https://example.com/.well-known/jwks.json",  # Required for JWT validation
        )

        # Invalid URLs
        with pytest.raises(ValidationError):
            OAuth2Config(
                client_id="client",
                client_secret=SecretStr("secret"),
                authorization_url="invalid-url",
                token_url="https://example.com/token",
                redirect_uri="https://app.com/callback",
            )

    def test_oauth2_validation_strategy(self):
        # JWT strategy requires jwks_url
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="client",
                client_secret=SecretStr("secret"),
                authorization_url="https://example.com/auth",
                token_url="https://example.com/token",
                redirect_uri="https://app.com/callback",
                validation_strategy="jwt",
                # Missing jwks_url
            )
        assert "jwks_url required" in str(exc_info.value)

        # Introspection strategy requires introspection_endpoint
        with pytest.raises(ValidationError) as exc_info:
            OAuth2Config(
                client_id="client",
                client_secret=SecretStr("secret"),
                authorization_url="https://example.com/auth",
                token_url="https://example.com/token",
                redirect_uri="https://app.com/callback",
                validation_strategy="introspection",
                # Missing introspection_endpoint
            )
        assert "introspection_endpoint required" in str(exc_info.value)


class TestSecurityConfig:
    def test_minimal_security_config(self):
        config = SecurityConfig(auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])})

        assert config.enabled is True
        assert config.require_https is True
        assert AuthType.API_KEY in config.auth
        assert isinstance(config.auth[AuthType.API_KEY], APIKeyConfig)

    def test_multiple_auth_methods(self):
        config = SecurityConfig(
            auth={
                AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))]),
                AuthType.JWT: JWTConfig(secret_key=SecretStr("jwt-secret-key-32-chars-long!!")),
            }
        )

        assert len(config.auth) == 2
        assert AuthType.API_KEY in config.auth
        assert AuthType.JWT in config.auth

    def test_empty_auth_validation(self):
        with pytest.raises(ValidationError) as exc_info:
            SecurityConfig(auth={})
        assert "At least one authentication method must be configured" in str(exc_info.value)

    def test_cors_origins_validation(self):
        # Valid origins
        SecurityConfig(
            auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])},
            allowed_origins=["*"],
        )
        SecurityConfig(
            auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])},
            allowed_origins=["https://example.com", "https://app.example.com"],
        )

        # Invalid origins
        with pytest.raises(ValidationError):
            SecurityConfig(
                auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])},
                allowed_origins=["invalid-origin"],
            )

    def test_security_config_defaults(self):
        config = SecurityConfig(auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8))])})

        assert config.enabled is True
        assert config.require_https is True
        assert config.enable_hsts is True
        assert config.enable_csrf is True
        assert config.audit_logging is True
        assert config.audit_log_retention_days == 90
        assert config.enable_rate_limiting is True
        assert config.rate_limit_requests == 60


class TestAuthContext:
    def test_auth_context_creation(self):
        context = AuthContext(
            authenticated=True,
            auth_type=AuthType.API_KEY,
            auth_result=AuthResult.SUCCESS,
            user_id="user123",
            scopes={Scope(name="read"), Scope(name="api:v1")},
        )

        assert context.authenticated is True
        assert context.auth_type == AuthType.API_KEY
        assert context.user_id == "user123"
        assert len(context.scopes) == 2

    def test_scope_checking_methods(self):
        context = AuthContext(
            authenticated=True,
            scopes={Scope(name="api"), Scope(name="read"), Scope(name="user:profile")},
        )

        # has_scope
        assert context.has_scope("read")
        assert context.has_scope("api:v1")  # Subscope
        assert not context.has_scope("write")

        # has_any_scope
        assert context.has_any_scope(["read", "write"]) is True
        assert context.has_any_scope(["write", "delete"]) is False

        # has_all_scopes
        assert context.has_all_scopes(["read", "api"]) is True
        assert context.has_all_scopes(["read", "write"]) is False


class TestAuditLogEntry:
    def test_audit_log_creation(self):
        entry = AuditLogEntry(
            event_type="auth",
            action=AuditAction.LOGIN,
            result=AuditResult.SUCCESS,
            user_id="user123",
            ip_address="192.168.1.1",
        )

        assert entry.event_type == "auth"
        assert entry.action == AuditAction.LOGIN
        assert entry.result == AuditResult.SUCCESS
        assert entry.user_id == "user123"
        assert entry.ip_address == "192.168.1.1"
        assert isinstance(entry.timestamp, datetime)

    def test_audit_log_formatting(self):
        entry = AuditLogEntry(
            event_type="api",
            action=AuditAction.READ,
            result=AuditResult.SUCCESS,
            user_id="user123",
            resource_type="document",
            resource_id="doc456",
            ip_address="10.0.0.1",
        )

        log_line = entry.to_log_format()

        assert "EVENT=api" in log_line
        assert "ACTION=read" in log_line
        assert "RESULT=success" in log_line
        assert "USER=user123" in log_line
        assert "RESOURCE=document:doc456" in log_line
        assert "IP=10.0.0.1" in log_line

    def test_audit_log_with_error(self):
        entry = AuditLogEntry(
            event_type="auth",
            action=AuditAction.LOGIN,
            result=AuditResult.FAILURE,
            error_message="Invalid credentials",
        )

        log_line = entry.to_log_format()
        assert "RESULT=failure" in log_line
        assert "ERROR=Invalid credentials" in log_line


class TestPermissionModels:
    def test_permission_check(self):
        check = PermissionCheck(
            user_id="user123",
            resource_type="document",
            resource_id="doc456",
            action="read",
            context={"department": "engineering"},
        )

        assert check.user_id == "user123"
        assert check.resource_type == "document"
        assert check.action == "read"
        assert check.context["department"] == "engineering"

    def test_permission_result(self):
        result = PermissionResult(
            granted=False,
            reason="Insufficient privileges",
            required_scopes=["document:read"],
            missing_scopes=["document:read"],
            conditions=["Must be in same department"],
        )

        assert result.granted is False
        assert result.reason == "Insufficient privileges"
        assert "document:read" in result.required_scopes
        assert "document:read" in result.missing_scopes
        assert len(result.conditions) == 1


class TestModelSerialization:
    def test_security_config_serialization(self):
        config = SecurityConfig(
            auth={AuthType.API_KEY: APIKeyConfig(keys=[APIKeyData(key=SecretStr("Aa1!" * 8), name="Test Key")])},
            require_https=False,
        )

        # Serialize to dict
        config_dict = config.model_dump()
        assert "auth" in config_dict
        assert config_dict["require_https"] is False

        # Note: SecretStr values are not included in dict() by default
        # This is correct security behavior

    def test_auth_context_with_sets(self):
        context = AuthContext(authenticated=True, scopes={Scope(name="read"), Scope(name="write")})

        # Should be able to convert to dict (use mode='json' for better serialization of complex types)
        context_dict = context.model_dump(mode="json")
        assert context_dict["authenticated"] is True
        # Sets are converted to lists in serialization
        assert isinstance(context_dict["scopes"], list)
        assert len(context_dict["scopes"]) == 2

    def test_json_serialization_with_datetime(self):
        entry = AuditLogEntry(event_type="test", action=AuditAction.READ, result=AuditResult.SUCCESS)

        # Should serialize datetime properly
        json_str = entry.model_dump_json()
        assert entry.timestamp.isoformat() in json_str
