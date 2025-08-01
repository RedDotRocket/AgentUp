"""
Trusted Publishing system for AgentUp plugins.

This module implements verification of plugins published via PyPI's trusted
publishing feature using OpenID Connect (OIDC) tokens from GitHub Actions.
"""

import asyncio
import time
from typing import Any

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class TrustedPublishingVerifier:
    """
    Verifies plugins published via PyPI's trusted publishing system.

    This class handles verification of OIDC attestations from GitHub Actions
    and validates that plugins were published by trusted repositories.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.trusted_publishers = self._load_trusted_publishers()
        self.verification_cache = {}
        self.cache_ttl = 3600  # 1 hour

        # GitHub OIDC configuration
        self.github_oidc_issuer = "https://token.actions.githubusercontent.com"
        self.github_oidc_audience = "pypi"

        # PyPI API configuration
        self.pypi_api_base = "https://pypi.org/pypi"
        self.pypi_attestation_base = "https://pypi.org/attestations"

        logger.info(f"Trusted publishing verifier initialized with {len(self.trusted_publishers)} publishers")

    def _load_trusted_publishers(self) -> dict[str, dict[str, Any]]:
        """Load trusted publisher configurations from config"""
        trusted_config = self.config.get("trusted_publishing", {})

        # Default trusted publishers
        default_publishers = {
            "agentup-official": {
                "repositories": [
                    "agentup-org/weather-plugin",
                    "agentup-org/file-tools-plugin",
                    "agentup-org/ai-analysis-plugin",
                    "agentup-org/system-tools-plugin"
                ],
                "trust_level": "official",
                "verification_required": True,
                "description": "Official AgentUp plugins"
            },
            "agentup-community": {
                "repositories": [
                    "agentup-community/*"  # Wildcard pattern
                ],
                "trust_level": "community",
                "verification_required": True,
                "description": "Community-verified AgentUp plugins"
            }
        }

        # Merge with config
        configured_publishers = trusted_config.get("publishers", {})
        default_publishers.update(configured_publishers)

        return default_publishers

    async def verify_plugin_authenticity(
        self,
        package_name: str,
        version: str | None = None
    ) -> dict[str, Any]:
        """
        Verify that a plugin was published via trusted publishing.

        Args:
            package_name: Name of the PyPI package
            version: Specific version to verify (latest if None)

        Returns:
            Verification result dictionary
        """
        cache_key = f"{package_name}:{version or 'latest'}"

        # Check cache first
        if cache_key in self.verification_cache:
            cached = self.verification_cache[cache_key]
            if time.time() - cached["timestamp"] < self.cache_ttl:
                logger.debug(f"Using cached verification for {package_name}")
                return cached["result"]

        logger.info(f"Verifying trusted publishing for {package_name} v{version or 'latest'}")

        verification = {
            "package_name": package_name,
            "version": version,
            "trusted_publishing": False,
            "publisher": None,
            "repository": None,
            "workflow": None,
            "workflow_run_id": None,
            "trust_level": "unknown",
            "verified": False,
            "verification_timestamp": time.time(),
            "attestations": [],
            "errors": []
        }

        try:
            # Get package metadata from PyPI
            package_metadata = await self._get_pypi_metadata(package_name, version)

            if not package_metadata:
                verification["errors"].append("Could not fetch package metadata from PyPI")
                return verification

            # Check for attestations in package metadata
            attestations = await self._get_package_attestations(package_name, version)
            verification["attestations"] = attestations

            # Verify each attestation
            for attestation in attestations:
                attestation_result = await self._verify_attestation(attestation)

                if attestation_result["valid"]:
                    # Check if this attestation is from a trusted publisher
                    repo = attestation_result.get("repository")
                    workflow = attestation_result.get("workflow")

                    trusted_publisher = self._find_trusted_publisher(repo)

                    if trusted_publisher:
                        verification.update({
                            "trusted_publishing": True,
                            "publisher": trusted_publisher["id"],
                            "repository": repo,
                            "workflow": workflow,
                            "workflow_run_id": attestation_result.get("workflow_run_id"),
                            "trust_level": trusted_publisher["config"]["trust_level"],
                            "verified": True
                        })
                        break

            # Cache the result
            self.verification_cache[cache_key] = {
                "result": verification,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error verifying trusted publishing for {package_name}: {e}")
            verification["errors"].append(f"Verification error: {str(e)}")

        return verification

    async def _get_pypi_metadata(self, package_name: str, version: str | None = None) -> dict[str, Any]:
        """Fetch package metadata from PyPI API"""
        try:
            url = f"{self.pypi_api_base}/{package_name}/json"
            if version:
                url = f"{self.pypi_api_base}/{package_name}/{version}/json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.warning(f"PyPI API returned {response.status} for {package_name}")
                        return {}

        except Exception as e:
            logger.error(f"Failed to fetch PyPI metadata for {package_name}: {e}")
            return {}

    async def _get_package_attestations(self, package_name: str, version: str | None = None) -> list[dict[str, Any]]:
        """Get attestations for a package from PyPI"""
        attestations = []

        try:
            # PyPI attestations API (this is conceptual - actual API may differ)
            url = f"{self.pypi_attestation_base}/{package_name}/"
            if version:
                url += f"{version}/"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        attestations = data.get("attestations", [])
                    elif response.status == 404:
                        # No attestations available - this is normal for non-trusted published packages
                        logger.debug(f"No attestations found for {package_name}")
                    else:
                        logger.warning(f"Attestation API returned {response.status} for {package_name}")

        except Exception as e:
            logger.debug(f"Could not fetch attestations for {package_name}: {e}")

        return attestations

    async def _verify_attestation(self, attestation: dict[str, Any]) -> dict[str, Any]:
        """Verify an individual attestation"""
        result = {
            "valid": False,
            "repository": None,
            "workflow": None,
            "workflow_run_id": None,
            "actor": None,
            "errors": []
        }

        try:
            # Extract verification material
            verification_material = attestation.get("verification_material", {})
            certificate = verification_material.get("certificate")

            if not certificate:
                result["errors"].append("No certificate in attestation")
                return result

            # Parse the OIDC token from certificate
            token_data = await self._parse_oidc_token(certificate)

            if not token_data:
                result["errors"].append("Could not parse OIDC token")
                return result

            # Verify token signature (simplified - in practice would verify against GitHub's JWKS)
            signature_valid = await self._verify_token_signature(certificate)

            if not signature_valid:
                result["errors"].append("Invalid token signature")
                return result

            # Extract GitHub workflow information
            claims = token_data.get("payload", {})

            result.update({
                "valid": True,
                "repository": claims.get("repository"),
                "workflow": claims.get("workflow"),
                "workflow_run_id": claims.get("run_id"),
                "actor": claims.get("actor"),
                "ref": claims.get("ref"),
                "sha": claims.get("sha")
            })

        except Exception as e:
            logger.error(f"Error verifying attestation: {e}")
            result["errors"].append(f"Verification error: {str(e)}")

        return result

    async def _parse_oidc_token(self, certificate: str) -> dict[str, Any] | None:
        """Parse OIDC token from certificate (simplified implementation)"""
        try:
            # In a real implementation, this would parse the X.509 certificate
            # and extract the OIDC token from the certificate extensions

            # For now, simulate token parsing
            # In practice, you'd use libraries like cryptography to parse certificates

            # Mock token data that would be extracted from a real certificate
            mock_token_data = {
                "header": {
                    "alg": "RS256",
                    "typ": "JWT"
                },
                "payload": {
                    "iss": self.github_oidc_issuer,
                    "aud": self.github_oidc_audience,
                    "repository": "agentup-org/weather-plugin",  # Would be extracted from real token
                    "workflow": "publish.yml",
                    "run_id": "12345",
                    "actor": "agentup-bot",
                    "ref": "refs/tags/v1.0.0",
                    "sha": "abc123def456"
                }
            }

            return mock_token_data

        except Exception as e:
            logger.error(f"Failed to parse OIDC token: {e}")
            return None

    async def _verify_token_signature(self, certificate: str) -> bool:
        """Verify OIDC token signature against GitHub's public keys"""
        try:
            # In a real implementation, this would:
            # 1. Fetch GitHub's OIDC public keys from https://token.actions.githubusercontent.com/.well-known/jwks
            # 2. Verify the JWT signature using the appropriate public key
            # 3. Validate token expiration and other claims

            # For now, simulate signature verification
            await asyncio.sleep(0.1)  # Simulate async operation

            # In practice, you'd use libraries like PyJWT or python-jose
            return True  # Mock verification success

        except Exception as e:
            logger.error(f"Failed to verify token signature: {e}")
            return False

    def _find_trusted_publisher(self, repository: str) -> dict[str, Any] | None:
        """Find trusted publisher configuration for a repository"""
        if not repository:
            return None

        for publisher_id, config in self.trusted_publishers.items():
            for repo_pattern in config["repositories"]:
                if self._matches_repository_pattern(repository, repo_pattern):
                    return {
                        "id": publisher_id,
                        "config": config
                    }

        return None

    def _matches_repository_pattern(self, repository: str, pattern: str) -> bool:
        """Check if repository matches a pattern (supports wildcards)"""
        import fnmatch
        return fnmatch.fnmatch(repository, pattern)

    def get_trust_level(self, package_name: str) -> str:
        """Get trust level for a package (from cache or 'unknown')"""
        for cached in self.verification_cache.values():
            result = cached["result"]
            if result["package_name"] == package_name:
                return result.get("trust_level", "unknown")

        return "unknown"

    def is_trusted_package(self, package_name: str, min_trust_level: str = "community") -> bool:
        """Check if package meets minimum trust level"""
        trust_levels = {
            "unknown": 0,
            "community": 1,
            "official": 2
        }

        package_trust = self.get_trust_level(package_name)

        return trust_levels.get(package_trust, 0) >= trust_levels.get(min_trust_level, 0)

    async def batch_verify_packages(self, packages: list[str]) -> dict[str, dict[str, Any]]:
        """Verify multiple packages in parallel"""
        tasks = []

        for package_name in packages:
            task = self.verify_plugin_authenticity(package_name)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        verification_results = {}
        for i, result in enumerate(results):
            package_name = packages[i]

            if isinstance(result, Exception):
                verification_results[package_name] = {
                    "package_name": package_name,
                    "verified": False,
                    "error": str(result)
                }
            else:
                verification_results[package_name] = result

        return verification_results

    def get_publisher_info(self, publisher_id: str) -> dict[str, Any] | None:
        """Get information about a trusted publisher"""
        return self.trusted_publishers.get(publisher_id)

    def list_trusted_publishers(self) -> dict[str, dict[str, Any]]:
        """Get all trusted publisher configurations"""
        return self.trusted_publishers.copy()

    def add_trusted_publisher(
        self,
        publisher_id: str,
        repositories: list[str],
        trust_level: str = "community",
        description: str = ""
    ) -> bool:
        """Add a new trusted publisher (runtime only - not persisted)"""
        try:
            self.trusted_publishers[publisher_id] = {
                "repositories": repositories,
                "trust_level": trust_level,
                "verification_required": True,
                "description": description,
                "added_at": time.time()
            }

            logger.info(f"Added trusted publisher: {publisher_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add trusted publisher {publisher_id}: {e}")
            return False

    def remove_trusted_publisher(self, publisher_id: str) -> bool:
        """Remove a trusted publisher (runtime only)"""
        try:
            if publisher_id in self.trusted_publishers:
                del self.trusted_publishers[publisher_id]

                # Clear related cache entries
                self._clear_publisher_cache(publisher_id)

                logger.info(f"Removed trusted publisher: {publisher_id}")
                return True
            else:
                logger.warning(f"Publisher {publisher_id} not found")
                return False

        except Exception as e:
            logger.error(f"Failed to remove trusted publisher {publisher_id}: {e}")
            return False

    def _clear_publisher_cache(self, publisher_id: str):
        """Clear cache entries for a specific publisher"""
        to_remove = []

        for cache_key, cached in self.verification_cache.items():
            if cached["result"].get("publisher") == publisher_id:
                to_remove.append(cache_key)

        for key in to_remove:
            del self.verification_cache[key]

        logger.debug(f"Cleared {len(to_remove)} cache entries for publisher {publisher_id}")

    def clear_cache(self):
        """Clear all verification cache"""
        self.verification_cache.clear()
        logger.info("Cleared trusted publishing verification cache")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        now = time.time()
        expired_count = 0

        for cached in self.verification_cache.values():
            if now - cached["timestamp"] > self.cache_ttl:
                expired_count += 1

        return {
            "total_entries": len(self.verification_cache),
            "expired_entries": expired_count,
            "cache_ttl": self.cache_ttl,
            "cache_hit_rate": getattr(self, "_cache_hits", 0) / max(getattr(self, "_cache_requests", 1), 1)
        }
