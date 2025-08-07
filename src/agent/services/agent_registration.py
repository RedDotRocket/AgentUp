"""Agent registration service for multi-agent orchestration.

This module handles agent self-registration with an orchestrator,
enabling multi-agent system coordination.
"""

import asyncio
from typing import Any

import httpx

from .base import Service
from .config import ConfigurationManager
from .model import AgentRegistrationPayload


class AgentRegistrationClient(Service):
    """Service for registering an agent with an orchestrator.

    This service handles the self-registration process where an agent
    announces itself to an orchestrator, enabling multi-agent coordination.
    """

    def __init__(self, config_manager: ConfigurationManager):
        """Initialize the registration client.

        Args:
            config_manager: Configuration manager instance
        """
        super().__init__(config_manager)
        self.orchestrator_url: str | None = None
        self.agent_url: str | None = None
        self.registration_endpoint = "/agent/register"
        self.max_retries = 3
        self.retry_delay = 2.0  # seconds
        self.timeout = 30.0  # seconds

    async def initialize(self) -> None:
        """Initialize the registration service and perform registration."""
        self.logger.debug("Initializing agent registration service")

        # Get the Pydantic config object
        from agent.config import Config

        # Check if orchestrator is configured
        if not Config.orchestrator:
            self.logger.debug("No orchestrator configured, skipping registration")
            self._initialized = True
            return

        # Convert Pydantic HttpUrl to string
        self.orchestrator_url = str(Config.orchestrator)

        # Get agent information using Pydantic attributes
        agent_info = {"name": Config.project_name, "version": Config.version, "description": Config.description}

        # Determine agent URL from API config
        host = Config.api.host
        port = Config.api.port

        # Handle different host configurations for agent URL
        # Bandit: We are converting from 0.0.0.0, so false postive.
        if host in ["0.0.0.0", "127.0.0.1"]:  # nosec
            # Use localhost for local addresses
            agent_host = "localhost"
        else:
            agent_host = host

        self.agent_url = f"http://{agent_host}:{port}"

        # Perform registration
        await self._register_with_orchestrator(agent_info)

        self._initialized = True

    async def _register_with_orchestrator(self, agent_info: dict[str, Any]) -> None:
        """Register this agent with the orchestrator.

        Args:
            agent_info: Dictionary containing agent metadata
        """
        if not self.orchestrator_url or not self.agent_url:
            self.logger.warning("Missing orchestrator or agent URL, skipping registration")
            return

        # Prepare registration payload
        payload = AgentRegistrationPayload(
            agent_url=self.agent_url,
            name=agent_info["name"],
            version=agent_info["version"],
            agent_card_url=f"{self.agent_url}/.well-known/agent-card.json",
            description=agent_info.get("description"),
        )

        registration_url = f"{self.orchestrator_url.rstrip('/')}{self.registration_endpoint}"

        # Attempt registration with retries
        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    f"Attempting to register with orchestrator (attempt {attempt + 1}/{self.max_retries})",
                    orchestrator_url=self.orchestrator_url,
                    agent_url=self.agent_url,
                )

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        registration_url, json=payload.model_dump(), headers={"Content-Type": "application/json"}
                    )

                    if response.status_code == 200:
                        self.logger.info(
                            "Successfully registered with orchestrator",
                            orchestrator_url=self.orchestrator_url,
                            response_data=response.json() if response.content else None,
                        )
                        return
                    else:
                        self.logger.warning(
                            f"Registration failed with status {response.status_code}",
                            orchestrator_url=self.orchestrator_url,
                            status_code=response.status_code,
                            response_text=response.text[:500] if response.text else None,
                        )

            except httpx.TimeoutException:
                self.logger.warning(
                    f"Registration timeout (attempt {attempt + 1}/{self.max_retries})",
                    orchestrator_url=self.orchestrator_url,
                    timeout=self.timeout,
                )

            except httpx.ConnectError as e:
                self.logger.warning(
                    f"Failed to connect to orchestrator (attempt {attempt + 1}/{self.max_retries})",
                    orchestrator_url=self.orchestrator_url,
                    error=str(e),
                )

            except Exception as e:
                self.logger.error(
                    f"Unexpected error during registration (attempt {attempt + 1}/{self.max_retries})",
                    orchestrator_url=self.orchestrator_url,
                    error=str(e),
                    exc_info=True,
                )

            # Wait before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay)

        # All retries exhausted
        self.logger.warning(
            f"Failed to register with orchestrator after {self.max_retries} attempts",
            orchestrator_url=self.orchestrator_url,
        )

    async def shutdown(self) -> None:
        """Clean up registration service resources."""
        self.logger.debug("Shutting down agent registration service")

        # Could potentially send a deregistration message here in the future
        # For now, just mark as not initialized
        self._initialized = False

    def get_registration_status(self) -> dict[str, Any]:
        """Get the current registration status.

        Returns:
            Dictionary containing registration status information
        """
        return {
            "registered": self._initialized and self.orchestrator_url is not None,
            "orchestrator_url": self.orchestrator_url,
            "agent_url": self.agent_url,
        }
