"""Memory integration models for iterative agents."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LearningType(str, Enum):
    """Types of learning insights."""

    SUCCESS_PATTERN = "success_pattern"
    ERROR_PATTERN = "error_pattern"
    OPTIMIZATION = "optimization"
    USER_PREFERENCE = "user_preference"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


class LearningInsight(BaseModel):
    """A learning insight extracted from agent execution."""

    insight: str
    learning_type: LearningType
    context: str = Field(description="Context where this insight was learned")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    usage_count: int = 0
    first_observed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """Memory context for agent execution."""

    context_id: str
    agent_type: str
    session_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_iterations: int = 0
    successful_completions: int = 0
    failed_attempts: int = 0
    learning_insights: list[LearningInsight] = Field(default_factory=list)
    common_patterns: dict[str, int] = Field(default_factory=dict)

    def add_insight(self, insight: LearningInsight) -> None:
        """Add a learning insight to memory."""
        # Check for duplicate insights
        existing = next((i for i in self.learning_insights if i.insight == insight.insight), None)

        if existing:
            existing.usage_count += 1
            existing.last_used = lambda: datetime.now(timezone.utc)()
            existing.confidence = min(existing.confidence + 0.1, 1.0)
        else:
            self.learning_insights.append(insight)

    def increment_iteration(self) -> None:
        """Increment total iterations counter."""
        self.total_iterations += 1

    def mark_success(self) -> None:
        """Mark a successful completion."""
        self.successful_completions += 1

    def mark_failure(self) -> None:
        """Mark a failed attempt."""
        self.failed_attempts += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total_attempts = self.successful_completions + self.failed_attempts
        if total_attempts == 0:
            return 0.0
        return self.successful_completions / total_attempts
