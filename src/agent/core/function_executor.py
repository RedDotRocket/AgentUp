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

    async def execute_function_call(self, function_name: str, arguments: dict[str, Any]) -> str | Any:
        """Execute a function call with comprehensive security error handling."""
        import traceback
        import uuid

        from agent.security.audit_logger import get_security_audit_logger

        # Generate correlation ID for security tracking
        correlation_id = str(uuid.uuid4())[:8]
        audit_logger = get_security_audit_logger()

        try:
            # Check if this is an MCP tool
            if self.function_registry.is_mcp_tool(function_name):
                try:
                    result = await self.function_registry.call_mcp_tool(function_name, arguments)
                    logger.info(f"MCP tool '{function_name}' completed [corr:{correlation_id}]")
                    return str(result)
                except PermissionError:
                    # Security audit logging for permission denials
                    audit_logger.log_authorization_failure(
                        user_id="system", resource=f"mcp_tool:{function_name}", action="execute"
                    )
                    # Generic error message to prevent information leakage
                    logger.warning(f"Permission denied for MCP tool '{function_name}' [corr:{correlation_id}]")
                    return "I'm unable to perform that action due to insufficient permissions."
                except Exception as e:
                    # Log detailed error for debugging but don't expose to user
                    logger.error(f"MCP tool call failed: {function_name} [corr:{correlation_id}], error: {e}")
                    audit_logger.log_configuration_error(
                        "mcp_tool_execution",
                        "mcp_tool_execution_failed",
                        {
                            "correlation_id": correlation_id,
                            "error_type": type(e).__name__,
                            "function_name": function_name,
                        },
                    )
                    # Return generic error to user
                    return f"An error occurred while executing the requested action [ref:{correlation_id}]"

            # Handle local function
            handler = self.function_registry.get_handler(function_name)
            logger.debug(f"Handler for '{function_name}': {handler} [corr:{correlation_id}]")
            logger.info(f"Executing function '{function_name}' [corr:{correlation_id}]")

            if not handler:
                error_msg = (
                    f"Function '{function_name}' not found in handlers: {self.function_registry.list_functions()}"
                )
                logger.error(f"{error_msg} [corr:{correlation_id}]")
                audit_logger.log_configuration_error(
                    "function_registry",
                    "function_not_found",
                    {
                        "correlation_id": correlation_id,
                        "function_name": function_name,
                        "available_functions_count": len(self.function_registry.list_functions()),
                    },
                )
                # Don't expose internal function list to user
                return f"The requested function is not available [ref:{correlation_id}]"

            # Create task with function parameters - validate parameter safety
            # Create a copy of the task to avoid mutating the original's metadata
            import copy

            task_with_params = copy.deepcopy(self.task)
            if not hasattr(task_with_params, "metadata") or task_with_params.metadata is None:
                task_with_params.metadata = {}

            # Sanitize arguments before adding to task metadata
            sanitized_arguments = self._sanitize_function_arguments(arguments, correlation_id)
            task_with_params.metadata.update(sanitized_arguments)

            # Apply state management if handler accepts context parameters
            result = await self._execute_with_state_management(handler, task_with_params, function_name)

            # Check if result is a FunctionExecutionResult - preserve it for completion signaling
            from agent.core.models.iteration import FunctionExecutionResult

            if isinstance(result, FunctionExecutionResult):
                logger.info(f"Function '{function_name}' completed [corr:{correlation_id}]")
                return result  # Return as-is for completion detection
            else:
                logger.info(f"Function '{function_name}' completed [corr:{correlation_id}]")
                return str(result)

        except PermissionError as e:
            # Security audit logging for permission denials
            audit_logger.log_authorization_failure(
                user_id="system", resource=f"function:{function_name}", action="execute"
            )
            # Generic error message to prevent scope information leakage
            logger.warning(f"Permission denied for function '{function_name}' [corr:{correlation_id}]: {str(e)[:100]}")
            return "I'm unable to perform that action due to insufficient permissions."

        except ValueError as e:
            # Handle validation errors securely
            logger.warning(f"Validation error in function '{function_name}' [corr:{correlation_id}]: {str(e)[:100]}")
            audit_logger.log_configuration_error(
                "function_validation",
                "function_validation_failed",
                {
                    "correlation_id": correlation_id,
                    "error_type": "ValueError",
                    "function_name": function_name,
                },
            )
            return f"Invalid request format [ref:{correlation_id}]"

        except Exception as e:
            # Comprehensive error handling with security audit
            error_type = type(e).__name__

            # Full error details for debugging (server logs only)
            logger.error(
                f"Function execution failed: {function_name} [corr:{correlation_id}]",
                exc_info=True,
                extra={
                    "function_name": function_name,
                    "error_type": error_type,
                    "correlation_id": correlation_id,
                    "arguments": str(arguments)[:200],
                },
            )

            # Security audit for system errors
            audit_logger.log_configuration_error(
                "function_execution",
                "function_execution_failed",
                {
                    "correlation_id": correlation_id,
                    "error_type": error_type,
                    "function_name": function_name,
                    "stack_trace": traceback.format_exc()[:500],  # Truncated stack trace
                },
            )

            # Generic error message for user (no sensitive details)
            return f"An error occurred while processing your request [ref:{correlation_id}]"

    def _sanitize_function_arguments(self, arguments: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        """Sanitize function arguments to prevent injection attacks."""
        # Get configuration for security settings
        try:
            from agent.config import get_config

            config = get_config()
            security_config = config.security

            # Check if sanitization is disabled
            if not security_config.sanitization_enabled:
                logger.debug(f"Function argument sanitization disabled [corr:{correlation_id}]")
                return arguments

            # Get configurable string length limit
            max_string_length = security_config.max_string_length
            # A value of -1 indicates no limit. This is handled in the truncation logic below.

        except Exception as e:
            logger.warning(f"Failed to load security config, using defaults [corr:{correlation_id}]: {e}")
            max_string_length = 100000  # Fallback to 100KB

        MAX_NESTED_DEPTH = 5
        ALLOWED_TYPES = (str, int, float, bool, list, dict, type(None))

        def _sanitize_value(value, depth=0):
            if depth > MAX_NESTED_DEPTH:
                logger.warning(f"Argument nesting too deep, truncating [corr:{correlation_id}]")
                return None

            if not isinstance(value, ALLOWED_TYPES):
                logger.warning(f"Disallowed argument type: {type(value)} [corr:{correlation_id}]")
                sanitized_str = str(value)
                if max_string_length != -1:
                    return sanitized_str[:max_string_length]
                return sanitized_str

            if isinstance(value, str):
                # Sanitize string length and remove potential control characters
                sanitized = "".join(char for char in value if ord(char) >= 32 or char in "\t\n\r")
                if max_string_length != -1 and len(sanitized) > max_string_length:
                    logger.debug(
                        f"String truncated from {len(sanitized)} to {max_string_length} chars [corr:{correlation_id}]"
                    )
                    return sanitized[:max_string_length]
                return sanitized

            elif isinstance(value, list):
                if len(value) > 100:  # Limit array size
                    logger.warning(f"Array too large ({len(value)}), truncating [corr:{correlation_id}]")
                    value = value[:100]
                return [_sanitize_value(item, depth + 1) for item in value]

            elif isinstance(value, dict):
                if len(value) > 50:  # Limit object size
                    logger.warning(f"Object too large ({len(value)}), truncating [corr:{correlation_id}]")
                    value = dict(list(value.items())[:50])
                return {str(k)[:100]: _sanitize_value(v, depth + 1) for k, v in value.items()}

            return value

        try:
            sanitized = {}
            for key, value in arguments.items():
                sanitized_key = str(key)[:100]  # Limit key length
                sanitized[sanitized_key] = _sanitize_value(value)

            logger.debug(f"Sanitized {len(arguments)} function arguments [corr:{correlation_id}]")
            return sanitized

        except Exception as e:
            logger.error(f"Failed to sanitize arguments [corr:{correlation_id}]: {e}")
            # Return empty dict on sanitization failure for security
            return {}

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
                    from agent.capabilities.manager import _load_state_config
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
            from agent.middleware import (
                execute_ai_function_with_middleware,
                get_ai_compatible_middleware,
            )

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
