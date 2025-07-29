import asyncio
from typing import Any
from unittest.mock import Mock


class MockLLMResponse:
    def __init__(self, content: str, usage: dict[str, int] | None = None):
        self.content = content
        self.usage = usage or {"total_tokens": 100, "input_tokens": 50, "output_tokens": 50}
        self.model = "mock-model"
        self.finish_reason = "stop"

    def strip(self):
        return self.content.strip()

    def __str__(self):
        return self.content


class MockOpenAIService:
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["Mock OpenAI response"]
        self.call_count = 0
        self.last_request = None

    async def generate_response(self, messages: list[dict[str, str]], **kwargs) -> MockLLMResponse:
        self.last_request = {"messages": messages, **kwargs}
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockLLMResponse(response_text)

    def chat_completion(self, messages: list[dict[str, str]], **kwargs):
        return asyncio.run(self.generate_response(messages, **kwargs))


class MockAnthropicService:
    def __init__(self, responses: list[str] | None = None):
        self.responses = responses or ["Mock Anthropic response"]
        self.call_count = 0
        self.last_request = None

    async def generate_response(self, messages: list[dict[str, str]], **kwargs) -> MockLLMResponse:
        self.last_request = {"messages": messages, **kwargs}
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockLLMResponse(response_text)


class MockOllamaService:
    def __init__(self, responses: list[str] | None = None, available: bool = True):
        self.responses = responses or ["Mock Ollama response"]
        self.call_count = 0
        self.last_request = None
        self.available = available

    async def generate_response(self, messages: list[dict[str, str]], **kwargs) -> MockLLMResponse:
        if not self.available:
            raise ConnectionError("Ollama service not available")

        self.last_request = {"messages": messages, **kwargs}
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return MockLLMResponse(response_text)

    async def check_connection(self) -> bool:
        return self.available


class MockValkeyService:
    def __init__(self):
        self.data = {}
        self.call_count = 0

    async def get(self, key: str) -> str | None:
        self.call_count += 1
        return self.data.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        self.call_count += 1
        self.data[key] = value
        return True

    async def delete(self, key: str) -> bool:
        self.call_count += 1
        if key in self.data:
            del self.data[key]
            return True
        return False

    def clear(self):
        self.data.clear()


class MockDatabaseService:
    def __init__(self):
        self.queries = []
        self.results = []
        self.connected = True

    async def execute(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.queries.append({"query": query, "params": params})
        if self.results:
            return self.results.pop(0)
        return {"rows": [], "count": 0}

    async def connect(self) -> bool:
        return self.connected

    async def disconnect(self):
        self.connected = False

    def set_results(self, results: list[dict[str, Any]]):
        self.results = results


class MockServiceRegistry:
    def __init__(self):
        self.services = {}
        self.llm_services = {}
        self.cache_services = {}
        self.database_services = {}

    def register_service(self, name: str, service: Any, service_type: str = "generic"):
        self.services[name] = service

        if service_type == "llm":
            self.llm_services[name] = service
        elif service_type == "cache":
            self.cache_services[name] = service
        elif service_type == "database":
            self.database_services[name] = service

    def get_service(self, name: str) -> Any | None:
        return self.services.get(name)

    def get_llm(self, name: str) -> Any | None:
        return self.llm_services.get(name)

    def get_cache(self, name: str) -> Any | None:
        return self.cache_services.get(name)

    def get_database(self, name: str) -> Any | None:
        return self.database_services.get(name)

    def list_services(self) -> list[str]:
        return list(self.services.keys())


class MockA2ARequest:
    def __init__(
        self, method: str = "send_message", params: dict[str, Any] | None = None, request_id: str = "test-123"
    ):
        self.method = method
        self.params = params or {}
        self.id = request_id
        self.jsonrpc = "2.0"


class MockA2AResponse:
    def __init__(
        self, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None, request_id: str = "test-123"
    ):
        self.result = result
        self.error = error
        self.id = request_id
        self.jsonrpc = "2.0"


class MockMCPClient:
    def __init__(self):
        self.connected = False
        self.servers = {}
        self.tools = {}
        self.resources = {}

    async def connect(self, server_name: str, command: str, args: list[str], env: dict[str, str]):
        self.connected = True
        self.servers[server_name] = {"command": command, "args": args, "env": env, "connected": True}

    async def list_tools(self, server_name: str) -> list[dict[str, Any]]:
        return self.tools.get(server_name, [])

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": f"Mock result from {tool_name}"}], "isError": False}

    def add_tool(self, server_name: str, tool_name: str, schema: dict[str, Any]):
        if server_name not in self.tools:
            self.tools[server_name] = []
        self.tools[server_name].append(
            {"name": tool_name, "description": f"Mock tool {tool_name}", "inputSchema": schema}
        )


def create_mock_services() -> MockServiceRegistry:
    registry = MockServiceRegistry()

    # Add LLM services
    registry.register_service("openai", MockOpenAIService(), "llm")
    registry.register_service("anthropic", MockAnthropicService(), "llm")
    registry.register_service("ollama", MockOllamaService(), "llm")

    # Add cache services
    registry.register_service("valkey", MockValkeyService(), "cache")

    return registry


def create_mock_llm_manager():
    mock_manager = Mock()
    mock_manager.get_provider.return_value = MockOpenAIService()
    mock_manager.list_providers.return_value = ["openai", "anthropic", "ollama"]
    mock_manager.is_available.return_value = True
    return mock_manager


def create_mock_config_manager():
    mock_manager = Mock()
    mock_manager.load_config.return_value = {
        "agent": {"name": "test-agent"},
        "ai": {"enabled": True, "llm_service": "openai", "model": "gpt-4o-mini"},
        "services": {"openai": {"type": "llm", "provider": "openai"}},
    }
    mock_manager.validate_config.return_value = True
    mock_manager.get_service_config.return_value = {"type": "llm", "provider": "openai"}
    return mock_manager


def patch_llm_services():
    from unittest.mock import patch

    def patcher():
        patches = [
            patch("src.agent.llm_providers.openai.OpenAIProvider", MockOpenAIService),
            patch("src.agent.llm_providers.anthropic.AnthropicProvider", MockAnthropicService),
            patch("src.agent.llm_providers.ollama.OllamaProvider", MockOllamaService),
        ]

        for p in patches:
            p.start()

        yield

        for p in patches:
            p.stop()

    return patcher()
