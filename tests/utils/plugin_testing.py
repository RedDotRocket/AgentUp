import asyncio
from typing import Any
from unittest.mock import Mock

from a2a.types import Task, TaskState, TaskStatus

from src.agent.plugins.models import CapabilityContext, CapabilityResult, PluginDefinition


class MockTask:
    def __init__(self, user_input: str = "", task_id: str = "test-123"):
        # Create a proper Task object that's compatible with Pydantic
        self._task = Task(
            id=task_id,
            context_id="test-context",
            status=TaskStatus(state=TaskState.submitted),
        )
        self._task.history = [Mock(parts=[Mock(text=user_input)])]
        self._task.metadata = {}

    def __getattr__(self, name):
        return getattr(self._task, name)

    def model_dump(self, **kwargs):
        return self._task.model_dump(**kwargs)

    def model_validate(self, obj, **kwargs):
        return self._task.model_validate(obj, **kwargs)


class PluginTestCase:
    def create_context(
        self,
        user_input: str = "",
        config: dict[str, Any] | None = None,
        services: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CapabilityContext:
        mock_task = MockTask(user_input)
        return CapabilityContext(
            task=mock_task._task,  # Pass the actual Task object
            config=config or {},
            services=services or {},
            state=state or {},
            metadata=metadata or {},
        )

    def assert_capability_info_valid(self, capability_info: PluginDefinition) -> None:
        assert isinstance(capability_info, PluginDefinition)
        assert capability_info.id
        assert capability_info.name
        assert capability_info.version
        assert isinstance(capability_info.capabilities, list)

    def assert_result_success(self, result: CapabilityResult) -> None:
        assert isinstance(result, CapabilityResult)
        assert result.success
        assert result.content
        assert result.error is None

    def assert_result_failure(self, result: CapabilityResult) -> None:
        assert isinstance(result, CapabilityResult)
        assert not result.success
        assert result.error is not None


class PluginTestRunner:
    def __init__(self, plugin_class):
        self.plugin_class = plugin_class
        self.plugin = None

    def setup(self) -> None:
        self.plugin = self.plugin_class()

    def teardown(self) -> None:
        self.plugin = None

    def test_registration(self) -> bool:
        try:
            capability_info = self.plugin.register_capability()
            assert isinstance(capability_info, PluginDefinition)
            assert capability_info.id
            assert capability_info.name
            return True
        except Exception as e:
            print(f"Registration test failed: {e}")
            return False

    def test_validation(self, test_configs: list[dict[str, Any]]) -> bool:
        try:
            for config in test_configs:
                result = self.plugin.validate_config(config)
                # Just check it returns a result, not whether it's valid
                assert hasattr(result, "valid")
            return True
        except Exception as e:
            print(f"Validation test failed: {e}")
            return False

    def test_execution(self, test_inputs: list[str]) -> bool:
        try:
            for user_input in test_inputs:
                mock_task = MockTask(user_input)
                context = CapabilityContext(task=mock_task._task)
                result = self.plugin.execute_capability(context)
                assert isinstance(result, CapabilityResult)
            return True
        except Exception as e:
            print(f"Execution test failed: {e}")
            return False

    def test_routing(self, test_cases: list[tuple[str, bool | float]]) -> bool:
        try:
            for user_input, expected in test_cases:
                mock_task = MockTask(user_input)
                context = CapabilityContext(task=mock_task._task)
                result = self.plugin.can_handle_task(context)

                if isinstance(expected, bool):
                    assert bool(result) == expected
                else:
                    # For float expectations, check within tolerance
                    assert abs(float(result) - expected) < 0.01
            return True
        except Exception as e:
            print(f"Routing test failed: {e}")
            return False

    def run_all_tests(self) -> dict[str, bool]:
        self.setup()

        results = {
            "registration": self.test_registration(),
            "validation": self.test_validation([{}, {"test": "config"}]),
            "execution": self.test_execution(["test input", "another test"]),
            "routing": self.test_routing([("test", True), ("unrelated", False)]),
        }

        self.teardown()
        return results


def create_test_plugin(skill_id: str, name: str) -> type:
    class TestPlugin:
        def register_capability(self) -> PluginDefinition:
            return PluginDefinition(
                id=skill_id,
                name=name,
                version="1.0.0",
                description=f"Test plugin: {name}",
                capabilities=["text"],
            )

        def validate_config(self, config: dict) -> Any:
            from src.agent.plugins.models import PluginValidationResult

            return PluginValidationResult(valid=True)

        def can_handle_task(self, context: CapabilityContext) -> bool:
            return True

        def execute_capability(self, context: CapabilityContext) -> CapabilityResult:
            return CapabilityResult(
                content=f"Executed {skill_id}",
                success=True,
            )

    return TestPlugin


async def test_plugin_async(plugin_instance) -> dict[str, Any]:
    results = {}

    # Test registration
    try:
        capability_info = plugin_instance.register_capability()
        results["registration"] = {
            "success": True,
            "capability_id": capability_info.id,
            "capability_name": capability_info.name,
        }
    except Exception as e:
        results["registration"] = {
            "success": False,
            "error": str(e),
        }

    # Test execution with various inputs
    test_inputs = [
        "Hello, plugin!",
        "Test message",
        "Complex query with multiple parts",
    ]

    execution_results = []
    for user_input in test_inputs:
        try:
            mock_task = MockTask(user_input)
            context = CapabilityContext(task=mock_task._task)

            # Handle both sync and async execute methods
            if asyncio.iscoroutinefunction(plugin_instance.execute_capability):
                result = await plugin_instance.execute_capability(context)
            else:
                result = plugin_instance.execute_capability(context)

            execution_results.append(
                {
                    "input": user_input,
                    "success": result.success,
                    "output": result.content[:100],  # Truncate for display
                }
            )
        except Exception as e:
            execution_results.append(
                {
                    "input": user_input,
                    "success": False,
                    "error": str(e),
                }
            )

    results["execution"] = execution_results

    # Test AI functions if available
    if hasattr(plugin_instance, "get_ai_functions"):
        try:
            ai_functions = plugin_instance.get_ai_functions()
            results["ai_functions"] = {
                "count": len(ai_functions),
                "names": [f.name for f in ai_functions],
            }
        except Exception as e:
            results["ai_functions"] = {
                "error": str(e),
            }

    return results
