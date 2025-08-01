import asyncio
import importlib.metadata
from typing import Any

import structlog

from .manager import PluginRegistry
from .models import PluginDefinition, PluginStatus
from .trusted_publishing import TrustedPublishingVerifier

logger = structlog.get_logger(__name__)


class TrustedPluginRegistry(PluginRegistry):
    """
    Enhanced plugin registry with trusted publishing verification.

    This registry verifies plugin authenticity using PyPI's trusted publishing
    system and provides enhanced security controls.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)

        # Initialize trusted publishing verifier
        self.trust_verifier = TrustedPublishingVerifier(self.config)

        # Trust verification results
        self.trust_results: dict[str, dict[str, Any]] = {}

        # Enhanced security settings
        self.trust_config = self.config.get("trusted_publishing", {})
        self.require_trusted_publishing = self.trust_config.get("require_trusted_publishing", False)
        self.minimum_trust_level = self.trust_config.get("minimum_trust_level", "community")
        self.auto_verify_plugins = self.trust_config.get("auto_verify_plugins", True)

        logger.info(f"Trusted plugin registry initialized (require_trusted: {self.require_trusted_publishing})")

    async def discover_plugins(self) -> None:
        """Discover and load plugins with trust verification"""
        logger.debug("Plugin discovery with trust verification started")

        # First, do standard plugin discovery
        super().discover_plugins()

        # Then verify trust for all discovered plugins
        if self.auto_verify_plugins:
            await self._verify_all_plugins()

        # Apply trust-based filtering
        await self._apply_trust_filters()

        logger.info(f"Trusted plugin discovery completed. {len(self.plugins)} plugins loaded, {len(self.trust_results)} verified")

    async def _verify_all_plugins(self):
        """Verify trust for all discovered plugins"""
        verification_tasks = []

        for plugin_id, plugin_def in self.plugin_definitions.items():
            # Skip filesystem plugins (they can't have trusted publishing)
            if plugin_def.metadata.get("source") == "filesystem":
                continue

            # Extract package name from entry point or metadata
            package_name = self._extract_package_name(plugin_def)

            if package_name:
                task = self._verify_plugin_trust(plugin_id, package_name)
                verification_tasks.append(task)

        if verification_tasks:
            logger.info(f"Verifying trust for {len(verification_tasks)} plugins...")
            await asyncio.gather(*verification_tasks, return_exceptions=True)

    async def _verify_plugin_trust(self, plugin_id: str, package_name: str):
        """Verify trust for a single plugin"""
        try:
            logger.debug(f"Verifying trust for plugin {plugin_id} (package: {package_name})")

            verification_result = await self.trust_verifier.verify_plugin_authenticity(package_name)

            # Store verification result
            self.trust_results[plugin_id] = verification_result

            # Update plugin definition with trust information
            if plugin_id in self.plugin_definitions:
                plugin_def = self.plugin_definitions[plugin_id]
                plugin_def.metadata.update({
                    "trusted_publishing": verification_result["trusted_publishing"],
                    "trust_level": verification_result["trust_level"],
                    "publisher": verification_result.get("publisher"),
                    "repository": verification_result.get("repository")
                })

            if verification_result["trusted_publishing"]:
                logger.info(f"✅ Plugin {plugin_id} verified via trusted publishing (level: {verification_result['trust_level']})")
            else:
                logger.warning(f"⚠️  Plugin {plugin_id} not published via trusted publishing")

        except Exception as e:
            logger.error(f"Failed to verify trust for plugin {plugin_id}: {e}")
            self.trust_results[plugin_id] = {
                "package_name": package_name,
                "verified": False,
                "error": str(e),
                "trust_level": "unknown"
            }

    async def _apply_trust_filters(self):
        """Apply trust-based filtering to loaded plugins"""
        plugins_to_remove = []

        for plugin_id in list(self.plugins.keys()):
            trust_result = self.trust_results.get(plugin_id, {})
            trust_level = trust_result.get("trust_level", "unknown")

            # Check if plugin meets minimum trust requirements
            if self.require_trusted_publishing and not trust_result.get("trusted_publishing", False):
                logger.warning(f"Removing plugin {plugin_id} - trusted publishing required but not verified")
                plugins_to_remove.append(plugin_id)
                continue

            # Check minimum trust level
            if not self._meets_minimum_trust_level(trust_level):
                logger.warning(f"Removing plugin {plugin_id} - trust level '{trust_level}' below minimum '{self.minimum_trust_level}'")
                plugins_to_remove.append(plugin_id)
                continue

        # Remove plugins that don't meet trust requirements
        for plugin_id in plugins_to_remove:
            self._remove_plugin(plugin_id, "Trust verification failed")

        if plugins_to_remove:
            logger.info(f"Removed {len(plugins_to_remove)} plugins due to trust requirements")

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

    def _remove_plugin(self, plugin_id: str, reason: str):
        """Remove a plugin and all its capabilities"""
        try:
            # Remove from plugins dict
            if plugin_id in self.plugins:
                del self.plugins[plugin_id]

            # Remove capabilities
            capabilities_to_remove = [
                cap_id for cap_id, plugin in self.capability_to_plugin.items()
                if plugin == plugin_id
            ]

            for cap_id in capabilities_to_remove:
                if cap_id in self.capabilities:
                    del self.capabilities[cap_id]
                if cap_id in self.capability_to_plugin:
                    del self.capability_to_plugin[cap_id]

            # Update plugin definition status
            if plugin_id in self.plugin_definitions:
                self.plugin_definitions[plugin_id].status = PluginStatus.ERROR
                self.plugin_definitions[plugin_id].error = reason

            logger.debug(f"Removed plugin {plugin_id}: {reason}")

        except Exception as e:
            logger.error(f"Error removing plugin {plugin_id}: {e}")

    def _extract_package_name(self, plugin_def: PluginDefinition) -> str | None:
        """Extract PyPI package name from plugin definition"""
        try:
            # Try to find the package by module name
            if plugin_def.module_name:
                # Common patterns for package names
                possible_names = [
                    plugin_def.module_name.split('.')[0],  # First part of module
                    f"agentup-{plugin_def.name}-plugin",   # Standard naming
                    f"agentup-{plugin_def.name}",          # Alternative naming
                    plugin_def.name                        # Direct name
                ]

                # Try to verify which package name exists
                for name in possible_names:
                    try:
                        # Check if this package exists in installed packages
                        importlib.metadata.distribution(name)
                        return name
                    except importlib.metadata.PackageNotFoundError:
                        continue

            # Fallback: try standard naming patterns
            return f"agentup-{plugin_def.name}-plugin"

        except Exception as e:
            logger.debug(f"Could not extract package name for {plugin_def.name}: {e}")
            return None

    # === Enhanced Plugin Information Methods ===

    def get_plugin_trust_info(self, plugin_id: str) -> dict[str, Any]:
        """Get trust information for a plugin"""
        trust_result = self.trust_results.get(plugin_id, {})
        plugin_def = self.plugin_definitions.get(plugin_id)

        info = {
            "plugin_id": plugin_id,
            "trusted_publishing": trust_result.get("trusted_publishing", False),
            "trust_level": trust_result.get("trust_level", "unknown"),
            "publisher": trust_result.get("publisher"),
            "repository": trust_result.get("repository"),
            "verification_errors": trust_result.get("errors", []),
            "package_name": trust_result.get("package_name"),
            "verified_at": trust_result.get("verification_timestamp")
        }

        if plugin_def:
            info.update({
                "plugin_name": plugin_def.name,
                "version": plugin_def.version,
                "status": plugin_def.status.value
            })

        return info

    def list_plugins_by_trust_level(self, trust_level: str) -> list[str]:
        """Get list of plugins with specific trust level"""
        matching_plugins = []

        for plugin_id, trust_result in self.trust_results.items():
            if trust_result.get("trust_level") == trust_level:
                matching_plugins.append(plugin_id)

        return matching_plugins

    def get_trust_summary(self) -> dict[str, Any]:
        """Get summary of trust verification results"""
        summary = {
            "total_plugins": len(self.plugin_definitions),
            "verified_plugins": len(self.trust_results),
            "trusted_published": 0,
            "trust_levels": {
                "official": 0,
                "community": 0,
                "unknown": 0
            },
            "publishers": {},
            "verification_errors": 0
        }

        for trust_result in self.trust_results.values():
            if trust_result.get("trusted_publishing"):
                summary["trusted_published"] += 1

            trust_level = trust_result.get("trust_level", "unknown")
            if trust_level in summary["trust_levels"]:
                summary["trust_levels"][trust_level] += 1

            publisher = trust_result.get("publisher")
            if publisher:
                summary["publishers"][publisher] = summary["publishers"].get(publisher, 0) + 1

            if trust_result.get("errors"):
                summary["verification_errors"] += 1

        return summary

    # === Publisher Management ===

    def get_trusted_publishers(self) -> dict[str, dict[str, Any]]:
        """Get all trusted publisher configurations"""
        return self.trust_verifier.list_trusted_publishers()

    def add_trusted_publisher(
        self,
        publisher_id: str,
        repositories: list[str],
        trust_level: str = "community",
        description: str = ""
    ) -> bool:
        """Add a new trusted publisher"""
        success = self.trust_verifier.add_trusted_publisher(
            publisher_id, repositories, trust_level, description
        )

        if success:
            logger.info(f"Added trusted publisher {publisher_id} with {len(repositories)} repositories")

        return success

    def remove_trusted_publisher(self, publisher_id: str) -> bool:
        """Remove a trusted publisher"""
        success = self.trust_verifier.remove_trusted_publisher(publisher_id)

        if success:
            # Re-verify plugins that were published by this publisher
            affected_plugins = [
                plugin_id for plugin_id, trust_result in self.trust_results.items()
                if trust_result.get("publisher") == publisher_id
            ]

            if affected_plugins:
                logger.warning(f"Publisher {publisher_id} removed - {len(affected_plugins)} plugins affected")

                # Mark affected plugins for re-verification
                for plugin_id in affected_plugins:
                    if plugin_id in self.trust_results:
                        self.trust_results[plugin_id]["trust_level"] = "unknown"
                        self.trust_results[plugin_id]["verified"] = False

        return success

    # === Plugin Installation and Verification ===

    async def verify_plugin_before_installation(self, package_name: str) -> dict[str, Any]:
        """Verify a plugin before installation"""
        logger.info(f"Pre-installation verification for {package_name}")

        verification = await self.trust_verifier.verify_plugin_authenticity(package_name)

        result = {
            "package_name": package_name,
            "safe_to_install": False,
            "verification": verification,
            "recommendations": []
        }

        # Determine if it's safe to install
        if verification["trusted_publishing"]:
            trust_level = verification["trust_level"]

            if self._meets_minimum_trust_level(trust_level):
                result["safe_to_install"] = True
                result["recommendations"].append(f"✅ Verified via trusted publishing (level: {trust_level})")
            else:
                result["recommendations"].append(f"⚠️  Trust level '{trust_level}' below minimum '{self.minimum_trust_level}'")
        else:
            if self.require_trusted_publishing:
                result["recommendations"].append("❌ Trusted publishing required but not verified")
            else:
                result["recommendations"].append("⚠️  Not published via trusted publishing - proceed with caution")
                result["safe_to_install"] = True  # Allow if not strictly required

        # Add additional recommendations
        if verification.get("errors"):
            result["recommendations"].append("⚠️  Verification errors occurred - check logs")

        return result

    async def refresh_plugin_trust_verification(self, plugin_id: str | None = None) -> dict[str, Any]:
        """Refresh trust verification for plugins"""
        if plugin_id:
            # Refresh specific plugin
            if plugin_id not in self.plugin_definitions:
                return {"error": f"Plugin {plugin_id} not found"}

            package_name = self._extract_package_name(self.plugin_definitions[plugin_id])
            if package_name:
                await self._verify_plugin_trust(plugin_id, package_name)
                return {"refreshed": [plugin_id]}
            else:
                return {"error": f"Could not determine package name for {plugin_id}"}
        else:
            # Refresh all plugins
            self.trust_verifier.clear_cache()
            await self._verify_all_plugins()
            return {"refreshed": list(self.trust_results.keys())}

    # === Health and Monitoring ===

    async def get_health_status(self) -> dict:
        """Get health status including trust verification"""
        base_health = await super().get_health_status()

        trust_summary = self.get_trust_summary()
        cache_stats = self.trust_verifier.get_cache_stats()

        base_health.update({
            "trusted_publishing": {
                "enabled": True,
                "require_trusted_publishing": self.require_trusted_publishing,
                "minimum_trust_level": self.minimum_trust_level,
                "trust_summary": trust_summary,
                "cache_stats": cache_stats
            }
        })

        return base_health


# Global trusted plugin registry instance
_trusted_plugin_registry: TrustedPluginRegistry | None = None


def get_trusted_plugin_registry() -> TrustedPluginRegistry:
    """Get the global trusted plugin registry instance"""
    global _trusted_plugin_registry
    if _trusted_plugin_registry is None:
        # Try to load configuration
        config = None
        try:
            from agent.config import Config
            config = Config.model_dump()
        except ImportError:
            logger.debug("Could not load configuration for trusted plugin registry")

        _trusted_plugin_registry = TrustedPluginRegistry(config)
        # Note: discover_plugins() should be called asynchronously by the application

    return _trusted_plugin_registry
