from typing import Any

import structlog

from agent.core.models import IterationState, LearningInsight, MemoryContext
from agent.state import get_context_manager

logger = structlog.get_logger(__name__)


class IterativeMemoryManager:
    """Memory manager specifically designed for iterative agents.

    This class extends AgentUp's existing memory system to support
    iterative agent-specific data like iteration states, learning
    insights, and cross-session context restoration.
    """

    def __init__(self, storage_type: str = "memory", **kwargs) -> None:
        """Initialize the memory manager.

        Args:
            storage_type: Type of storage backend (memory, file, valkey)
            **kwargs: Additional arguments for storage backend
        """
        self.context_manager = get_context_manager(storage_type, **kwargs)
        self.storage_type = storage_type

    async def store_iteration_state(self, context_id: str, state: IterationState) -> None:
        """Store iteration state in memory.

        Args:
            context_id: Unique context identifier
            state: Current iteration state to store
        """
        try:
            state_key = f"iteration_state_{context_id}"
            state_data = state.model_dump()

            # Store as metadata in existing context manager
            await self.context_manager.set_metadata(context_id, state_key, state_data)

            logger.debug(f"Stored iteration state for context {context_id}")

        except Exception as e:
            logger.error(f"Error storing iteration state for {context_id}: {e}")
            raise

    async def load_iteration_state(self, context_id: str) -> IterationState | None:
        """Load iteration state from memory.

        Args:
            context_id: Unique context identifier

        Returns:
            IterationState if found, None otherwise
        """
        try:
            state_key = f"iteration_state_{context_id}"
            state_data = await self.context_manager.get_metadata(context_id, state_key)

            if state_data:
                return IterationState(**state_data)

            return None

        except Exception as e:
            logger.error(f"Error loading iteration state for {context_id}: {e}")
            return None

    async def store_memory_context(self, context_id: str, memory_context: MemoryContext) -> None:
        """Store memory context with learning insights.

        Args:
            context_id: Unique context identifier
            memory_context: Memory context to store
        """
        try:
            memory_key = f"memory_context_{context_id}"
            memory_data = memory_context.model_dump()

            await self.context_manager.set_metadata(context_id, memory_key, memory_data)

            logger.debug(f"Stored memory context for {context_id}")

        except Exception as e:
            logger.error(f"Error storing memory context for {context_id}: {e}")
            raise

    async def load_memory_context(self, context_id: str) -> MemoryContext | None:
        """Load memory context from storage.

        Args:
            context_id: Unique context identifier

        Returns:
            MemoryContext if found, None otherwise
        """
        try:
            memory_key = f"memory_context_{context_id}"
            memory_data = await self.context_manager.get_metadata(context_id, memory_key)

            if memory_data:
                return MemoryContext(**memory_data)

            return None

        except Exception as e:
            logger.error(f"Error loading memory context for {context_id}: {e}")
            return None

    async def add_learning_insight(self, context_id: str, insight: LearningInsight) -> None:
        """Add a learning insight to memory context.

        Args:
            context_id: Unique context identifier
            insight: Learning insight to add
        """
        try:
            # Load existing memory context or create new one
            memory_context = await self.load_memory_context(context_id)
            if not memory_context:
                memory_context = MemoryContext(context_id=context_id, agent_type="iterative")

            # Add the insight
            memory_context.add_insight(insight)

            # Store updated context
            await self.store_memory_context(context_id, memory_context)

            logger.debug(f"Added learning insight to {context_id}: {insight.insight}")

        except Exception as e:
            logger.error(f"Error adding learning insight for {context_id}: {e}")
            raise

    async def get_learning_insights(self, context_id: str, learning_type: str | None = None) -> list[LearningInsight]:
        """Get learning insights for a context.

        Args:
            context_id: Unique context identifier
            learning_type: Optional filter by learning type

        Returns:
            List of learning insights
        """
        try:
            memory_context = await self.load_memory_context(context_id)
            if not memory_context:
                return []

            insights = memory_context.learning_insights

            # Filter by type if specified
            if learning_type:
                insights = [insight for insight in insights if insight.learning_type.value == learning_type]

            # Sort by usage count and recency
            insights.sort(key=lambda x: (x.usage_count, x.last_used), reverse=True)

            return insights

        except Exception as e:
            logger.error(f"Error getting learning insights for {context_id}: {e}")
            return []

    async def update_iteration_metrics(self, context_id: str, success: bool) -> None:
        """Update iteration metrics in memory context.

        Args:
            context_id: Unique context identifier
            success: Whether the iteration was successful
        """
        try:
            # Load or create memory context
            memory_context = await self.load_memory_context(context_id)
            if not memory_context:
                memory_context = MemoryContext(context_id=context_id, agent_type="iterative")

            # Update metrics
            memory_context.increment_iteration()
            if success:
                memory_context.mark_success()
            else:
                memory_context.mark_failure()

            # Store updated context
            await self.store_memory_context(context_id, memory_context)

            logger.debug(f"Updated iteration metrics for {context_id}, success: {success}")

        except Exception as e:
            logger.error(f"Error updating iteration metrics for {context_id}: {e}")
            raise

    async def store_custom_data(self, context_id: str, key: str, data: Any) -> None:
        """Store custom data in memory.

        Args:
            context_id: Unique context identifier
            key: Data key
            data: Data to store
        """
        try:
            full_key = f"custom_{key}_{context_id}"
            await self.context_manager.set_metadata(context_id, full_key, data)

            logger.debug(f"Stored custom data {key} for context {context_id}")

        except Exception as e:
            logger.error(f"Error storing custom data {key} for {context_id}: {e}")
            raise

    async def get_custom_data(self, context_id: str, key: str) -> Any | None:
        """Get custom data from memory.

        Args:
            context_id: Unique context identifier
            key: Data key

        Returns:
            Stored data if found, None otherwise
        """
        try:
            full_key = f"custom_{key}_{context_id}"
            return await self.context_manager.get_metadata(context_id, full_key)

        except Exception as e:
            logger.error(f"Error getting custom data {key} for {context_id}: {e}")
            return None

    async def cleanup_old_data(self, max_age_days: int = 30) -> None:
        """Clean up old iteration data.

        Args:
            max_age_days: Maximum age in days for data retention
        """
        try:
            # Use existing cleanup functionality
            await self.context_manager.cleanup_old_contexts(max_age_days)

            logger.info(f"Cleaned up iteration data older than {max_age_days} days")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            raise

    async def get_context_statistics(self, context_id: str) -> dict[str, Any]:
        """Get statistics for a context.

        Args:
            context_id: Unique context identifier

        Returns:
            Dictionary with context statistics
        """
        try:
            memory_context = await self.load_memory_context(context_id)
            iteration_state = await self.load_iteration_state(context_id)

            stats = {
                "context_exists": memory_context is not None,
                "iteration_exists": iteration_state is not None,
                "total_iterations": 0,
                "success_rate": 0.0,
                "insights_count": 0,
                "current_iteration": 0,
            }

            if memory_context:
                stats.update(
                    {
                        "total_iterations": memory_context.total_iterations,
                        "success_rate": memory_context.success_rate,
                        "insights_count": len(memory_context.learning_insights),
                        "successful_completions": memory_context.successful_completions,
                        "failed_attempts": memory_context.failed_attempts,
                    }
                )

            if iteration_state:
                stats.update(
                    {
                        "current_iteration": iteration_state.iteration_count,
                        "goal": iteration_state.goal,
                        "completed_tasks": len(iteration_state.completed_tasks),
                        "should_continue": iteration_state.should_continue,
                    }
                )

            return stats

        except Exception as e:
            logger.error(f"Error getting context statistics for {context_id}: {e}")
            return {"error": str(e)}
