from typing import Any

import structlog

from .a2a_client import A2AClient
from .models import SkillInfo

# Try to import AgentUpTool, which depends on CrewAI
try:
    from .agentup_tool import AgentUpTool

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

    # Provide a stub class
    class AgentUpTool:
        def __init__(self, *args, **kwargs):
            raise ImportError("CrewAI is not installed. Install with: pip install agentup[crewai]")


logger = structlog.get_logger(__name__)


class AgentUpDiscovery:
    """Discover and create tools from AgentUp AgentCards."""

    def __init__(
        self,
        base_urls: list[str] | str,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        """Initialize the discovery client.

        Args:
            base_urls: Single URL or list of URLs to discover agents from
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        if isinstance(base_urls, str):
            base_urls = [base_urls]

        self.base_urls = base_urls
        self.api_key = api_key
        self.timeout = timeout

    async def discover_agents(self) -> list[dict[str, Any]]:
        """Discover available AgentUp agents and their capabilities.

        Returns:
            List of agent information dictionaries
        """
        agents = []

        for base_url in self.base_urls:
            try:
                async with A2AClient(
                    base_url=base_url,
                    api_key=self.api_key,
                    timeout=self.timeout,
                ) as client:
                    agent_card = await client.get_agent_card()

                    agent_info = {
                        "name": agent_card.get("name", "Unknown Agent"),
                        "description": agent_card.get("description", ""),
                        "base_url": base_url,
                        "version": agent_card.get("version", "unknown"),
                        "capabilities": agent_card.get("capabilities", {}),
                        "skills": agent_card.get("skills", []),
                        "security_schemes": agent_card.get("securitySchemes", {}),
                        "default_input_modes": agent_card.get("defaultInputModes", ["text"]),
                        "default_output_modes": agent_card.get("defaultOutputModes", ["text"]),
                    }

                    agents.append(agent_info)
                    logger.info(
                        f"Discovered agent: {agent_info['name']}",
                        base_url=base_url,
                        skills_count=len(agent_info["skills"]),
                    )

            except Exception as e:
                logger.error(f"Failed to discover agent at {base_url}", error=str(e))
                continue

        logger.info(f"Discovery completed: found {len(agents)} agents")
        return agents

    async def create_tools_from_agents(self) -> list[AgentUpTool]:
        """Create AgentUpTool instances from discovered agents.

        Returns:
            List of configured AgentUpTool instances
        """
        if not CREWAI_AVAILABLE:
            logger.error("Cannot create tools: CrewAI is not installed. Install with: pip install agentup[crewai]")
            return []

        agents = await self.discover_agents()
        tools = []

        for agent_info in agents:
            try:
                tool = AgentUpTool(
                    base_url=agent_info["base_url"],
                    api_key=self.api_key,
                    timeout=self.timeout,
                    agent_name=agent_info["name"],
                    name=f"AgentUp {agent_info['name']}",
                    description=agent_info["description"]
                    or f"Interact with {agent_info['name']} for specialized tasks",
                )
                tools.append(tool)

                logger.info(
                    f"Created tool for agent: {agent_info['name']}",
                    base_url=agent_info["base_url"],
                )

            except Exception as e:
                logger.error(
                    f"Failed to create tool for agent {agent_info['name']}",
                    error=str(e),
                )
                continue

        return tools

    async def create_skill_specific_tools(self) -> list[AgentUpTool]:
        """Create individual tools for each skill from discovered agents.

        Returns:
            List of skill-specific AgentUpTool instances
        """
        if not CREWAI_AVAILABLE:
            logger.error("Cannot create tools: CrewAI is not installed. Install with: pip install agentup[crewai]")
            return []

        agents = await self.discover_agents()
        tools = []

        for agent_info in agents:
            for skill in agent_info["skills"]:
                try:
                    skill_info = SkillInfo(**skill)

                    # Create a specialized tool for this skill
                    tool = AgentUpTool(
                        base_url=agent_info["base_url"],
                        api_key=self.api_key,
                        timeout=self.timeout,
                        agent_name=f"{agent_info['name']} - {skill_info.name}",
                        name=f"{skill_info.name}",
                        description=skill_info.description,
                    )

                    # Add skill-specific metadata
                    tool.skill_id = skill_info.id
                    tool.skill_tags = skill_info.tags
                    tool.input_modes = skill_info.input_modes
                    tool.output_modes = skill_info.output_modes

                    tools.append(tool)

                    logger.debug(
                        f"Created skill tool: {skill_info.name}",
                        agent=agent_info["name"],
                        skill_id=skill_info.id,
                    )

                except Exception as e:
                    logger.error(
                        "Failed to create skill tool",
                        skill=skill,
                        agent=agent_info["name"],
                        error=str(e),
                    )
                    continue

        logger.info(f"Created {len(tools)} skill-specific tools")
        return tools

    async def get_agent_health_status(self) -> dict[str, bool]:
        """Check health status of all discovered agents.

        Returns:
            Dictionary mapping agent URLs to health status
        """
        health_status = {}

        for base_url in self.base_urls:
            try:
                async with A2AClient(
                    base_url=base_url,
                    api_key=self.api_key,
                    timeout=5,  # Quick timeout for health checks
                ) as client:
                    # Try to fetch AgentCard as health check
                    await client.get_agent_card()
                    health_status[base_url] = True
                    logger.debug(f"Agent at {base_url} is healthy")

            except Exception as e:
                health_status[base_url] = False
                logger.warning(f"Agent at {base_url} is unhealthy", error=str(e))

        return health_status

    async def find_agents_by_capability(self, capability: str) -> list[dict[str, Any]]:
        """Find agents that have a specific capability or skill.

        Args:
            capability: Capability name or skill tag to search for

        Returns:
            List of matching agent information
        """
        agents = await self.discover_agents()
        matching_agents = []

        for agent_info in agents:
            # Check skills for capability
            for skill in agent_info["skills"]:
                skill_tags = skill.get("tags", [])
                skill_name = skill.get("name", "").lower()
                skill_desc = skill.get("description", "").lower()

                if (
                    capability.lower() in skill_tags
                    or capability.lower() in skill_name
                    or capability.lower() in skill_desc
                ):
                    matching_agents.append(agent_info)
                    break  # Found match, no need to check other skills

        logger.info(f"Found {len(matching_agents)} agents with capability: {capability}")
        return matching_agents


# Convenience functions for common discovery patterns
async def discover_local_agents(ports: list[int] = None, api_key: str | None = None) -> list[AgentUpTool]:
    """Discover agents running on localhost with common ports.

    Args:
        ports: List of ports to check (defaults to common ports)
        api_key: Optional API key for authentication

    Returns:
        List of discovered AgentUpTool instances
    """
    if not CREWAI_AVAILABLE:
        logger.error("Cannot create tools: CrewAI is not installed. Install with: pip install agentup[crewai]")
        return []

    if ports is None:
        ports = [8000, 8001, 8002, 8003, 8080, 8081]

    base_urls = [f"http://localhost:{port}" for port in ports]

    discovery = AgentUpDiscovery(base_urls=base_urls, api_key=api_key)
    return await discovery.create_tools_from_agents()


async def discover_from_registry(registry_url: str, api_key: str | None = None) -> list[AgentUpTool]:
    """Discover agents from a registry service.

    Args:
        registry_url: URL of the agent registry
        api_key: Optional API key for authentication

    Returns:
        List of discovered AgentUpTool instances
    """
    # This would integrate with a future agent registry service
    # For now, it's a placeholder for the pattern
    logger.warning(
        "Agent registry discovery not yet implemented",
        registry_url=registry_url,
    )
    return []


async def discover_and_filter_tools(
    base_urls: list[str],
    required_capabilities: list[str] = None,
    api_key: str | None = None,
) -> list[AgentUpTool]:
    """Discover agents and filter by required capabilities.

    Args:
        base_urls: List of agent URLs to discover
        required_capabilities: List of required capability names/tags
        api_key: Optional API key for authentication

    Returns:
        Filtered list of AgentUpTool instances
    """
    if not CREWAI_AVAILABLE:
        logger.error("Cannot create tools: CrewAI is not installed. Install with: pip install agentup[crewai]")
        return []

    discovery = AgentUpDiscovery(base_urls=base_urls, api_key=api_key)
    all_tools = await discovery.create_tools_from_agents()

    if not required_capabilities:
        return all_tools

    # Filter tools by capabilities
    filtered_tools = []
    agents = await discovery.discover_agents()

    for i, tool in enumerate(all_tools):
        agent_info = agents[i]
        agent_skills = agent_info.get("skills", [])

        # Check if agent has any of the required capabilities
        has_required_capability = False
        for capability in required_capabilities:
            for skill in agent_skills:
                skill_tags = skill.get("tags", [])
                skill_name = skill.get("name", "").lower()

                if capability.lower() in skill_tags or capability.lower() in skill_name:
                    has_required_capability = True
                    break

            if has_required_capability:
                break

        if has_required_capability:
            filtered_tools.append(tool)

    logger.info(
        f"Filtered {len(all_tools)} tools to {len(filtered_tools)} with required capabilities: {required_capabilities}"
    )

    return filtered_tools
