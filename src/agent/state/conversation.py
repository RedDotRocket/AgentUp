from datetime import timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConversationManager:
    def __init__(self):
        pass

    @staticmethod
    def extract_text_from_parts(parts) -> str:
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

    async def prepare_llm_conversation(self, task) -> list[dict[str, str]]:
        """Prepare LLM conversation from A2A task history AND stored conversation state."""
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

        # First, try to get stored conversation history from persistent state
        stored_conversation_turns = []
        if hasattr(task, "context_id") and task.context_id:
            try:
                stored_conversation_turns = await self.get_conversation_history(task.context_id)
                if stored_conversation_turns:
                    logger.info(
                        f"Retrieved {len(stored_conversation_turns)} stored conversation turns for context {task.context_id}"
                    )
                else:
                    logger.debug(f"No stored conversation history found for context {task.context_id}")
            except Exception as e:
                logger.warning(f"Failed to retrieve stored conversation history for {task.context_id}: {e}")

        # Convert stored conversation turns to individual messages
        for turn in stored_conversation_turns:
            if isinstance(turn, dict):
                # Add user message
                if turn.get("user", "").strip():
                    messages.append({"role": "user", "content": turn["user"]})
                # Add agent response
                if turn.get("agent", "").strip():
                    messages.append({"role": "assistant", "content": turn["agent"]})

        # Then add A2A task.history (most recent messages) - last 5 messages to avoid context overflow
        if hasattr(task, "history") and task.history:
            for message in task.history[-5:]:
                if hasattr(message, "role") and hasattr(message, "parts"):
                    content = self.extract_text_from_parts(message.parts)
                    if content.strip():
                        messages.append({"role": message.role, "content": content})

        logger.debug(f"Prepared LLM conversation with {len(messages)} total messages (including system prompt)")
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
            stored_history = await context.get_history(context_id)

            # Robust conversation turn reconstruction
            history = []
            current_user_msg = None

            for msg in stored_history:
                if msg.get("role") == "user":
                    # If we have a pending user message, save it with empty agent response
                    if current_user_msg is not None:
                        history.append(
                            {
                                "user": current_user_msg,
                                "agent": "",
                            }
                        )
                    # Store new user message
                    current_user_msg = msg.get("content", "")

                elif msg.get("role") == "agent" and current_user_msg is not None:
                    # Complete the conversation turn
                    history.append(
                        {
                            "user": current_user_msg,
                            "agent": msg.get("content", ""),
                        }
                    )
                    current_user_msg = None

            # Handle any remaining unpaired user message
            if current_user_msg is not None:
                history.append(
                    {
                        "user": current_user_msg,
                        "agent": "",
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
                logger.debug(f"State management disabled - not storing history for context {context_id}")
                return

            backend = state_config.get("backend", "memory")
            backend_config = state_config.get("config", {})

            # Get context manager
            context = get_context_manager(backend, **backend_config)

            # Store user message
            await context.add_to_history(
                context_id,
                "user",
                user_input,
                {"timestamp": datetime.now(timezone.utc).isoformat()},
            )

            # Store agent response
            await context.add_to_history(
                context_id,
                "agent",
                response,
                {"timestamp": datetime.now(timezone.utc).isoformat()},
            )

            logger.debug(f"Updated conversation history for context {context_id}")

        except Exception as e:
            logger.error(f"Failed to update conversation history: {e}")
