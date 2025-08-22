from collections.abc import Callable
from typing import Any, cast

import structlog
from a2a.types import Task

from agent.services import get_services
from agent.services.llm.manager import LLMManager
from agent.state.conversation import ConversationManager
from agent.utils.messages import MessageProcessor

from .function_executor import FunctionExecutor

logger = structlog.get_logger(__name__)


class FunctionRegistry:
    """
    Function registry model for managing available functions.

    This class provides a centralized registry for functions, including
    local functions, MCP tools, and their handlers. It supports registration,
    retrieval, and filtering of functions based on user scopes.
    """

    def __init__(self):
        self._functions: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable] = {}
        self._mcp_tools: dict[str, dict[str, Any]] = {}
        self._mcp_client = None

    def register_function(self, name: str, handler: Callable, schema: dict[str, Any]):
        if name in self._functions:
            # Check if this is the same function being registered again
            existing_schema = self._functions[name]
            if existing_schema.get("description") == schema.get("description") and existing_schema.get(
                "parameters"
            ) == schema.get("parameters"):
                logger.debug(f"Function '{name}' already registered with same schema - skipping duplicate")
                return
            else:
                logger.warning(f"Function '{name}' being re-registered with different schema - overriding")

        self._functions[name] = schema
        self._handlers[name] = handler
        logger.debug(f"Registered function '{name}' in registry")

    def get_function_schemas(self) -> list[dict[str, Any]]:
        # Use a dict to deduplicate by function name
        schema_dict = {}

        # Add local functions
        for schema in self._functions.values():
            name = schema.get("name")
            if name:
                schema_dict[name] = schema

        # Add MCP tools (may override local functions with same name)
        for schema in self._mcp_tools.values():
            name = schema.get("name")
            if name:
                if name in schema_dict:
                    logger.debug(f"MCP tool '{name}' overrides local function with same name")
                schema_dict[name] = schema

        return list(schema_dict.values())

    def get_available_tools_for_ai(self, user_scopes: set[str]) -> list[dict[str, Any]]:
        """Filter tools based on user scopes - AI sees only what it can use.

        The AI will only see tools that the user has permission to use, providing transparent
        security without the AI needing to know about scopes.

        Args:
            user_scopes: Set of scopes the user has access to

        Returns:
            list[dict[str, Any]]: List of tool schemas filtered by user permissions
        """
        scope_service = None
        try:
            from agent.security.scope_service import get_scope_service

            # If no scopes provided, return empty list for security
            if not user_scopes:
                return []

            scope_service = get_scope_service()
            if not scope_service._hierarchy:
                logger.error("No scope hierarchy available - denying all tool access")
                return []

            available_tools = []
            logger.debug("Using optimized scope service for tool filtering")

            # Start request-scoped cache
            _cache = scope_service.start_request_cache()

            # Check local plugin capabilities
            try:
                available_tools.extend(self._get_plugin_tools(scope_service, user_scopes))
            except Exception as e:
                logger.warning(f"Failed to filter plugin tools by scopes: {e}")
                # Security: Do NOT fallback to all tools - continue with empty plugin tools list

            # Check MCP tools with scope enforcement
            try:
                available_tools.extend(self._get_mcp_tools(scope_service, user_scopes))
            except Exception as e:
                logger.warning(f"Failed to filter MCP tools by scopes: {e}")
                # Security: Do NOT fallback to all tools

            # Deduplicate tools by name before returning
            deduplicated_tools = {}
            for tool in available_tools:
                name = tool.get("name")
                if name:
                    if name in deduplicated_tools:
                        logger.debug(f"Removing duplicate tool: {name}")
                    deduplicated_tools[name] = tool

            final_tools = list(deduplicated_tools.values())

            logger.info(
                f"AI tool filtering completed: {len(final_tools)} tools available for user (removed {len(available_tools) - len(final_tools)} duplicates)"
            )
            if final_tools:
                tool_names = [tool.get("name", "unnamed") for tool in final_tools]
                logger.debug(f"Tools granted to user: {tool_names}")

            # Clean up request cache
            scope_service.clear_request_cache()

            return final_tools

        except Exception as e:
            logger.error(f"Failed to filter tools by user scopes: {e}")
            # Clean up cache on error
            if scope_service:
                try:
                    scope_service.clear_request_cache()
                except Exception:
                    pass  # nosec
            return []

    def _get_plugin_tools(self, scope_service, user_scopes: set[str]) -> list[dict[str, Any]]:
        from agent.plugins.integration import get_plugin_adapter
        from agent.security.audit_logger import get_security_audit_logger

        tools = []
        plugin_adapter = get_plugin_adapter()
        audit_logger = get_security_audit_logger()

        # Get current user ID for audit logging
        user_id = None
        try:
            from agent.security.context import get_current_auth

            auth_result = get_current_auth()
            if auth_result:
                user_id = getattr(auth_result, "user_id", None)
        except Exception:
            pass  # nosec

        # Generate unique session ID for unauthenticated users
        if not user_id:
            import hashlib
            import uuid

            user_id = f"session_{hashlib.sha256(uuid.uuid4().bytes).hexdigest()}"

        if not plugin_adapter:
            return tools

        # Get plugins from the integration system instead of old config
        from agent.plugins.integration import get_plugin_registry_instance

        plugin_registry = get_plugin_registry_instance()

        if not plugin_registry:
            return tools

        for plugin_name, plugin_instance in plugin_registry.plugins.items():
            if not plugin_name:
                continue

            # Get capabilities from modern decorator-based plugins
            try:
                plugin_capabilities = plugin_instance.get_capability_definitions()

                for capability_def in plugin_capabilities:
                    capability_id = capability_def.id
                    # Get required scopes from the @capability decorator
                    required_scopes = capability_def.required_scopes

                    # Use centralized scope validation
                    result = scope_service.validate_multiple_scopes(user_scopes, required_scopes)

                    if result.has_access:
                        # Get AI functions for this capability
                        ai_functions = plugin_adapter.get_ai_functions(capability_id)
                        for ai_function in ai_functions:
                            tool_spec = {
                                "name": ai_function.name,
                                "description": ai_function.description,
                                "parameters": ai_function.parameters,
                            }
                            tools.append(tool_spec)
                    else:
                        # Log function access denied for security audit
                        ai_functions = plugin_adapter.get_ai_functions(capability_id)
                        for ai_function in ai_functions:
                            audit_logger.log_function_access_denied(user_id, ai_function.name, len(required_scopes))
            except Exception as e:
                logger.warning(f"Failed to get capabilities for plugin '{plugin_name}': {e}")
                continue
        return tools

    def _get_mcp_tools(self, scope_service, user_scopes: set[str]) -> list[dict[str, Any]]:
        from agent.config import Config

        tools = []

        if not Config.mcp.client_enabled:
            return tools

        servers = Config.mcp.servers

        # Extract tool scopes from server configuration
        from agent.mcp_support.mcp_integration import _extract_tool_scopes_from_servers

        tool_scopes = _extract_tool_scopes_from_servers(servers)

        # Filter MCP tools based on scopes
        for tool_name, tool_schema in self._mcp_tools.items():
            # Get the original name (with colon) to check scopes
            original_name = tool_schema.get("original_name", tool_name)
            required_scopes = tool_scopes.get(original_name, ["mcp:access"])  # Default to mcp:access

            # Use centralized scope validation
            result = scope_service.validate_multiple_scopes(user_scopes, required_scopes)
            if result.has_access:
                tools.append(tool_schema)
                logger.debug(f"Granted MCP tool '{tool_name}' (original: '{original_name}')")

        return tools

    def get_handler(self, function_name: str) -> Callable | None:
        return self._handlers.get(function_name)

    def list_functions(self) -> list[str]:
        local_functions = list(self._functions.keys())
        mcp_functions = list(self._mcp_tools.keys())
        return local_functions + mcp_functions

    async def register_mcp_client(self, mcp_client) -> None:
        # CONDITIONAL_MCP_IMPORTS
        logger.debug(f"Registering MCP client, initialized: {mcp_client.is_initialized if mcp_client else False}")
        self._mcp_client = mcp_client

        if mcp_client and mcp_client.is_initialized:
            # Get available MCP tools
            mcp_tools = await mcp_client.get_available_tools()
            logger.debug(f"Got {len(mcp_tools)} MCP tools from client")

            for tool_schema in mcp_tools:
                original_name = tool_schema.get("name", "unknown")
                # Convert MCP tool names to valid OpenAI function names
                # Replace colons with underscores: "filesystem:read_file" -> "filesystem_read_file"
                function_name = original_name.replace(":", "_")

                # Only register if not already registered by register_mcp_tool (which has better scope handling)
                if function_name not in self._mcp_tools:
                    # Store with the cleaned name but keep original info
                    cleaned_schema = tool_schema.copy()
                    cleaned_schema["name"] = function_name
                    cleaned_schema["original_name"] = original_name  # Keep for MCP calls

                    self._mcp_tools[function_name] = cleaned_schema
                    logger.debug(f"Registered MCP tool in function registry: {original_name} -> {function_name}")
                else:
                    logger.debug(f"Skipping MCP tool '{function_name}' - already registered with scope enforcement")
        else:
            logger.warning(
                f"Cannot register MCP client - client: {mcp_client is not None}, initialized: {mcp_client.is_initialized if mcp_client else False}"
            )

    async def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if not self._mcp_client:
            raise ValueError("No MCP client registered")

        if tool_name not in self._mcp_tools:
            raise ValueError(f"MCP tool {tool_name} not found")

        # Get the original MCP tool name (with colon) for the actual call
        tool_schema = self._mcp_tools[tool_name]
        original_name = tool_schema.get("original_name", tool_name)

        return await self._mcp_client.call_tool(original_name, arguments)

    def is_mcp_tool(self, function_name: str) -> bool:
        return function_name in self._mcp_tools

    async def register_mcp_tool(self, tool_name: str, wrapped_tool, tool_schema):
        # Add the scope-enforced tool to the function schemas for AI
        self._mcp_tools[tool_name] = tool_schema

        # Register the wrapped handler for execution
        self._handlers[tool_name] = wrapped_tool

        logger.debug(f"Registered MCP tool '{tool_name}' with scope enforcement")


class FunctionDispatcher:
    def __init__(self, function_registry: FunctionRegistry):
        self.function_registry = function_registry
        self.conversation_manager = ConversationManager()
        # Import StreamingHandler lazily to avoid circular imports
        from agent.api.streaming import StreamingHandler

        self.streaming_handler = StreamingHandler(function_registry, self.conversation_manager)

    async def process_task(self, task: Task, auth_result=None) -> str:
        """Process A2A task using LLM intelligence.

        Args:
            task: A2A Task object
            auth_result: Optional authentication result (will use current context if not provided)

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
                logger.warning("1. At least one LLM service is enabled in agentup.yml")
                logger.warning("2. Required API keys are set in environment variables")
                logger.warning("3. Service initialization completed successfully")
                logger.warning("Falling back to basic response")
                return self._fallback_response(user_input)

            # Get conversation context
            try:
                # Use context_id if available, otherwise use task ID
                # This allows for better conversation management across tasks
                logger.debug(f"Using context ID: {getattr(task, 'context_id', task.id)}")
                context_id = getattr(task, "context_id", task.id)
            except AttributeError:
                logger.warning("Task does not have context_id, using task ID instead")
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

            # Get available functions filtered by user scopes
            try:
                # Use provided auth_result or try to get from authentication context
                if auth_result is None:
                    from agent.security.context import get_current_auth

                    auth_result = get_current_auth()

                logger.debug(f"Authentication context: {auth_result is not None}")
                if auth_result:
                    logger.debug(f"User scopes: {auth_result.scopes}")
                    logger.debug(f"User ID: {getattr(auth_result, 'user_id', 'unknown')}")
                if auth_result:
                    # User is authenticated - use scope-filtered tools (even if scopes are empty)
                    function_schemas = self.function_registry.get_available_tools_for_ai(auth_result.scopes)
                    if auth_result.scopes:
                        logger.debug(f"Using scope-filtered tools for user with {len(auth_result.scopes)} scopes")
                    else:
                        logger.warning(
                            f"User '{getattr(auth_result, 'user_id', 'unknown')}' has no scopes - no tools available"
                        )
                else:
                    # No authentication - no tools available
                    function_schemas = []
                    logger.error("No authentication context found - denying all tool access")
            except Exception as e:
                logger.error(f"Error retrieving function schemas: {e}", exc_info=True)
                function_schemas = []
            logger.info(f"Available function schemas for AI: {len(function_schemas)} functions")
            if len(function_schemas) == 0:
                logger.warning("No function schemas available for AI - this will prevent tool calling")
                logger.warning(
                    "Possible causes: 1) No user scopes, 2) All tools filtered out by scopes, 3) No tools configured"
                )
            else:
                function_names = [schema.get("name", "unnamed") for schema in function_schemas]
                logger.debug(f"Available functions for AI: {function_names}")

            # Create function executor for this task
            function_executor = FunctionExecutor(self.function_registry, task)

            # Apply state management to AI processing
            ai_context = None
            ai_context_id = None
            try:
                ai_context, ai_context_id = await self._get_ai_processing_state_context(task)
                if ai_context and ai_context_id:
                    logger.debug(f"AI processing: Applied state management for context {ai_context_id}")
                else:
                    logger.warning(
                        f"AI processing: No state context available - context={ai_context is not None}, context_id={ai_context_id}"
                    )
            except Exception as e:
                logger.error(f"AI processing: Failed to initialize state management: {e}")

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

            # Store AI processing state if available
            if ai_context and ai_context_id:
                try:
                    await self._store_ai_processing_state(ai_context, ai_context_id, user_input, response)
                    logger.info(f"AI processing: Stored conversation state for context {ai_context_id}")
                except Exception as e:
                    logger.error(f"AI processing: Failed to store state: {e}")
            else:
                logger.warning("AI processing: Skipping state storage - no context available")

            # Update conversation history
            self.conversation_manager.update_conversation_history(context_id, user_input, response)

            return response

        except Exception as e:
            logger.error(f"Function dispatcher error: {e}", exc_info=True)
            return f"I encountered an error processing your request: {str(e)}"

    async def _get_ai_processing_state_context(self, task: Task) -> tuple[Any, str] | tuple[None, None]:
        try:
            from agent.capabilities.manager import _load_state_config
            from agent.state.context import get_context_manager

            state_config = _load_state_config()
            logger.info(
                f"AI processing: State config loaded - enabled={state_config.get('enabled', False)}, backend={state_config.get('backend', 'none')}"
            )

            if not state_config.get("enabled", False):
                logger.info("AI processing: State management disabled in config")
                return None, None

            backend = state_config.get("backend", "memory")
            backend_config = state_config.get("config", {})

            # Get context manager
            context = get_context_manager(backend, **backend_config)

            # Extract context ID from task
            context_id = getattr(task, "context_id", None) or getattr(task, "context_id", None) or task.id
            logger.info(
                f"AI processing: Using context_id={context_id} (context_id={getattr(task, 'context_id', 'missing')}, task.id={task.id})"
            )

            return context, context_id

        except Exception as e:
            logger.error(f"Failed to get AI processing state context: {e}")
            return None, None

    async def _store_ai_processing_state(self, context, context_id: str, user_input: str, response: str):
        try:
            # Get conversation count
            conversation_count = await context.get_variable(context_id, "ai_conversation_count", 0)
            conversation_count += 1
            await context.set_variable(context_id, "ai_conversation_count", conversation_count)

            # Add to conversation history
            await context.add_to_history(
                context_id,
                "user",
                user_input,
                {"processing": "ai_direct", "count": conversation_count},
            )
            await context.add_to_history(
                context_id,
                "assistant",
                response,
                {"processing": "ai_direct", "count": conversation_count},
            )

            logger.info(f"AI processing: Stored state - Context: {context_id}, Count: {conversation_count}")

        except Exception as e:
            logger.error(f"Failed to store AI processing state: {e}")

    def _extract_user_message(self, task: Task) -> str:
        # Use existing MessageProcessor for A2A compliance
        messages = MessageProcessor.extract_messages(task)
        latest_message = MessageProcessor.get_latest_user_message(cast(Any, messages))

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
        # Get the latest A2A message from task history
        if hasattr(task, "history") and task.history:
            for message in reversed(task.history):
                if hasattr(message, "role") and message.role == "user":
                    # Convert A2A Message to dict format for LLM processing
                    if hasattr(message, "parts") and message.parts:
                        return {
                            "role": "user",
                            "parts": message.parts,  # Keep full A2A parts for multi-modal
                            "message_id": getattr(message, "message_id", "unknown"),
                        }

        # Fallback to text extraction
        user_text = self._extract_user_message(task)
        if user_text:
            return {"role": "user", "content": user_text}

        return ""

    async def cancel_task(self, task_id: str) -> None:
        """Cancel a running task if possible.

        Args:
            task_id: ID of the task to cancel
        """
        # This would need to be implemented based on the LLM provider's capabilities
        # Some providers support cancelling ongoing requests
        logger.info(f"Cancelling task: {task_id}")

        # Clean up any task-specific resources
        # For now, just log the cancellation
        pass

    def _fallback_response(self, user_input: str) -> str:
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
        schema: dict[str, Any] = {
            "name": func.__name__.replace("handle_", ""),
            "description": description,
        }

        if parameters:
            schema["parameters"] = {
                "type": "object",
                "properties": parameters,
                "required": list(parameters.keys()),
            }

        # Store schema on function for later registration
        func._ai_function_schema = schema  # type: ignore[attr-defined]
        func._is_ai_function = True  # type: ignore[attr-defined]

        return func

    return decorator


# Global instances
_function_registry: FunctionRegistry | None = None
_function_dispatcher: FunctionDispatcher | None = None


def get_function_registry() -> FunctionRegistry:
    global _function_registry
    if _function_registry is None:
        _function_registry = FunctionRegistry()
        # Register AI functions from capabilities when registry is first created
        register_ai_functions_from_capabilities()
    return _function_registry


def get_function_dispatcher() -> FunctionDispatcher:
    global _function_dispatcher
    if _function_dispatcher is None:
        _function_dispatcher = FunctionDispatcher(get_function_registry())
    return _function_dispatcher


# Legacy compatibility
def get_dispatcher() -> FunctionDispatcher:
    return get_function_dispatcher()


def register_ai_functions_from_capabilities():
    # CONDITIONAL_EXECUTORS_IMPORT
    try:
        from agent.capabilities import manager

        # Also try importing individual executor modules
        executor_modules = []
        try:
            from agent.capabilities import manager as main_executors

            executor_modules.append(main_executors)
        except ImportError:
            pass

        # Dynamic discovery of capability modules
        # This will work with any capability modules that were successfully imported
        try:
            import sys
            from pathlib import Path

            # Get the capabilities package
            capabilities_pkg = sys.modules.get("src.agent.capabilities") or sys.modules.get(".capabilities", None)
            if capabilities_pkg and capabilities_pkg.__file__:
                capabilities_dir = Path(capabilities_pkg.__file__).parent

                # Find all potential capability modules
                for py_file in capabilities_dir.glob("*.py"):
                    if py_file.name in ["__init__.py", "executors.py", "executors_multimodal.py"]:
                        continue

                    module_name = py_file.stem
                    module_attr_name = module_name

                    # Try to get the module from the capabilities package
                    if hasattr(capabilities_pkg, module_attr_name):
                        executor_module = getattr(capabilities_pkg, module_attr_name)
                        if executor_module not in executor_modules:
                            executor_modules.append(executor_module)
                            logger.debug(f"Added dynamically discovered capability module: {module_name}")
                    else:
                        # Try to import it directly
                        try:
                            executor_module = __import__(
                                f"src.agent.capabilities.{module_name}", fromlist=[module_name]
                            )
                            if executor_module not in executor_modules:
                                executor_modules.append(executor_module)
                                logger.debug(f"Dynamically imported capability module: {module_name}")
                        except ImportError as e:
                            logger.debug(f"Could not dynamically import {module_name}: {e}")
                        except Exception as e:
                            logger.warning(f"Error dynamically importing {module_name}: {e}")

        except Exception as e:
            logger.debug(f"Dynamic capability discovery failed: {e}")

        # If no specific modules, scan the main executors module
        if not executor_modules:
            executor_modules = [manager]

    except ImportError:
        logger.warning("Capabilities module not available for AI function registration")
        return

    registry = get_function_registry()
    registered_count = 0

    # Scan all capability modules for AI functions
    for executor_module in executor_modules:
        logger.debug(f"Scanning capability modules {executor_module.__name__} for AI functions")
        ai_functions_in_module = 0
        for name in dir(executor_module):
            obj = getattr(executor_module, name)
            if callable(obj):
                has_ai_flag = hasattr(obj, "_is_ai_function")
                has_schema = hasattr(obj, "_ai_function_schema")

                # Only log functions that might be AI functions (start with handle_ or have AI attributes)
                # TODO: We can likely drop this, its from a debugging phase (Luke), but will keep for now
                # and mark down to debug level
                if name.startswith("handle_") or has_ai_flag or has_schema:
                    logger.debug(
                        f"Function {name}: callable=True, _is_ai_function={has_ai_flag}, _ai_function_schema={has_schema}"
                    )

                if has_ai_flag and has_schema:
                    schema = obj._ai_function_schema  # type: ignore[attr-defined]
                    registry.register_function(schema["name"], obj, schema)
                    logger.debug(f"Auto-registered AI function: {schema['name']} from {name}")
                    registered_count += 1
                    ai_functions_in_module += 1

        logger.debug(f"Module {executor_module.__name__}: found {ai_functions_in_module} AI functions")

    # Also register AI functions from plugins
    try:
        from agent.plugins.integration import get_plugin_adapter

        plugin_adapter = get_plugin_adapter()
        if plugin_adapter:
            plugin_functions_count = 0

            # Get all available plugin capabilities
            available_plugins = plugin_adapter.list_available_capabilities()

            # Get configured plugins from unified configuration
            try:
                from agent.config.plugin_resolver import get_plugin_resolver

                resolver = get_plugin_resolver()
                if resolver:
                    # Get enabled plugins from intent config
                    enabled_plugins = {}
                    for package_name, plugin_config in resolver.intent_config.plugins.items():
                        if hasattr(plugin_config, "enabled") and plugin_config.enabled:
                            enabled_plugins[package_name] = plugin_config
                    configured_plugins = set(enabled_plugins.keys())
                else:
                    configured_plugins = set()
            except Exception as e:
                logger.warning(f"Could not load unified plugin config for AI functions: {e}")
                configured_plugins = set()

            # Build mapping of plugin names to capabilities
            plugin_to_capabilities = {}
            for capability_id in available_plugins:
                capability_info = plugin_adapter.get_capability_info(capability_id)
                if capability_info and "plugin_name" in capability_info:
                    plugin_name = capability_info["plugin_name"]
                    if plugin_name not in plugin_to_capabilities:
                        plugin_to_capabilities[plugin_name] = []
                    plugin_to_capabilities[plugin_name].append(capability_id)

            # Register AI functions only for capabilities from configured plugins
            for capability_id in available_plugins:
                capability_info = plugin_adapter.get_capability_info(capability_id)
                if not capability_info or "plugin_name" not in capability_info:
                    continue

                plugin_name = capability_info["plugin_name"]

                # Normalize plugin name to match configuration format (hyphens)
                normalized_plugin_name = plugin_name.replace("_", "-")
                if normalized_plugin_name not in configured_plugins:
                    continue

                ai_functions = plugin_adapter.get_ai_functions(capability_id)

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
                            # func_handler is already bound to the plugin instance, just pass context
                            result = await func_handler(context)
                            return result.content if hasattr(result, "content") else str(result)

                        return plugin_function_wrapper

                    wrapped_handler = create_wrapper(ai_function.handler)
                    registry.register_function(ai_function.name, wrapped_handler, schema)
                    plugin_functions_count += 1

            if plugin_functions_count > 0:
                logger.info(f"Registered {plugin_functions_count} AI functions from plugins")
        else:
            logger.debug("No plugin adapter available for AI function registration")

    except ImportError:
        logger.debug("Plugin system not available for AI function registration")
    except Exception as e:
        logger.error(f"Failed to register plugin AI functions: {e}", exc_info=True)
