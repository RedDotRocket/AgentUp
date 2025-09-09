"""
MCP package installation service for handling different package types.

This module provides functionality to install MCP server packages from various
registries including npm, PyPI, and Docker.
"""

from __future__ import annotations

import asyncio
import shutil

from .mcp_registry import RegistryPackage


class MCPPackageInstaller:
    """Handles installation of MCP server packages."""

    def __init__(self):
        self.installation_cache: dict[str, bool] = {}

    async def install_package(self, package: RegistryPackage, dry_run: bool = False) -> tuple[str, list[str]]:
        """Install package and return command configuration."""

        if package.registry_type == "npm":
            return await self._handle_npm_package(package, dry_run)
        elif package.registry_type == "pypi":
            return await self._handle_pypi_package(package, dry_run)
        elif package.registry_type == "docker":
            return await self._handle_docker_package(package, dry_run)
        else:
            raise MCPPackageError(f"Unsupported package type: {package.registry_type}")

    async def _handle_npm_package(self, package: RegistryPackage, dry_run: bool = False) -> tuple[str, list[str]]:
        """Handle npm package installation."""
        # For npm packages, we use npx which handles installation automatically
        command = "npx"
        args = ["-y", f"{package.identifier}@{package.version}"]

        # Add package arguments if any
        for arg in package.package_arguments:
            if arg.get("is_required") and "default" in arg:
                args.extend([f"--{arg.get('name')}", str(arg.get("default"))])

        # Verify npx is available (skip during dry-run)
        if not dry_run and not await self._check_command_available("npx"):
            raise MCPPackageError("npx is not available. Please install Node.js and npm.")

        return command, args

    async def _handle_pypi_package(self, package: RegistryPackage, dry_run: bool = False) -> tuple[str, list[str]]:
        """Handle PyPI package installation."""
        # For Python packages, we use uvx which handles installation automatically
        command = "uvx"
        args = [f"{package.identifier}=={package.version}"]

        # Add package arguments if any
        for arg in package.package_arguments:
            if arg.get("is_required") and "default" in arg:
                args.extend([f"--{arg.get('name')}", str(arg.get("default"))])

        # Verify uvx is available (skip during dry-run)
        if not dry_run and not await self._check_command_available("uvx"):
            raise MCPPackageError("uvx is not available. Please install uv.")

        return command, args

    async def _handle_docker_package(self, package: RegistryPackage, dry_run: bool = False) -> tuple[str, list[str]]:
        """Handle Docker package installation."""
        # For Docker packages, we use docker run
        command = "docker"
        args = ["run", "--rm", "-i", f"{package.identifier}:{package.version}"]

        # Add package arguments if any
        for arg in package.package_arguments:
            if arg.get("is_required") and "default" in arg:
                args.extend([f"--{arg.get('name')}", str(arg.get("default"))])

        # Verify docker is available (skip during dry-run)
        if not dry_run and not await self._check_command_available("docker"):
            raise MCPPackageError("docker is not available. Please install Docker.")

        # Pre-pull the image to avoid startup delays (skip during dry-run)
        if not dry_run:
            await self._pull_docker_image(f"{package.identifier}:{package.version}")

        return command, args

    async def _check_command_available(self, command: str) -> bool:
        """Check if a command is available in the system PATH."""
        try:
            # Use shutil.which for more reliable command detection
            return shutil.which(command) is not None
        except (FileNotFoundError, OSError):
            return False

    async def _pull_docker_image(self, image: str) -> None:
        """Pre-pull a Docker image."""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "pull", image, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise MCPPackageError(f"Failed to pull Docker image {image}: {error_msg}")

        except (FileNotFoundError, OSError) as e:
            raise MCPPackageError(f"Docker command failed: {e}") from e

    def validate_package(self, package: RegistryPackage) -> bool:
        """Validate package configuration."""
        if not package.identifier:
            return False

        if not package.version:
            return False

        if package.registry_type not in ("npm", "pypi", "docker"):
            return False

        return True


class MCPPackageError(Exception):
    """Exception raised for package installation errors."""

    pass
