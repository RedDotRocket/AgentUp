import pluggy

from .models import (
    AIFunction,
    CapabilityContext,
    CapabilityResult,
    PluginDefinition,
    PluginValidationResult,
)

# Create the hook specification marker
hookspec = pluggy.HookspecMarker("agentup")


class CapabilitySpec:
    @hookspec
    def register_capability(self) -> PluginDefinition | list[PluginDefinition]:
        """
        Register the capability or capabilities with AgentUp.

        This hook is called during plugin discovery to get information
        about the capability or capabilities provided by this plugin.

        Returns:
            PluginDefinition or list[PluginDefinition]: Information about the capability/capabilities
                                                    including ID, name, features, and configuration schema.
                                                    A plugin can provide a single capability or multiple capabilities.
        """

    @hookspec
    def validate_config(self, config: dict) -> PluginValidationResult:
        """
        Validate capability configuration.

        Called when the capability is being configured to ensure all required
        settings are present and valid.

        Args:
            config: Configuration dictionary for the capability

        Returns:
            PluginValidationResult: Validation result with any errors or warnings
        """

    @hookspec(firstresult=True)
    def can_handle_task(self, context: CapabilityContext) -> bool | float:
        """
        Check if this capability can handle the given task.

        This hook is used for  routing. Capabilities can return:
        - True/False for simple binary routing
        - Float (0.0-1.0) for confidence-based routing

        Args:
            context: Capability context containing the task and configuration

        Returns:
            bool or float: Whether the capability can handle the task,
                          or confidence level (0.0-1.0)
        """

    @hookspec
    def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
        """
        Execute the capability logic.

        This is the main entry point for capability execution. The capability should
        process the task and return a result.

        Args:
            context: Capability context with task, config, services, and state

        Returns:
            CapabilityResult: Result of capability execution including content and metadata
        """

    @hookspec
    def get_ai_functions(self) -> list[AIFunction]:
        """
        Get AI functions provided by this capability.

        For capabilities that support LLM function calling, this returns the
        function definitions that should be made available to the LLM.

        Returns:
            list[AIFunction]: List of AI function definitions
        """

    @hookspec
    def get_middleware_config(self) -> list[dict]:
        """
        Get middleware configuration for this capability.

        Capabilities can request specific middleware to be applied to their
        execution (rate limiting, caching, etc).

        Returns:
            list[dict]: List of middleware configurations
        """

    @hookspec
    def get_state_schema(self) -> dict:
        """
        Get state schema for stateful capabilities.

        For capabilities that maintain state between invocations, this defines
        the schema for the state data.

        Returns:
            dict: JSON schema for state data
        """

    @hookspec
    def configure_services(self, services: dict) -> None:
        """
        Configure services for the capability.

        Called during initialization to provide access to services like
        LLM, database, cache, etc.

        Args:
            services: Dictionary of available services
        """

    @hookspec
    def wrap_execution(self, context: CapabilityContext, next_handler) -> CapabilityResult:
        """
        Wrap capability execution with custom logic.

        This allows capabilities to add pre/post processing around execution.
        Capabilities should call next_handler(context) to continue the chain.

        Args:
            context: Capability context
            next_handler: Next handler in the chain

        Returns:
            CapabilityResult: Result from execution
        """

    @hookspec
    def on_install(self, install_path: str) -> None:
        """
        Called when the capability is installed.

        Capabilities can perform one-time setup tasks like creating directories,
        downloading models, etc.

        Args:
            install_path: Path where the capability is installed
        """

    @hookspec
    def on_uninstall(self) -> None:
        """
        Called when the capability is being uninstalled.

        Capabilities should clean up any resources, temporary files, etc.
        """

    @hookspec
    def get_health_status(self) -> dict:
        """
        Get health status of the capability.

        Used for monitoring and debugging. Capabilities can report their
        operational status, resource usage, etc.

        Returns:
            dict: Health status information
        """
