#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set the config path to use our correct agentup.yml (relative to script location)
export AGENT_CONFIG_PATH="$SCRIPT_DIR/agentup.yml"

# Change to the script directory to ensure relative paths work
cd "$SCRIPT_DIR"

# Run unit tests
uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ -v -m "not integration and not e2e and not performance"