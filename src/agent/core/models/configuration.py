"""Configuration models for AgentUp execution system."""

from pydantic import BaseModel, Field, field_validator

from agent.config.model import AgentType, IterativeConfig, MemoryConfig


class AgentConfiguration(BaseModel):
    """Complete agent configuration model."""

    model_config = {"use_enum_values": True}

    agent_type: AgentType = AgentType.REACTIVE
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    iterative: IterativeConfig = Field(default_factory=IterativeConfig)

    @field_validator("agent_type", mode="before")
    @classmethod
    def validate_agent_type(cls, v):
        """Validate and convert agent_type to proper enum value."""
        if isinstance(v, str):
            # Handle string values
            if v.lower() in ["reactive", "iterative"]:
                return v.lower()
            else:
                raise ValueError(f"Invalid agent_type: {v}. Must be 'reactive' or 'iterative'")
        elif isinstance(v, AgentType):
            # Handle enum instances
            return v.value
        else:
            # Default to reactive
            return AgentType.REACTIVE.value
