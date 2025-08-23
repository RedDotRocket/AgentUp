"""Main executor factory for AgentUp execution system."""

import structlog
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCard

from agent.config.model import BaseAgent

# Re-export for compatibility with existing imports
from agent.core.models import AgentConfiguration, AgentType
from agent.core.strategies import IterativeStrategy, ReactiveStrategy

logger = structlog.get_logger(__name__)


class AgentExecutorFactory:
    """Factory for creating appropriate executor strategies based on configuration."""

    @staticmethod
    def create_executor(agent: BaseAgent | AgentCard, config: AgentConfiguration | None = None):
        """Create the appropriate executor strategy based on configuration.

        Args:
            agent: Agent configuration (BaseAgent or AgentCard)
            config: Agent execution configuration

        Returns:
            Configured executor strategy instance
        """
        # Use default config if none provided
        if config is None:
            config = AgentConfiguration()

        # Create executor based on agent type (config.agent_type is a string due to use_enum_values=True)
        if config.agent_type == AgentType.ITERATIVE:
            logger.info("Creating iterative executor")
            return IterativeStrategy(agent, config)
        elif config.agent_type == AgentType.REACTIVE:
            logger.info("Creating reactive executor")
            return ReactiveStrategy(agent, config)
        else:
            # Default to reactive
            logger.warning(f"Unknown agent type {config.agent_type}, defaulting to reactive")
            return ReactiveStrategy(agent, config)


class AgentUpExecutor(AgentExecutor):
    """Main AgentUp executor - new strategy-based architecture.

    This class serves as the main entry point for agent execution using
    the new clean strategy-based architecture with strong Pydantic typing
    and LLM-driven decision making.
    """

    def __init__(self, agent: BaseAgent | AgentCard, config: AgentConfiguration | None = None):
        """Initialize the executor.

        Args:
            agent: Agent configuration
            config: Execution configuration
        """
        self.agent = agent
        self.config = config or AgentConfiguration()

        # Create the appropriate strategy , e.g. AgentType (Reactive, Iterative)
        self.strategy = AgentExecutorFactory.create_executor(agent, self.config)

        # Expose common properties for compatibility
        self.agent_name = self.strategy.agent_name
        self.supports_streaming = self.strategy.supports_streaming

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute the agent task using the configured strategy.

        Args:
            context: Request context containing task and message data
            event_queue: Event queue for status updates and results
        """
        logger.info(f"Executing {self.config.agent_type} agent: {self.agent_name}")
        await self.strategy.execute(context, event_queue)

    async def execute_streaming(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute task with streaming support.

        Args:
            context: Request context
            event_queue: Event queue for streaming updates
        """
        logger.info(f"Executing {self.config.agent_type} agent with streaming: {self.agent_name}")
        await self.strategy.execute_streaming(context, event_queue)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel the current task execution.

        Args:
            context: Request context
            event_queue: Event queue for cancellation updates
        """
        logger.info(f"Canceling {self.config.agent_type} agent: {self.agent_name}")
        await self.strategy.cancel(context, event_queue)


# Factory function for creating executors
def create_agent_executor(
    agent: BaseAgent | AgentCard, agent_type: str | AgentType | None = None, **config_kwargs
) -> AgentUpExecutor:
    """Create an agent executor with the specified type and configuration.

    Args:
        agent: Agent configuration
        agent_type: Type of agent execution (reactive, iterative)
        **config_kwargs: Additional configuration parameters

    Returns:
        Configured AgentUpExecutor instance
    """
    # Parse agent type - AgentConfiguration accepts both strings and enums
    if isinstance(agent_type, AgentType):
        agent_type_value = agent_type
    elif isinstance(agent_type, str):
        try:
            agent_type_value = AgentType(agent_type.lower())
        except ValueError:
            logger.warning(f"Invalid agent_type '{agent_type}', defaulting to reactive")
            agent_type_value = AgentType.REACTIVE
    else:
        agent_type_value = AgentType.REACTIVE  # Default

    # Create configuration
    config = AgentConfiguration(agent_type=agent_type_value, **config_kwargs)

    # Create executor
    return AgentUpExecutor(agent, config)
