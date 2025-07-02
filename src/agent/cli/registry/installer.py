import logging
import os
import shutil
import subprocess  # nosec
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from ..cli_utils import safe_extract
from .client import RegistryClient
from .validator import SkillValidator

console = Console()
logger = logging.getLogger(__name__)


class SkillInstaller:
    """Manages skill installation and local storage."""

    def __init__(self):
        # No longer using global cache - skills go directly into projects
        self.client = RegistryClient()
        self.validator = SkillValidator()
        self.current_project = self._detect_agent_project()

    def _detect_agent_project(self) -> Path | None:
        """Detect if we're in an AgentUp project directory."""
        # Look for agent_config.yaml in current directory or parents
        current = Path.cwd()

        # Check current directory and up to 3 levels up
        for _ in range(4):
            config_path = current / "agent_config.yaml"
            if config_path.exists():
                return current

            # Don't go above home directory
            if current == current.parent or current == Path.home():
                break

            current = current.parent

        return None

    def _is_in_agent_project(self) -> bool:
        """Check if we're in an agent project."""
        return self.current_project is not None

    def _parse_skill_id(self, skill_id: str) -> tuple[str, str, str]:
        """Parse skill_id into namespace, name, and full_id.

        Args:
            skill_id: Either 'skill_name' or 'namespace/skill_name'

        Returns:
            Tuple of (namespace, skill_name, full_skill_id)
            - For 'weather_forecast': ('', 'weather_forecast', 'weather_forecast')
            - For 'lukehinds/weather_forecast': ('lukehinds', 'weather_forecast', 'lukehinds/weather_forecast')
        """
        if "/" in skill_id:
            namespace, skill_name = skill_id.split("/", 1)
            return namespace, skill_name, skill_id
        else:
            return "", skill_id, skill_id

    def _get_handler_path(self, skill_id: str) -> Path:
        """Get the handler file path for a skill based on namespace."""
        if not self.current_project:
            raise ValueError("Not in an agent project")

        namespace, skill_name, _ = self._parse_skill_id(skill_id)
        handlers_dir = self.current_project / "src" / "agent" / "handlers"

        if namespace:
            # Namespaced skill: src/agent/handlers/community/namespace/skill_handler.py
            return handlers_dir / "community" / namespace / f"{skill_name}_handler.py"
        else:
            # Non-namespaced skill: src/agent/handlers/skill_handler.py
            return handlers_dir / f"{skill_name}_handler.py"

    def _is_skill_in_project_config(self, skill_id: str) -> bool:
        """Check if skill is configured in current project."""
        if not self.current_project:
            return False

        config_path = self.current_project / "agent_config.yaml"
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Check main skills section
            for skill in config.get("skills", []):
                if skill.get("skill_id") == skill_id:
                    return True

        except FileNotFoundError:
            logger.debug(f"Config file not found: {config_path}")
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in config file {config_path}: {e}")
        except PermissionError:
            logger.error(f"Permission denied reading config file: {config_path}")
        except Exception as e:
            logger.error(f"Unexpected error reading config file {config_path}: {e}")

        return False

    async def install_skill(
        self, skill_id: str, version: str = "latest", preview_only: bool = False, force: bool = False
    ) -> bool:
        """Install a skill from the registry directly into the project."""

        # Must be in a project to install skills
        if not self._is_in_agent_project():
            console.print("[red]❌ Must be in an AgentUp project to install skills[/red]")
            console.print("Create a project first: [cyan]agentup agent create my-project[/cyan]")
            return False

        try:
            # 1. Get skill information
            skill_info = await self.client.get_skill_details(skill_id)

            if version == "latest":
                version = skill_info["latest_version"]["version"]

            # 2. Check if already installed in current project
            if not force and self._is_skill_in_project_config(skill_id):
                console.print(f"[yellow]Skill {skill_id}@{version} is already installed in this project[/yellow]")

                # Show handler path
                handler_path = self._get_handler_path(skill_id)
                if handler_path.exists():
                    console.print(f"[dim]Handler: {handler_path.relative_to(self.current_project)}[/dim]")

                return True

            if preview_only:
                self._show_install_preview(skill_info, version)
                return True

            # 3. Download and integrate into project
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                console.print(f"[blue]📦 Installing {skill_id}@{version} into project...[/blue]")
                package_path = await self.client.download_skill_package(skill_id, temp_path, version)

                # 4. Extract and validate
                console.print("[dim]Validating package...[/dim]")
                extracted_path = temp_path / "extracted"
                self._extract_package(package_path, extracted_path)

                # Find skill directory in extracted package
                skill_content_dir = self._find_skill_directory(extracted_path)
                if not skill_content_dir:
                    console.print("[red]❌ Invalid package structure[/red]")
                    return False

                # 5. Validate package
                validation_result = await self.validator.validate_package(package_path)

                # Show validation results
                if validation_result.warnings:
                    console.print("[yellow]Warnings:[/yellow]")
                    for warning in validation_result.warnings:
                        console.print(f"  ⚠️  {warning}")

                if not validation_result.is_valid:
                    console.print("[red]Validation failed:[/red]")
                    for error in validation_result.errors:
                        console.print(f"  ❌ {error}")
                    return False

                # 6. Integrate directly into project
                console.print(f"[blue]📍 Integrating into project: {self.current_project.name}[/blue]")

                # Copy handler to project with namespace support
                handler_copied = await self._copy_handler_to_project(skill_id, skill_content_dir)

                # Install dependencies to project
                deps_installed = await self._install_dependencies_to_project(skill_content_dir, skill_info)

                # Add to project config (main skills section)
                config_updated = await self._add_to_project_skills(skill_info, version)

                if handler_copied and config_updated:
                    self._show_integration_success_message(
                        skill_id, version, skill_info, deps_installed, config_updated
                    )
                    return True
                else:
                    console.print(f"[red]❌ Failed to integrate {skill_id}[/red]")
                    return False

        except Exception as e:
            console.print(f"[red]❌ Error installing skill: {e}[/red]")
            return False

    def _find_skill_directory(self, extracted_path: Path) -> Path | None:
        """Find the actual skill directory in extracted package."""
        # Look for directory containing skill.yaml
        for item in extracted_path.iterdir():
            if item.is_dir():
                if (item / "skill.yaml").exists():
                    return item

        # Check if skill.yaml is directly in extracted_path
        if (extracted_path / "skill.yaml").exists():
            return extracted_path

        return None

    def is_skill_installed(self, skill_id: str, version: str | None = None) -> bool:
        """Check if a skill is installed in the current project."""
        if not self._is_in_agent_project():
            return False

        # Check if handler file exists
        handler_path = self._get_handler_path(skill_id)
        if not handler_path.exists():
            return False

        # Check if it's in the config
        return self._is_skill_in_project_config(skill_id)

    def list_installed_skills(self) -> list[dict[str, Any]]:
        """list all installed skills in the current project."""
        installed = []

        if not self._is_in_agent_project():
            return installed

        # Read from agent_config.yaml to get installed skills
        config_path = self.current_project / "agent_config.yaml"
        if not config_path.exists():
            return installed

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Look for skills in main skills section
            for skill in config.get("skills", []):
                skill_id = skill.get("skill_id")
                if not skill_id:
                    continue

                # Check if this is a registry skill by checking if handler exists
                handler_path = self._get_handler_path(skill_id)
                if handler_path.exists():
                    installed.append(
                        {
                            "skill_id": skill_id,
                            "name": skill.get("name", skill_id),
                            "version": skill.get("version", "unknown"),
                            "description": skill.get("description", ""),
                            "enabled": skill.get("enabled", True),
                            "source": "registry",
                        }
                    )

        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in config file {config_path}: {e}")
        except PermissionError:
            logger.error(f"Permission denied reading config file: {config_path}")
        except Exception as e:
            logger.error(f"Unexpected error reading config file {config_path}: {e}")

        return installed

    async def remove_skill(self, skill_id: str) -> bool:
        """Remove an installed skill from the current project."""
        if not self._is_in_agent_project():
            console.print("[red]❌ Must be in an AgentUp project to remove skills[/red]")
            return False

        # Check if skill is installed
        if not self.is_skill_installed(skill_id):
            console.print(f"[yellow]Skill {skill_id} is not installed in this project[/yellow]")
            return False

        try:
            # Remove handler file and directories
            handler_path = self._get_handler_path(skill_id)
            if handler_path.exists():
                handler_path.unlink()
                console.print(f"[green]✅ Removed handler: {handler_path.relative_to(self.current_project)}[/green]")

                # Clean up empty namespace directories
                self._cleanup_empty_directories(handler_path.parent)

            # Remove from agent config
            await self._remove_from_agent_config(skill_id)

            console.print(f"[green]✅ Removed skill {skill_id} from project[/green]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Error removing skill: {e}[/red]")
            return False

    def _cleanup_empty_directories(self, directory: Path) -> None:
        """Remove empty directories up to handlers/community."""
        handlers_dir = self.current_project / "src" / "agent" / "handlers"
        community_dir = handlers_dir / "community"

        current = directory
        while current != community_dir and current != handlers_dir and current != current.parent:
            try:
                if current.is_dir() and not any(current.iterdir()):
                    current.rmdir()
                    current = current.parent
                else:
                    break
            except OSError:
                break

    async def update_skill(self, skill_id: str) -> bool:
        """Update a skill to the latest version."""
        if not self.is_skill_installed(skill_id):
            console.print(f"[yellow]Skill {skill_id} is not installed[/yellow]")
            return False

        try:
            # Get current version
            current_info = self._get_installed_skill_info(skill_id)
            current_version = current_info.get("version", "unknown")

            # Get latest version from registry
            skill_info = await self.client.get_skill_details(skill_id)
            latest_version = skill_info["latest_version"]["version"]

            if current_version == latest_version:
                console.print(f"[green]Skill {skill_id} is already up to date ({latest_version})[/green]")
                return True

            console.print(f"[cyan]Updating {skill_id} from {current_version} to {latest_version}[/cyan]")
            return await self.install_skill(skill_id, latest_version, force=True)

        except Exception as e:
            console.print(f"[red]Error updating skill: {e}[/red]")
            return False

    async def enable_skill(self, skill_id: str) -> bool:
        """Enable a skill in agent configuration."""
        # Check if we're in a project
        if not self._is_in_agent_project():
            console.print("[red]❌ No agent project found[/red]")
            console.print("Navigate to an agent project directory (with agent_config.yaml)")
            return False

        # Check if skill is installed in project
        if not self.is_skill_installed(skill_id):
            console.print(f"[red]❌ Skill {skill_id} is not installed in this project[/red]")
            console.print(f"Install it first: [cyan]agentup skill install {skill_id}[/cyan]")
            return False

        # Check if skill is already enabled
        if self._is_skill_enabled(skill_id):
            console.print(f"[yellow]Skill {skill_id} is already enabled[/yellow]")
            return True

        # Enable the skill
        return await self._update_skill_status(skill_id, enabled=True)

    async def disable_skill(self, skill_id: str) -> bool:
        """Disable a skill in agent configuration."""
        return await self._update_skill_status(skill_id, enabled=False)

    def _extract_package(self, package_path: Path, destination: Path) -> None:
        """Extract a skill package safely, preventing path traversal attacks."""
        destination.mkdir(parents=True, exist_ok=True)

        with tarfile.open(package_path, "r:gz") as tar:
            # Validate each member before extraction to prevent path traversal
            for member in tar.getmembers():
                # Check for path traversal attempts
                if member.name.startswith("/") or ".." in member.name:
                    raise ValueError(f"Unsafe path in archive: {member.name}")

                # Check for absolute paths and normalize
                if member.name.startswith("/"):
                    member.name = member.name.lstrip("/")

                # Ensure we don't extract outside destination directory
                member_path = destination / member.name
                if not str(member_path.resolve()).startswith(str(destination.resolve())):
                    raise ValueError(f"Path traversal attempt detected: {member.name}")

            # Extract all validated members
            safe_extract(tar, path=destination)

    async def _handle_dependencies(self, skill_dir: Path, skill_info: dict[str, Any]) -> bool:
        """Handle skill dependencies with better UX."""
        # First check skill.yaml for dependencies
        dependencies = self._extract_dependencies(skill_dir, skill_info)

        if not dependencies:
            return True

        console.print("\n[bold]📋 Dependencies required:[/bold]")
        for dep in dependencies:
            console.print(f"  • {dep}")

        # If we're in a project and have uv, auto-install dependencies
        if self._is_in_agent_project() and self._has_uv():
            console.print("\n[blue]Installing dependencies automatically...[/blue]")
            return await self._install_with_uv(dependencies)
        else:
            # Show manual installation instructions
            console.print("\n[yellow]Install dependencies manually:[/yellow]")
            if self._has_uv():
                console.print(f"  [cyan]uv add {' '.join(dependencies)}[/cyan]")
            else:
                console.print(f"  [cyan]pip install {' '.join(dependencies)}[/cyan]")
            return False

    def _extract_dependencies(self, skill_dir: Path, skill_info: dict[str, Any]) -> list[str]:
        """Extract dependencies from skill.yaml or requirements.txt."""
        dependencies = []

        # First try skill.yaml
        skill_yaml = skill_dir / "skill.yaml"
        if skill_yaml.exists():
            try:
                with open(skill_yaml) as f:
                    skill_config = yaml.safe_load(f)

                deps = skill_config.get("dependencies", {})
                packages = deps.get("packages", [])
                if packages:
                    dependencies.extend(packages)
            except yaml.YAMLError as e:
                logger.warning(f"Invalid YAML in skill.yaml {skill_yaml}: {e}")
            except Exception as e:
                logger.debug(f"Could not read skill dependencies from {skill_yaml}: {e}")

        # Fallback to requirements.txt
        if not dependencies:
            requirements_file = skill_dir / "requirements.txt"
            if requirements_file.exists():
                try:
                    with open(requirements_file) as f:
                        dependencies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                except PermissionError:
                    logger.warning(f"Permission denied reading requirements.txt: {requirements_file}")
                except Exception as e:
                    logger.debug(f"Could not read requirements.txt {requirements_file}: {e}")

        return dependencies

    async def _copy_handler_to_project(self, skill_id: str, skill_dir: Path) -> bool:
        """Copy skill handler to project's handlers directory with namespace support."""
        if not self.current_project:
            return False

        # Source handler file
        handler_file = skill_dir / "handler.py"
        if not handler_file.exists():
            console.print("[red]❌ No handler.py found in skill package[/red]")
            return False

        # Get destination path with namespace support
        dest_file = self._get_handler_path(skill_id)

        # Create directory structure if it doesn't exist
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Create __init__.py files for Python package structure
        self._create_init_files(dest_file.parent)

        try:
            shutil.copy2(handler_file, dest_file)
            console.print(f"[green]✅ Copied handler to {dest_file.relative_to(self.current_project)}[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Failed to copy handler: {e}[/red]")
            return False

    def _create_init_files(self, directory: Path) -> None:
        """Create __init__.py files for proper Python package structure."""
        handlers_dir = self.current_project / "src" / "agent" / "handlers"

        # Walk up from the target directory to handlers dir and create __init__.py files
        current = directory
        while current != handlers_dir and current != current.parent:
            init_file = current / "__init__.py"
            if not init_file.exists():
                init_file.touch()
            current = current.parent

    async def _install_dependencies_to_project(self, skill_dir: Path, skill_info: dict[str, Any]) -> bool:
        """Install skill dependencies to the current project."""
        if not self.current_project:
            return False

        dependencies = self._extract_dependencies(skill_dir, skill_info)

        if not dependencies:
            console.print("[dim]No dependencies to install[/dim]")
            return True

        console.print("\n[bold]📋 Installing dependencies to project:[/bold]")
        for dep in dependencies:
            console.print(f"  • {dep}")

        if not self._has_uv():
            console.print("\n[red]❌ 'uv' not found. Install dependencies manually:[/red]")
            console.print(f"  [cyan]pip install {' '.join(dependencies)}[/cyan]")
            return False

        try:
            # Change to project directory for uv add
            original_cwd = Path.cwd()
            os.chdir(self.current_project)

            cmd = ["uv", "add"] + dependencies
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

            # Bandit: subprocess is used for uv, no external input involved
            result = subprocess.run(  # nosec
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # Change back to original directory
            os.chdir(original_cwd)

            if result.returncode == 0:
                console.print("[green]✅ Dependencies installed to project[/green]")
                return True
            else:
                console.print(f"[red]❌ Failed to install dependencies: {result.stderr}[/red]")
                return False

        except subprocess.TimeoutExpired:
            console.print("[red]❌ Dependency installation timed out[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error installing dependencies: {e}[/red]")
            return False
        finally:
            # Ensure we're back in original directory
            try:
                os.chdir(original_cwd)
            except Exception as e:
                logger.debug(f"Could not change back to original directory {original_cwd}: {e}")

    def _has_uv(self) -> bool:
        """Check if uv is available."""
        try:
            # Bandit: subprocess is used to check for uv, no external input involved
            subprocess.run(["uv", "--version"], capture_output=True, check=True)  # nosec
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    async def _install_with_uv(self, dependencies: list[str]) -> bool:
        """Install dependencies using uv."""
        try:
            cmd = ["uv", "add"] + dependencies
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")

            # Bandit: subprocess is used for uv, no external input involved
            result = subprocess.run(  # nosec
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                console.print("[green]✅ Dependencies installed[/green]")
                return True
            else:
                console.print(f"[red]❌ Failed to install dependencies: {result.stderr}[/red]")
                console.print(f"\n[yellow]Try manually:[/yellow] [cyan]uv add {' '.join(dependencies)}[/cyan]")
                return False

        except subprocess.TimeoutExpired:
            console.print("[red]❌ Dependency installation timed out[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error installing dependencies: {e}[/red]")
            return False

    def _show_install_preview(self, skill_info: dict[str, Any], version: str) -> None:
        """Show what would be installed."""
        latest_version = skill_info["latest_version"]

        console.print(f"[cyan]Would install: {skill_info['name']} v{version}[/cyan]")
        console.print(f"Description: {skill_info['description']}")
        console.print(f"Author: {skill_info['author']['display_name']}")
        console.print(f"Category: {skill_info['category']}")
        console.print(f"Tags: {', '.join(skill_info['tags'])}")

        deps = latest_version.get("dependencies", {})
        if deps.get("packages"):
            console.print(f"Dependencies: {', '.join(deps['packages'])}")

        apis = latest_version.get("external_apis", [])
        if apis:
            console.print("External APIs required:")
            for api in apis:
                env_var = api.get("env_var", "N/A")
                required = "Required" if api.get("required", True) else "Optional"
                console.print(f"  - {api['name']}: {env_var} ({required})")

    # Agent config management methods
    async def _update_project_config(self, skill_info: dict[str, Any], version: str) -> bool:
        """Add skill to project's agent_config.yaml."""
        if not self.current_project:
            return False

        config_path = self.current_project / "agent_config.yaml"

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            console.print("[red]❌ Config file not found: agent_config.yaml[/red]")
            return False
        except yaml.YAMLError as e:
            console.print(f"[red]❌ Invalid YAML in agent_config.yaml: {e}[/red]")
            return False
        except PermissionError:
            console.print("[red]❌ Permission denied reading agent_config.yaml[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Unexpected error reading agent_config.yaml: {e}[/red]")
            return False

        # Ensure registry_skills section exists
        if "registry_skills" not in config:
            config["registry_skills"] = []
            console.print("[blue]🔧 Adding registry_skills section to agent_config.yaml[/blue]")

        # Remove existing entry for this skill
        config["registry_skills"] = [
            skill for skill in config["registry_skills"] if skill.get("skill_id") != skill_info["skill_id"]
        ]

        # Add new skill entry
        latest_version = skill_info["latest_version"]
        skill_entry = {
            "skill_id": skill_info["skill_id"],
            "name": skill_info["name"],
            "description": skill_info["description"],
            "version": version,
            "source": "registry",
            "enabled": True,
        }

        # Add external API config if present
        apis = latest_version.get("external_apis", [])
        if apis:
            skill_entry["external_apis"] = apis

        config["registry_skills"].append(skill_entry)

        # Write back to file
        try:
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            console.print(f"[green]✅ Added {skill_info['skill_id']} to agent_config.yaml[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Could not update agent_config.yaml: {e}[/red]")
            return False

    async def _add_to_project_skills(self, skill_info: dict[str, Any], version: str) -> bool:
        """Add skill to the main 'skills' section of agent_config.yaml."""
        if not self.current_project:
            return False

        config_path = self.current_project / "agent_config.yaml"

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            console.print("[red]❌ Config file not found: agent_config.yaml[/red]")
            return False
        except yaml.YAMLError as e:
            console.print(f"[red]❌ Invalid YAML in agent_config.yaml: {e}[/red]")
            return False
        except PermissionError:
            console.print("[red]❌ Permission denied reading agent_config.yaml[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Unexpected error reading agent_config.yaml: {e}[/red]")
            return False

        # Ensure skills section exists
        if "skills" not in config:
            config["skills"] = []

        skill_id = skill_info["skill_id"]

        # Remove existing entry for this skill
        config["skills"] = [skill for skill in config["skills"] if skill.get("skill_id") != skill_id]

        # Create skill entry following the AgentUp format
        latest_version = skill_info.get("latest_version", {})

        # Determine input/output modes from skill.yaml
        input_modes = latest_version.get("input_modes", ["text"])
        output_modes = latest_version.get("output_modes", ["text"])

        skill_entry = {
            "skill_id": skill_id,
            "name": skill_info["name"],
            "description": skill_info["description"],
            "input_mode": input_modes[0] if input_modes else "text",  # Take first mode
            "output_mode": output_modes[0] if output_modes else "text",  # Take first mode
        }

        config["skills"].append(skill_entry)

        # Write back to file
        try:
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            console.print(f"[green]✅ Added {skill_id} to skills section[/green]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Could not update agent_config.yaml: {e}[/red]")
            return False

    def _show_integration_success_message(
        self, skill_id: str, version: str, skill_info: dict[str, Any], deps_installed: bool, config_updated: bool
    ) -> None:
        """Show success message for full project integration."""
        console.print(f"\n[bold green]✨ Successfully integrated {skill_id}@{version} into your project![/bold green]")

        # Show what was integrated
        console.print("\n[bold]Integrated components:[/bold]")

        # Show handler path with namespace
        _handler_path = self._get_handler_path(skill_id)
        console.print("  ✅ Handler: [cyan]{handler_path.relative_to(self.current_project)}[/cyan]")
        console.print("  ✅ Configuration: Added to [cyan]skills[/cyan] section")

        if deps_installed:
            console.print("  ✅ Dependencies: Installed to project")

        # Show environment variables if needed
        latest_version = skill_info.get("latest_version", {})
        apis = latest_version.get("external_apis", [])

        env_vars_needed = []
        for api in apis:
            if api.get("required", True) and api.get("env_var"):
                env_vars_needed.append(api)

        if env_vars_needed:
            console.print("\n[bold yellow]Environment variables required:[/bold yellow]")
            for api in env_vars_needed:
                env_var = api.get("env_var")
                signup_url = api.get("signup_url", "")
                if signup_url:
                    console.print(f"  • [cyan]{env_var}[/cyan] - Get from {signup_url}")
                else:
                    console.print(f"  • [cyan]{env_var}[/cyan] - {api.get('description', '')}")

        # Show next steps
        console.print("\n[bold]Next steps:[/bold]")

        step = 1
        if env_vars_needed:
            console.print(f"{step}. Set required environment variables")
            step += 1

        console.print(f"{step}. Start your agent: [cyan]agentup agent serve[/cyan]")
        step += 1
        console.print(f"{step}. The {skill_id} skill is now part of your agent!")

    def _show_success_message(
        self, skill_id: str, version: str, skill_info: dict[str, Any], deps_installed: bool, config_updated: bool
    ) -> None:
        """Show comprehensive success message with next steps."""
        console.print(f"\n[bold green]✨ Successfully installed {skill_id}@{version}![/bold green]")

        # Show environment variables if needed
        latest_version = skill_info.get("latest_version", {})
        apis = latest_version.get("external_apis", [])

        env_vars_needed = []
        for api in apis:
            if api.get("required", True) and api.get("env_var"):
                env_vars_needed.append(api)

        if env_vars_needed:
            console.print("\n[bold yellow]Environment variables required:[/bold yellow]")
            for api in env_vars_needed:
                env_var = api.get("env_var")
                signup_url = api.get("signup_url", "")
                if signup_url:
                    console.print(f"  • [cyan]{env_var}[/cyan] - Get from {signup_url}")
                else:
                    console.print(f"  • [cyan]{env_var}[/cyan] - {api.get('description', '')}")

        # Show next steps
        console.print("\n[bold]Next steps:[/bold]")

        step = 1
        if env_vars_needed:
            console.print(f"{step}. Set required environment variables")
            step += 1

        if not config_updated and self._is_in_agent_project():
            console.print(f"{step}. Enable the skill: [cyan]agentup skill enable {skill_id}[/cyan]")
            step += 1

        if self._is_in_agent_project():
            console.print(f"{step}. Start your agent: [cyan]agentup agent serve[/cyan]")
            step += 1
            console.print(f"{step}. The {skill_id} skill is now available to your agent")
        else:
            console.print(f"{step}. Navigate to an agent project and enable the skill")

    async def _add_skill_to_project(self, skill_id: str) -> bool:
        """Add an installed skill to the current project configuration."""
        try:
            # Get skill info from installed skill
            skill_dir = self.skills_dir / skill_id
            skill_yaml = skill_dir / "skill.yaml"

            if not skill_yaml.exists():
                console.print(f"[red]❌ Skill configuration not found: {skill_yaml}[/red]")
                return False

            with open(skill_yaml) as f:
                skill_config = yaml.safe_load(f)

            # Create skill info dict similar to registry response
            skill_info = {
                "skill_id": skill_config.get("skill_id", skill_id),
                "name": skill_config.get("name", skill_id),
                "description": skill_config.get("description", ""),
                "latest_version": {"external_apis": skill_config.get("external_apis", [])},
            }

            version = skill_config.get("version", "unknown")
            return await self._update_project_config(skill_info, version)

        except Exception as e:
            console.print(f"[red]❌ Error adding skill to project: {e}[/red]")
            return False

    def _show_manual_config_instructions(self, skill_id: str) -> None:
        """Show manual configuration instructions."""
        console.print(f"\n[yellow]To add {skill_id} manually, add this to your agent_config.yaml:[/yellow]")

        # Try to get skill info for better YAML
        try:
            skill_dir = self.skills_dir / skill_id
            skill_yaml = skill_dir / "skill.yaml"

            if skill_yaml.exists():
                with open(skill_yaml) as f:
                    skill_config = yaml.safe_load(f)

                config_snippet = f"""
registry_skills:
- skill_id: {skill_config.get("skill_id", skill_id)}
  name: "{skill_config.get("name", skill_id)}"
  description: "{skill_config.get("description", "")}"
  version: "{skill_config.get("version", "unknown")}"
  source: "registry"
  enabled: true"""

                console.print(f"[cyan]{config_snippet}[/cyan]")

                # Show env vars if needed
                apis = skill_config.get("external_apis", [])
                if apis:
                    console.print("\n[yellow]Environment variables needed:[/yellow]")
                    for api in apis:
                        if api.get("env_var"):
                            console.print(f"  • [cyan]{api['env_var']}[/cyan]")
            else:
                # Basic fallback
                config_snippet = f"""
registry_skills:
- skill_id: {skill_id}
  name: "{skill_id.replace("_", " ").title()}"
  description: "Registry skill"
  enabled: true"""
                console.print(f"[cyan]{config_snippet}[/cyan]")

        except Exception as e:
            # Basic fallback when skill config can't be read
            logger.debug(f"Could not read skill config for preview, using basic fallback: {e}")
            config_snippet = f"""
registry_skills:
- skill_id: {skill_id}
  enabled: true"""
            console.print(f"[cyan]{config_snippet}[/cyan]")

    async def _remove_from_agent_config(self, skill_id: str) -> None:
        """Remove skill from agent_config.yaml."""
        config_path = Path("agent_config.yaml")

        if not config_path.exists():
            return

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Remove from registry_skills
            if "registry_skills" in config:
                config["registry_skills"] = [
                    skill for skill in config["registry_skills"] if skill.get("skill_id") != skill_id
                ]

            # Remove from skills (legacy)
            if "skills" in config:
                config["skills"] = [skill for skill in config["skills"] if skill.get("skill_id") != skill_id]

            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            console.print(f"[yellow]Warning: Could not update agent_config.yaml: {e}[/yellow]")

    async def _update_skill_status(self, skill_id: str, enabled: bool) -> bool:
        """Update skill enabled status in agent_config.yaml."""
        config_path = Path("agent_config.yaml")

        if not config_path.exists():
            console.print("[red]No agent_config.yaml found[/red]")
            return False

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Update in registry_skills
            updated = False
            if "registry_skills" in config:
                for skill in config["registry_skills"]:
                    if skill.get("skill_id") == skill_id:
                        skill["enabled"] = enabled
                        updated = True
                        break

            # Update in skills (legacy)
            if "skills" in config:
                for skill in config["skills"]:
                    if skill.get("skill_id") == skill_id:
                        skill["enabled"] = enabled
                        updated = True
                        break

            if updated:
                with open(config_path, "w") as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                status = "enabled" if enabled else "disabled"
                console.print(f"[green]✅ Skill {skill_id} {status}[/green]")
                return True
            else:
                console.print(f"[yellow]Skill {skill_id} not found in configuration[/yellow]")
                return False

        except Exception as e:
            console.print(f"[red]Error updating skill status: {e}[/red]")
            return False

    def _is_skill_enabled(self, skill_id: str) -> bool:
        """Check if skill is enabled in agent config."""
        if not self.current_project:
            return False

        config_path = self.current_project / "agent_config.yaml"

        if not config_path.exists():
            return False

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Check main skills section - skills are enabled by default when present
            for skill in config.get("skills", []):
                if skill.get("skill_id") == skill_id:
                    return skill.get("enabled", True)  # Default to enabled for skills

        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in config file {config_path}: {e}")
        except PermissionError:
            logger.warning(f"Permission denied reading config file: {config_path}")
        except Exception as e:
            logger.debug(f"Could not read config file {config_path}: {e}")

        return False

    def _get_installed_skill_info(self, skill_id: str) -> dict[str, Any]:
        """Get info about an installed skill from agent config."""
        if not self.current_project:
            return {}

        config_path = self.current_project / "agent_config.yaml"
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            # Find skill in config
            for skill in config.get("skills", []):
                if skill.get("skill_id") == skill_id:
                    return skill

        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in config file {config_path}: {e}")
        except PermissionError:
            logger.warning(f"Permission denied reading config file: {config_path}")
        except Exception as e:
            logger.debug(f"Could not read config file {config_path}: {e}")

        return {}
