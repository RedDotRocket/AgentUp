import json
from datetime import datetime, timezone

import structlog
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.types import DataPart, Part, Role, Task, TaskState, TextPart
from a2a.utils import new_agent_text_message, new_artifact

from agent.core.base import AgentExecutorBase, get_current_auth_for_executor
from agent.core.models import (
    ActionResult,
    AgentConfiguration,
    GoalStatus,
    IterationState,
    LearningInsight,
    LearningType,
    ReflectionData,
)
from agent.core.models.iteration import CompletionData

# Removed GoalCompletedException import - now using structured completion results

logger = structlog.get_logger(__name__)


class IterativeStrategy(AgentExecutorBase):
    """Iterative execution strategy for self-directed multi-turn agent interactions.

    This strategy implements a continuous loop of:
    1. Decompose goal into actionable tasks
    2. Execute task using available tools
    3. Observe and record results
    4. Reflect on progress using LLM reasoning
    5. Decide whether to continue or complete

    Key Features:
    - LLM-driven decision making throughout the loop
    - Memory integration for learning and context preservation
    - Structured reflection and progress tracking
    - Configurable iteration limits and termination conditions
    """

    def __init__(self, agent, config: AgentConfiguration | None = None) -> None:
        super().__init__(agent)

        # Store configuration
        self.config = config or AgentConfiguration()

        # Initialize Function Dispatcher for tool access
        from agent.core.dispatcher import get_function_dispatcher

        self.dispatcher = get_function_dispatcher()

        # Initialize memory integration
        from agent.state import get_context_manager

        self.memory_manager = get_context_manager()

        # Thread-safe synchronization for completion state
        import asyncio

        self._completion_lock = asyncio.Lock()
        self._completion_data: CompletionData | None = None
        self._completion_detected = False
        self._completion_from_tool = False  # Track if completion came from mark_goal_complete capability

        # Track execution timing
        self._execution_start_time = None

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute iterative agent processing."""
        # Record execution start time
        self._execution_start_time = datetime.now(timezone.utc)
        logger.info(f"Executing iterative agent {self.agent_name}")

        # Reset completion state for new execution
        async with self._completion_lock:
            self._completion_detected = False
            self._completion_data = None
            self._completion_from_tool = False

        # Validate request
        error = self._validate_request(context)
        if error:
            from a2a.types import InvalidParamsError
            from a2a.utils.errors import ServerError

            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        # Ensure task exists
        task = self._ensure_task_exists(context, event_queue)
        updater = self._create_task_updater(task, event_queue)

        try:
            # Initialize iteration state
            iteration_state = await self._initialize_iteration_state(task)

            # Transition to working state
            await self._transition_to_working(task, updater)

            # Main iterative loop
            while (
                iteration_state.should_continue
                and iteration_state.iteration_count < self.config.iterative.max_iterations
            ):
                # Execute one iteration
                await self._execute_iteration(iteration_state, task, updater, event_queue)

                # Save state to memory after each iteration
                await self._save_iteration_state(iteration_state)

            # Handle completion
            await self._handle_completion(iteration_state, task, updater)

        except Exception as e:
            await self._handle_execution_error(e, task, updater)

    async def execute_streaming(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute iterative agent processing with streaming support."""
        # Record execution start time
        self._execution_start_time = datetime.now(timezone.utc)
        logger.info(f"Executing iterative agent {self.agent_name} with streaming")

        # Reset completion state for new execution
        async with self._completion_lock:
            self._completion_detected = False
            self._completion_data = None

        # Validate request
        error = self._validate_request(context)
        if error:
            from a2a.types import InvalidParamsError
            from a2a.utils.errors import ServerError

            raise ServerError(error=InvalidParamsError(data={"reason": error}))

        # Ensure task exists
        task = self._ensure_task_exists(context, event_queue)
        updater = self._create_task_updater(task, event_queue)

        try:
            # Initialize iteration state
            iteration_state = await self._initialize_iteration_state(task)

            # Transition to working state
            await self._transition_to_working(task, updater)

            # Main iterative loop with streaming
            while (
                iteration_state.should_continue
                and iteration_state.iteration_count < self.config.iterative.max_iterations
            ):
                # Execute one iteration (now with streaming support)
                await self._execute_iteration(iteration_state, task, updater, event_queue)

                # Save state to memory after each iteration
                await self._save_iteration_state(iteration_state)

            # Handle completion
            await self._handle_completion(iteration_state, task, updater)

        except Exception as e:
            await self._handle_execution_error(e, task, updater)

    async def _handle_execution_error(self, error: Exception, task: Task, updater) -> None:
        """Handle execution errors with secure logging and user-safe messages."""
        import traceback
        import uuid

        from agent.security.audit_logger import get_security_audit_logger

        # Generate correlation ID for error tracking
        correlation_id = str(uuid.uuid4())[:8]
        audit_logger = get_security_audit_logger()
        error_type = type(error).__name__

        # Detailed logging for debugging (server logs only)
        logger.error(
            f"Iterative strategy execution failed [corr:{correlation_id}]",
            exc_info=True,
            extra={
                "agent_name": self.agent_name,
                "task_id": task.id if hasattr(task, "id") else "unknown",
                "error_type": error_type,
                "correlation_id": correlation_id,
            },
        )

        # Security audit logging
        audit_logger.log_configuration_error(
            "iterative_strategy",
            f"Agent execution failed: {self.agent_name}",
            {
                "correlation_id": correlation_id,
                "error_type": error_type,
                "agent_name": self.agent_name,
                "stack_trace": traceback.format_exc()[:500],  # Truncated for security
            },
        )

        # Determine user-safe error message based on error type
        if isinstance(error, PermissionError):
            user_message = "Access denied: insufficient permissions to complete the task."
            audit_logger.log_authorization_failure(
                user_id="system",
                resource=f"agent:{self.agent_name}",
                action="execute",
                missing_scopes=["required_scope"],  # Placeholder, populate as needed
            )
        elif isinstance(error, ValueError):
            user_message = f"Invalid request parameters [ref:{correlation_id}]"
        elif isinstance(error, TimeoutError):
            user_message = "The operation timed out. Please try again."
        else:
            # Generic message for unknown errors to prevent information leakage
            user_message = f"An unexpected error occurred while processing your request [ref:{correlation_id}]"

        # Update task with error state and user-safe message
        try:
            # Update task status to error state with user-safe message
            from a2a.types import TaskState

            await updater.update_status(
                TaskState.failed,
                new_agent_text_message(user_message, task.context_id, task.id),
                final=True,
            )
            logger.info(f"Task updated with error state [corr:{correlation_id}]")
        except Exception as update_error:
            # Fallback if task update fails
            logger.error(f"Failed to update task with error state [corr:{correlation_id}]: {update_error}")
            audit_logger.log_configuration_error(
                "task_update_failure",
                "Failed to update task with error state",
                {
                    "correlation_id": correlation_id,
                    "original_error": error_type,
                    "update_error": str(update_error)[:200],
                },
            )

    async def _initialize_iteration_state(self, task: Task) -> IterationState:
        """Initialize iteration state from task and memory."""
        # Extract initial goal from user message
        goal = self._extract_user_message(task)

        # Try to restore from memory first
        existing_state = await self._load_iteration_state(task.context_id)
        if existing_state:
            # Check if this is a completed state or if the goal has changed
            existing_goal = existing_state.goal.strip().lower()
            current_goal = goal.strip().lower()

            # If the goal has changed significantly or the state is completed, create new state
            if not existing_state.should_continue or existing_goal != current_goal:
                logger.info(
                    f"Creating new iteration state for context {task.context_id} - goal changed or previous completed"
                )
                logger.debug(
                    f"Previous goal: '{existing_goal}' | New goal: '{current_goal}' | Should continue: {existing_state.should_continue}"
                )

                # Clear the completed state to avoid conflicts
                await self._clear_completed_iteration_state(task.context_id)

                # Create new iteration state for the new goal/request
                iteration_state = IterationState(
                    goal=goal,
                    context_id=task.context_id,
                    task_id=task.id,
                )

                # Decompose goal into initial plan using LLM
                initial_plan = await self._decompose_goal_with_llm(goal, task)
                iteration_state.current_plan = initial_plan

                logger.info(f"Initialized new iteration state with {len(initial_plan)} planned tasks")
                return iteration_state
            else:
                # Continue with existing state for the same ongoing goal
                logger.info(f"Restored continuing iteration state for context {task.context_id}")
                existing_state.task_id = task.id  # Update with current task ID
                return existing_state

        # Create new iteration state
        iteration_state = IterationState(
            goal=goal,
            context_id=task.context_id,
            task_id=task.id,
        )

        # Decompose goal into initial plan using LLM
        initial_plan = await self._decompose_goal_with_llm(goal, task)
        iteration_state.current_plan = initial_plan

        logger.info(f"Initialized new iteration state with {len(initial_plan)} planned tasks")
        return iteration_state

    async def _execute_iteration(self, state: IterationState, task: Task, updater, event_queue: EventQueue) -> None:
        """Execute one iteration of the agent loop with thread-safe completion detection."""
        logger.info(f"Starting iteration {state.iteration_count + 1}")

        # Update working status with progress
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                f"Iteration {state.iteration_count + 1}: Working on goal - {state.goal}",
                task.context_id,
                task.id,
            ),
            final=False,
        )

        # Thread-safe completion state management
        async with self._completion_lock:
            # Check if completion was already detected (race condition protection)
            if self._completion_detected:
                logger.warning(f"Completion already detected, skipping iteration {state.iteration_count + 1}")
                state.should_continue = False
                return

            # Reset completion data for this iteration
            self._completion_data = None

        # Build iteration prompt with full context
        iteration_prompt = self._build_iteration_prompt(state)

        # Create new task with updated prompt
        iteration_task = self._create_iteration_task(iteration_prompt, task)

        # Single dispatcher call (LLM + tools) - check for completion signal
        auth_result = get_current_auth_for_executor()
        result = await self.dispatcher.process_task(iteration_task, auth_result)

        # Stream meaningful results (skip completion signals)
        if result and isinstance(result, str) and result.strip():
            logger.info(f"Streaming result from iteration {state.iteration_count + 1}: {result[:100]}...")

            try:
                # Create artifact with the iteration result content
                parts = [Part(root=TextPart(text=result))]
                artifact = new_artifact(
                    parts,
                    name=f"{self.agent_name}-iteration-{state.iteration_count + 1}",
                    description=f"Iteration {state.iteration_count + 1} result",
                )

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(f"Iteration {state.iteration_count + 1} progress", task.context_id, task.id),
                    final=False,
                )

                # Add the artifact with the actual content
                await updater.add_artifact(parts, name=artifact.name)
                logger.info(f"Successfully streamed {len(result)} characters to user with artifact")
            except Exception as e:
                logger.error(f"Failed to stream result: {e}")
        elif isinstance(result, dict) and result.get("completed"):
            logger.info(f"Iteration {state.iteration_count + 1} returned completion signal - not streaming")

        # Thread-safe completion detection and state updates
        async with self._completion_lock:
            # Double-check completion hasn't been detected by another thread
            if self._completion_detected:
                logger.warning("Completion detected during execution, prioritizing earlier detection")
                state.should_continue = False
                return

            # Check for string-based completion signal (GOAL_COMPLETED:)
            if isinstance(result, str) and self._check_goal_completion_tool_called(result, state):
                logger.info("Goal completion detected from string signal - acquiring completion lock")

                # Mark completion as detected to prevent race conditions
                self._completion_detected = True
                self._completion_from_tool = True  # Flag that completion came from goal completion tool

                # Set completion state
                state.should_continue = False

                # Completion data is already stored in _completion_data by the check method
                logger.info("String-based goal completion processed successfully")
                return

            # Check if result indicates completion (structured format)
            if isinstance(result, dict) and result.get("completed"):
                logger.info("Goal completion detected from structured result - acquiring completion lock")

                # Parse structured result using Pydantic model
                from agent.core.models.iteration import StructuredCompletionResult

                try:
                    structured_result = StructuredCompletionResult(**result)
                except Exception as e:
                    logger.error(f"Failed to parse structured completion result: {e}")
                    # Continue with normal processing if parsing fails
                    return

                # Mark completion as detected to prevent race conditions
                self._completion_detected = True
                self._completion_from_tool = True  # Flag that completion came from goal completion tool

                # Set completion state
                state.should_continue = False

                # Update state with completion data
                completion_data = structured_result.completion_data
                if completion_data:
                    # Validate completion data integrity
                    validated_completion_data = self._validate_completion_data(completion_data)

                    # Store completion data for the completion handler
                    self._completion_data = validated_completion_data

                    # Add completed tasks to state
                    for completed_task in validated_completion_data.tasks_completed:
                        if isinstance(completed_task, str) and completed_task.strip():
                            state.add_completed_task(completed_task.strip())

                    # Create reflection data from completion info
                    from agent.core.models.iteration import GoalStatus, ReflectionData

                    state.reflection_data = ReflectionData(
                        progress_assessment=validated_completion_data.summary,
                        goal_achievement_status=GoalStatus.FULLY_ACHIEVED,
                        next_action_reasoning="Goal completed successfully",
                        learned_insights=validated_completion_data.remaining_issues,
                    )

                    logger.info(
                        f"Completion data validated and stored: {len(validated_completion_data.tasks_completed)} tasks completed"
                    )

                logger.info("Structured goal completion processed successfully")
                logger.info(f"Set should_continue=False, returning from iteration {state.iteration_count + 1}")
                return

        # Store result in action history (outside completion lock to avoid deadlock)
        action_result = ActionResult(
            action=f"Iteration {state.iteration_count + 1}",
            result=str(result),
            success=True,
            timestamp=datetime.now(timezone.utc),
        )
        state.add_action_result(action_result)

        # Increment iteration count after completing iteration
        state.iteration_count += 1

        logger.info(f"Completed iteration {state.iteration_count}, should_continue: {state.should_continue}")

    def _validate_completion_data(self, completion_data: dict) -> CompletionData:
        """Validate completion data to prevent corruption or injection."""
        ALLOWED_KEYS = {"summary", "result_content", "confidence", "tasks_completed", "remaining_issues"}
        MAX_STRING_LENGTH = 2000
        MAX_RESULT_CONTENT_LENGTH = 8000
        MAX_ARRAY_SIZE = 50

        validated = {
            "summary": "Goal completed successfully",
            "result_content": "",
            "confidence": 1.0,
            "tasks_completed": [],
            "remaining_issues": [],
        }

        for key, value in completion_data.items():
            if key not in ALLOWED_KEYS:
                logger.warning(f"Ignoring invalid completion data key: {key}")
                continue

            try:
                if key == "summary" and isinstance(value, str):
                    validated[key] = value[:MAX_STRING_LENGTH].strip()
                elif key == "result_content" and isinstance(value, str):
                    validated[key] = value[:MAX_RESULT_CONTENT_LENGTH].strip()
                elif key == "confidence" and isinstance(value, int | float):
                    validated[key] = max(0.0, min(1.0, float(value)))  # Clamp to valid range
                elif key in ["tasks_completed", "remaining_issues"] and isinstance(value, list):
                    if len(value) <= MAX_ARRAY_SIZE:
                        validated[key] = [
                            str(item)[:200].strip()
                            for item in value[:MAX_ARRAY_SIZE]
                            if isinstance(item, str) and str(item).strip()
                        ]
                    else:
                        logger.warning(f"Completion data array '{key}' too large, truncating")
                        validated[key] = [
                            str(item)[:200].strip()
                            for item in value[:MAX_ARRAY_SIZE]
                            if isinstance(item, str) and str(item).strip()
                        ]
                else:
                    logger.warning(f"Invalid completion data type for '{key}': {type(value)}")

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to validate completion data '{key}': {e}")

        return CompletionData(**validated)

    async def _decompose_goal_with_llm(self, goal: str, task: Task) -> list[str]:
        """Use LLM to decompose goal into actionable tasks."""
        decomposition_prompt = f"""
        Please analyze this goal and break it down into specific, actionable tasks:

        Goal: {goal}

        Provide your response as a JSON object with this structure:
        {{
            "tasks": ["task1", "task2", "task3"],
            "reasoning": "explanation of your decomposition approach"
        }}

        Make each task specific, measurable, and achievable using available tools.
        """

        try:
            # Use dispatcher to get LLM response
            auth_result = get_current_auth_for_executor()

            # Create a temporary task for decomposition
            decomposition_task = self._create_decomposition_task(decomposition_prompt, task)

            result = await self.dispatcher.process_task(decomposition_task, auth_result)

            # Parse LLM response to extract tasks
            if isinstance(result, str):
                # Simple parsing - in production would use more robust JSON parsing
                tasks = self._parse_task_list_from_response(result)
                return tasks

            return ["Complete the requested goal"]  # Fallback

        except Exception as e:
            logger.error(f"Error decomposing goal with LLM: {e}")
            return ["Complete the requested goal"]  # Fallback

    async def _determine_next_action_with_llm(self, state: IterationState, task: Task) -> str:
        """Use LLM to determine the next action based on current state."""
        context = self._build_context_for_llm(state)

        action_prompt = f"""
        Based on the current progress, determine the next action to take:

        {context}

        Provide your response as a JSON object:
        {{
            "next_action": "specific action to take",
            "reasoning": "why this action was chosen",
            "tool_needed": "name of tool to use (if any)"
        }}

        Choose actions that make concrete progress toward the goal.
        """

        try:
            auth_result = get_current_auth_for_executor()

            # Create task for action determination
            action_task = self._create_action_task(action_prompt, task)

            result = await self.dispatcher.process_task(action_task, auth_result)

            # Parse action from response
            if isinstance(result, str):
                action = self._parse_action_from_response(result)
                return action

            return "Continue working on the goal"  # Fallback

        except Exception as e:
            logger.error(f"Error determining next action with LLM: {e}")
            return "Continue working on the goal"  # Fallback

    async def _execute_action(self, action: str, task: Task) -> ActionResult:
        """Execute the determined action and return result."""
        logger.info(f"Executing action: {action}")

        start_time = datetime.now(timezone.utc)

        try:
            # Use dispatcher to execute the action
            auth_result = get_current_auth_for_executor()

            # Create task for action execution
            action_task = self._create_action_execution_task(action, task)

            result = await self.dispatcher.process_task(action_task, auth_result)

            return ActionResult(
                action=action,
                result=str(result) if result else "Action completed",
                success=True,
                timestamp=start_time,
            )

        except Exception as e:
            logger.error(f"Error executing action '{action}': {e}")
            return ActionResult(
                action=action,
                result=f"Error: {str(e)}",
                success=False,
                timestamp=start_time,
            )

    async def _reflect_on_progress_with_llm(self, state: IterationState, task: Task) -> ReflectionData:
        """Use LLM to reflect on progress and decide next steps."""
        context = self._build_context_for_llm(state)

        reflection_prompt = f"""
        Reflect on the current progress and determine if the goal is achieved:

        {context}

        Provide your response as a JSON object:
        {{
            "progress_assessment": "detailed assessment of current progress",
            "goal_achievement_status": "not_started|in_progress|partially_achieved|fully_achieved|failed|requires_clarification",
            "next_action_reasoning": "reasoning for what to do next",
            "learned_insights": ["insight1", "insight2"],
            "challenges_encountered": ["challenge1", "challenge2"],
            "estimated_completion": "time estimate or percentage complete"
        }}

        Be honest about progress and challenges.
        """

        try:
            auth_result = get_current_auth_for_executor()

            # Create task for reflection
            reflection_task = self._create_reflection_task(reflection_prompt, task)

            result = await self.dispatcher.process_task(reflection_task, auth_result)

            # Parse reflection from response
            if isinstance(result, str):
                return self._parse_reflection_from_response(result)

            # Fallback reflection
            return ReflectionData(
                progress_assessment="Making progress on the goal",
                goal_achievement_status=GoalStatus.IN_PROGRESS,
                next_action_reasoning="Continue with current approach",
            )

        except Exception as e:
            logger.error(f"Error reflecting on progress with LLM: {e}")
            # Return fallback reflection
            return ReflectionData(
                progress_assessment=f"Error in reflection: {str(e)}",
                goal_achievement_status=GoalStatus.IN_PROGRESS,
                next_action_reasoning="Continue despite reflection error",
            )

    def _build_context_for_llm(self, state: IterationState) -> str:
        """Build context string for LLM prompts."""
        context_parts = [
            f"Goal: {state.goal}",
            f"Iteration: {state.iteration_count}",
            f"Planned Tasks: {', '.join(state.current_plan)}",
            f"Completed Tasks: {', '.join(state.completed_tasks)}",
        ]

        if state.action_history:
            recent_actions = state.action_history[-3:]  # Last 3 actions
            context_parts.append("Recent Actions:")
            for action in recent_actions:
                status = "✓" if action.success else "✗"
                context_parts.append(f"  {status} {action.action}: {action.result[:100]}...")

        if state.reflection_data:
            context_parts.append(f"Last Reflection: {state.reflection_data.progress_assessment}")

        return "\\n".join(context_parts)

    def _detect_stuck_loop(self, state: IterationState) -> bool:
        """Detect if the agent is stuck in a loop without progress.

        Returns True if:
        1. More than 5 iterations with similar results
        2. Last 3 actions have very similar text
        3. No new completed tasks in last 5 iterations
        """
        # Check iteration count
        if state.iteration_count < 5:
            return False

        # Check if recent actions are repetitive
        if len(state.action_history) >= 3:
            recent_results = [action.result.lower()[:100] for action in state.action_history[-3:]]

            # Check for high similarity in recent results
            similar_count = 0
            for i in range(len(recent_results) - 1):
                # Simple similarity check - if results share significant text
                if ("not yet retrieved" in recent_results[i] and "not yet retrieved" in recent_results[i + 1]) or (
                    recent_results[i][:50] == recent_results[i + 1][:50]
                ):
                    similar_count += 1

            if similar_count >= 2:
                logger.warning(f"Detected stuck loop at iteration {state.iteration_count}: repetitive actions")
                return True

        # Check if no progress in completed tasks
        if state.iteration_count >= 10:
            # Count completed tasks in last 5 iterations
            recent_history = state.action_history[-5:] if len(state.action_history) >= 5 else state.action_history
            any_progress = any(
                "complete" in action.result.lower()
                or "achieved" in action.result.lower()
                or "finished" in action.result.lower()
                for action in recent_history
            )
            if not any_progress:
                logger.warning(f"Detected stuck loop at iteration {state.iteration_count}: no progress in 5 iterations")
                return True

        return False

    def _extract_user_message(self, task: Task) -> str:
        """Extract user message text from A2A task history."""
        try:
            if not (hasattr(task, "history") and task.history):
                return "Complete the requested task"

            # Get the latest user message from history
            for message in reversed(task.history):
                if message.role == Role.user and message.parts:
                    from agent.state.conversation import ConversationManager

                    return ConversationManager.extract_text_from_parts(message.parts)

            return "Complete the requested task"
        except Exception as e:
            logger.error(f"Error extracting user message: {e}")
            return "Complete the requested task"

    # Helper methods for creating temporary tasks
    def _create_decomposition_task(self, prompt: str, original_task: Task) -> Task:
        """Create a temporary task for goal decomposition."""
        from a2a.types import Message, Part, TextPart
        from a2a.utils import new_task

        # Create message with decomposition prompt
        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=prompt))],
            message_id=f"decompose-{original_task.id}",
            context_id=original_task.context_id,
            kind="message",
        )

        # Create new task for decomposition
        return new_task(message)

    def _create_action_task(self, prompt: str, original_task: Task) -> Task:
        """Create a temporary task for action determination."""
        from a2a.types import Message, Part, TextPart
        from a2a.utils import new_task

        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=prompt))],
            message_id=f"action-{original_task.id}",
            context_id=original_task.context_id,
            kind="message",
        )

        return new_task(message)

    def _create_action_execution_task(self, action: str, original_task: Task) -> Task:
        """Create a temporary task for action execution."""
        from a2a.types import Message, Part, TextPart
        from a2a.utils import new_task

        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=action))],
            message_id=f"execute-{original_task.id}",
            context_id=original_task.context_id,
            kind="message",
        )

        return new_task(message)

    def _create_reflection_task(self, prompt: str, original_task: Task) -> Task:
        """Create a temporary task for reflection."""
        from a2a.types import Message, Part, TextPart
        from a2a.utils import new_task

        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=prompt))],
            message_id=f"reflect-{original_task.id}",
            context_id=original_task.context_id,
            kind="message",
        )

        return new_task(message)

    def _create_iteration_task(self, prompt: str, original_task: Task) -> Task:
        """Create a task for the iteration with updated context."""
        from a2a.types import Message, Part, TextPart
        from a2a.utils import new_task

        message = Message(
            role=Role.agent,
            parts=[Part(root=TextPart(text=prompt))],
            message_id=f"iterate-{original_task.id}",
            context_id=original_task.context_id,
            kind="message",
        )

        return new_task(message)

    def _build_iteration_prompt(self, state: IterationState) -> str:
        """Build iteration prompt with full context for the LLM."""
        context_parts = [
            f"GOAL: {state.goal}",
            f"ITERATION: {state.iteration_count + 1}",
        ]

        # Add planned tasks if available
        if state.current_plan:
            context_parts.append(f"PLANNED TASKS: {', '.join(state.current_plan)}")

        # Add completed tasks
        if state.completed_tasks:
            context_parts.append(f"COMPLETED: {', '.join(state.completed_tasks)}")

        # Add recent progress
        if state.action_history:
            recent_actions = state.action_history[-2:]  # Last 2 iterations
            context_parts.append("RECENT PROGRESS:")
            for i, action in enumerate(recent_actions):
                context_parts.append(
                    f"  {len(state.action_history) - len(recent_actions) + i + 1}. {action.result[:200]}..."
                )

        # Check for lack of progress (stuck in a loop)
        is_stuck = self._detect_stuck_loop(state)

        # Get confidence threshold from configuration
        confidence_threshold = self.config.iterative.completion_confidence_threshold

        # Build the main prompt
        stuck_warning = ""
        if is_stuck:
            stuck_warning = """
WARNING: You appear to be stuck in a loop without making progress!
If you cannot complete the goal with available tools, mark it as complete with:
- A clear explanation of what you DID accomplish
- Note what information/tools were missing
- Set confidence based on partial completion
"""

        # Adjust confidence guidance based on stuck state
        confidence_guidance = f"must be > {confidence_threshold} to complete"
        if is_stuck:
            partial_threshold = confidence_threshold * 0.8
            confidence_guidance = f"use {partial_threshold:.1f} for partial completion when tools are missing"

        prompt = f"""
{chr(10).join(context_parts)}

FIRST: Check if the goal has been achieved based on the recent progress above.
{stuck_warning}
IF THE GOAL IS COMPLETE OR CANNOT BE COMPLETED:
Call the 'mark_goal_complete' tool with:
- summary: A comprehensive summary of what was accomplished (or why it couldn't be completed)
- confidence: Your confidence level ({confidence_guidance})
- tasks_completed: List of all tasks that were finished
- remaining_issues: Any known limitations, missing tools, or incomplete aspects

IF THE GOAL IS NOT COMPLETE AND YOU CAN MAKE PROGRESS:
Take the next concrete action to make progress using the appropriate tools.

GOAL REMINDER: {state.goal}

Evaluate the current state and decide: Is the goal complete, partially complete, or do you need to continue?
"""

        return prompt

    def _check_goal_completion_tool_called(
        self, dispatcher_result: str | None = None, state: IterationState | None = None
    ) -> bool:
        """Check if the goal completion tool was called with sufficient confidence.

        Args:
            dispatcher_result: The result from the dispatcher to check for completion signals
            state: Current iteration state (used to check if stuck in loop)
        """

        # Check for completion signal in dispatcher result
        logger.debug(f"Checking dispatcher result for completion signal: {dispatcher_result is not None}")
        if dispatcher_result and "GOAL_COMPLETED:" in dispatcher_result:
            logger.info("Found GOAL_COMPLETED signal in result")
            try:
                # Extract JSON object from the string using a regex for robustness
                import re

                json_match = re.search(r"\{.*\}", dispatcher_result, re.DOTALL)
                if not json_match:
                    logger.warning("Could not extract JSON from GOAL_COMPLETED signal", signal=dispatcher_result)
                    return False

                completion_json = json_match.group(0)
                logger.debug(f"Parsing completion JSON: {completion_json}")
                completion_dict = json.loads(completion_json)

                # Create structured Pydantic model from completion data
                from agent.core.models.iteration import CompletionData

                self._completion_data = CompletionData(**completion_dict)
                logger.debug(
                    f"Stored completion data: summary='{self._completion_data.summary}', result_content='{self._completion_data.result_content[:100] if self._completion_data.result_content else 'None'}...'"
                )

                confidence = self._completion_data.confidence
                threshold = self.config.iterative.completion_confidence_threshold

                # Lower threshold if agent is stuck in a loop
                if state and self._detect_stuck_loop(state):
                    threshold = threshold * 0.8
                    logger.info(f"Agent is stuck, using lower threshold: {threshold}")

                logger.info(f"Goal completion confidence: {confidence}, threshold: {threshold}")
                return confidence > threshold
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Failed to parse completion signal: {e}")
                return False
        else:
            logger.debug("No GOAL_COMPLETED signal found in result")

        # Legacy check for old completion data format
        if hasattr(self, "_completion_data") and self._completion_data:
            confidence = self._completion_data.confidence
            threshold = self.config.iterative.completion_confidence_threshold

            # Lower threshold if agent is stuck in a loop
            if state and self._detect_stuck_loop(state):
                threshold = threshold * 0.8
                logger.info(f"Agent is stuck, using lower threshold: {threshold}")

            return confidence > threshold

        return False

    # Parsing methods - robust implementations
    def _parse_task_list_from_response(self, response: str) -> list[str]:
        """Parse task list from LLM response."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*"tasks"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                if "tasks" in parsed and isinstance(parsed["tasks"], list):
                    return parsed["tasks"]

            # Fallback: Look for bullet points or numbered lists
            lines = response.split("\n")
            tasks = []
            for line in lines:
                line = line.strip()
                # Match various list formats
                if re.match(r"^[0-9]+\.\s*", line) or re.match(r"^[-*]\s*", line):
                    task = re.sub(r"^[0-9]+\.\s*|^[-*]\s*", "", line).strip()
                    if task:
                        tasks.append(task)

            return tasks if tasks else ["Complete the requested goal"]

        except Exception as e:
            logger.error(f"Error parsing task list: {e}")
            return ["Complete the requested goal"]

    def _parse_action_from_response(self, response: str) -> str:
        """Parse next action from LLM response."""
        import json
        import re

        try:
            # Try to extract JSON
            json_match = re.search(r'\{[^{}]*"next_action"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                if "next_action" in parsed:
                    return parsed["next_action"]

            # Fallback: Look for action patterns
            lines = response.split("\n")
            for line in lines:
                if "action:" in line.lower():
                    action = line.split(":", 1)[1].strip()
                    if action:
                        return action

            # Last resort: use first meaningful sentence
            sentences = response.split(".")
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 10 and not sentence.startswith("{"):
                    return sentence

            return "Continue working on the goal"

        except Exception as e:
            logger.error(f"Error parsing action: {e}")
            return "Continue working on the goal"

    def _parse_reflection_from_response(self, response: str) -> ReflectionData:
        """Parse reflection data from LLM response."""
        import json
        import re

        try:
            # Try to extract JSON
            json_match = re.search(r'\{[^{}]*"progress_assessment"[^{}]*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)

                # Parse goal achievement status
                status_str = parsed.get("goal_achievement_status", "in_progress")
                try:
                    status = GoalStatus(status_str)
                except ValueError:
                    status = GoalStatus.IN_PROGRESS

                return ReflectionData(
                    progress_assessment=parsed.get("progress_assessment", "Making progress"),
                    goal_achievement_status=status,
                    next_action_reasoning=parsed.get("next_action_reasoning", "Continue current approach"),
                    learned_insights=parsed.get("learned_insights", []),
                    challenges_encountered=parsed.get("challenges_encountered", []),
                    estimated_completion=parsed.get("estimated_completion"),
                )

            # Fallback parsing
            lines = response.split("\n")
            progress_assessment = "Making progress"
            status = GoalStatus.IN_PROGRESS

            # Look for completion indicators
            response_lower = response.lower()
            if any(word in response_lower for word in ["complete", "finished", "done", "achieved", "accomplished"]):
                if any(word in response_lower for word in ["partially", "some", "part"]):
                    status = GoalStatus.PARTIALLY_ACHIEVED
                else:
                    status = GoalStatus.FULLY_ACHIEVED
            elif any(word in response_lower for word in ["failed", "error", "impossible", "cannot"]):
                status = GoalStatus.FAILED

            # Extract first meaningful sentence as progress assessment
            for line in lines:
                line = line.strip()
                if len(line) > 20 and not line.startswith("{"):
                    progress_assessment = line
                    break

            return ReflectionData(
                progress_assessment=progress_assessment,
                goal_achievement_status=status,
                next_action_reasoning="Continue based on current progress",
            )

        except Exception as e:
            logger.error(f"Error parsing reflection: {e}")
            return ReflectionData(
                progress_assessment=f"Error in reflection: {str(e)}",
                goal_achievement_status=GoalStatus.IN_PROGRESS,
                next_action_reasoning="Continue despite parsing error",
            )

    async def _extract_learning_insights(
        self, state: IterationState, action_result: ActionResult, reflection: ReflectionData
    ) -> None:
        """Extract learning insights from the current iteration."""
        # Create learning insights based on action results
        insights = []

        if action_result.success:
            insights.append(
                LearningInsight(
                    insight=f"Successful action: {action_result.action}",
                    learning_type=LearningType.SUCCESS_PATTERN,
                    context=f"Goal: {state.goal}",
                )
            )
        else:
            insights.append(
                LearningInsight(
                    insight=f"Failed action: {action_result.action} - {action_result.result}",
                    learning_type=LearningType.ERROR_PATTERN,
                    context=f"Goal: {state.goal}",
                )
            )

        # Add insights from reflection
        for insight_text in reflection.learned_insights:
            insights.append(
                LearningInsight(
                    insight=insight_text,
                    learning_type=LearningType.DOMAIN_KNOWLEDGE,
                    context=f"Goal: {state.goal}",
                )
            )

        # Store insights in memory
        try:
            from agent.core.models import MemoryContext

            memory_context = MemoryContext(
                context_id=state.context_id,
                agent_type="iterative",
            )

            for insight in insights:
                memory_context.add_insight(insight)

            # Save to memory system
            await self.memory_manager.set_variable(
                state.context_id, f"memory_{state.context_id}", memory_context.model_dump()
            )

        except Exception as e:
            logger.error(f"Error storing learning insights: {e}")

    async def _save_iteration_state(self, state: IterationState) -> None:
        """Save iteration state to memory."""
        try:
            state_key = f"iteration_state_{state.context_id}"
            await self.memory_manager.set_variable(state.context_id, state_key, state.model_dump())
        except Exception as e:
            logger.error(f"Error saving iteration state: {e}")

    async def _load_iteration_state(self, context_id: str) -> IterationState | None:
        """Load iteration state from memory."""
        try:
            state_key = f"iteration_state_{context_id}"
            state_data = await self.memory_manager.get_variable(context_id, state_key)
            if state_data:
                return IterationState(**state_data)
        except Exception as e:
            logger.error(f"Error loading iteration state: {e}")
        return None

    async def _clear_completed_iteration_state(self, context_id: str) -> None:
        """Clear completed iteration state to allow fresh starts for new goals."""
        try:
            state_key = f"iteration_state_{context_id}"
            await self.memory_manager.set_variable(context_id, state_key, None)
            logger.info(f"Cleared completed iteration state for context {context_id}")
        except Exception as e:
            logger.error(f"Error clearing iteration state: {e}")

    async def _handle_completion(self, state: IterationState, task: Task, updater) -> None:
        """Handle completion of iterative processing with confidence threshold enforcement."""
        from agent.security.audit_logger import get_security_audit_logger

        audit_logger = get_security_audit_logger()
        completion_confidence = 0.0
        confidence_threshold = self.config.iterative.completion_confidence_threshold
        completion_approved = False

        # Check if we have completion data from mark_goal_complete
        if hasattr(self, "_completion_data") and self._completion_data:
            completion_confidence = self._completion_data.confidence

            # Enforce minimum confidence threshold for security
            if completion_confidence < confidence_threshold:
                logger.warning(
                    f"Completion confidence {completion_confidence:.2f} below threshold {confidence_threshold:.2f} - rejecting completion"
                )
                audit_logger.log_configuration_error(
                    "completion_confidence_threshold",
                    f"Goal completion rejected due to low confidence: {completion_confidence:.2f} < {confidence_threshold:.2f}",
                    {
                        "agent_name": self.agent_name,
                        "confidence": completion_confidence,
                        "threshold": confidence_threshold,
                        "goal": state.goal[:200],  # Truncate for security
                    },
                )

                # Override completion - force continuation with warning
                state.should_continue = True
                self._completion_detected = False

                # Create low confidence warning message
                warning_message = (
                    f"Goal completion confidence ({completion_confidence:.1%}) is below the required threshold "
                    f"({confidence_threshold:.1%}). Continuing iterations for quality assurance."
                )

                # Update task with warning
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(warning_message, task.context_id, task.id),
                    final=False,
                )
                logger.info("Completion rejected due to confidence threshold - continuing iterations")

                # Store partial conversation history even for rejected completions
                try:
                    from agent.core.dispatcher import get_function_dispatcher

                    dispatcher = get_function_dispatcher()
                    user_input = self._extract_user_message(task)

                    if user_input and warning_message:
                        logger.info(f"Storing conversation history for context {task.context_id} (rejected completion)")
                        await dispatcher.conversation_manager.update_conversation_history(
                            task.context_id, user_input, warning_message
                        )
                except Exception as e:
                    logger.error(f"Failed to store conversation history: {e}")

                return
            else:
                completion_approved = True
                logger.info(
                    f"Completion confidence {completion_confidence:.2f} meets threshold {confidence_threshold:.2f}"
                )

            # Calculate total execution time
            total_time = self._get_total_execution_time()

            # Always show completion metadata (confidence, iterations, time) but not duplicate content
            # User has already seen the full analysis via streaming
            completion_message = (
                f"🎯 Goal completed after {state.iteration_count} iterations "
                f"(confidence: {completion_confidence:.1%}) in {total_time}."
            )
            logger.info("Sending completion metadata summary")
        elif state.reflection_data and state.reflection_data.goal_achievement_status == GoalStatus.FULLY_ACHIEVED:
            total_time = self._get_total_execution_time()
            completion_message = f"🎯 Goal achieved after {state.iteration_count} iterations in {total_time}."
            completion_approved = True
        elif state.iteration_count >= self.config.iterative.max_iterations:
            total_time = self._get_total_execution_time()
            completion_message = (
                f"⏱️ Reached maximum iterations ({self.config.iterative.max_iterations}) in {total_time}."
            )
            completion_approved = False  # Max iterations reached without proper completion

            # Log max iterations reached for security monitoring
            audit_logger.log_configuration_error(
                "max_iterations_reached",
                "Agent reached maximum iterations without completion",
                {
                    "agent_name": self.agent_name,
                    "max_iterations": self.config.iterative.max_iterations,
                    "goal": state.goal[:200],  # Truncate for security
                },
            )
        else:
            total_time = self._get_total_execution_time()
            completion_message = f"⏹️ Processing stopped after {state.iteration_count} iterations in {total_time}."
            completion_approved = False

        # Security audit for completion events
        if completion_approved:
            audit_logger.log_authentication_success(
                user_id="system",
                client_ip="internal",
                auth_method=f"goal_completion_confidence_{completion_confidence:.2f}",
            )

        # Mark success in memory for successful completions
        if state.reflection_data and state.reflection_data.goal_achievement_status == GoalStatus.FULLY_ACHIEVED:
            try:
                from agent.core.models import MemoryContext

                memory_context = MemoryContext(
                    context_id=state.context_id,
                    agent_type="iterative",
                )
                memory_context.mark_success()
                await self.memory_manager.set_variable(
                    state.context_id, f"memory_{state.context_id}", memory_context.model_dump()
                )
            except Exception as e:
                logger.error(f"Error updating memory with success: {e}")

        # Create completion artifact with detailed completion info
        artifact_data = {
            "goal": state.goal,
            "iterations_completed": state.iteration_count,
            "tasks_completed": state.completed_tasks,
            "final_status": state.reflection_data.goal_achievement_status if state.reflection_data else "unknown",
            "completion_approved": completion_approved,
            "confidence_threshold": confidence_threshold,
            "total_execution_time": self._get_total_execution_time(),
        }

        # Add completion tool data if available
        if hasattr(self, "_completion_data") and self._completion_data:
            artifact_data.update(
                {
                    "completion_confidence": completion_confidence,
                    "completion_summary": self._completion_data.summary,
                    "tasks_completed_details": self._completion_data.tasks_completed,
                    "remaining_issues": self._completion_data.remaining_issues,
                }
            )

        parts = [
            Part(root=TextPart(text=completion_message)),
            Part(root=DataPart(data=artifact_data)),
        ]

        artifact = new_artifact(
            parts,
            name=f"{self.agent_name}-iterative-result",
            description=f"Iterative processing result for: {state.goal}",
        )

        await updater.add_artifact(parts, name=artifact.name)

        # Store conversation history for context persistence before completion
        try:
            from agent.core.dispatcher import get_function_dispatcher

            dispatcher = get_function_dispatcher()
            user_input = self._extract_user_message(task)

            if user_input and completion_message:
                logger.info(f"Storing conversation history for context {task.context_id}")
                await dispatcher.conversation_manager.update_conversation_history(
                    task.context_id, user_input, completion_message
                )
        except Exception as e:
            logger.error(f"Failed to store conversation history: {e}")

        # Send the completion metadata summary (confidence, iterations, time)
        # User has already seen all the content via streaming, this is just the final metadata
        logger.info("Sending completion metadata summary and marking execution as final")
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(completion_message, task.context_id, task.id),
            final=True,  # Mark as final to close this execution's stream
        )

    def _get_total_execution_time(self) -> str:
        """Get formatted total execution time from start to completion."""
        if not self._execution_start_time:
            return "unknown duration"

        end_time = datetime.now(timezone.utc)
        total_duration = end_time - self._execution_start_time

        # Format duration in a human-readable way
        total_seconds = int(total_duration.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:  # Less than 1 hour
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:  # 1 hour or more
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours}h {minutes}m {seconds}s"
