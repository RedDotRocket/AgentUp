import os

from pydantic import BaseModel, Field

from agent.integrations.crewai.models import AgentUpConfig


class CrewAIIntegrationConfig(BaseModel):
    """Configuration for CrewAI integration."""

    enabled: bool = Field(default=True, description="Enable CrewAI integration")
    default_agent_url: str = Field(
        default="http://localhost:8000",
        description="Default AgentUp agent URL for CrewAI tools",
    )
    default_api_key: str | None = Field(default=None, description="Default API key for AgentUp agents")
    default_timeout: int = Field(default=30, description="Default timeout for agent requests")
    default_max_retries: int = Field(default=3, description="Default maximum number of retries")
    auto_discovery: bool = Field(default=False, description="Enable automatic agent discovery")
    discovery_urls: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000"],
        description="URLs to discover agents from",
    )
    health_check_interval: int = Field(default=300, description="Health check interval in seconds")


class IntegrationConfig(BaseModel):
    """Master configuration for all integrations."""

    crewai: CrewAIIntegrationConfig = Field(
        default_factory=CrewAIIntegrationConfig,
        description="CrewAI integration configuration",
    )

    @classmethod
    def from_env(cls) -> "IntegrationConfig":
        """Create configuration from environment variables."""
        crewai_config = CrewAIIntegrationConfig(
            enabled=os.getenv("AGENTUP_CREWAI_ENABLED", "true").lower() == "true",
            default_agent_url=os.getenv("AGENTUP_URL", "http://localhost:8000"),
            default_api_key=os.getenv("AGENTUP_API_KEY"),
            default_timeout=int(os.getenv("AGENTUP_TIMEOUT", "30")),
            default_max_retries=int(os.getenv("AGENTUP_MAX_RETRIES", "3")),
            auto_discovery=os.getenv("AGENTUP_AUTO_DISCOVERY", "false").lower() == "true",
            discovery_urls=_parse_urls_from_env(),
            health_check_interval=int(os.getenv("AGENTUP_HEALTH_CHECK_INTERVAL", "300")),
        )

        return cls(crewai=crewai_config)

    def to_agentup_config(self, base_url: str | None = None, api_key: str | None = None) -> AgentUpConfig:
        """Convert to AgentUpConfig for tool creation."""
        return AgentUpConfig(
            base_url=base_url or self.crewai.default_agent_url,
            api_key=api_key or self.crewai.default_api_key,
            timeout=self.crewai.default_timeout,
            max_retries=self.crewai.default_max_retries,
        )


def _parse_urls_from_env() -> list[str]:
    """Parse URLs from environment variable."""
    urls_str = os.getenv("AGENTUP_URLS", "http://localhost:8000")
    return [url.strip() for url in urls_str.split(",")]


# Global configuration instance
_config: IntegrationConfig | None = None


def get_integration_config() -> IntegrationConfig:
    """Get the global integration configuration."""
    global _config
    if _config is None:
        _config = IntegrationConfig.from_env()
    return _config


def reload_integration_config() -> IntegrationConfig:
    """Reload configuration from environment."""
    global _config
    _config = IntegrationConfig.from_env()
    return _config


# Environment variable reference
INTEGRATION_ENV_VARS = {
    "AGENTUP_CREWAI_ENABLED": "Enable/disable CrewAI integration (true/false)",
    "AGENTUP_URL": "Default AgentUp agent URL",
    "AGENTUP_API_KEY": "Default API key for authentication",
    "AGENTUP_TIMEOUT": "Default request timeout in seconds",
    "AGENTUP_MAX_RETRIES": "Default maximum number of retries",
    "AGENTUP_AUTO_DISCOVERY": "Enable automatic agent discovery (true/false)",
    "AGENTUP_URLS": "Comma-separated list of URLs for discovery",
    "AGENTUP_HEALTH_CHECK_INTERVAL": "Health check interval in seconds",
}
