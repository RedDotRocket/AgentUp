"""CrewAI integration for AgentUp agents."""

import warnings

from .a2a_client import A2AClient
from .discovery import AgentUpDiscovery

# Check if CrewAI is available
_CREWAI_AVAILABLE = False
try:
    import crewai  # noqa: F401

    _CREWAI_AVAILABLE = True
except ImportError:
    warnings.warn(
        "CrewAI not installed. AgentUpTool will not be available. Install with: pip install crewai",
        stacklevel=2,
    )

if _CREWAI_AVAILABLE:
    from .agentup_tool import AgentUpTool

    __all__ = ["AgentUpTool", "A2AClient", "AgentUpDiscovery"]
else:
    __all__ = ["A2AClient", "AgentUpDiscovery"]

    # Create a custom __getattr__ to handle AgentUpTool imports
    def __getattr__(name: str):
        if name == "AgentUpTool":
            raise ImportError("CrewAI not installed. Install with: pip install agentup[crewai]")
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
