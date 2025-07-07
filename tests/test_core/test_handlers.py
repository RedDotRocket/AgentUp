# import logging

# from a2a.types import Task

# from src.agent.handlers.handlers import register_handler

# logger = logging.getLogger(__name__)


# @register_handler("stateful_echo")
# async def handle_stateful_echo(task: Task, context=None, context_id=None) -> str:
#     """Echo handler that demonstrates state management."""

#     # Extract user message
#     user_message = "No message"
#     if task.history and len(task.history) > 0:
#         latest_message = task.history[-1]
#         if latest_message.parts and len(latest_message.parts) > 0:
#             user_message = latest_message.parts[0].text

#     response_parts = [f"Echo: {user_message}"]

#     # If we have state context, use it
#     if context and context_id:
#         try:
#             # Get previous message count
#             prev_count = await context.get_variable(context_id, "message_count", 0)
#             new_count = prev_count + 1

#             # Store updated count
#             await context.set_variable(context_id, "message_count", new_count)

#             # Store this message in history
#             await context.add_to_history(
#                 context_id,
#                 "user",
#                 user_message,
#                 {"timestamp": str(task.status.timestamp) if task.status and task.status.timestamp else "unknown"},
#             )

#             # Get recent history
#             history = await context.get_history(context_id, limit=3)

#             response_parts.append(f"Message count: {new_count}")
#             response_parts.append(f"Recent messages: {len(history)}")

#             logger.info(f"State used - Context ID: {context_id}, Count: {new_count}")

#         except Exception as e:
#             logger.error(f"State management error: {e}")
#             response_parts.append(f"State error: {e}")
#     else:
#         response_parts.append("No state management available")
#         logger.info("No state context provided")

#     return " | ".join(response_parts)


# @register_handler("stateful_counter")
# async def handle_stateful_counter(task: Task, context=None, context_id=None) -> str:
#     """Simple counter that persists state."""

#     if not context or not context_id:
#         return "Counter: No state management available"

#     try:
#         # Get current count
#         current_count = await context.get_variable(context_id, "counter", 0)
#         new_count = current_count + 1

#         # Store updated count
#         await context.set_variable(context_id, "counter", new_count)

#         logger.info(f"Counter updated - Context ID: {context_id}, Count: {new_count}")

#         return f"Counter: {new_count} (Context: {context_id})"

#     except Exception as e:
#         logger.error(f"Counter state error: {e}")
#         return f"Counter error: {e}"


# @register_handler("state_info")
# async def handle_state_info(task: Task, context=None, context_id=None) -> str:
#     """Show state management information."""

#     if not context or not context_id:
#         return "State Info: No state management available"

#     try:
#         # Get all variables for this context
#         variables = await context.get_variable(context_id, "_all_variables", {})
#         history_count = len(await context.get_history(context_id))

#         return f"State Info - Context: {context_id} | Variables: {len(variables)} | History: {history_count}"

#     except Exception as e:
#         logger.error(f"State info error: {e}")
#         return f"State info error: {e}"
