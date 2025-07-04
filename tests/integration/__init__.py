"""Integration tests for AgentUp.

This package contains integration tests that require a running AgentUp server.
These tests validate the behavior of the complete system including middleware,
handlers, and API endpoints.

To run integration tests:
    pytest tests/integration/ -m integration

To run stress tests:
    pytest tests/integration/ -m stress

Prerequisites:
- Start an AgentUp server: agentup agent serve --port 8000
- Ensure the server is healthy and responding to requests
"""
