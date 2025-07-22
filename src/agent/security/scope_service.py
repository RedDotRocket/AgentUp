from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ScopeCheckResult:
    """Result of a scope validation check."""

    has_access: bool
    expanded_scopes: frozenset[str] = field(default_factory=frozenset)
    missing_scopes: list[str] = field(default_factory=list)
    cache_hit: bool = False


class ScopeCache:
    """Request-scoped cache for expanded user scopes."""

    def __init__(self):
        self._expanded_scopes_cache: dict[frozenset[str], frozenset[str]] = {}
        self._validation_cache: dict[tuple[frozenset[str], str], bool] = {}

    def get_expanded_scopes(self, user_scopes: frozenset[str]) -> frozenset[str] | None:
        """Get cached expanded scopes for user."""
        return self._expanded_scopes_cache.get(user_scopes)

    def set_expanded_scopes(self, user_scopes: frozenset[str], expanded: frozenset[str]) -> None:
        """Cache expanded scopes for user."""
        self._expanded_scopes_cache[user_scopes] = expanded

    def get_validation_result(self, expanded_scopes: frozenset[str], required_scope: str) -> bool | None:
        """Get cached validation result."""
        cache_key = (expanded_scopes, required_scope)
        return self._validation_cache.get(cache_key)

    def set_validation_result(self, expanded_scopes: frozenset[str], required_scope: str, result: bool) -> None:
        """Cache validation result."""
        cache_key = (expanded_scopes, required_scope)
        self._validation_cache[cache_key] = result


class OptimizedScopeHierarchy:
    """Optimized scope hierarchy with pre-computed transitive closures."""

    def __init__(self, hierarchy: dict[str, list[str]]):
        self._hierarchy = hierarchy.copy()
        self._transitive_closures: dict[str, frozenset[str]] = {}
        self._wildcard_scopes: frozenset[str] = frozenset()
        self._precompute_closures()

    def _precompute_closures(self) -> None:
        """Pre-compute transitive closure for all scopes."""
        logger.debug(f"Pre-computing scope closures for {len(self._hierarchy)} scopes")

        # Find wildcard scopes first
        wildcard_scopes = set()
        for scope, children in self._hierarchy.items():
            if "*" in children:
                wildcard_scopes.add(scope)

        self._wildcard_scopes = frozenset(wildcard_scopes)
        logger.debug(f"Found {len(wildcard_scopes)} wildcard scopes: {wildcard_scopes}")

        # Pre-compute closure for each scope
        for scope in self._hierarchy.keys():
            self._transitive_closures[scope] = self._compute_closure(scope)

        logger.info(f"Pre-computed {len(self._transitive_closures)} scope closures")

    def _compute_closure(self, scope: str) -> frozenset[str]:
        """Compute transitive closure for a single scope."""
        if scope in self._transitive_closures:
            return self._transitive_closures[scope]

        closure = {scope}
        stack = [scope]

        while stack:
            current = stack.pop()
            if current in self._hierarchy:
                children = self._hierarchy[current]

                # Handle wildcard
                if "*" in children:
                    # Wildcard grants everything - return special marker
                    return frozenset({"*"})

                for child in children:
                    if child not in closure:
                        closure.add(child)
                        stack.append(child)

        return frozenset(closure)

    def expand_scopes_fast(self, user_scopes: frozenset[str]) -> frozenset[str]:
        """Fast scope expansion using pre-computed closures."""
        if not user_scopes:
            return frozenset()

        # Check for wildcard scopes first
        if any(scope in self._wildcard_scopes for scope in user_scopes):
            logger.debug("User has wildcard scope - granting all permissions")
            return frozenset({"*"})

        expanded = set()
        for scope in user_scopes:
            if scope in self._transitive_closures:
                closure = self._transitive_closures[scope]
                if "*" in closure:
                    return frozenset({"*"})
                expanded.update(closure)
            else:
                # Scope not in hierarchy - add as-is
                expanded.add(scope)

        return frozenset(expanded)

    def validate_scope_fast(self, expanded_scopes: frozenset[str], required_scope: str) -> bool:
        """Fast scope validation using expanded scopes."""
        return "*" in expanded_scopes or required_scope in expanded_scopes

    @property
    def hierarchy(self) -> dict[str, list[str]]:
        """Get the original hierarchy for compatibility."""
        return self._hierarchy.copy()


# Request-scoped cache context
_request_scope_cache: ContextVar[ScopeCache | None] = ContextVar("request_scope_cache", default=None)


class ScopeService:
    """Centralized, high-performance scope validation service."""

    def __init__(self, hierarchy_config: dict[str, list[str]] | None = None):
        self._hierarchy: OptimizedScopeHierarchy | None = None
        if hierarchy_config:
            self._hierarchy = OptimizedScopeHierarchy(hierarchy_config)

        self._cache_enabled = True

    def initialize_hierarchy(self, hierarchy_config: dict[str, list[str]]) -> None:
        """Initialize or update the scope hierarchy."""
        logger.info(f"Initializing scope hierarchy with {len(hierarchy_config)} entries")
        self._hierarchy = OptimizedScopeHierarchy(hierarchy_config)
        logger.info("Scope hierarchy initialized successfully")

    def start_request_cache(self) -> ScopeCache:
        """Start a new request-scoped cache."""
        cache = ScopeCache()
        _request_scope_cache.set(cache)
        logger.debug("Started request-scoped scope cache")
        return cache

    def clear_request_cache(self) -> None:
        """Clear request cache."""
        _request_scope_cache.set(None)

    def expand_user_scopes(self, user_scopes: list[str] | set[str]) -> frozenset[str]:
        """Expand user scopes using hierarchy with caching."""
        if not self._hierarchy:
            logger.warning("No scope hierarchy available - returning original scopes")
            return frozenset(user_scopes)

        # Sanitize user-provided scopes
        sanitized_scopes = []
        for scope in user_scopes:
            if "*" in scope or not scope.replace(":", "").replace("_", "").replace("-", "").isalnum():
                logger.warning(f"Rejecting invalid scope format")
                continue
            sanitized_scopes.append(scope)

        user_scopes_frozen = frozenset(sanitized_scopes)

        # Try cache first
        cache = _request_scope_cache.get() if self._cache_enabled else None
        if cache:
            cached_result = cache.get_expanded_scopes(user_scopes_frozen)
            if cached_result is not None:
                return cached_result

        # Compute expansion
        expanded = self._hierarchy.expand_scopes_fast(user_scopes_frozen)

        # Cache result
        if cache:
            cache.set_expanded_scopes(user_scopes_frozen, expanded)

        logger.debug(f"Expanded {len(sanitized_scopes)} user scopes to {len(expanded)} scopes")
        return expanded

    def validate_scope_access(self, user_scopes: list[str] | set[str], required_scope: str) -> ScopeCheckResult:
        """Validate if user has required scope access."""
        if not self._hierarchy:
            logger.error("No scope hierarchy available for validation")
            return ScopeCheckResult(has_access=False, missing_scopes=[required_scope])

        # Expand user scopes
        expanded_scopes = self.expand_user_scopes(user_scopes)

        # Try cache first
        cache = _request_scope_cache.get() if self._cache_enabled else None
        cached_result = None
        if cache:
            cached_result = cache.get_validation_result(expanded_scopes, required_scope)

        if cached_result is not None:
            has_access = cached_result
            cache_hit = True
        else:
            # Perform validation
            has_access = self._hierarchy.validate_scope_fast(expanded_scopes, required_scope)
            cache_hit = False

            # Cache result
            if cache:
                cache.set_validation_result(expanded_scopes, required_scope, has_access)

        missing_scopes = [] if has_access else [required_scope]

        # Only log at DEBUG level to reduce noise
        logger.debug(f"Scope validation: user_scopes={len(user_scopes)}, required='{required_scope}', result={has_access}, cache_hit={cache_hit}")

        return ScopeCheckResult(
            has_access=has_access,
            expanded_scopes=expanded_scopes,
            missing_scopes=missing_scopes,
            cache_hit=cache_hit
        )

    def validate_multiple_scopes(self, user_scopes: list[str] | set[str], required_scopes: list[str]) -> ScopeCheckResult:
        """Validate if user has all required scopes."""
        if not required_scopes:
            return ScopeCheckResult(has_access=True)

        expanded_scopes = self.expand_user_scopes(user_scopes)
        missing_scopes = []
        cache_hits = 0

        for required_scope in required_scopes:
            result = self.validate_scope_access(user_scopes, required_scope)
            if not result.has_access:
                missing_scopes.append(required_scope)
            if result.cache_hit:
                cache_hits += 1

        has_access = len(missing_scopes) == 0

        logger.debug(f"Multiple scope validation: {len(required_scopes)} scopes, {len(missing_scopes)} missing")

        return ScopeCheckResult(
            has_access=has_access,
            expanded_scopes=expanded_scopes,
            missing_scopes=missing_scopes,
            cache_hit=cache_hits == len(required_scopes)
        )


    def get_hierarchy_summary(self) -> dict[str, Any]:
        """Get hierarchy summary for debugging (safe for logging)."""
        if not self._hierarchy:
            return {"error": "No hierarchy available"}

        return {
            "total_scopes": len(self._hierarchy.hierarchy),
            "wildcard_scopes_count": len(self._wildcard_scopes) if hasattr(self._hierarchy, '_wildcard_scopes') else 0
        }


# Global service instance
_scope_service: ScopeService | None = None


def get_scope_service() -> ScopeService:
    """Get the global scope service instance."""
    global _scope_service
    if _scope_service is None:
        _scope_service = ScopeService()
    return _scope_service


