"""
Plugin installer with trusted publishing verification.

This module provides secure plugin installation with trust verification,
interactive prompts, and comprehensive safety checks.
"""

import asyncio
import sys
from typing import Any

import structlog

from .trusted_publishing import TrustedPublishingVerifier

logger = structlog.get_logger(__name__)


class SecurePluginInstaller:
    """
    Secure plugin installer with trusted publishing verification.

    This installer verifies plugin authenticity before installation and
    provides interactive safety prompts for untrusted packages.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.trust_verifier = TrustedPublishingVerifier(config)

        # Installation settings
        self.install_config = config.get("plugin_installation", {})
        self.require_trusted_publishing = self.install_config.get("require_trusted_publishing", False)
        self.minimum_trust_level = self.install_config.get("minimum_trust_level", "community")
        self.interactive_prompts = self.install_config.get("interactive_prompts", True)
        self.auto_approve_official = self.install_config.get("auto_approve_official", True)

        # Package manager settings
        self.package_manager = self.install_config.get("package_manager", "uv")  # uv, pip
        self.install_timeout = self.install_config.get("install_timeout", 300)  # 5 minutes

        logger.info(f"Plugin installer initialized (package_manager: {self.package_manager})")

    async def install_plugin(
        self,
        package_name: str,
        version: str | None = None,
        force: bool = False,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Install a plugin with security verification.

        Args:
            package_name: Name of the PyPI package
            version: Specific version to install (latest if None)
            force: Skip safety prompts and install anyway
            dry_run: Only verify, don't actually install

        Returns:
            Installation result dictionary
        """
        result = {
            "package_name": package_name,
            "version": version,
            "success": False,
            "installed": False,
            "verification": {},
            "messages": [],
            "warnings": [],
            "errors": []
        }

        try:
            logger.info(f"Installing plugin: {package_name}" + (f" v{version}" if version else ""))

            # Step 1: Pre-installation verification
            result["messages"].append("🔍 Verifying plugin authenticity...")
            verification = await self.trust_verifier.verify_plugin_authenticity(package_name, version)
            result["verification"] = verification

            # Step 2: Evaluate installation safety
            safety_result = self._evaluate_installation_safety(verification)
            result.update(safety_result)

            if not safety_result["safe_to_install"] and not force:
                result["errors"].append("Installation blocked due to safety concerns")
                return result

            # Step 3: Interactive safety prompt (if enabled)
            if self.interactive_prompts and not force and not dry_run:
                user_approved = await self._prompt_user_approval(package_name, verification, safety_result)
                if not user_approved:
                    result["messages"].append("❌ Installation cancelled by user")
                    return result

            # Step 4: Dry run check
            if dry_run:
                result["messages"].append("✅ Dry run completed - plugin would be installed")
                result["success"] = True
                return result

            # Step 5: Actual installation
            result["messages"].append("📦 Installing package...")
            install_result = await self._install_package(package_name, version)

            if install_result["success"]:
                result["installed"] = True
                result["success"] = True
                result["messages"].append(f"✅ Plugin {package_name} installed successfully")

                # Step 6: Post-installation verification
                await self._post_installation_checks(package_name, result)

            else:
                result["errors"].extend(install_result["errors"])
                result["messages"].append(f"❌ Installation failed: {install_result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Error installing plugin {package_name}: {e}", exc_info=True)
            result["errors"].append(f"Installation error: {str(e)}")

        return result

    def _evaluate_installation_safety(self, verification: dict[str, Any]) -> dict[str, Any]:
        """Evaluate whether it's safe to install a plugin"""
        safety = {
            "safe_to_install": False,
            "trust_score": 0.0,
            "safety_messages": [],
            "risk_factors": []
        }

        # Check trusted publishing
        if verification["trusted_publishing"]:
            trust_level = verification["trust_level"]

            if trust_level == "official":
                safety["trust_score"] = 1.0
                safety["safety_messages"].append("✅ Official AgentUp plugin")
            elif trust_level == "community":
                safety["trust_score"] = 0.7
                safety["safety_messages"].append("✅ Community-verified plugin")
            else:
                safety["trust_score"] = 0.3
                safety["safety_messages"].append("⚠️  Unrecognized trust level")

            # Check publisher reputation
            publisher = verification.get("publisher")
            if publisher == "agentup-official":
                safety["trust_score"] = min(1.0, safety["trust_score"] + 0.2)
                safety["safety_messages"].append("✅ Published by official AgentUp team")

        else:
            safety["risk_factors"].append("Not published via trusted publishing")
            safety["safety_messages"].append("⚠️  Standard PyPI upload (not trusted publishing)")

        # Check for verification errors
        if verification.get("errors"):
            safety["risk_factors"].append("Verification errors occurred")
            safety["trust_score"] = max(0.0, safety["trust_score"] - 0.3)

        # Apply policy checks
        if self.require_trusted_publishing and not verification["trusted_publishing"]:
            safety["safety_messages"].append("❌ Trusted publishing required by policy")
        elif not self._meets_minimum_trust_level(verification.get("trust_level", "unknown")):
            safety["safety_messages"].append(f"❌ Trust level below minimum requirement ({self.minimum_trust_level})")
        else:
            safety["safe_to_install"] = True

        return safety

    def _meets_minimum_trust_level(self, trust_level: str) -> bool:
        """Check if trust level meets minimum requirement"""
        trust_levels = {
            "unknown": 0,
            "community": 1,
            "official": 2
        }

        current_level = trust_levels.get(trust_level, 0)
        minimum_level = trust_levels.get(self.minimum_trust_level, 0)

        return current_level >= minimum_level

    async def _prompt_user_approval(
        self,
        package_name: str,
        verification: dict[str, Any],
        safety_result: dict[str, Any]
    ) -> bool:
        """Prompt user for installation approval"""
        print("\n" + "="*60)
        print(f"🔒 Security Review: {package_name}")
        print("="*60)

        # Display trust information
        if verification["trusted_publishing"]:
            print("✅ Trusted Publishing: Yes")
            print(f"   Publisher: {verification.get('publisher', 'Unknown')}")
            print(f"   Repository: {verification.get('repository', 'Unknown')}")
            print(f"   Trust Level: {verification.get('trust_level', 'Unknown')}")
        else:
            print("⚠️  Trusted Publishing: No")
            print("   This plugin was uploaded using traditional PyPI methods")

        # Display safety messages
        print(f"\n📊 Trust Score: {safety_result['trust_score']:.1f}/1.0")

        if safety_result["safety_messages"]:
            print("\n💬 Safety Assessment:")
            for message in safety_result["safety_messages"]:
                print(f"   {message}")

        if safety_result["risk_factors"]:
            print("\n⚠️  Risk Factors:")
            for risk in safety_result["risk_factors"]:
                print(f"   • {risk}")

        # Auto-approve official plugins if configured
        if (self.auto_approve_official and
            verification.get("trust_level") == "official" and
            verification.get("publisher") == "agentup-official"):
            print("\n✅ Auto-approved (official plugin)")
            return True

        # Prompt user
        print("\n🤔 Do you want to install this plugin? (y/N): ", end="")

        try:
            # Run input in executor to avoid blocking async loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, input)

            return response.lower().strip() in ['y', 'yes']

        except Exception as e:
            logger.warning(f"Error reading user input: {e}")
            return False

    async def _install_package(self, package_name: str, version: str | None = None) -> dict[str, Any]:
        """Install package using configured package manager"""
        result = {
            "success": False,
            "errors": [],
            "stdout": "",
            "stderr": ""
        }

        try:
            # Build install command
            if self.package_manager == "uv":
                cmd = ["uv", "add"]
                if version:
                    cmd.append(f"{package_name}=={version}")
                else:
                    cmd.append(package_name)
            else:  # pip
                cmd = [sys.executable, "-m", "pip", "install"]
                if version:
                    cmd.append(f"{package_name}=={version}")
                else:
                    cmd.append(package_name)

            logger.debug(f"Running install command: {' '.join(cmd)}")

            # Run installation with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.install_timeout
            )

            result["stdout"] = stdout.decode()
            result["stderr"] = stderr.decode()

            if process.returncode == 0:
                result["success"] = True
            else:
                result["errors"].append(f"Package manager returned code {process.returncode}")
                if result["stderr"]:
                    result["errors"].append(f"Error output: {result['stderr']}")

        except asyncio.TimeoutError:
            result["errors"].append(f"Installation timed out after {self.install_timeout} seconds")
        except Exception as e:
            result["errors"].append(f"Installation failed: {str(e)}")

        return result

    async def _post_installation_checks(self, package_name: str, result: dict[str, Any]):
        """Perform post-installation verification"""
        try:
            # Check if package is importable
            import importlib

            # Try to import the package
            try:
                module = importlib.import_module(package_name.replace("-", "_"))
                result["messages"].append("✅ Package import successful")
            except ImportError as e:
                result["warnings"].append(f"⚠️  Package import failed: {e}")

            # Try to discover plugin entry points
            try:
                import importlib.metadata

                entry_points = importlib.metadata.entry_points()
                if hasattr(entry_points, "select"):
                    plugin_entries = entry_points.select(group="agentup.plugins")
                else:
                    plugin_entries = entry_points.get("agentup.plugins", [])

                plugin_count = len(list(plugin_entries))
                if plugin_count > 0:
                    result["messages"].append(f"✅ Discovered {plugin_count} plugin entry points")
                else:
                    result["warnings"].append("⚠️  No plugin entry points found")

            except Exception as e:
                result["warnings"].append(f"⚠️  Entry point discovery failed: {e}")

        except Exception as e:
            result["warnings"].append(f"⚠️  Post-installation checks failed: {e}")

    async def uninstall_plugin(self, package_name: str, force: bool = False) -> dict[str, Any]:
        """Uninstall a plugin package"""
        result = {
            "package_name": package_name,
            "success": False,
            "messages": [],
            "errors": []
        }

        try:
            logger.info(f"Uninstalling plugin: {package_name}")

            # Interactive confirmation
            if self.interactive_prompts and not force:
                print(f"\n⚠️  Are you sure you want to uninstall '{package_name}'? (y/N): ", end="")
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, input)

                if response.lower().strip() not in ['y', 'yes']:
                    result["messages"].append("❌ Uninstallation cancelled by user")
                    return result

            # Build uninstall command
            if self.package_manager == "uv":
                cmd = ["uv", "remove", package_name]
            else:  # pip
                cmd = [sys.executable, "-m", "pip", "uninstall", "-y", package_name]

            logger.debug(f"Running uninstall command: {' '.join(cmd)}")

            # Run uninstallation
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                result["success"] = True
                result["messages"].append(f"✅ Plugin {package_name} uninstalled successfully")
            else:
                result["errors"].append(f"Uninstall failed with code {process.returncode}")
                if stderr:
                    result["errors"].append(f"Error: {stderr.decode()}")

        except Exception as e:
            logger.error(f"Error uninstalling plugin {package_name}: {e}")
            result["errors"].append(f"Uninstall error: {str(e)}")

        return result

    async def list_installed_plugins(self) -> list[dict[str, Any]]:
        """List all installed AgentUp plugins"""
        plugins = []

        try:
            import importlib.metadata

            # Get all installed packages
            for dist in importlib.metadata.distributions():
                package_name = dist.metadata["Name"]

                # Check if this looks like an AgentUp plugin
                if self._is_agentup_plugin(dist):
                    plugin_info = {
                        "package_name": package_name,
                        "version": dist.version,
                        "summary": dist.metadata.get("Summary", ""),
                        "author": dist.metadata.get("Author", ""),
                        "has_entry_points": False,
                        "entry_points": []
                    }

                    # Check for AgentUp entry points
                    try:
                        entry_points = dist.entry_points
                        if hasattr(entry_points, "select"):
                            agentup_entries = entry_points.select(group="agentup.plugins")
                        else:
                            agentup_entries = [ep for ep in entry_points if ep.group == "agentup.plugins"]

                        plugin_info["entry_points"] = [ep.name for ep in agentup_entries]
                        plugin_info["has_entry_points"] = len(plugin_info["entry_points"]) > 0

                    except Exception as e:
                        logger.debug(f"Error checking entry points for {package_name}: {e}")

                    plugins.append(plugin_info)

        except Exception as e:
            logger.error(f"Error listing installed plugins: {e}")

        return plugins

    def _is_agentup_plugin(self, dist) -> bool:
        """Check if a distribution is an AgentUp plugin"""
        package_name = dist.metadata["Name"].lower()

        # Check naming patterns
        if "agentup" in package_name:
            return True

        # Check for AgentUp entry points
        try:
            entry_points = dist.entry_points
            if hasattr(entry_points, "select"):
                agentup_entries = list(entry_points.select(group="agentup.plugins"))
            else:
                agentup_entries = [ep for ep in entry_points if ep.group == "agentup.plugins"]

            return len(agentup_entries) > 0

        except Exception:
            return False

    async def upgrade_plugin(self, package_name: str, force: bool = False) -> dict[str, Any]:
        """Upgrade a plugin to the latest version"""
        result = {
            "package_name": package_name,
            "success": False,
            "messages": [],
            "errors": []
        }

        try:
            logger.info(f"Upgrading plugin: {package_name}")

            # Build upgrade command
            if self.package_manager == "uv":
                cmd = ["uv", "add", "--upgrade", package_name]
            else:  # pip
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", package_name]

            # Run upgrade
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                result["success"] = True
                result["messages"].append(f"✅ Plugin {package_name} upgraded successfully")
            else:
                result["errors"].append(f"Upgrade failed with code {process.returncode}")
                if stderr:
                    result["errors"].append(f"Error: {stderr.decode()}")

        except Exception as e:
            logger.error(f"Error upgrading plugin {package_name}: {e}")
            result["errors"].append(f"Upgrade error: {str(e)}")

        return result

    async def search_plugins(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Search for AgentUp plugins on PyPI"""
        results = []

        try:
            # Use PyPI search API (simplified implementation)
            import aiohttp

            search_url = "https://pypi.org/search/"
            params = {
                "q": f"agentup {query}",
                "o": "relevance"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params) as response:
                    if response.status == 200:
                        # In a real implementation, you'd parse the HTML response
                        # or use a proper PyPI API when available

                        # For now, return mock results
                        mock_results = [
                            {
                                "name": f"agentup-{query}-plugin",
                                "version": "1.0.0",
                                "summary": f"AgentUp plugin for {query}",
                                "author": "AgentUp Community"
                            }
                        ]

                        results.extend(mock_results[:max_results])

        except Exception as e:
            logger.error(f"Error searching plugins: {e}")

        return results
