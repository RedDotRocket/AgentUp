"""
Hook specifications for AgentUp plugin system.

All skill plugins must implement these hooks to integrate with AgentUp.
"""

import pluggy

from .models import AIFunction, SkillContext, SkillInfo, SkillResult, ValidationResult

# Create the hook specification marker
hookspec = pluggy.HookspecMarker("agentup")


class SkillSpec:
    """Hook specifications that skill plugins must implement."""

    @hookspec
    def register_skill(self) -> SkillInfo:
        """
        Register the skill with AgentUp.

        This hook is called during plugin discovery to get information
        about the skill provided by this plugin.

        Returns:
            SkillInfo: Information about the skill including ID, name,
                      capabilities, and configuration schema.
        """

    @hookspec
    def validate_config(self, config: dict) -> ValidationResult:
        """
        Validate skill configuration.

        Called when the skill is being configured to ensure all required
        settings are present and valid.

        Args:
            config: Configuration dictionary for the skill

        Returns:
            ValidationResult: Validation result with any errors or warnings
        """

    @hookspec(firstresult=True)
    def can_handle_task(self, context: SkillContext) -> bool | float:
        """
        Check if this skill can handle the given task.

        This hook is used for intelligent routing. Skills can return:
        - True/False for simple binary routing
        - Float (0.0-1.0) for confidence-based routing

        Args:
            context: Skill context containing the task and configuration

        Returns:
            bool or float: Whether the skill can handle the task,
                          or confidence level (0.0-1.0)
        """

    @hookspec
    def execute_skill(self, context: SkillContext) -> SkillResult:
        """
        Execute the skill logic.

        This is the main entry point for skill execution. The skill should
        process the task and return a result.

        Args:
            context: Skill context with task, config, services, and state

        Returns:
            SkillResult: Result of skill execution including content and metadata
        """

    @hookspec
    def get_ai_functions(self) -> list[AIFunction]:
        """
        Get AI functions provided by this skill.

        For skills that support LLM function calling, this returns the
        function definitions that should be made available to the LLM.

        Returns:
            list[AIFunction]: List of AI function definitions
        """

    @hookspec
    def get_middleware_config(self) -> list[dict]:
        """
        Get middleware configuration for this skill.

        Skills can request specific middleware to be applied to their
        execution (rate limiting, caching, etc).

        Returns:
            list[dict]: List of middleware configurations
        """

    @hookspec
    def get_state_schema(self) -> dict:
        """
        Get state schema for stateful skills.

        For skills that maintain state between invocations, this defines
        the schema for the state data.

        Returns:
            dict: JSON schema for state data
        """

    @hookspec
    def configure_services(self, services: dict) -> None:
        """
        Configure services for the skill.

        Called during initialization to provide access to services like
        LLM, database, cache, etc.

        Args:
            services: Dictionary of available services
        """

    @hookspec
    def wrap_execution(self, context: SkillContext, next_handler) -> SkillResult:
        """
        Wrap skill execution with custom logic.

        This allows skills to add pre/post processing around execution.
        Skills should call next_handler(context) to continue the chain.

        Args:
            context: Skill context
            next_handler: Next handler in the chain

        Returns:
            SkillResult: Result from execution
        """

    @hookspec
    def on_install(self, install_path: str) -> None:
        """
        Called when the skill is installed.

        Skills can perform one-time setup tasks like creating directories,
        downloading models, etc.

        Args:
            install_path: Path where the skill is installed
        """

    @hookspec
    def on_uninstall(self) -> None:
        """
        Called when the skill is being uninstalled.

        Skills should clean up any resources, temporary files, etc.
        """

    @hookspec
    def get_health_status(self) -> dict:
        """
        Get health status of the skill.

        Used for monitoring and debugging. Skills can report their
        operational status, resource usage, etc.

        Returns:
            dict: Health status information
        """
