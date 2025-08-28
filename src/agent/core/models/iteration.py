"""Iteration state models for self-directed agents."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    """Goal achievement status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PARTIALLY_ACHIEVED = "partially_achieved"
    FULLY_ACHIEVED = "fully_achieved"
    FAILED = "failed"
    REQUIRES_CLARIFICATION = "requires_clarification"


class CompletionData(BaseModel):
    """Structured completion data from goal completion capability."""

    summary: str = "Goal completed successfully"
    result_content: str = ""  # The actual substantive result/answer
    confidence: float = 1.0
    tasks_completed: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)


class ActionResult(BaseModel):
    """Result of an action execution."""

    action: str
    tool_used: str | None = None
    result: str
    success: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class FunctionExecutionResult(BaseModel):
    """Result of a function execution with completion signaling."""

    success: bool
    result: Any
    completed: bool = False  # Signal for goal completion
    completion_data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReflectionData(BaseModel):
    """LLM-generated reflection on progress and next steps."""

    progress_assessment: str = Field(description="LLM assessment of current progress")
    goal_achievement_status: GoalStatus
    next_action_reasoning: str = Field(description="LLM reasoning for next action")
    learned_insights: list[str] = Field(default_factory=list)
    challenges_encountered: list[str] = Field(default_factory=list)
    estimated_completion: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IterationState(BaseModel):
    """Complete state of an iterative agent execution."""

    iteration_count: int = 0
    goal: str
    current_plan: list[str] = Field(default_factory=list)
    completed_tasks: list[str] = Field(default_factory=list)
    action_history: list[ActionResult] = Field(default_factory=list)
    reflection_data: ReflectionData | None = None
    should_continue: bool = True
    context_id: str
    task_id: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add_completed_task(self, task: str) -> None:
        """Add a completed task and update timestamp."""
        if task not in self.completed_tasks:
            self.completed_tasks.append(task)
        self.last_updated = datetime.now(timezone.utc)

    def add_action_result(self, result: ActionResult) -> None:
        """Add an action result to history."""
        self.action_history.append(result)
        self.last_updated = datetime.now(timezone.utc)

    def update_reflection(self, reflection: ReflectionData) -> None:
        """Update reflection data and iteration count."""
        self.reflection_data = reflection
        self.iteration_count += 1
        self.last_updated = datetime.now(timezone.utc)

        # Update should_continue based on reflection
        if reflection.goal_achievement_status == GoalStatus.FULLY_ACHIEVED:
            self.should_continue = False


class StructuredCompletionResult(BaseModel):
    """Structured completion result from goal completion capability."""

    completed: bool
    completion_data: dict[str, Any] = Field(default_factory=dict)
    final_response: str = ""
