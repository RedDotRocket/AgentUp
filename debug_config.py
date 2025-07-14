#!/usr/bin/env python3
"""Debug script to check configuration loading."""

import sys
sys.path.insert(0, 'src')

from agent.config import load_config
from agent.security.manager import SecurityManager
from agent.security.unified_auth import get_unified_auth_manager

# Load config from jwt_test agent
import os
os.chdir('../validation-agents/jwt_test')

config = load_config()
print("=== Full Config ===")
print(f"Config keys: {list(config.keys())}")

security_config = config.get("security", {})
print(f"\n=== Security Config ===")
print(f"Security config keys: {list(security_config.keys())}")
print(f"Security config: {security_config}")

# Initialize security manager
security_manager = SecurityManager(config)
print(f"\n=== Security Manager ===")
print(f"Security manager auth enabled: {security_manager.is_auth_enabled()}")

# Check unified auth manager
unified_auth_manager = get_unified_auth_manager()
print(f"\n=== Unified Auth Manager ===")
print(f"Unified auth manager: {unified_auth_manager}")
if unified_auth_manager:
    print(f"Hierarchy: {unified_auth_manager.scope_hierarchy.hierarchy}")
    print(f"Hierarchy size: {len(unified_auth_manager.scope_hierarchy.hierarchy)}")