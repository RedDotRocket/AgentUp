from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog
from a2a.types import Task

from agent.services import get_services
from agent.services.llm.manager import LLMManager
from agent.state.conversation import ConversationManager
from agent.utils.messages import MessageProcessor

from .function_executor import FunctionExecutor

logger = structlog.get_logger(__name__)


class FunctionRegistry:
    """Registry for LLM-callable functions (plugins)."""

    def __init__(self):
        self._functions: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable] = {}
        self._mcp_tools: dict[str, dict[str, Any]] = {}
        self._mcp_client = None

    def register_function(self, name: str, handler: Callable, schema: dict[str, Any]):
        """Register a plugin as an LLM-callable function."""
        self._functions[name] = schema
        self._handlers[name] = handler
        logger.debug(f"Registered AI function: {name}")

    def get_function_schemas(self) -> list[dict[str, Any]]:
        """Get all function schemas for LLM function calling (local + MCP)."""
        all_schemas = list(self._functions.values())
        all_schemas.extend(self._mcp_tools.values())
        return all_schemas

    def get_handler(self, function_name: str) -> Callable | None:
        """Get handler for a function."""
        return self._handlers.get(function_name)

    def list_functions(self) -> list[str]:
        """list all registered function names (local + MCP)."""
        local_functions = list(self._functions.keys())
        mcp_functions = list(self._mcp_tools.keys())
        return local_functions + mcp_functions

    async def register_mcp_client(self, mcp_client) -> None:
        """Register MCP client and discover available tools."""
        # CONDITIONAL_MCP_IMPORTS
        logger.info(f"Registering MCP client, initialized: {mcp_client.is_initialized if mcp_client else False}")
        self._mcp_client = mcp_client

        if mcp_client and mcp_client.is_initialized:
            # Get available MCP tools
            mcp_tools = await mcp_client.get_available_tools()
            logger.info(f"Got {len(mcp_tools)} MCP tools from client")

            for tool_schema in mcp_tools:
                original_name = tool_schema.get("name", "unknown")
                # Convert MCP tool names to valid OpenAI function names
                # Replace colons with underscores: "filesystem:read_file" -> "filesystem_read_file"
                function_name = original_name.replace(":", "_")

                # Store with the cleaned name but keep original info
                cleaned_schema = tool_schema.copy()
                cleaned_schema["name"] = function_name
                cleaned_schema["original_name"] = original_name  # Keep for MCP calls

                self._mcp_tools[function_name] = cleaned_schema
                logger.info(f"Registered MCP tool in function registry: {original_name} -> {function_name}")
        else:
            logger.warning(
                f"Cannot register MCP client - client: {mcp_client is not None}, initialized: {mcp_client.is_initialized if mcp_client else False}"
            )

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool through the registered client."""
        if not self._mcp_client:
            raise ValueError("No MCP client registered")

        if tool_name not in self._mcp_tools:
            raise ValueError(f"MCP tool {tool_name} not found")

        # Get the original MCP tool name (with colon) for the actual call
        tool_schema = self._mcp_tools[tool_name]
        original_name = tool_schema.get("original_name", tool_name)

        return await self._mcp_client.call_tool(original_name, arguments)

    def is_mcp_tool(self, function_name: str) -> bool:
        """Check if a function is an MCP tool."""
        return function_name in self._mcp_tools


class FunctionDispatcher:
    """LLM-powered function dispatcher that maintains A2A compliance."""

    def __init__(self, function_registry: FunctionRegistry):
        self.function_registry = function_registry
        self.conversation_manager = ConversationManager()
        # Import StreamingHandler lazily to avoid circular imports
        from agent.api.streaming import StreamingHandler

        self.streaming_handler = StreamingHandler(function_registry, self.conversation_manager)

    async def process_task(self, task: Task) -> str:
        """Process A2A task using LLM intelligence.

        Args:
            task: A2A Task object

        Returns:
            str: Response content for A2A message
        """
        try:
            # Extract user message from A2A task (with multi-modal support)
            user_message = self._extract_user_message_full(task)
            if not user_message:
                return "I didn't receive any message to process."

            # Extract text from A2A parts or content for backwards compatibility
            if isinstance(user_message, dict):
                if "parts" in user_message:
                    # Extract text from A2A parts using proper structure
                    user_input = ""
                    for part in user_message["parts"]:
                        if hasattr(part, "root") and hasattr(part.root, "kind"):
                            if part.root.kind == "text" and hasattr(part.root, "text"):
                                user_input += part.root.text
                        elif hasattr(part, "text"):
                            user_input += part.text
                        elif isinstance(part, dict) and "text" in part:
                            user_input += part["text"]
                else:
                    # Fallback to content field
                    user_input = user_message.get("content", "")
            else:
                user_input = str(user_message)

            # Get LLM service with automatic provider selection
            services = get_services()
            llm = await LLMManager.get_llm_service(services)
            logger.debug(f"Selected LLM service: {llm.name if llm else 'None'}")
            if not llm:
                logger.warning("No LLM service available. Check that:")
                logger.warning("1. At least one LLM service is enabled in agent_config.yaml")
                logger.warning("2. Required API keys are set in environment variables")
                logger.warning("3. Service initialization completed successfully")
                logger.warning("Falling back to basic response")
                return self._fallback_response(user_input)

            # Get conversation context
            try:
                # Use contextId if available, otherwise use task ID
                # This allows for better conversation management across tasks
                logger.debug(f"Using context ID: {getattr(task, 'contextId', task.id)}")
                context_id = getattr(task, "contextId", task.id)
            except AttributeError:
                logger.warning("Task does not have contextId, using task ID instead")
                context_id = task.id

            try:
                conversation = self.conversation_manager.get_conversation_history(context_id)
            except KeyError:
                logger.warning(f"No conversation history found for context ID: {context_id}, starting fresh")
                conversation = []

            # Prepare LLM conversation with system prompt and function definitions
            try:
                logger.debug(f"Preparing conversation for LLM with user message: {user_message}")
                messages = await self.conversation_manager.prepare_llm_conversation(user_message, conversation)
            except Exception as e:
                logger.error(f"Error preparing conversation for LLM: {e}", exc_info=True)
                return f"I encountered an error preparing your request: {str(e)}"

            # Get available functions
            try:
                function_schemas = self.function_registry.get_function_schemas()
            except Exception as e:
                logger.error(f"Error retrieving function schemas: {e}", exc_info=True)
                return f"I encountered an error retrieving available functions: {str(e)}"
            logger.debug(f"Available function schemas: {function_schemas}")

            # Create function executor for this task
            function_executor = FunctionExecutor(self.function_registry, task)

            # Apply state management to AI routing
            ai_context = None
            ai_context_id = None
            try:
                ai_context, ai_context_id = await self._get_ai_routing_state_context(task)
                if ai_context and ai_context_id:
                    logger.info(f"AI routing: Applied state management for context {ai_context_id}")
                else:
                    logger.warning(
                        f"AI routing: No state context available - context={ai_context is not None}, context_id={ai_context_id}"
                    )
            except Exception as e:
                logger.error(f"AI routing: Failed to initialize state management: {e}")

            # LLM processing with function calling
            if function_schemas:
                try:
                    response = await LLMManager.llm_with_functions(llm, messages, function_schemas, function_executor)
                except Exception as e:
                    logger.error(f"Error during LLM function calling: {e}", exc_info=True)
                    return f"I encountered an error processing your request with functions: {str(e)}"
            else:
                # No functions available, direct LLM response
                try:
                    response = await LLMManager.llm_direct_response(llm, messages)
                    if not response:
                        logger.warning("LLM response was empty, falling back to default response")
                        response = "I received your message but could not generate a response. Please try again later."

                except Exception as e:
                    logger.error(f"Error during direct LLM response: {e}", exc_info=True)
                    return f"I encountered an error processing your request: {str(e)}"

            # Store AI routing state if available
            if ai_context and ai_context_id:
                try:
                    await self._store_ai_routing_state(ai_context, ai_context_id, user_input, response)
                    logger.info(f"AI routing: Stored conversation state for context {ai_context_id}")
                except Exception as e:
                    logger.error(f"AI routing: Failed to store state: {e}")
            else:
                logger.warning("AI routing: Skipping state storage - no context available")

            # Update conversation history
            self.conversation_manager.update_conversation_history(context_id, user_input, response)

            return response

        except Exception as e:
            logger.error(f"Function dispatcher error: {e}", exc_info=True)
            return f"I encountered an error processing your request: {str(e)}"

    async def _get_ai_routing_state_context(self, task: Task) -> tuple[Any, str] | tuple[None, None]:
        """Get state context for AI routing if state management is enabled."""
        try:
            from agent.handlers.handlers import _load_state_config
            from agent.state.context import get_context_manager

            state_config = _load_state_config()
            logger.info(
                f"AI routing: State config loaded - enabled={state_config.get('enabled', False)}, backend={state_config.get('backend', 'none')}"
            )

            if not state_config.get("enabled", False):
                logger.info("AI routing: State management disabled in config")
                return None, None

            backend = state_config.get("backend", "memory")
            backend_config = state_config.get("config", {})

            # Get context manager
            context = get_context_manager(backend, **backend_config)

            # Extract context ID from task
            context_id = getattr(task, "contextId", None) or getattr(task, "context_id", None) or task.id
            logger.info(
                f"AI routing: Using context_id={context_id} (contextId={getattr(task, 'contextId', 'missing')}, task.id={task.id})"
            )

            return context, context_id

        except Exception as e:
            logger.error(f"Failed to get AI routing state context: {e}")
            return None, None

    async def _store_ai_routing_state(self, context, context_id: str, user_input: str, response: str):
        """Store conversation state for AI routing."""
        try:
            # Get conversation count
            conversation_count = await context.get_variable(context_id, "ai_conversation_count", 0)
            conversation_count += 1
            await context.set_variable(context_id, "ai_conversation_count", conversation_count)

            # Store user preferences if mentioned in input
            if "favorite" in user_input.lower() or "prefer" in user_input.lower():
                preferences = await context.get_variable(context_id, "ai_preferences", {})
                # Simple preference extraction
                if "color" in user_input.lower():
                    colors = ["red", "blue", "green", "yellow", "purple", "orange", "pink", "black", "white"]
                    for color in colors:
                        if color in user_input.lower():
                            preferences["favorite_color"] = color
                            break
                await context.set_variable(context_id, "ai_preferences", preferences)
                logger.info(f"AI routing: Updated preferences for {context_id}: {preferences}")

            # Add to conversation history
            await context.add_to_history(
                context_id, "user", user_input, {"routing": "ai_direct", "count": conversation_count}
            )
            await context.add_to_history(
                context_id, "assistant", response, {"routing": "ai_direct", "count": conversation_count}
            )

            logger.info(f"AI routing: Stored state - Context: {context_id}, Count: {conversation_count}")

        except Exception as e:
            logger.error(f"Failed to store AI routing state: {e}")

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message from A2A task."""
        # Use existing MessageProcessor for A2A compliance
        messages = MessageProcessor.extract_messages(task)
        latest_message = MessageProcessor.get_latest_user_message(messages)

        if latest_message:
            return (
                latest_message.get("content", "")
                if isinstance(latest_message, dict)
                else getattr(latest_message, "content", "")
            )

        # Fallback to task metadata
        if hasattr(task, "metadata") and task.metadata:
            return task.metadata.get("user_input", "")

        return ""

    def _extract_user_message_full(self, task: Task) -> dict[str, Any] | str:
        """Extract full user message from A2A task with multi-modal support."""
        # Get the latest A2A message from task history
        if hasattr(task, "history") and task.history:
            for message in reversed(task.history):
                if hasattr(message, "role") and message.role == "user":
                    # Convert A2A Message to dict format for LLM processing
                    if hasattr(message, "parts") and message.parts:
                        return {
                            "role": "user",
                            "parts": message.parts,  # Keep full A2A parts for multi-modal
                            "messageId": getattr(message, "messageId", "unknown"),
                        }

        # Fallback to text extraction
        user_text = self._extract_user_message(task)
        if user_text:
            return {"role": "user", "content": user_text}

        return ""

    async def process_task_streaming(self, task: Task) -> AsyncIterator[str | dict[str, Any]]:
        """Process A2A task with streaming support."""
        async for chunk in self.streaming_handler.process_task_streaming(
            task, LLMManager, self._extract_user_message, self._fallback_response
        ):
            yield chunk

    async def cancel_task(self, task_id: str) -> None:
        """Cancel a running task if possible.

        Args:
            task_id: ID of the task to cancel
        """
        # This would need to be implemented based on your LLM provider's capabilities
        # Some providers support cancelling ongoing requests
        logger.info(f"Cancelling task: {task_id}")

        # Clean up any task-specific resources
        # For now, just log the cancellation
        pass

    def _fallback_response(self, user_input: str) -> str:
        """Fallback response when LLM is not available."""
        return f"I received your message: '{user_input}'. However, my AI capabilities are currently unavailable. Please try again later."


# Decorator for registering plugins as AI functions
def ai_function(description: str, parameters: dict[str, Any] | None = None):
    """Decorator to register a plugin as an LLM-callable function.

    Args:
        description: Description of what the function does
        parameters: Parameter schema for the function
    """

    def decorator(func: Callable):
        # Create function schema
        schema = {
            "name": func.__name__.replace("handle_", ""),
            "description": description,
        }

        if parameters:
            schema["parameters"] = {"type": "object", "properties": parameters, "required": list(parameters.keys())}

        # Store schema on function for later registration
        func._ai_function_schema = schema
        func._is_ai_function = True

        return func

    return decorator


# Global instances
_function_registry: FunctionRegistry | None = None
_function_dispatcher: FunctionDispatcher | None = None


def get_function_registry() -> FunctionRegistry:
    """Get the global function registry."""
    global _function_registry
    if _function_registry is None:
        _function_registry = FunctionRegistry()
    return _function_registry


def get_function_dispatcher() -> FunctionDispatcher:
    """Get the global function dispatcher."""
    global _function_dispatcher
    if _function_dispatcher is None:
        _function_dispatcher = FunctionDispatcher(get_function_registry())
    return _function_dispatcher


# Legacy compatibility
def get_dispatcher() -> FunctionDispatcher:
    """Legacy compatibility function - returns function dispatcher."""
    return get_function_dispatcher()


def register_ai_functions_from_handlers():
    """Auto-register functions from handlers with @ai_function decorator."""
    # CONDITIONAL_HANDLERS_IMPORT
    try:
        from agent.handlers import handlers

        # Also try importing individual handler modules
        handler_modules = []
        try:
            from agent.handlers import handlers as main_handlers

            handler_modules.append(main_handlers)
        except ImportError:
            pass

        # Dynamic discovery of handler modules
        # This will work with any handler modules that were successfully imported
        try:
            import sys
            from pathlib import Path

            # Get the handlers package
            handlers_pkg = sys.modules.get("src.agent.handlers") or sys.modules.get(".handlers", None)
            if handlers_pkg:
                handlers_dir = Path(handlers_pkg.__file__).parent

                # Find all potential handler modules
                for py_file in handlers_dir.glob("*.py"):
                    if py_file.name in ["__init__.py", "handlers.py", "handlers_multimodal.py"]:
                        continue

                    module_name = py_file.stem
                    module_attr_name = module_name

                    # Try to get the module from the handlers package
                    if hasattr(handlers_pkg, module_attr_name):
                        handler_module = getattr(handlers_pkg, module_attr_name)
                        if handler_module not in handler_modules:
                            handler_modules.append(handler_module)
                            logger.debug(f"Added dynamically discovered handler module: {module_name}")
                    else:
                        # Try to import it directly
                        try:
                            handler_module = __import__(f"src.agent.handlers.{module_name}", fromlist=[module_name])
                            if handler_module not in handler_modules:
                                handler_modules.append(handler_module)
                                logger.debug(f"Dynamically imported handler module: {module_name}")
                        except ImportError as e:
                            logger.debug(f"Could not dynamically import {module_name}: {e}")
                        except Exception as e:
                            logger.warning(f"Error dynamically importing {module_name}: {e}")

        except Exception as e:
            logger.debug(f"Dynamic handler discovery failed: {e}")

        # If no specific modules, scan the main handlers module
        if not handler_modules:
            handler_modules = [handlers]

    except ImportError:
        logger.warning("Handlers module not available for AI function registration")
        return

    registry = get_function_registry()
    registered_count = 0

    # Scan all handler modules for AI functions
    for handler_module in handler_modules:
        logger.info(f"Scanning module {handler_module.__name__} for AI functions")
        ai_functions_in_module = 0
        for name in dir(handler_module):
            obj = getattr(handler_module, name)
            if callable(obj):
                has_ai_flag = hasattr(obj, "_is_ai_function")
                has_schema = hasattr(obj, "_ai_function_schema")

                # Only log functions that might be AI functions (start with handle_ or have AI attributes)
                if name.startswith("handle_") or has_ai_flag or has_schema:
                    logger.info(
                        f"Function {name}: callable=True, _is_ai_function={has_ai_flag}, _ai_function_schema={has_schema}"
                    )

                if has_ai_flag and has_schema:
                    schema = obj._ai_function_schema
                    registry.register_function(schema["name"], obj, schema)
                    logger.debug(f"Auto-registered AI function: {schema['name']} from {name}")
                    registered_count += 1
                    ai_functions_in_module += 1

        logger.info(f"Module {handler_module.__name__}: found {ai_functions_in_module} AI functions")

    logger.info(f"Registered {registered_count} AI functions from handlers")

    # Also register AI functions from plugins
    try:
        from agent.plugins.integration import get_plugin_adapter

        plugin_adapter = get_plugin_adapter()
        if plugin_adapter:
            plugin_functions_count = 0

            # Get all available plugin capabilities
            available_plugins = plugin_adapter.list_available_capabilities()

            # Get configured plugins from agent config
            try:
                from agent.config import load_config

                config = load_config()
                configured_plugins = {plugin.get("plugin_id") for plugin in config.get("plugins", [])}
            except Exception as e:
                logger.warning(f"Could not load agent config for plugin AI functions: {e}")
                configured_plugins = set(available_plugins)

            # Register AI functions only for configured plugins
            for plugin_id in available_plugins:
                if plugin_id not in configured_plugins:
                    logger.debug(f"Skipping AI functions for unconfigured plugin: {plugin_id}")
                    continue

                ai_functions = plugin_adapter.get_ai_functions(plugin_id)
                for ai_function in ai_functions:
                    # Convert plugin AIFunction to registry format
                    schema = {
                        "name": ai_function.name,
                        "description": ai_function.description,
                        "parameters": ai_function.parameters,
                    }

                    # Create a wrapper handler that uses the plugin's handler
                    # Use factory function to capture ai_function correctly
                    def create_wrapper(func_handler):
                        async def plugin_function_wrapper(task, **kwargs):
                            # Create plugin context from task
                            from agent.plugins.models import CapabilityContext

                            context = CapabilityContext(task=task, metadata={"parameters": kwargs})
                            result = await func_handler(task, context)
                            return result.content if hasattr(result, "content") else str(result)

                        return plugin_function_wrapper

                    wrapped_handler = create_wrapper(ai_function.handler)
                    registry.register_function(ai_function.name, wrapped_handler, schema)
                    logger.debug(f"Registered plugin AI function: {ai_function.name} from {plugin_id}")
                    plugin_functions_count += 1

            if plugin_functions_count > 0:
                logger.info(f"Registered {plugin_functions_count} AI functions from plugins")
        else:
            logger.debug("No plugin adapter available for AI function registration")

    except ImportError:
        logger.debug("Plugin system not available for AI function registration")
    except Exception as e:
        logger.error(f"Failed to register plugin AI functions: {e}", exc_info=True)
