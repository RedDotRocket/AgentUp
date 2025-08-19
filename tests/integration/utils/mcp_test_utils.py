"""MCP Integration Test Utilities.

This module provides helper functions for MCP integration testing including
server management, configuration generation, and response validation.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import yaml


class MCPServerManager:
    """Manages MCP weather server lifecycle for testing."""

    def __init__(self, transport: str, port: int = 8123, auth_token: str | None = None):
        self.transport = transport
        self.port = port
        self.auth_token = auth_token
        self.process: subprocess.Popen | None = None
        self.script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "mcp" / "weather_server.py"

    def start(self) -> None:
        """Start the MCP weather server."""
        if self.process:
            raise RuntimeError("Server already running")

        cmd = ["python", str(self.script_path), "--transport", self.transport]

        if self.transport in ["sse", "streamable_http"]:
            cmd.extend(["--port", str(self.port)])
            if self.auth_token:
                cmd.extend(["--auth-token", self.auth_token])

        # Start server in background
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Give server time to start
        time.sleep(2)

        # Check if server started successfully
        # Note: stdio servers may exit immediately if no input is provided, which is normal
        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate()
            # For stdio transport, immediate exit is expected, not a failure
            if self.transport == "stdio":
                # Check if the output indicates successful startup
                if "Starting MCP Weather Server" in stderr or "Available tools" in stderr:
                    # Server started successfully and exited normally
                    pass
                else:
                    raise RuntimeError(f"Stdio server failed to start properly: {stderr}")
            else:
                # For HTTP servers, immediate exit is a failure
                raise RuntimeError(f"Server failed to start: {stderr}")

    def stop(self) -> None:
        """Stop the MCP weather server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class AgentUpServerManager:
    """Manages AgentUp server lifecycle for testing."""

    def __init__(self, config_path: str, port: int = 8000):
        # Ensure we have an absolute path
        self.config_path = os.path.abspath(config_path)
        self.port = port
        self.process: subprocess.Popen | None = None

    def start(self) -> None:
        """Start the AgentUp server."""
        if self.process:
            raise RuntimeError("AgentUp server already running")

        env = os.environ.copy()
        env["AGENT_CONFIG_PATH"] = self.config_path
        env["SERVER_PORT"] = str(self.port)
        # Disable telemetry/tracing that causes hanging in tests
        env["OTEL_SDK_DISABLED"] = "true"
        env["A2A_TELEMETRY_DISABLED"] = "true"

        # Start AgentUp server
        self.process = subprocess.Popen(
            ["uv", "run", "agentup", "run", "--config", self.config_path, "--port", str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        # Wait for server to be ready
        self._wait_for_server()

    def _wait_for_server(self, timeout: int = 30) -> None:
        """Wait for server to be ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = httpx.get(f"http://localhost:{self.port}/health", timeout=1)
                if response.status_code == 200:
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass

            # Check if process died
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(f"AgentUp server failed to start: {stderr}")

            time.sleep(0.5)

        raise TimeoutError(f"AgentUp server did not start within {timeout} seconds")

    def stop(self) -> None:
        """Stop the AgentUp server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def generate_mcp_config(
    transport: str,
    server_name: str = "test",
    auth_token: str | None = None,
    mock_llm: bool = True,
    output_path: str | None = None,
) -> str:
    """Generate AgentUp configuration for MCP testing.

    Args:
        transport: MCP transport type (sse, streamable_http, stdio)
        server_name: Name for the MCP server
        auth_token: Authentication token for HTTP transports
        mock_llm: Whether to use mock LLM provider
        output_path: Path to save config file (uses temp file if not specified)

    Returns:
        Path to the generated configuration file
    """
    config = {
        "name": "MCP Test Agent",
        "description": "Agent for MCP integration testing",
        "version": "1.0.0",
        # Security configuration
        "security": {
            "enabled": True,
            "auth": {"api_key": {"header_name": "X-API-Key", "keys": [{"key": "test-api-key", "scopes": ["admin"]}]}},
            "scope_hierarchy": {"admin": ["*"], "weather:admin": ["weather:read", "alerts:read"]},
        },
        # MCP configuration
        "mcp": {"enabled": True, "client_enabled": True, "servers": []},
        # Logging
        "logging": {"enabled": True, "level": "DEBUG", "format": "text", "console": {"enabled": True, "colors": False}},
    }

    # Configure MCP server based on transport
    server_config = {
        "name": server_name,
        "enabled": True,
        "transport": transport,
        "timeout": 30,
        "tool_scopes": {
            "get_alerts": ["alerts:read"],
            "get_forecast": ["weather:read"],
            f"{server_name}:get_alerts": ["alerts:read"],
            f"{server_name}:get_forecast": ["weather:read"],
        },
    }

    if transport == "stdio":
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "mcp" / "weather_server.py"
        server_config.update({"command": "python", "args": [str(script_path), "--transport", "stdio"]})
    elif transport == "sse":
        server_config["url"] = "http://localhost:8123/sse"
        if auth_token:
            server_config["headers"] = {"Authorization": f"Bearer {auth_token}"}
    elif transport == "streamable_http":
        server_config["url"] = "http://localhost:8123/mcp"
        if auth_token:
            server_config["headers"] = {"Authorization": f"Bearer {auth_token}"}

    config["mcp"]["servers"].append(server_config)

    # Configure LLM provider
    if mock_llm:
        config["ai_provider"] = {
            "provider": "openai",
            "api_key": "sk-test-key-for-integration-tests",
            "model": "gpt-4o-mini",
            "temperature": 0,
        }
    else:
        config["ai_provider"] = {
            "provider": "openai",
            "api_key": "${OPENAI_API_KEY}",
            "model": "gpt-4o-mini",
            "temperature": 0,
        }

    # Save configuration
    if output_path:
        config_path = output_path
    else:
        fd, config_path = tempfile.mkstemp(suffix=".yml", prefix="mcp_test_")
        os.close(fd)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    return config_path


async def send_json_rpc_request(
    url: str, method: str, params: dict[str, Any], api_key: str = "test-api-key", timeout: float = 30.0
) -> dict[str, Any]:
    """Send a JSON-RPC request to AgentUp server.

    Args:
        url: Server URL
        method: JSON-RPC method
        params: Method parameters
        api_key: API key for authentication
        timeout: Request timeout in seconds

    Returns:
        JSON-RPC response
    """
    request_id = f"test_{int(time.time() * 1000)}"

    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": request_id}

    headers = {"Content-Type": "application/json", "X-API-Key": api_key}

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def validate_mcp_tool_response(response: dict[str, Any], expected_tool: str) -> bool:
    """Validate that an MCP tool was called in the response.

    Args:
        response: JSON-RPC response
        expected_tool: Expected tool name

    Returns:
        True if the expected tool was called
    """
    result = response.get("result", {})

    # Check in function calls
    if "function_calls" in result:
        for call in result["function_calls"]:
            if expected_tool in call.get("name", ""):
                return True

    # Check in history for assistant messages
    if "history" in result:
        for message in result["history"]:
            if message.get("role") == "assistant":
                for part in message.get("parts", []):
                    if part.get("kind") == "function_call":
                        if expected_tool in part.get("name", ""):
                            return True

    # Check in artifacts
    if "artifacts" in result:
        for artifact in result["artifacts"]:
            if "function_call" in str(artifact).lower() and expected_tool in str(artifact):
                return True

    return False


def extract_tool_result(response: dict[str, Any]) -> str | None:
    """Extract the result from an MCP tool call response.

    Args:
        response: JSON-RPC response

    Returns:
        Tool result text or None
    """
    result = response.get("result", {})

    # Check in history for tool results
    if "history" in result:
        for message in result["history"]:
            if message.get("role") == "tool":
                for part in message.get("parts", []):
                    if part.get("kind") == "text":
                        return part.get("text")

    # Check for direct result
    if "text" in result:
        return result["text"]

    # Check in artifacts
    if "artifacts" in result:
        for artifact in result["artifacts"]:
            if isinstance(artifact, dict) and "text" in artifact:
                return artifact["text"]

    return None
