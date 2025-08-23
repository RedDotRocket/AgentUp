from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConversationManager:
    def __init__(self):
        pass

    def extract_text_from_parts(self, parts) -> str:
        """Extract text content from A2A message parts."""
        text_content = ""
        for part in parts:
            if hasattr(part, "root") and hasattr(part.root, "kind"):
                if part.root.kind == "text" and hasattr(part.root, "text"):
                    text_content += part.root.text
            elif hasattr(part, "text"):
                text_content += part.text
            elif isinstance(part, dict) and "text" in part:
                text_content += part["text"]
        return text_content

    def prepare_llm_conversation(self, task) -> list[dict[str, str]]:
        """Prepare LLM conversation directly from A2A task history."""
        from agent.config import Config

        ai_config = Config.ai
        system_prompt = ai_config.get(
            "system_prompt",
            """You are an AI agent with access to specific functions/skills.

Your role:
- Understand user requests naturally
- Use the appropriate functions when needed
- Provide helpful, conversational responses
- Maintain context across the conversation

When users ask for something:
1. If you have a relevant function, call it with appropriate parameters
2. If multiple functions are needed, call them in logical order
3. Synthesize the results into a natural, helpful response
4. If no function is needed, respond conversationally

Always be helpful, accurate, and maintain a friendly tone.""",
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Use A2A task.history directly - last 10 messages for context management
        if hasattr(task, "history") and task.history:
            for message in task.history[-10:]:
                if hasattr(message, "role") and hasattr(message, "parts"):
                    content = self.extract_text_from_parts(message.parts)
                    if content.strip():
                        messages.append({"role": message.role, "content": content})

        return messages

    async def get_conversation_history(self, context_id: str) -> list[dict[str, Any]]:
        """Retrieve conversation history from persistent storage for streaming."""
        try:
            # Try to get history from persistent state if available
            from agent.capabilities.manager import _load_state_config
            from agent.state.context import get_context_manager

            state_config = _load_state_config()
            if not state_config.get("enabled", False):
                logger.debug(f"State management disabled - no history for context {context_id}")
                return []

            backend = state_config.get("backend", "memory")
            backend_config = state_config.get("config", {})

            # Get context manager
            context = get_context_manager(backend, **backend_config)

            # Retrieve conversation history
            history = []
            stored_history = await context.get_history(context_id)

            # Convert stored history to expected format
            for i in range(0, len(stored_history) - 1, 2):
                if i + 1 < len(stored_history):
                    user_msg = stored_history[i]
                    agent_msg = stored_history[i + 1]
                    if user_msg.get("role") == "user" and agent_msg.get("role") == "agent":
                        history.append(
                            {
                                "user": user_msg.get("content", ""),
                                "agent": agent_msg.get("content", ""),
                            }
                        )

            logger.debug(f"Retrieved {len(history)} conversation turns for context {context_id}")
            return history

        except Exception as e:
            logger.error(f"Failed to retrieve conversation history: {e}")
            return []

    async def update_conversation_history(self, context_id: str, user_input: str, response: str):
        """Update conversation history in persistent storage."""
        try:
            # Store in persistent state if available
            from datetime import datetime

            from agent.capabilities.manager import _load_state_config
            from agent.state.context import get_context_manager

            state_config = _load_state_config()
            if not state_config.get("enabled", False):
                logger.debug(
                    f"State management disabled - not storing history for context {context_id}"
                )
                return

            backend = state_config.get("backend", "memory")
            backend_config = state_config.get("config", {})

            # Get context manager
            context = get_context_manager(backend, **backend_config)

            # Store user message
            await context.add_to_history(
                context_id, "user", user_input, {"timestamp": datetime.utcnow().isoformat()}
            )

            # Store agent response
            await context.add_to_history(
                context_id, "agent", response, {"timestamp": datetime.utcnow().isoformat()}
            )

            logger.debug(f"Updated conversation history for context {context_id}")

        except Exception as e:
            logger.error(f"Failed to update conversation history: {e}")
