from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConversationManager:
    def __init__(self):
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    async def prepare_llm_conversation(
        self, user_input: str | dict[str, Any], conversation: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        # Get system prompt from config
        from agent.config import Config

        ai_config = Config.ai
        # Use configured system prompt or fallback to default
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

        # Add conversation history (last 10 turns to manage context length)
        for turn in conversation[-10:]:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["agent"]})

        # Add current user input - support both text string and A2A message dict
        if isinstance(user_input, dict):
            # A2A message format with parts
            messages.append(user_input)
        else:
            # Simple text string
            messages.append({"role": "user", "content": user_input})

        return messages

    def get_conversation_history(self, context_id: str) -> list[dict[str, Any]]:
        return self.conversation_history.get(context_id, [])

    def update_conversation_history(self, context_id: str, user_input: str, response: str):
        if context_id not in self.conversation_history:
            self.conversation_history[context_id] = []

        self.conversation_history[context_id].append(
            {
                "user": user_input,
                "agent": response,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Keep last 20 turns to manage memory
        if len(self.conversation_history[context_id]) > 20:
            self.conversation_history[context_id] = self.conversation_history[context_id][-20:]
