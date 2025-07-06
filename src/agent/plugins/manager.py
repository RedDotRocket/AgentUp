"""
Plugin manager for AgentUp skill plugins.

Handles plugin discovery, loading, and lifecycle management.
"""

import importlib
import importlib.metadata
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

import pluggy

from .hookspecs import SkillSpec
from .models import (
    AIFunction,
    PluginInfo,
    PluginStatus,
    SkillContext,
    SkillInfo,
    SkillResult,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Hook implementation marker
hookimpl = pluggy.HookimplMarker("agentup")


class PluginManager:
    """Manages skill plugins for AgentUp."""

    def __init__(self):
        """Initialize the plugin manager."""
        self.pm = pluggy.PluginManager("agentup")
        self.pm.add_hookspecs(SkillSpec)

        self.plugins: dict[str, PluginInfo] = {}
        self.skills: dict[str, SkillInfo] = {}
        self.skill_to_plugin: dict[str, str] = {}

        # Track plugin hooks for each skill
        self.skill_hooks: dict[str, Any] = {}

    def discover_plugins(self) -> None:
        """Discover and load all available plugins."""
        logger.info("Discovering AgentUp plugins...")

        # Load from entry points
        self._load_entry_point_plugins()

        # Load from installed skills directory
        self._load_installed_plugins()

        logger.info(f"Discovered {len(self.plugins)} plugins providing {len(self.skills)} skills")

    def _load_entry_point_plugins(self) -> None:
        """Load plugins from Python entry points."""
        try:
            # Get all entry points in the agentup.skills group
            entry_points = importlib.metadata.entry_points()

            # Handle different Python versions
            if hasattr(entry_points, "select"):
                # Python 3.10+
                skill_entries = entry_points.select(group="agentup.skills")
            else:
                # Python 3.9
                skill_entries = entry_points.get("agentup.skills", [])

            for entry_point in skill_entries:
                try:
                    logger.debug(f"Loading entry point: {entry_point.name}")
                    plugin_class = entry_point.load()
                    plugin_instance = plugin_class()

                    # Register the plugin
                    self.pm.register(plugin_instance, name=entry_point.name)

                    # Track plugin info
                    plugin_info = PluginInfo(
                        name=entry_point.name,
                        version=self._get_package_version(entry_point.name),
                        status=PluginStatus.LOADED,
                        entry_point=str(entry_point),
                        module_name=entry_point.module,
                    )
                    self.plugins[entry_point.name] = plugin_info

                    # Register the skill
                    self._register_plugin_skill(entry_point.name, plugin_instance)

                except Exception as e:
                    logger.error(f"Failed to load entry point {entry_point.name}: {e}")
                    self.plugins[entry_point.name] = PluginInfo(
                        name=entry_point.name, version="unknown", status=PluginStatus.ERROR, error=str(e)
                    )
        except Exception as e:
            logger.error(f"Error loading entry point plugins: {e}")


    def _load_installed_plugins(self) -> None:
        """Load plugins from installed skills directory."""
        installed_dir = Path.home() / ".agentup" / "plugins"
        if not installed_dir.exists():
            logger.debug("No installed plugins directory found")
            return

        for plugin_dir in installed_dir.iterdir():
            if plugin_dir.is_dir():
                try:
                    # Check for plugin.py or __init__.py
                    if (plugin_dir / "plugin.py").exists():
                        self._load_installed_plugin(plugin_dir, "plugin.py")
                    elif (plugin_dir / "__init__.py").exists():
                        self._load_installed_plugin(plugin_dir, "__init__.py")
                except Exception as e:
                    logger.error(f"Failed to load installed plugin from {plugin_dir}: {e}")

    def _load_installed_plugin(self, plugin_dir: Path, entry_file: str) -> None:
        """Load a single installed plugin."""
        plugin_name = f"installed_{plugin_dir.name}"
        plugin_file = plugin_dir / entry_file

        # Similar to local plugin loading
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load plugin from {plugin_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin_name] = module
        spec.loader.exec_module(module)

        # Find plugin class
        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is None:
            # Search for a class with our hooks
            for _, obj in vars(module).items():
                if isinstance(obj, type) and hasattr(obj, "register_skill"):
                    plugin_class = obj
                    break

        if plugin_class is None:
            raise ValueError(f"No plugin class found in {plugin_file}")

        # Instantiate and register
        plugin_instance = plugin_class()
        self.pm.register(plugin_instance, name=plugin_name)

        # Load metadata if available
        metadata = {}
        metadata_file = plugin_dir / "plugin.yaml"
        if metadata_file.exists():
            import yaml

            with open(metadata_file) as f:
                metadata = yaml.safe_load(f) or {}

        # Track plugin info
        plugin_info = PluginInfo(
            name=plugin_name,
            version=metadata.get("version", "1.0.0"),
            author=metadata.get("author"),
            description=metadata.get("description"),
            status=PluginStatus.LOADED,
            module_name=plugin_name,
            metadata={"source": "installed", "path": str(plugin_dir)},
        )
        self.plugins[plugin_name] = plugin_info

        # Register the skill
        self._register_plugin_skill(plugin_name, plugin_instance)

    def _register_plugin_skill(self, plugin_name: str, plugin_instance: Any) -> None:
        """Register a skill from a plugin."""
        try:
            # Get skill info from the plugin
            results = self.pm.hook.register_skill()
            if not results:
                logger.warning(f"Plugin {plugin_name} did not return skill info")
                return

            # Find the result from this specific plugin
            skill_info = None
            for result in results:
                # Check if this result came from our plugin
                if hasattr(plugin_instance, "register_skill"):
                    test_result = plugin_instance.register_skill()
                    if test_result == result:
                        skill_info = result
                        break

            if skill_info is None:
                skill_info = results[-1]  # Fallback to last result

            if not isinstance(skill_info, SkillInfo):
                logger.error(f"Plugin {plugin_name} returned invalid skill info")
                return

            # Register the skill
            self.skills[skill_info.id] = skill_info
            self.skill_to_plugin[skill_info.id] = plugin_name
            self.skill_hooks[skill_info.id] = plugin_instance

            logger.info(f"Discovered skill '{skill_info.id}' from plugin '{plugin_name}'")

        except Exception as e:
            logger.error(f"Failed to register skill from plugin {plugin_name}: {e}")

    def _get_package_version(self, package_name: str) -> str:
        """Get version of an installed package."""
        try:
            return importlib.metadata.version(package_name)
        except Exception:
            return "unknown"

    def get_skill(self, skill_id: str) -> SkillInfo | None:
        """Get skill information by ID."""
        return self.skills.get(skill_id)

    def list_skills(self) -> list[SkillInfo]:
        """List all available skills."""
        return list(self.skills.values())

    def list_plugins(self) -> list[PluginInfo]:
        """List all loaded plugins."""
        return list(self.plugins.values())

    def can_handle_task(self, skill_id: str, context: SkillContext) -> bool | float:
        """Check if a skill can handle a task."""
        if skill_id not in self.skill_hooks:
            return False

        plugin = self.skill_hooks[skill_id]
        if hasattr(plugin, "can_handle_task"):
            try:
                return plugin.can_handle_task(context)
            except Exception as e:
                logger.error(f"Error checking if skill {skill_id} can handle task: {e}")
                return False
        return True  # Default to true if no handler

    def execute_skill(self, skill_id: str, context: SkillContext) -> SkillResult:
        """Execute a skill."""
        if skill_id not in self.skill_hooks:
            return SkillResult(content=f"Skill '{skill_id}' not found", success=False, error="Skill not found")

        plugin = self.skill_hooks[skill_id]
        try:
            return plugin.execute_skill(context)
        except Exception as e:
            logger.error(f"Error executing skill {skill_id}: {e}", exc_info=True)
            return SkillResult(content=f"Error executing skill: {str(e)}", success=False, error=str(e))

    def get_ai_functions(self, skill_id: str) -> list[AIFunction]:
        """Get AI functions from a skill."""
        if skill_id not in self.skill_hooks:
            return []

        plugin = self.skill_hooks[skill_id]
        if hasattr(plugin, "get_ai_functions"):
            try:
                return plugin.get_ai_functions()
            except Exception as e:
                logger.error(f"Error getting AI functions from skill {skill_id}: {e}")
        return []

    def validate_config(self, skill_id: str, config: dict) -> ValidationResult:
        """Validate skill configuration."""
        if skill_id not in self.skill_hooks:
            return ValidationResult(valid=False, errors=[f"Skill '{skill_id}' not found"])

        plugin = self.skill_hooks[skill_id]
        if hasattr(plugin, "validate_config"):
            try:
                return plugin.validate_config(config)
            except Exception as e:
                logger.error(f"Error validating config for skill {skill_id}: {e}")
                return ValidationResult(valid=False, errors=[f"Validation error: {str(e)}"])
        return ValidationResult(valid=True)  # Default to valid if no validator

    def configure_services(self, skill_id: str, services: dict) -> None:
        """Configure services for a skill."""
        if skill_id not in self.skill_hooks:
            return

        plugin = self.skill_hooks[skill_id]
        if hasattr(plugin, "configure_services"):
            try:
                plugin.configure_services(services)
            except Exception as e:
                logger.error(f"Error configuring services for skill {skill_id}: {e}")

    def find_skills_for_task(self, context: SkillContext) -> list[tuple[str, float]]:
        """Find skills that can handle a task, sorted by confidence."""
        candidates = []

        for skill_id, _ in self.skills.items():
            confidence = self.can_handle_task(skill_id, context)
            if confidence:
                # Convert boolean True to 1.0
                if confidence is True:
                    confidence = 1.0
                elif confidence is False:
                    continue

                candidates.append((skill_id, float(confidence)))

        # Sort by confidence (highest first) and priority
        candidates.sort(key=lambda x: (x[1], self.skills[x[0]].priority), reverse=True)
        return candidates

    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (useful for development)."""
        try:
            # Unregister the old plugin
            if plugin_name in self.plugins:
                self.pm.unregister(name=plugin_name)

                # Remove associated skills
                skills_to_remove = [
                    skill_id for skill_id, pname in self.skill_to_plugin.items() if pname == plugin_name
                ]
                for skill_id in skills_to_remove:
                    del self.skills[skill_id]
                    del self.skill_to_plugin[skill_id]
                    del self.skill_hooks[skill_id]

            # Reload based on source
            plugin_info = self.plugins.get(plugin_name)
            if plugin_info and plugin_info.metadata.get("source") == "local":
                path = Path(plugin_info.metadata["path"])
                self._load_local_plugin(path)
                return True
            elif plugin_info and plugin_info.metadata.get("source") == "installed":
                path = Path(plugin_info.metadata["path"])
                entry_file = "plugin.py" if (path / "plugin.py").exists() else "__init__.py"
                self._load_installed_plugin(path, entry_file)
                return True
            else:
                # Entry point plugins can't be reloaded easily
                logger.warning(f"Cannot reload entry point plugin {plugin_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            return False


# Global plugin manager instance
_plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.discover_plugins()
    return _plugin_manager
