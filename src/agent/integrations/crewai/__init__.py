"""CrewAI integration for AgentUp agents."""

import warnings

from .a2a_client import A2AClient
from .discovery import AgentUpDiscovery

# Try to import AgentUpTool which depends on CrewAI
try:
    from .agentup_tool import AgentUpTool

    __all__ = ["AgentUpTool", "A2AClient", "AgentUpDiscovery"]
except ImportError:
    warnings.warn(
        "CrewAI is not installed. AgentUpTool will not be available. Install with: pip install agentup[crewai]",
        stacklevel=2,
    )

    # Provide a stub for AgentUpTool
    class AgentUpTool:
        def __init__(self, *args, **kwargs):
            raise ImportError("CrewAI is not installed. Install with: pip install agentup[crewai]")

    __all__ = ["A2AClient", "AgentUpDiscovery"]
