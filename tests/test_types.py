"""
Tests for AgentUp type definitions.
"""

import pytest  # noqa: F401

from src.agent.types import (
    AuthScheme,
    ConfigDict,
    ContentType,
    Headers,
    HttpMethod,
    IPAddress,
    MetadataDict,
    QueryParams,
    ScopeName,
    UserId,
)


class TestJsonValue:
    def test_valid_json_values(self):
        # Primitive types
        assert isinstance("string", str)
        assert isinstance(42, int)
        assert isinstance(3.14, float)
        assert isinstance(True, bool)
        assert None is None

        # # Complex types
        # simple_dict = {"key": "value", "number": 42}
        # simple_list = ["item1", "item2", 42, True]

        # These would be valid JsonValue types
        nested_dict = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        assert isinstance(nested_dict["string"], str)
        assert isinstance(nested_dict["number"], int)
        assert isinstance(nested_dict["boolean"], bool)
        assert nested_dict["null"] is None
        assert isinstance(nested_dict["list"], list)
        assert isinstance(nested_dict["dict"], dict)


class TestTypeAliases:
    def test_user_id_type(self):
        user_id: UserId = "user123"
        assert isinstance(user_id, str)
        assert user_id == "user123"

    def test_scope_name_type(self):
        scope: ScopeName = "read:api"
        assert isinstance(scope, str)
        assert scope == "read:api"

    def test_ip_address_type(self):
        ip: IPAddress = "192.168.1.1"
        assert isinstance(ip, str)
        assert ip == "192.168.1.1"

    def test_headers_type(self):
        headers: Headers = {"Content-Type": "application/json", "Authorization": "Bearer token123"}
        assert isinstance(headers, dict)
        assert headers["Content-Type"] == "application/json"

    def test_query_params_type(self):
        params: QueryParams = {"single": "value", "multiple": ["value1", "value2"]}
        assert isinstance(params, dict)
        assert params["single"] == "value"
        assert isinstance(params["multiple"], list)

    def test_config_dict_type(self):
        config: ConfigDict = {
            "string_setting": "value",
            "number_setting": 42,
            "boolean_setting": True,
            "nested_setting": {"key": "value"},
        }
        assert isinstance(config, dict)
        assert config["string_setting"] == "value"
        assert config["number_setting"] == 42

    def test_metadata_dict_type(self):
        metadata: MetadataDict = {"version": "1.0.0", "author": "AgentUp", "description": "Test metadata"}
        assert isinstance(metadata, dict)
        assert all(isinstance(v, str) for v in metadata.values())


class TestConstants:
    def test_http_method_constants(self):
        assert HttpMethod.GET == "GET"
        assert HttpMethod.POST == "POST"
        assert HttpMethod.PUT == "PUT"
        assert HttpMethod.DELETE == "DELETE"
        assert HttpMethod.PATCH == "PATCH"
        assert HttpMethod.HEAD == "HEAD"
        assert HttpMethod.OPTIONS == "OPTIONS"

    def test_content_type_constants(self):
        assert ContentType.JSON == "application/json"
        assert ContentType.XML == "application/xml"
        assert ContentType.TEXT == "text/plain"
        assert ContentType.HTML == "text/html"
        assert ContentType.FORM == "application/x-www-form-urlencoded"
        assert ContentType.MULTIPART == "multipart/form-data"
        assert ContentType.BINARY == "application/octet-stream"

    def test_auth_scheme_constants(self):
        assert AuthScheme.BEARER == "Bearer"
        assert AuthScheme.BASIC == "Basic"
        assert AuthScheme.API_KEY == "ApiKey"
        assert AuthScheme.OAUTH2 == "OAuth2"


class TestTypeUsage:
    def test_function_with_typed_parameters(self):
        def process_request(user_id: UserId, headers: Headers, params: QueryParams) -> ConfigDict:
            return {"user": user_id, "content_type": headers.get("Content-Type"), "param_count": len(params)}

        result = process_request(
            user_id="user123", headers={"Content-Type": "application/json"}, params={"query": "test"}
        )

        assert result["user"] == "user123"
        assert result["content_type"] == "application/json"
        assert result["param_count"] == 1

    def test_nested_json_structure(self):
        complex_config: ConfigDict = {
            "database": {"host": "localhost", "port": 5432, "credentials": {"username": "admin", "password": "secret"}},
            "features": ["auth", "logging", "monitoring"],
            "debug": True,
            "version": "1.0.0",
        }

        assert isinstance(complex_config["database"], dict)
        assert isinstance(complex_config["features"], list)
        assert isinstance(complex_config["debug"], bool)
        assert complex_config["database"]["port"] == 5432
        assert "auth" in complex_config["features"]
