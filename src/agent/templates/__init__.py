from typing import Any

import questionary


def get_template_choices() -> list[questionary.Choice]:
    """Get available project templates."""
    return [
        questionary.Choice(
            "Minimal - Barebone agent (no AI, no external dependencies)", value="minimal", shortcut_key="m"
        ),
        questionary.Choice("Full - Enterprise agent with all features", value="full", shortcut_key="f"),
    ]


def get_feature_choices() -> list[questionary.Choice]:
    """Get available features for custom template."""
    return [
        questionary.Choice("Authentication Method (API Key, Bearer(JWT), OAuth2)", value="auth", checked=True),
        questionary.Choice(
            "Context-Aware Middleware (caching, retry, rate limiting)", value="middleware", checked=True
        ),
        questionary.Choice("State Management (conversation persistence)", value="state_management", checked=True),
        questionary.Choice("AI Provider (ollama, openai, anthropic)", value="ai_provider"),
        questionary.Choice("MCP Integration (Model Context Protocol)", value="mcp", checked=True),
        questionary.Choice("Push Notifications (webhooks)", value="custom"),
    ]


def get_template_features(template: str = None) -> dict[str, dict[str, Any]]:
    """Get features included in each template."""
    return {
        "minimal": {
            "features": ["auth"],  # Minimal now includes basic AgentUp Security Framework
            "description": "Secure agent with AgentUp Security Framework - minimal features, maximum security",
        },
        "full": {
            "features": [
                "auth",
                "middleware",
                "state_management",
                "ai_provider",
                "mcp",
                "push_notifications",
            ],
            "description": "Enterprise-ready agent with AgentUp Security Framework and all advanced features",
        },
    }
