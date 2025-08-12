import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import structlog
from httpx import AsyncClient

from .models import A2ARequest, A2AResponse, Message, MessagePart

logger = structlog.get_logger(__name__)


class A2AClient:
    """Client for communicating with AgentUp agents via A2A protocol.

    This client MUST be used as an async context manager to ensure proper resource cleanup:

    Example:
        async with A2AClient("http://localhost:8000", api_key="your-key") as client:
            response = await client.send_message("Hello, agent!")

    Using the client outside of a context manager will raise a RuntimeError.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """Initialize the A2A client.

        Args:
            base_url: Base URL of the AgentUp agent
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.client: AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
        return None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def send_message(
        self,
        message: str,
        context_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a message to AgentUp agent via JSON-RPC.

        Args:
            message: The message text to send
            context_id: Optional context ID for conversation continuity
            message_id: Optional message ID (generated if not provided)

        Returns:
            The A2A response as a dictionary

        Raises:
            RuntimeError: If client is not properly initialized via context manager
        """
        if not self.client:
            raise RuntimeError(
                "A2AClient must be used as an async context manager. "
                "Use 'async with A2AClient(...) as client:' to ensure proper resource cleanup."
            )

        message_id = message_id or f"msg-{uuid.uuid4()}"
        request_id = f"req-{uuid.uuid4()}"

        # Build A2A message structure
        message_obj = Message(
            role="user",
            parts=[MessagePart(kind="text", text=message)],
            message_id=message_id,
            kind="message",
        )

        # Build JSON-RPC request
        request = A2ARequest(
            jsonrpc="2.0",
            method="message/send",
            params={"message": message_obj.model_dump()},
            id=request_id,
        )

        # Add context_id if provided
        if context_id:
            request.params["context_id"] = context_id

        logger.debug(
            "Sending A2A message",
            request_id=request_id,
            message_id=message_id,
            context_id=context_id,
        )

        # Send request with retries
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    self.base_url,
                    json=request.model_dump(),
                    headers=self._get_headers(),
                )
                response.raise_for_status()

                result = response.json()
                logger.debug("Received A2A response", request_id=request_id)

                # Parse and validate response
                a2a_response = A2AResponse(**result)
                if a2a_response.error:
                    logger.error(
                        "A2A error response",
                        error=a2a_response.error,
                        request_id=request_id,
                    )
                    raise Exception(f"A2A Error: {a2a_response.error}")

                return a2a_response.result or {}

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"HTTP error on attempt {attempt + 1}",
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.error(f"Error sending message: {e}", attempt=attempt + 1)
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("Max retries exceeded")

    async def stream_message(
        self,
        message: str,
        context_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream responses from AgentUp agent via SSE.

        Args:
            message: The message text to send
            context_id: Optional context ID for conversation continuity

        Yields:
            Chunks of the streaming response

        Raises:
            RuntimeError: If client is not properly initialized via context manager
        """
        if not self.client:
            raise RuntimeError(
                "A2AClient must be used as an async context manager. "
                "Use 'async with A2AClient(...) as client:' to ensure proper resource cleanup."
            )

        message_id = f"msg-{uuid.uuid4()}"
        request_id = f"req-{uuid.uuid4()}"

        # Build streaming request
        message_obj = Message(
            role="user",
            parts=[MessagePart(kind="text", text=message)],
            message_id=message_id,
            kind="message",
        )

        request = A2ARequest(
            jsonrpc="2.0",
            method="message/send_streaming",
            params={"message": message_obj.model_dump()},
            id=request_id,
        )

        if context_id:
            request.params["context_id"] = context_id

        logger.debug(
            "Starting streaming A2A message",
            request_id=request_id,
            message_id=message_id,
        )

        # Send streaming request
        async with self.client.stream(
            "POST",
            self.base_url,
            json=request.model_dump(),
            headers=self._get_headers(),
        ) as response:
            response.raise_for_status()

            # Process SSE stream
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {e}", line=line)

    async def get_agent_card(self) -> dict[str, Any]:
        """Fetch the AgentCard from the AgentUp agent.

        Returns:
            The AgentCard as a dictionary

        Raises:
            RuntimeError: If client is not properly initialized via context manager
        """
        if not self.client:
            raise RuntimeError(
                "A2AClient must be used as an async context manager. "
                "Use 'async with A2AClient(...) as client:' to ensure proper resource cleanup."
            )

        try:
            response = await self.client.get(f"{self.base_url}/.well-known/agent-card.json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch AgentCard: {e}")
            raise

    async def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get the status of a task.

        Args:
            task_id: The task ID to check

        Returns:
            Task status information

        Raises:
            RuntimeError: If client is not properly initialized via context manager
        """
        if not self.client:
            raise RuntimeError(
                "A2AClient must be used as an async context manager. "
                "Use 'async with A2AClient(...) as client:' to ensure proper resource cleanup."
            )

        try:
            response = await self.client.get(
                f"{self.base_url}/task/{task_id}/status",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get task status: {e}", task_id=task_id)
            raise

    def extract_text_from_response(self, response: dict[str, Any]) -> str:
        """Extract text content from an A2A response.

        Args:
            response: The A2A response dictionary

        Returns:
            Extracted text content
        """
        if not response:
            return ""

        # Handle direct message response
        if "message" in response:
            message = response["message"]
            if isinstance(message, dict) and "parts" in message:
                text_parts = []
                for part in message["parts"]:
                    if isinstance(part, dict) and part.get("kind") == "text":
                        text_parts.append(part.get("text", ""))
                return " ".join(text_parts)

        # Handle task response
        if "task" in response:
            task = response["task"]
            if isinstance(task, dict) and "artifacts" in task:
                text_parts = []
                for artifact in task["artifacts"]:
                    if isinstance(artifact, dict) and artifact.get("kind") == "text":
                        text_parts.append(artifact.get("content", ""))
                return " ".join(text_parts)

        # Fallback to string representation
        return str(response)
