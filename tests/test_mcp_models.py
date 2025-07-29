"""
Tests for MCP support models.

This module tests all MCP-related Pydantic models for validation,
serialization, and business logic.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from src.agent.mcp_support.model import (
    MCPCapability,
    MCPCapabilityValidator,
    MCPMessage,
    MCPMessageType,
    MCPResource,
    MCPResourceType,
    MCPResourceValidator,
    MCPSession,
    MCPSessionState,
    MCPSessionValidator,
    MCPTool,
    MCPToolType,
    MCPToolValidator,
    create_mcp_validator,
)


class TestMCPResource:
    def test_valid_resource_creation(self):
        resource = MCPResource(
            name="test-resource",
            uri="agent://test",
            description="A test resource",
            mime_type="text/plain",
            resource_type=MCPResourceType.TEXT,
            text="Hello, world!",
        )

        assert resource.name == "test-resource"
        assert resource.uri == "agent://test"
        assert resource.description == "A test resource"
        assert resource.resource_type == MCPResourceType.TEXT
        assert resource.text == "Hello, world!"
        assert resource.size_bytes == len(b"Hello, world!")

    def test_binary_resource_creation(self):
        blob_data = b"binary data"
        resource = MCPResource(
            name="binary-resource",
            uri="file:///test.bin",
            resource_type=MCPResourceType.BINARY,
            blob=blob_data,
        )

        assert resource.resource_type == MCPResourceType.BINARY
        assert resource.blob == blob_data
        assert resource.size_bytes == len(blob_data)
        assert resource.is_binary is True

    def test_resource_uri_validation(self):
        # Valid URIs
        valid_uris = [
            "file:///test.txt",
            "http://example.com/resource",
            "https://example.com/resource",
            "agent://info",
            "mcp://server/resource",
        ]

        for uri in valid_uris:
            resource = MCPResource(name="test", uri=uri, text="test")
            assert resource.uri == uri

        # Invalid URI
        with pytest.raises(ValidationError) as exc_info:
            MCPResource(name="test", uri="invalid://test", text="test")
        assert "URI must use supported scheme" in str(exc_info.value)

    def test_mime_type_validation(self):
        # Valid MIME type
        resource = MCPResource(name="test", uri="agent://test", mime_type="application/json", text="test")
        assert resource.mime_type == "application/json"

        # Invalid MIME type
        with pytest.raises(ValidationError) as exc_info:
            MCPResource(name="test", uri="agent://test", mime_type="invalid", text="test")
        assert "MIME type must be in format 'type/subtype'" in str(exc_info.value)

    def test_text_resource_validation(self):
        # Text resource without text content should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPResource(
                name="test",
                uri="agent://test",
                resource_type=MCPResourceType.TEXT,
            )
        assert "Text resources must have text content" in str(exc_info.value)

    def test_binary_resource_validation(self):
        # Binary resource without blob data should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPResource(
                name="test",
                uri="agent://test",
                resource_type=MCPResourceType.BINARY,
            )
        assert "Binary resources must have blob data" in str(exc_info.value)

    def test_human_readable_size(self):
        resource = MCPResource(name="test", uri="agent://test", text="a" * 1024, size_bytes=1024)
        assert "1.0 KB" in resource.human_readable_size

        large_resource = MCPResource(name="test", uri="agent://test", text="test", size_bytes=1024 * 1024)
        assert "1.0 MB" in large_resource.human_readable_size

    def test_resource_serialization(self):
        resource = MCPResource(
            name="test-resource",
            uri="agent://test",
            description="A test resource",
            text="Hello, world!",
        )

        data = resource.model_dump()
        assert data["name"] == "test-resource"
        assert data["uri"] == "agent://test"
        assert data["text"] == "Hello, world!"

        # Round trip
        resource2 = MCPResource.model_validate(data)
        assert resource2.name == resource.name
        assert resource2.uri == resource.uri
        assert resource2.text == resource.text


class TestMCPTool:
    def test_valid_tool_creation(self):
        tool = MCPTool(
            name="test_function",
            description="A test function for MCP",
            tool_type=MCPToolType.FUNCTION,
            input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
            required_scopes=["read", "execute"],
        )

        assert tool.name == "test_function"
        assert tool.description == "A test function for MCP"
        assert tool.tool_type == MCPToolType.FUNCTION
        assert tool.has_required_scopes is True
        assert tool.security_level == "low"

    def test_tool_name_validation(self):
        # Valid names
        valid_names = ["test_function", "my-tool", "getData", "_private"]
        for name in valid_names:
            tool = MCPTool(name=name, description="Test tool")
            assert tool.name == name

        # Invalid names
        invalid_names = ["123invalid", "test function", "test@tool"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                MCPTool(name=name, description="Test tool")

    def test_schema_validation(self):
        # Valid schema
        tool = MCPTool(
            name="test_tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
        )
        assert tool.input_schema["type"] == "object"

        # Invalid schema (missing type)
        with pytest.raises(ValidationError) as exc_info:
            MCPTool(
                name="test_tool",
                description="Test tool",
                input_schema={"properties": {}},
            )
        assert "Schema must have 'type' property" in str(exc_info.value)

    def test_version_validation(self):
        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha", "1.0.0+build"]
        for version in valid_versions:
            tool = MCPTool(name="test", description="Test", version=version)
            assert tool.version == version

        # Invalid version
        with pytest.raises(ValidationError):
            MCPTool(name="test", description="Test", version="1.0")

    def test_security_level_calculation(self):
        # Public tool (no scopes)
        tool = MCPTool(name="public", description="Public tool")
        assert tool.security_level == "public"

        # Low security (1-2 scopes)
        tool = MCPTool(name="low", description="Low security", required_scopes=["read"])
        assert tool.security_level == "low"

        # Medium security (3-5 scopes)
        tool = MCPTool(
            name="medium",
            description="Medium security",
            required_scopes=["read", "write", "delete"],
        )
        assert tool.security_level == "medium"

        # High security (6+ scopes)
        tool = MCPTool(
            name="high",
            description="High security",
            required_scopes=["read", "write", "delete", "admin", "root", "execute"],
        )
        assert tool.security_level == "high"

    def test_tool_serialization(self):
        tool = MCPTool(
            name="test_function",
            description="A test function",
            input_schema={"type": "object"},
            required_scopes=["read"],
        )

        data = tool.model_dump()
        assert data["name"] == "test_function"
        assert data["description"] == "A test function"
        assert data["required_scopes"] == ["read"]

        # Round trip
        tool2 = MCPTool.model_validate(data)
        assert tool2.name == tool.name
        assert tool2.description == tool.description


class TestMCPMessage:
    def test_request_message_creation(self):
        message = MCPMessage(
            id="req-123",
            message_type=MCPMessageType.REQUEST,
            method="tools/list",
            params={"filter": "enabled"},
        )

        assert message.id == "req-123"
        assert message.message_type == MCPMessageType.REQUEST
        assert message.method == "tools/list"
        assert message.is_request is True
        assert message.is_response is False

    def test_response_message_creation(self):
        message = MCPMessage(
            id="resp-123",
            message_type=MCPMessageType.RESPONSE,
            result={"tools": ["tool1", "tool2"]},
        )

        assert message.id == "resp-123"
        assert message.message_type == MCPMessageType.RESPONSE
        assert message.result == {"tools": ["tool1", "tool2"]}
        assert message.is_response is True

    def test_error_message_creation(self):
        message = MCPMessage(
            id="err-123",
            message_type=MCPMessageType.ERROR,
            error={"code": -32602, "message": "Invalid params"},
        )

        assert message.message_type == MCPMessageType.ERROR
        assert message.is_error is True
        assert message.error["code"] == -32602

    def test_jsonrpc_version_validation(self):
        # Valid version
        message = MCPMessage(id="test", message_type=MCPMessageType.REQUEST, method="test", jsonrpc="2.0")
        assert message.jsonrpc == "2.0"

        # Invalid version
        with pytest.raises(ValidationError) as exc_info:
            MCPMessage(id="test", message_type=MCPMessageType.REQUEST, method="test", jsonrpc="1.0")
        assert "Only JSON-RPC 2.0 is supported" in str(exc_info.value)

    def test_request_message_validation(self):
        # Request without method should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPMessage(id="test", message_type=MCPMessageType.REQUEST)
        assert "Request messages must have method" in str(exc_info.value)

        # Request with result should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPMessage(
                id="test",
                message_type=MCPMessageType.REQUEST,
                method="test",
                result="invalid",
            )
        assert "Request messages cannot have result or error" in str(exc_info.value)

    def test_response_message_validation(self):
        # Response with method should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPMessage(
                id="test",
                message_type=MCPMessageType.RESPONSE,
                method="invalid",
                result="test",
            )
        assert "Response messages cannot have method" in str(exc_info.value)

        # Response without result or error should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPMessage(id="test", message_type=MCPMessageType.RESPONSE)
        assert "Response messages must have result or error" in str(exc_info.value)


class TestMCPSession:
    def test_valid_session_creation(self):
        session = MCPSession(
            session_id="session-123",
            server_name="test-server",
            state=MCPSessionState.CONNECTED,
            capabilities={"tools": True, "resources": True},
        )

        assert session.session_id == "session-123"
        assert session.server_name == "test-server"
        assert session.state == MCPSessionState.CONNECTED
        assert session.is_active is True
        assert session.is_healthy is True

    def test_session_id_validation(self):
        # Valid session IDs
        valid_ids = ["session-123", "test_session", "session123", "a-b-c"]
        for session_id in valid_ids:
            session = MCPSession(session_id=session_id, server_name="test")
            assert session.session_id == session_id

        # Invalid session ID
        with pytest.raises(ValidationError):
            MCPSession(session_id="invalid session!", server_name="test")

    def test_session_state_validation(self):
        # Error state without error message should fail
        with pytest.raises(ValidationError) as exc_info:
            MCPSession(
                session_id="test",
                server_name="test",
                state=MCPSessionState.ERROR,
            )
        assert "Error state requires error message" in str(exc_info.value)

        # Valid error state
        session = MCPSession(
            session_id="test",
            server_name="test",
            state=MCPSessionState.ERROR,
            error_message="Connection failed",
        )
        assert session.error_message == "Connection failed"

    def test_session_timeout_check(self):
        # Recent session should be healthy
        session = MCPSession(
            session_id="test",
            server_name="test",
            timeout_seconds=300,
        )
        assert session.is_healthy is True

        # Old session should be unhealthy
        old_time = datetime.utcnow() - timedelta(seconds=400)
        session = MCPSession(
            session_id="test",
            server_name="test",
            timeout_seconds=300,
            last_activity=old_time,
        )
        assert session.is_healthy is False

    def test_session_activity_update(self):
        session = MCPSession(session_id="test", server_name="test")
        old_activity = session.last_activity

        # Small delay to ensure timestamp difference
        import time

        time.sleep(0.01)

        session.update_activity()
        assert session.last_activity > old_activity

    def test_session_tool_and_resource_counts(self):
        from src.agent.mcp_support.model import MCPResource, MCPTool

        tools = [
            MCPTool(name="tool1", description="Tool 1"),
            MCPTool(name="tool2", description="Tool 2"),
        ]
        resources = [
            MCPResource(name="resource1", uri="agent://resource1", text="test1"),
        ]

        session = MCPSession(
            session_id="test",
            server_name="test",
            available_tools=tools,
            available_resources=resources,
        )

        assert session.tool_count == 2
        assert session.resource_count == 1


class TestMCPCapability:
    def test_valid_capability_creation(self):
        capability = MCPCapability(
            name="tools",
            version="1.0.0",
            description="Tool management capability",
            supported_methods=["tools/list", "tools/call"],
            supported_notifications=["tools/updated"],
        )

        assert capability.name == "tools"
        assert capability.version == "1.0.0"
        assert capability.is_stable is True
        assert capability.method_count == 2
        assert capability.notification_count == 1

    def test_capability_name_validation(self):
        # Valid names
        valid_names = ["tools", "resources", "file-system", "test_capability"]
        for name in valid_names:
            capability = MCPCapability(name=name)
            assert capability.name == name

        # Invalid names (starting with number)
        with pytest.raises(ValidationError):
            MCPCapability(name="123invalid")

    def test_version_validation(self):
        # Valid versions
        capability = MCPCapability(
            name="test",
            version="2.1.0",
            required_client_version="1.0.0",
        )
        assert capability.version == "2.1.0"
        assert capability.required_client_version == "1.0.0"

        # Invalid version
        with pytest.raises(ValidationError):
            MCPCapability(name="test", version="invalid")

    def test_stability_check(self):
        # Stable capability
        stable = MCPCapability(name="stable")
        assert stable.is_stable is True

        # Experimental capability
        experimental = MCPCapability(name="experimental", experimental=True)
        assert experimental.is_stable is False

        # Deprecated capability
        deprecated = MCPCapability(name="deprecated", deprecated=True)
        assert deprecated.is_stable is False


class TestMCPValidators:
    def test_mcp_resource_validator(self):
        validator = MCPResourceValidator(MCPResource)

        # Large resource should generate warning
        large_resource = MCPResource(
            name="large",
            uri="agent://large",
            text="test",
            size_bytes=15 * 1024 * 1024,  # 15MB
        )
        result = validator.validate(large_resource)
        assert not result.valid or result.warnings
        assert any("Large resource may impact performance" in w for w in result.warnings)

        # File URI should generate suggestion
        file_resource = MCPResource(
            name="file",
            uri="file:///test.txt",
            text="test",
        )
        result = validator.validate(file_resource)
        assert any("security implications" in s for s in result.suggestions)

    def test_mcp_tool_validator(self):
        validator = MCPToolValidator(MCPTool)

        # Dangerous tool name should generate warning
        dangerous_tool = MCPTool(
            name="delete_everything",
            description="Deletes everything",
        )
        result = validator.validate(dangerous_tool)
        assert any("dangerous pattern" in w for w in result.warnings)

        # Function tool without scopes should generate suggestion
        unsecured_tool = MCPTool(
            name="test_function",
            description="Test function",
            tool_type=MCPToolType.FUNCTION,
        )
        result = validator.validate(unsecured_tool)
        assert any("permission scopes" in s for s in result.suggestions)

    def test_mcp_session_validator(self):
        validator = MCPSessionValidator(MCPSession)

        # Stale session should generate warning
        old_time = datetime.utcnow() - timedelta(seconds=200)
        stale_session = MCPSession(
            session_id="stale",
            server_name="test",
            timeout_seconds=300,
            last_activity=old_time,
        )
        result = validator.validate(stale_session)
        assert any("stale" in w for w in result.warnings)

        # Ready session without capabilities should generate warning
        empty_session = MCPSession(
            session_id="empty",
            server_name="test",
            state=MCPSessionState.READY,
        )
        result = validator.validate(empty_session)
        assert any("capabilities" in w for w in result.warnings)

    def test_mcp_capability_validator(self):
        validator = MCPCapabilityValidator(MCPCapability)

        # Experimental capability without description should generate suggestion
        experimental = MCPCapability(
            name="experimental",
            experimental=True,
        )
        result = validator.validate(experimental)
        assert any("clear descriptions" in s for s in result.suggestions)

        # Capability with no methods or notifications should generate warning
        empty_capability = MCPCapability(name="empty")
        result = validator.validate(empty_capability)
        assert any("methods or notifications" in w for w in result.warnings)

    def test_composite_mcp_validator(self):
        validator = create_mcp_validator()

        # Test with valid resource
        resource = MCPResource(
            name="test",
            uri="agent://test",
            text="Hello, world!",
        )
        result = validator.validate(resource)
        assert result.valid is True


class TestMCPModelSerialization:
    def test_mcp_resource_json_round_trip(self):
        resource = MCPResource(
            name="test-resource",
            uri="agent://test",
            description="A test resource",
            mime_type="application/json",
            resource_type=MCPResourceType.JSON,
            text='{"key": "value"}',
            metadata={"created_by": "test"},
        )

        # Serialize to JSON
        json_data = resource.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        resource2 = MCPResource.model_validate_json(json_data)
        assert resource2.name == resource.name
        assert resource2.uri == resource.uri
        assert resource2.metadata == resource.metadata

    def test_mcp_tool_json_round_trip(self):
        tool = MCPTool(
            name="test_tool",
            description="A comprehensive test tool",
            input_schema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"],
            },
            required_scopes=["read", "execute"],
            examples=[{"param": "example"}],
        )

        # Serialize to JSON
        json_data = tool.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        tool2 = MCPTool.model_validate_json(json_data)
        assert tool2.name == tool.name
        assert tool2.input_schema == tool.input_schema
        assert tool2.required_scopes == tool.required_scopes

    def test_mcp_session_json_round_trip(self):
        session = MCPSession(
            session_id="test-session",
            server_name="test-server",
            state=MCPSessionState.READY,
            capabilities={"tools": True, "resources": False},
            metadata={"client_version": "1.0.0"},
        )

        # Serialize to JSON
        json_data = session.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        session2 = MCPSession.model_validate_json(json_data)
        assert session2.session_id == session.session_id
        assert session2.capabilities == session.capabilities
        assert session2.state == session.state
