import asyncio
from typing import Any

import structlog
from pydantic import BaseModel, Field

from .a2a_client import A2AClient
from .models import AgentUpConfig

logger = structlog.get_logger(__name__)


class AgentUpToolInput(BaseModel):
    """Input schema for AgentUp tool."""

    query: str = Field(..., description="Query to send to the AgentUp agent")
    context_id: str | None = Field(None, description="Optional context ID for conversation continuity")


try:
    # Try to import CrewAI's BaseTool
    from crewai.tools import BaseTool  # type: ignore  # noqa: I001

    class AgentUpTool(BaseTool):
        """Tool for integrating AgentUp agents into CrewAI workflows."""

        name: str = "AgentUp Tool"
        description: str = (
            "Interact with AgentUp agents for specialized capabilities. "
            "Send queries to domain-specific agents and receive structured responses."
        )
        args_schema: type[BaseModel] = AgentUpToolInput

        model_config = {"extra": "allow"}

        def __init__(
            self,
            base_url: str = "http://localhost:8000",
            api_key: str | None = None,
            timeout: int = 30,
            max_retries: int = 3,
            agent_name: str | None = None,
            **kwargs,
        ):
            """Initialize the AgentUp tool.

            Args:
                base_url: Base URL of the AgentUp agent
                api_key: Optional API key for authentication
                timeout: Request timeout in seconds
                max_retries: Maximum number of retries
                agent_name: Optional name for the agent (used in descriptions)
                **kwargs: Additional arguments for BaseTool
            """
            # Update name and description if agent_name provided
            if agent_name:
                kwargs["name"] = kwargs.get("name", f"AgentUp {agent_name}")
                kwargs["description"] = kwargs.get(
                    "description",
                    f"Interact with {agent_name} AgentUp agent for specialized tasks.",
                )

            super().__init__(**kwargs)

            # Set attributes after super().__init__()
            self.config = AgentUpConfig(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
            )
            self.agent_name = agent_name or "AgentUp Agent"

            logger.info(
                f"Initialized AgentUpTool for {self.agent_name}",
                base_url=base_url,
                has_api_key=bool(api_key),
            )

        def _run(self, query: str, context_id: str | None = None) -> str:
            """Execute the tool synchronously.

            Args:
                query: Query to send to the AgentUp agent
                context_id: Optional context ID for conversation continuity

            Returns:
                Response from the AgentUp agent
            """
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(self._arun(query, context_id))

        async def _arun(self, query: str, context_id: str | None = None) -> str:
            """Execute the tool asynchronously.

            Args:
                query: Query to send to the AgentUp agent
                context_id: Optional context ID for conversation continuity

            Returns:
                Response from the AgentUp agent
            """
            logger.debug(
                f"Executing AgentUpTool query for {self.agent_name}",
                query=query[:100] + "..." if len(query) > 100 else query,
                context_id=context_id,
            )

            async with A2AClient(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            ) as client:
                try:
                    result = await client.send_message(message=query, context_id=context_id)

                    # Extract text from A2A response
                    response_text = client.extract_text_from_response(result)

                    if not response_text:
                        response_text = f"Agent {self.agent_name} processed the request but returned no text response."

                    logger.debug(
                        f"AgentUpTool received response from {self.agent_name}",
                        response_length=len(response_text),
                    )

                    return response_text

                except Exception as e:
                    error_msg = f"Error communicating with {self.agent_name}: {str(e)}"
                    logger.error(error_msg, error=str(e))
                    return error_msg

        async def stream_response(self, query: str, context_id: str | None = None):
            """Stream responses from the AgentUp agent.

            Args:
                query: Query to send to the AgentUp agent
                context_id: Optional context ID for conversation continuity

            Yields:
                Streaming chunks from the agent response
            """
            logger.debug(f"Streaming query to {self.agent_name}", query=query[:100])

            async with A2AClient(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            ) as client:
                try:
                    async for chunk in client.stream_message(message=query, context_id=context_id):
                        yield chunk
                except Exception as e:
                    logger.error(f"Error streaming from {self.agent_name}", error=str(e))
                    yield {"error": str(e)}

        async def get_capabilities(self) -> dict[str, Any]:
            """Get the capabilities of the AgentUp agent.

            Returns:
                Agent capabilities from the AgentCard
            """
            async with A2AClient(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            ) as client:
                try:
                    agent_card = await client.get_agent_card()
                    return agent_card.get("capabilities", {})
                except Exception as e:
                    logger.error(
                        f"Error fetching capabilities for {self.agent_name}",
                        error=str(e),
                    )
                    return {}

        def health_check(self) -> bool:
            """Perform a health check on the AgentUp agent.

            Returns:
                True if the agent is healthy, False otherwise
            """
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def _health_check():
                async with A2AClient(
                    base_url=self.config.base_url,
                    api_key=self.config.api_key,
                    timeout=5,  # Quick timeout for health check
                    max_retries=1,
                ) as client:
                    try:
                        await client.get_agent_card()
                        return True
                    except Exception:
                        return False

            return loop.run_until_complete(_health_check())


except ImportError:
    logger.warning("CrewAI not installed. AgentUpTool will not be available. Install with: pip install crewai")

    # Provide a mock class for testing/development
    class AgentUpTool:
        """Mock AgentUpTool when CrewAI is not available."""

        def __init__(self, *_args, **_kwargs):
            raise ImportError("CrewAI is not installed. Install with: pip install crewai")


# Standalone function for use without CrewAI
async def query_agentup_agent(
    query: str,
    base_url: str = "http://localhost:8000",
    api_key: str | None = None,
    context_id: str | None = None,
) -> str:
    """Standalone function to query an AgentUp agent.

    Args:
        query: Query to send to the AgentUp agent
        base_url: Base URL of the AgentUp agent
        api_key: Optional API key for authentication
        context_id: Optional context ID for conversation continuity

    Returns:
        Response from the AgentUp agent
    """
    async with A2AClient(base_url=base_url, api_key=api_key) as client:
        result = await client.send_message(message=query, context_id=context_id)
        return client.extract_text_from_response(result)


# Factory function for creating multiple tools
def create_agentup_tools(agents: list[dict[str, Any]]) -> list[AgentUpTool]:
    """Create multiple AgentUpTool instances from agent configurations.

    Args:
        agents: List of agent configurations with keys:
            - name: Agent name
            - base_url: Agent URL
            - api_key: Optional API key
            - description: Optional description

    Returns:
        List of configured AgentUpTool instances
    """
    tools = []
    for agent_config in agents:
        tool = AgentUpTool(
            base_url=agent_config["base_url"],
            api_key=agent_config.get("api_key"),
            agent_name=agent_config["name"],
            name=f"AgentUp {agent_config['name']}",
            description=agent_config.get("description", f"Interact with {agent_config['name']} agent"),
        )
        tools.append(tool)
        logger.info(f"Created AgentUpTool for {agent_config['name']}")

    return tools
