import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml


class RegistryClient:
    """Client for interacting with the AgentUp Skills Registry."""

    def __init__(self, base_url: str = None):
        # Default to production API, but allow override via config or parameter
        if base_url is None:
            base_url = self._get_registry_url()

        self.base_url = base_url
        self.cache_dir = Path.home() / ".agentup" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # HTTP client settings
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.headers = {"User-Agent": "AgentUp-CLI/0.1.0", "Accept": "application/json"}

    def _get_registry_url(self) -> str:
        """Get registry URL from config or environment, with fallback to default."""
        # 1. Check environment variable first
        env_url = os.getenv("AGENTUP_REGISTRY_URL")
        if env_url:
            return env_url

        # 2. Check agent_config.yaml for registry URL override
        try:
            config_path = Path("agent_config.yaml")
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                registry_config = config.get("registry", {})
                if registry_config.get("url"):
                    return registry_config["url"]
        except Exception:
            # If config loading fails, use default
            pass

        # 3. Production default
        return "https://api.agentai.dev/api/v1"

    async def search_skills(
        self,
        query: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        author: str | None = None,
        sort: str = "relevance",
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search for skills in the registry."""
        params = {"sort": sort, "page": page, "limit": limit}

        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if tag:
            params["tag"] = tag
        if author:
            params["author"] = author

        # Check cache first
        cache_key = self._generate_cache_key("search", params)
        cached_data = self._get_cached_data(cache_key, max_age_minutes=60)
        if cached_data:
            return cached_data

        # Make API request
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/skills", params=params)
            response.raise_for_status()
            data = response.json()

            # Cache the results
            self._cache_data(cache_key, data)
            return data

    async def get_skill_details(self, skill_id: str) -> dict[str, Any]:
        """Get detailed information about a skill."""
        # Check cache first
        cache_key = f"skill_{skill_id}"
        cached_data = self._get_cached_data(cache_key, max_age_minutes=120)
        if cached_data:
            return cached_data

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/skills/{skill_id}")
            response.raise_for_status()
            data = response.json()

            # Cache the result
            self._cache_data(cache_key, data)
            return data

    async def download_skill_package(
        self,
        skill_id: str,
        destination: Path,
        version: str = "latest",
        progress_callback: Optional[callable] = None,  # noqa: UP007
    ) -> Path:
        """Download a skill package with progress tracking."""
        download_url = f"{self.base_url}/packages/{skill_id}"
        if version != "latest":
            download_url += f"/{version}"

        package_filename = f"{skill_id}-{version}.tar.gz"
        package_path = destination / package_filename

        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()

                # Get total size from headers
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(package_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback and total_size > 0:
                            progress = downloaded / total_size
                            progress_callback(progress, downloaded, total_size)

            return package_path

    async def get_categories(self) -> list[dict[str, Any]]:
        """Get all available skill categories."""
        # Check cache first (cache for 24 hours)
        cache_key = "categories"
        cached_data = self._get_cached_data(cache_key, max_age_minutes=1440)
        if cached_data:
            return cached_data["categories"]

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/categories")
            response.raise_for_status()
            data = response.json()

            # Cache the result
            self._cache_data(cache_key, data)
            return data["categories"]

    async def get_skill_versions(self, skill_id: str) -> list[dict[str, Any]]:
        """Get all available versions for a skill."""
        # Use skill details endpoint which includes versions
        skill_details = await self.get_skill_details(skill_id)
        return skill_details.get("versions", [])

    async def check_for_updates(self, installed_skills: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Check for updates for installed skills."""
        updates = []

        for skill in installed_skills:
            try:
                skill_details = await self.get_skill_details(skill["skill_id"])
                latest_version = skill_details["latest_version"]["version"]

                if skill["version"] != latest_version:
                    updates.append(
                        {
                            "skill_id": skill["skill_id"],
                            "name": skill["name"],
                            "current_version": skill["version"],
                            "latest_version": latest_version,
                            "has_update": True,
                        }
                    )
            except Exception:
                # Skip skills that can't be checked
                continue

        return updates

    # Cache helper methods
    def _generate_cache_key(self, operation: str, params: dict[str, Any]) -> str:
        """Generate a cache key from operation and parameters."""
        # Sort params for consistent keys
        sorted_params = sorted(params.items())
        params_str = "_".join(f"{k}={v}" for k, v in sorted_params)
        return f"{operation}_{params_str}".replace(" ", "_").replace("/", "_")

    def _get_cached_data(self, cache_key: str, max_age_minutes: int = 60) -> dict[str, Any] | None:
        """Get data from cache if it exists and is not expired."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            # Check age
            file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_age > timedelta(minutes=max_age_minutes):
                return None

            # Load and return cached data
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            # If cache read fails, return None
            return None

    def _cache_data(self, cache_key: str, data: dict[str, Any]) -> None:
        """Save data to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # If caching fails, continue without caching
            pass

    def clear_cache(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception:
                pass
