"""Mock LLM Provider for MCP Integration Testing.

This module provides a deterministic LLM provider that returns predictable
responses for testing MCP tool integration without relying on external APIs.
"""

import json
import re
from typing import Any


class MockLLMProvider:
    """Mock LLM provider that returns deterministic responses for testing."""

    def __init__(self):
        self.conversation_history: list[dict[str, Any]] = []

    def generate_response(
        self, messages: list[dict[str, Any]], available_tools: list[dict[str, Any]] | None = None, **kwargs
    ) -> dict[str, Any]:
        """Generate a mock response based on the user's message.

        Args:
            messages: Conversation messages
            available_tools: Available function tools
            **kwargs: Additional parameters

        Returns:
            Mock response with tool calls or text response
        """
        if not messages:
            return self._create_text_response("I'm ready to help!")

        last_message = messages[-1]
        user_content = last_message.get("content", "")

        # Extract tool calls based on message content
        tool_call = self._determine_tool_call(user_content)

        if tool_call and available_tools:
            # Return function call response
            return self._create_function_call_response(tool_call)
        else:
            # Return text response
            return self._create_text_response(f"I understand you're asking about: {user_content}")

    def _determine_tool_call(self, content: str) -> dict[str, Any] | None:
        """Determine which tool to call based on message content.

        Args:
            content: User message content

        Returns:
            Tool call information or None
        """
        content_lower = content.lower()

        # Direct coordinate patterns - CHECK FIRST to avoid location name lookups
        coord_pattern = r"(?:weather|forecast).*?(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
        match = re.search(coord_pattern, content_lower)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            return {"name": "get_forecast", "arguments": {"latitude": lat, "longitude": lon}}

        # Weather alerts patterns - CHECK SECOND to avoid false matches with forecast patterns
        alert_patterns = [
            r"alert.*(?:in|for)\s+([a-z]{2})\b",
            r"alerts.*(?:in|for)\s+([a-z]{2})\b",  # Added "alerts" plural
            r"warning.*(?:in|for)\s+([a-z]{2})\b",
            r"warnings.*(?:in|for)\s+([a-z]{2})\b",  # Added "warnings" plural
            r"get.*alert.*(?:in|for)\s+([a-z]{2})\b",  # Added "get" prefix
            r"storm.*(?:in|for)\s+([a-z]{2})\b",
            r"(?:weather\s+)?alert.*\s+([a-z]{2})\b",  # Fixed pattern
        ]

        for pattern in alert_patterns:
            match = re.search(pattern, content_lower)
            if match:
                state = match.group(1).upper()
                return {"name": "get_alerts", "arguments": {"state": state}}

        # Weather forecast patterns - CHECK LAST to avoid conflicts
        forecast_patterns = [
            r"weather.*(?:in|for)\s+(.+?)(?:\s|$|,|\?)",
            r"forecast.*(?:in|for)\s+(.+?)(?:\s|$|,|\?)",
            r"temperature.*(?:in|for)\s+(.+?)(?:\s|$|,|\?)",
            r"what.*weather.*(.+?)(?:\s|$|,|\?)",
        ]

        for pattern in forecast_patterns:
            match = re.search(pattern, content_lower)
            if match:
                location = match.group(1).strip()
                # Skip if this looks like an alert request that didn't match above
                if "alert" in location or "warning" in location:
                    continue
                # Skip if this looks like coordinates that didn't match above (safety check)
                if re.search(r"\d+\.?\d*\s*,\s*-?\d+\.?\d*", location):
                    continue
                lat, lon = self._get_coordinates_for_location(location)
                return {"name": "get_forecast", "arguments": {"latitude": lat, "longitude": lon}}

        return None

    def _get_coordinates_for_location(self, location: str) -> tuple[float, float]:
        """Get coordinates for a location (hardcoded for testing).

        Args:
            location: Location name

        Returns:
            Latitude and longitude tuple
        """
        # Hardcoded coordinates for common test locations
        locations = {
            "seattle": (47.6062, -122.3321),
            "new york": (40.7128, -74.0060),
            "los angeles": (34.0522, -118.2437),
            "chicago": (41.8781, -87.6298),
            "miami": (25.7617, -80.1918),
            "denver": (39.7392, -104.9903),
            "san francisco": (37.7749, -122.4194),
            "boston": (42.3601, -71.0589),
            # Handle partial matches
            "york": (40.7128, -74.0060),
            "angeles": (34.0522, -118.2437),
            "francisco": (37.7749, -122.4194),
        }

        location_lower = location.lower().strip()

        # Exact match
        if location_lower in locations:
            return locations[location_lower]

        # Partial match
        for loc_name, coords in locations.items():
            if loc_name in location_lower or location_lower in loc_name:
                return coords

        # Default to Seattle if no match
        return locations["seattle"]

    def _create_function_call_response(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Create a function call response.

        Args:
            tool_call: Tool call information

        Returns:
            Function call response
        """
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "function_call": {"name": tool_call["name"], "arguments": json.dumps(tool_call["arguments"])},
                    },
                    "finish_reason": "function_call",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }

    def _create_text_response(self, content: str) -> dict[str, Any]:
        """Create a text response.

        Args:
            content: Response content

        Returns:
            Text response
        """
        return {
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        }

    def create_completion(self, **kwargs) -> dict[str, Any]:
        """Create a completion (OpenAI-compatible interface).

        Args:
            **kwargs: Completion parameters

        Returns:
            Completion response
        """
        messages = kwargs.get("messages", [])
        tools = kwargs.get("tools", [])

        # Convert tools format if needed
        available_tools = []
        if tools:
            for tool in tools:
                if "function" in tool:
                    available_tools.append(tool["function"])

        return self.generate_response(messages, available_tools, **kwargs)


# Factory function for creating mock LLM provider
def create_mock_llm_provider() -> MockLLMProvider:
    """Create a mock LLM provider instance.

    Returns:
        MockLLMProvider instance
    """
    return MockLLMProvider()


# Test cases for mock responses
TEST_CASES = [
    {
        "input": "What's the weather in Seattle?",
        "expected_tool": "get_forecast",
        "expected_args": {"latitude": 47.6062, "longitude": -122.3321},
    },
    {"input": "Get weather alerts for CA", "expected_tool": "get_alerts", "expected_args": {"state": "CA"}},
    {
        "input": "Show me the forecast for New York",
        "expected_tool": "get_forecast",
        "expected_args": {"latitude": 40.7128, "longitude": -74.0060},
    },
    {"input": "Any storm warnings in TX?", "expected_tool": "get_alerts", "expected_args": {"state": "TX"}},
    {
        "input": "Weather forecast for coordinates 40.7, -74.0",
        "expected_tool": "get_forecast",
        "expected_args": {"latitude": 40.7, "longitude": -74.0},
    },
    {
        "input": "Hello there!",
        "expected_tool": None,
        "expected_response": "I understand you're asking about: Hello there!",
    },
]


def test_mock_llm_provider():
    """Test the mock LLM provider with various inputs."""
    provider = create_mock_llm_provider()

    # Sample available tools
    available_tools = [
        {
            "name": "get_forecast",
            "description": "Get weather forecast",
            "parameters": {
                "type": "object",
                "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}},
            },
        },
        {
            "name": "get_alerts",
            "description": "Get weather alerts",
            "parameters": {"type": "object", "properties": {"state": {"type": "string"}}},
        },
    ]

    for test_case in TEST_CASES:
        messages = [{"role": "user", "content": test_case["input"]}]
        response = provider.generate_response(messages, available_tools)

        if test_case["expected_tool"]:
            # Should be a function call
            assert response["choices"][0]["finish_reason"] == "function_call"
            func_call = response["choices"][0]["message"]["function_call"]
            assert func_call["name"] == test_case["expected_tool"]

            args = json.loads(func_call["arguments"])
            expected_args = test_case["expected_args"]

            for key, expected_value in expected_args.items():
                assert (
                    abs(args[key] - expected_value) < 0.001
                    if isinstance(expected_value, float)
                    else args[key] == expected_value
                )
        else:
            # Should be a text response
            assert response["choices"][0]["finish_reason"] == "stop"
            assert test_case["expected_response"] in response["choices"][0]["message"]["content"]

    print("All test cases passed!")


if __name__ == "__main__":
    test_mock_llm_provider()
