import importlib.util
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RegistrySkillLoader:
    """Loads and registers skills from the registry skills directory."""

    def __init__(self):
        self.skills_dir = Path.home() / ".agentup" / "skills"
        self.loaded_skills: dict[str, Any] = {}
        self.skill_handlers: dict[str, Callable] = {}

    def load_all_registry_skills(self) -> None:
        """Load all installed registry skills."""
        if not self.skills_dir.exists():
            logger.debug("No registry skills directory found")
            return

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                try:
                    self.load_skill(skill_dir.name)
                except Exception as e:
                    logger.error(f"Failed to load skill {skill_dir.name}: {e}")

    def load_skill(self, skill_id: str) -> Callable | None:
        """Load a specific skill by ID."""
        skill_dir = self.skills_dir / skill_id

        if not skill_dir.exists():
            logger.warning(f"Skill directory not found: {skill_dir}")
            return None

        # Check if skill is enabled in agent config
        if not self._is_skill_enabled(skill_id):
            logger.debug(f"Skill {skill_id} is not enabled in agent config")
            return None

        try:
            # Load skill metadata
            skill_yaml = skill_dir / "skill.yaml"
            if not skill_yaml.exists():
                logger.error(f"No skill.yaml found for {skill_id}")
                return None

            with open(skill_yaml) as f:
                skill_config = yaml.safe_load(f)

            # Load the handler module
            handler_file = skill_dir / "handler.py"
            if not handler_file.exists():
                logger.error(f"No handler.py found for {skill_id}")
                return None

            # Dynamically import the handler module
            module_name = f"registry_skill_{skill_id}"
            spec = importlib.util.spec_from_file_location(module_name, handler_file)

            if spec is None or spec.loader is None:
                logger.error(f"Could not load module spec for {skill_id}")
                return None

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules to prevent reimport issues
            sys.modules[module_name] = module

            # Execute the module
            spec.loader.exec_module(module)

            # Look for the handler function
            handler_func = self._find_handler_function(module, skill_id, skill_config)

            if handler_func:
                self.skill_handlers[skill_id] = handler_func
                self.loaded_skills[skill_id] = {"config": skill_config, "module": module, "handler": handler_func}
                logger.info(f"Successfully loaded registry skill: {skill_id}")
                return handler_func
            else:
                logger.error(f"No handler function found for {skill_id}")
                return None

        except Exception as e:
            logger.error(f"Error loading skill {skill_id}: {e}")
            return None

    def _find_handler_function(self, module: Any, skill_id: str, skill_config: dict[str, Any]) -> Callable | None:
        """Find the handler function in the loaded module."""

        # Look for common handler function names
        possible_names = [
            f"handle_{skill_id}",
            f"handle_{skill_id.replace('-', '_')}",
            "handler",
            "main_handler",
            "skill_handler",
        ]

        for name in possible_names:
            if hasattr(module, name):
                func = getattr(module, name)
                if callable(func):
                    logger.debug(f"Found handler function: {name}")
                    return func

        # Look for any function that looks like a handler
        for attr_name in dir(module):
            if attr_name.startswith("handle_") and not attr_name.startswith("_"):
                attr = getattr(module, attr_name)
                if callable(attr):
                    logger.debug(f"Found handler function: {attr_name}")
                    return attr

        return None

    def _is_skill_enabled(self, skill_id: str) -> bool:
        """Check if a skill is enabled in the agent configuration."""
        try:
            config_path = Path("agent_config.yaml")
            if not config_path.exists():
                return False

            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Check registry_skills section
            registry_skills = config.get("registry_skills", [])
            for skill in registry_skills:
                if skill.get("skill_id") == skill_id:
                    return skill.get("enabled", True)

            # Check legacy skills section
            skills = config.get("skills", [])
            for skill in skills:
                if skill.get("skill_id") == skill_id:
                    return skill.get("enabled", True)

            return False

        except Exception as e:
            logger.error(f"Error checking if skill {skill_id} is enabled: {e}")
            return False

    def get_handler(self, skill_id: str) -> Callable | None:
        """Get a handler for a skill, loading it if necessary."""
        # Check if already loaded
        if skill_id in self.skill_handlers:
            return self.skill_handlers[skill_id]

        # Try to load it
        return self.load_skill(skill_id)

    def list_loaded_skills(self) -> list[str]:
        """list all loaded registry skills."""
        return list(self.loaded_skills.keys())

    def get_skill_info(self, skill_id: str) -> dict[str, Any] | None:
        """Get information about a loaded skill."""
        return self.loaded_skills.get(skill_id, {}).get("config")


# Global instance
_skill_loader = RegistrySkillLoader()


def get_registry_skill_handler(skill_id: str) -> Callable | None:
    """Get a handler for a registry skill."""
    return _skill_loader.get_handler(skill_id)


def load_all_registry_skills() -> None:
    """Load all registry skills at startup."""
    _skill_loader.load_all_registry_skills()


def list_registry_skills() -> list[str]:
    """list all loaded registry skills."""
    return _skill_loader.list_loaded_skills()
