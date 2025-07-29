import inspect
import re
from typing import Any

import structlog
from a2a.types import Task

logger = structlog.get_logger(__name__)


class FunctionExecutor:
    def __init__(self, function_registry, task: Task):
        self.function_registry = function_registry
        self.task = task

    async def execute_function_calls(self, llm_response: str) -> str:
        lines = llm_response.split("\n")
        function_results = []
        natural_response = []

        for line in lines:
            line = line.strip()
            if line.startswith("FUNCTION_CALL:"):
                # Parse function call
                function_call = line.replace("FUNCTION_CALL:", "").strip()
                try:
                    result = await self._execute_single_function_call(function_call)
                    function_results.append(result)
                except PermissionError as e:
                    # Generic error message to prevent scope information leakage
                    logger.warning(f"Permission denied for function call: {function_call}, error: {e}")
                    function_results.append("I'm unable to perform that action due to insufficient permissions.")
                except Exception as e:
                    logger.error(f"Function call failed: {function_call}, error: {e}")
                    function_results.append(f"Error: {str(e)}")
            else:
                # Natural language response
                if line and not line.startswith("FUNCTION_CALL:"):
                    natural_response.append(line)

        # Combine function results with natural response
        if function_results and natural_response:
            return f"{' '.join(natural_response)}\n\nResults: {'; '.join(function_results)}"
        elif function_results:
            return "; ".join(function_results)
        else:
            return " ".join(natural_response)

    async def _execute_single_function_call(self, function_call: str) -> str:
        # Simple parsing - in production, would use proper parsing

        # Extract function name and parameters
        match = re.match(r"(\w+)\((.*)\)", function_call)
        if not match:
            raise ValueError(f"Invalid function call format: {function_call}")

        function_name, params_str = match.groups()

        # Parse parameters (simplified - would need proper parsing in production)
        params = {}
        if params_str:
            # Basic parameter parsing
            param_pairs = params_str.split(",")
            for pair in param_pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    key = key.strip().strip('"')
                    value = value.strip().strip('"')
                    params[key] = value

        # Use the new function call method
        return await self.execute_function_call(function_name, params)

    async def execute_function_call(self, function_name: str, arguments: dict[str, Any]) -> str:
        try:
            # Check if this is an MCP tool
            if self.function_registry.is_mcp_tool(function_name):
                try:
                    result = await self.function_registry.call_mcp_tool(function_name, arguments)
                    return str(result)
                except PermissionError as e:
                    # Generic error message to prevent scope information leakage
                    logger.warning(f"Permission denied for MCP tool '{function_name}': {e}")
                    return "I'm unable to perform that action due to insufficient permissions."
                except Exception as e:
                    logger.error(f"MCP tool call failed: {function_name}, error: {e}")
                    raise

            # Handle local function
            handler = self.function_registry.get_handler(function_name)
            logger.info(f"Executing function '{function_name}' with arguments: {arguments}")
            if not handler:
                raise ValueError(f"Function not found: {function_name}")

            # Create task with function parameters
            task_with_params = self.task
            if hasattr(self.task, "metadata"):
                if self.task.metadata is None:
                    self.task.metadata = {}
                self.task.metadata.update(arguments)

            # Apply state management if handler accepts context parameters
            result = await self._execute_with_state_management(handler, task_with_params, function_name)
            return str(result)

        except PermissionError as e:
            # Generic error message to prevent scope information leakage
            logger.warning(f"Permission denied for function '{function_name}': {e}")
            return "I'm unable to perform that action due to insufficient permissions."

    async def _execute_with_state_management(self, handler, task, function_name: str):
        try:
            # Apply AI-compatible middleware first
            wrapped_handler = await self._apply_ai_middleware(handler, function_name)

            # Check if the function can accept context parameters
            sig = inspect.signature(wrapped_handler)
            accepts_context = "context" in sig.parameters
            accepts_context_id = "context_id" in sig.parameters

            if accepts_context or accepts_context_id:
                # Get state configuration and apply state management
                try:
                    from agent.capabilities.executors import _load_state_config
                    from agent.state.decorators import with_state

                    state_config = _load_state_config()
                    if state_config.get("enabled", False):
                        # Apply state management to this specific call
                        state_configs = [state_config]
                        wrapped_handler = with_state(state_configs)(wrapped_handler)

                        logger.debug(f"AI routing: Applied state management to function '{function_name}'")
                        return await wrapped_handler(task)
                    else:
                        logger.debug(f"AI routing: State management disabled for function '{function_name}'")

                except Exception as e:
                    logger.error(f"AI routing: Failed to apply state management to '{function_name}': {e}")

            # Execute handler normally (with AI middleware applied, with/without state)
            return await wrapped_handler(task)

        except Exception as e:
            logger.error(f"AI routing: Error executing function '{function_name}': {e}")
            raise

    async def _apply_ai_middleware(self, handler, function_name: str):
        try:
            from agent.middleware import execute_ai_function_with_middleware, get_ai_compatible_middleware

            # Check if there's any AI-compatible middleware to apply
            ai_middleware = get_ai_compatible_middleware()
            if not ai_middleware:
                logger.debug(f"AI routing: No AI-compatible middleware to apply to '{function_name}'")
                return handler

            # Create a wrapper that applies middleware
            async def middleware_wrapper(task):
                return await execute_ai_function_with_middleware(function_name, handler, task)

            return middleware_wrapper

        except Exception as e:
            logger.error(f"AI routing: Failed to apply AI middleware to '{function_name}': {e}")
            return handler
