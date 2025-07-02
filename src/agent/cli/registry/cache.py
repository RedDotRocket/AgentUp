import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RegistryCache:
    """Manages caching for registry operations."""

    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".agentup" / "cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache metadata file
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load cache metadata: {e}")  # Expected for first run
        return {"version": 1, "entries": {}}

    def _save_metadata(self) -> None:
        """Save cache metadata."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")

    def get(self, key: str, max_age_seconds: int = 3600) -> Any | None:
        """Get item from cache if not expired."""
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            return None

        # Check metadata for expiry
        entry_metadata = self.metadata["entries"].get(key, {})
        if "timestamp" in entry_metadata:
            age = time.time() - entry_metadata["timestamp"]
            if age > max_age_seconds:
                self.delete(key)
                return None

        try:
            with open(cache_file) as f:
                return json.load(f)
        except Exception:
            self.delete(key)
            return None

    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        cache_file = self.cache_dir / f"{key}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump(value, f, indent=2)

            # Update metadata
            self.metadata["entries"][key] = {"timestamp": time.time(), "size": cache_file.stat().st_size}
            self._save_metadata()
        except Exception:
            pass

    def delete(self, key: str) -> None:
        """Delete item from cache."""
        cache_file = self.cache_dir / f"{key}.json"

        try:
            if cache_file.exists():
                cache_file.unlink()

            # Update metadata
            if key in self.metadata["entries"]:
                del self.metadata["entries"][key]
                self._save_metadata()
        except Exception:
            pass

    def clear(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file != self.metadata_file:
                try:
                    cache_file.unlink()
                except Exception:
                    pass

        self.metadata = {"version": 1, "entries": {}}
        self._save_metadata()

    def get_size(self) -> int:
        """Get total cache size in bytes."""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                total_size += cache_file.stat().st_size
            except Exception:
                pass
        return total_size

    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        """Remove expired cache entries. Returns number of entries removed."""
        removed = 0
        current_time = time.time()

        for key, metadata in list(self.metadata["entries"].items()):
            if "timestamp" in metadata:
                age = current_time - metadata["timestamp"]
                if age > max_age_seconds:
                    self.delete(key)
                    removed += 1

        return removed
