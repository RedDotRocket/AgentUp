#!/bin/bash

# Set the config path to use our correct agentup.yml
export AGENT_CONFIG_PATH="/Users/lhinds/dev/agentup-ws/AgentUp/agentup.yml"

# Run unit tests
uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ -v -m "not integration and not e2e and not performance"