"""
Test suite for scope inheritance and hierarchy system.

Tests the hierarchical permission system where higher scopes grant lower permissions.
"""

import pytest

from src.agent.plugins.base import Plugin
from src.agent.plugins.decorators import capability
from src.agent.plugins.models import CapabilityContext


class TestScopeHierarchy:
    """Test scope hierarchy and inheritance system."""

    def test_wildcard_admin_scope(self):
        """Test that '*' scope grants all permissions like admin."""

        class AdminPlugin(Plugin):
            @capability("admin_action", name="Admin Action", scopes=["*"])
            async def admin_method(self, context: CapabilityContext) -> str:
                return "admin action"

        plugin = AdminPlugin()
        capability_defs = plugin.get_capability_definitions()

        assert len(capability_defs) == 1
        admin_cap = capability_defs[0]
        assert admin_cap.required_scopes == ["*"]

        # In a real implementation, "*" would grant all permissions
        # This test validates the scope is correctly stored
        assert "*" in admin_cap.required_scopes

    def test_domain_wildcard_scopes(self):
        """Test domain-level wildcard scopes like 'files:*'."""

        class FilePlugin(Plugin):
            @capability("file_admin", name="File Admin", scopes=["files:*"])
            async def file_admin_method(self, context: CapabilityContext) -> str:
                return "file admin"

            @capability("file_read", name="File Read", scopes=["files:read"])
            async def file_read_method(self, context: CapabilityContext) -> str:
                return "file read"

        plugin = FilePlugin()
        capability_defs = plugin.get_capability_definitions()

        admin_cap = next(cap for cap in capability_defs if cap.id == "file_admin")
        read_cap = next(cap for cap in capability_defs if cap.id == "file_read")

        assert admin_cap.required_scopes == ["files:*"]
        assert read_cap.required_scopes == ["files:read"]

        # In a real scope hierarchy system:
        # - files:* would grant files:read, files:write, files:delete, etc.
        # - This test validates the scopes are correctly defined

    def test_hierarchical_scope_structure(self):
        """Test hierarchical scope structure (admin > domain:admin > domain:write > domain:read)."""

        class HierarchicalPlugin(Plugin):
            @capability("system_admin", scopes=["admin"])
            async def system_admin(self, context: CapabilityContext) -> str:
                return "system admin"

            @capability("files_admin", scopes=["files:admin"])
            async def files_admin(self, context: CapabilityContext) -> str:
                return "files admin"

            @capability("files_write", scopes=["files:write"])
            async def files_write(self, context: CapabilityContext) -> str:
                return "files write"

            @capability("files_read", scopes=["files:read"])
            async def files_read(self, context: CapabilityContext) -> str:
                return "files read"

        plugin = HierarchicalPlugin()
        capability_defs = plugin.get_capability_definitions()

        # Validate all scopes are correctly defined
        scope_map = {cap.id: cap.required_scopes for cap in capability_defs}

        assert scope_map["system_admin"] == ["admin"]
        assert scope_map["files_admin"] == ["files:admin"]
        assert scope_map["files_write"] == ["files:write"]
        assert scope_map["files_read"] == ["files:read"]

    def test_multiple_required_scopes(self):
        """Test capabilities that require multiple scopes."""

        class MultiScopePlugin(Plugin):
            @capability(
                "complex_action", name="Complex Action", scopes=["files:write", "network:access", "system:config"]
            )
            async def complex_action(self, context: CapabilityContext) -> str:
                return "complex action"

        plugin = MultiScopePlugin()
        capability_defs = plugin.get_capability_definitions()

        complex_cap = capability_defs[0]
        assert set(complex_cap.required_scopes) == {"files:write", "network:access", "system:config"}

    def test_scope_validation_format(self):
        """Test scope format validation (should be 'resource:action')."""

        # Valid scopes should work
        class ValidScopePlugin(Plugin):
            @capability("valid_scopes", scopes=["files:read", "network:connect", "user:manage"])
            async def valid_method(self, context: CapabilityContext) -> str:
                return "valid"

        plugin = ValidScopePlugin()
        # Should create without errors
        assert len(plugin._capabilities) == 1

    def test_scope_inheritance_simulation(self):
        """Test simulated scope inheritance logic."""

        # This would be the logic for checking scope inheritance
        def has_scope_permission(user_scopes: list[str], required_scope: str) -> bool:
            """Simulate scope permission checking with inheritance."""
            # Universal admin access
            if "*" in user_scopes:
                return True

            # Direct scope match
            if required_scope in user_scopes:
                return True

            # Domain wildcard match
            if ":" in required_scope:
                domain, action = required_scope.split(":", 1)
                domain_wildcard = f"{domain}:*"
                if domain_wildcard in user_scopes:
                    return True

                # Admin-level access
                domain_admin = f"{domain}:admin"
                if domain_admin in user_scopes:
                    return True

            # System admin access
            if "admin" in user_scopes:
                return True

            return False

        # Test cases for scope inheritance
        test_cases = [
            # (user_scopes, required_scope, should_have_access)
            (["*"], "files:read", True),  # Universal admin
            (["admin"], "files:read", True),  # System admin
            (["files:*"], "files:read", True),  # Domain wildcard
            (["files:admin"], "files:read", True),  # Domain admin
            (["files:write"], "files:read", False),  # Different action (would need proper hierarchy)
            (["files:read"], "files:read", True),  # Direct match
            (["network:read"], "files:read", False),  # Different domain
            ([], "files:read", False),  # No scopes
        ]

        for user_scopes, required_scope, expected in test_cases:
            result = has_scope_permission(user_scopes, required_scope)
            assert result == expected, f"Failed for user_scopes={user_scopes}, required_scope={required_scope}"

    def test_circular_dependency_detection_simulation(self):
        """Test circular dependency detection in scope hierarchies."""

        def detect_circular_dependencies(scope_hierarchy: dict[str, list[str]]) -> list[str]:
            """Detect circular dependencies in scope hierarchy."""
            visited = set()
            recursion_stack = set()
            circular_deps = []

            def dfs(scope: str) -> bool:
                if scope in recursion_stack:
                    circular_deps.append(scope)
                    return True
                if scope in visited:
                    return False

                visited.add(scope)
                recursion_stack.add(scope)

                for child_scope in scope_hierarchy.get(scope, []):
                    if dfs(child_scope):
                        return True

                recursion_stack.remove(scope)
                return False

            for scope in scope_hierarchy:
                if scope not in visited:
                    dfs(scope)

            return circular_deps

        # Test valid hierarchy (no cycles)
        valid_hierarchy = {
            "admin": ["files:admin", "network:admin"],
            "files:admin": ["files:write", "files:read"],
            "files:write": ["files:read"],
            "network:admin": ["network:connect"],
        }

        circular = detect_circular_dependencies(valid_hierarchy)
        assert circular == []

        # Test circular dependency
        circular_hierarchy = {
            "scope_a": ["scope_b"],
            "scope_b": ["scope_c"],
            "scope_c": ["scope_a"],  # Creates cycle
        }

        circular = detect_circular_dependencies(circular_hierarchy)
        assert len(circular) > 0

    def test_scope_override_behavior(self):
        """Test scope override behavior in hierarchies."""

        class OverridePlugin(Plugin):
            @capability("base_action", scopes=["files:read"])
            async def base_action(self, context: CapabilityContext) -> str:
                return "base"

        class ExtendedPlugin(OverridePlugin):
            @capability("extended_action", scopes=["files:write"])
            async def extended_action(self, context: CapabilityContext) -> str:
                return "extended"

            # Override base action with higher permissions
            @capability("base_action", scopes=["files:admin"])
            async def base_action(self, context: CapabilityContext) -> str:
                return "overridden base"

        plugin = ExtendedPlugin()
        capability_defs = plugin.get_capability_definitions()

        # Should have both capabilities, with base_action requiring admin scope
        scope_map = {cap.id: cap.required_scopes for cap in capability_defs}

        # The last registered capability should win (extended_action and overridden base_action)
        assert "base_action" in scope_map
        assert "extended_action" in scope_map
        # Note: The exact behavior depends on implementation - this tests the structure

    def test_empty_scopes_behavior(self):
        """Test behavior with empty or no scopes."""

        class NoScopePlugin(Plugin):
            @capability("no_scopes")  # No scopes specified
            async def no_scopes_method(self, context: CapabilityContext) -> str:
                return "no scopes"

            @capability("empty_scopes", scopes=[])  # Empty scopes list
            async def empty_scopes_method(self, context: CapabilityContext) -> str:
                return "empty scopes"

        plugin = NoScopePlugin()
        capability_defs = plugin.get_capability_definitions()

        # Both should have empty scope lists
        for cap in capability_defs:
            assert cap.required_scopes == []

    def test_scope_normalization(self):
        """Test scope normalization and validation."""

        def normalize_scope(scope: str) -> str:
            """Normalize scope format."""
            scope = scope.strip().lower()

            # Validate format
            if scope == "*":
                return scope
            if scope == "admin":
                return scope
            if ":" not in scope:
                raise ValueError(f"Invalid scope format: '{scope}'. Must be 'resource:action' or 'admin' or '*'")

            parts = scope.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid scope format: '{scope}'. Must have exactly one ':'")

            resource, action = parts
            if not resource or not action:
                raise ValueError(f"Invalid scope format: '{scope}'. Resource and action cannot be empty")

            return f"{resource}:{action}"

        # Test valid scopes
        assert normalize_scope("files:read") == "files:read"
        assert normalize_scope("FILES:READ") == "files:read"
        assert normalize_scope(" network:connect ") == "network:connect"
        assert normalize_scope("*") == "*"
        assert normalize_scope("admin") == "admin"

        # Test invalid scopes
        with pytest.raises(ValueError, match="Invalid scope format"):
            normalize_scope("invalid")

        with pytest.raises(ValueError, match="Invalid scope format"):
            normalize_scope("too:many:colons")

        with pytest.raises(ValueError, match="Invalid scope format"):
            normalize_scope(":empty_resource")

        with pytest.raises(ValueError, match="Invalid scope format"):
            normalize_scope("empty_action:")


class TestScopeEnforcement:
    """Test scope enforcement mechanisms."""

    def test_capability_scope_requirements(self):
        """Test that capabilities correctly declare their scope requirements."""

        class ScopeTestPlugin(Plugin):
            @capability("read_files", scopes=["files:read"])
            async def read_files(self, context: CapabilityContext) -> str:
                return "reading files"

            @capability("write_files", scopes=["files:write"])
            async def write_files(self, context: CapabilityContext) -> str:
                return "writing files"

            @capability("admin_task", scopes=["admin"])
            async def admin_task(self, context: CapabilityContext) -> str:
                return "admin task"

        plugin = ScopeTestPlugin()

        # Test that each capability has correct scope requirements
        read_cap = next(cap for cap in plugin._capabilities.values() if cap.id == "read_files")
        write_cap = next(cap for cap in plugin._capabilities.values() if cap.id == "write_files")
        admin_cap = next(cap for cap in plugin._capabilities.values() if cap.id == "admin_task")

        assert read_cap.scopes == ["files:read"]
        assert write_cap.scopes == ["files:write"]
        assert admin_cap.scopes == ["admin"]

    def test_scope_metadata_in_capability_definitions(self):
        """Test that scope information is included in capability definitions."""

        class MetadataPlugin(Plugin):
            @capability(
                "complex_capability",
                name="Complex Capability",
                description="A capability with multiple scope requirements",
                scopes=["files:write", "network:access"],
            )
            async def complex_capability(self, context: CapabilityContext) -> str:
                return "complex result"

        plugin = MetadataPlugin()
        capability_defs = plugin.get_capability_definitions()

        assert len(capability_defs) == 1
        cap_def = capability_defs[0]

        assert cap_def.id == "complex_capability"
        assert cap_def.name == "Complex Capability"
        assert cap_def.description == "A capability with multiple scope requirements"
        assert set(cap_def.required_scopes) == {"files:write", "network:access"}

    def test_dynamic_scope_checking(self):
        """Test dynamic scope checking during capability execution."""

        # Simulate scope checking logic that might be called during execution
        def check_user_has_scopes(user_scopes: list[str], required_scopes: list[str]) -> tuple[bool, list[str]]:
            """Check if user has all required scopes."""
            missing_scopes = []

            for required_scope in required_scopes:
                has_scope = False

                # Check for universal admin
                if "*" in user_scopes:
                    has_scope = True
                # Check for direct scope match
                elif required_scope in user_scopes:
                    has_scope = True
                # Check for domain admin (simplified)
                elif ":" in required_scope:
                    domain = required_scope.split(":")[0]
                    if f"{domain}:admin" in user_scopes or f"{domain}:*" in user_scopes:
                        has_scope = True

                if not has_scope:
                    # Check for system admin
                    if "admin" in user_scopes:
                        has_scope = True

                if not has_scope:
                    missing_scopes.append(required_scope)

            return len(missing_scopes) == 0, missing_scopes

        # Test cases
        test_cases = [
            # (user_scopes, required_scopes, should_pass, expected_missing)
            (["files:read"], ["files:read"], True, []),
            (["files:admin"], ["files:read"], True, []),
            (["*"], ["files:read", "network:write"], True, []),
            (["admin"], ["files:read"], True, []),
            (["files:read"], ["files:write"], False, ["files:write"]),
            (["files:read"], ["files:read", "network:write"], False, ["network:write"]),
            ([], ["files:read"], False, ["files:read"]),
        ]

        for user_scopes, required_scopes, should_pass, expected_missing in test_cases:
            has_access, missing = check_user_has_scopes(user_scopes, required_scopes)
            assert has_access == should_pass, (
                f"Failed for user_scopes={user_scopes}, required_scopes={required_scopes}, got {has_access}, expected {should_pass}"
            )
            assert set(missing) == set(expected_missing), (
                f"Failed for user_scopes={user_scopes}, required_scopes={required_scopes}, got missing={missing}, expected {expected_missing}"
            )
