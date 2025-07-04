from typing import Any

import questionary


def get_template_choices() -> list[questionary.Choice]:
    """Get available project templates."""
    return [
        questionary.Choice(
            "Minimal - Barebone agent (no AI, no external dependencies)", value="minimal", shortcut_key="m"
        ),
        questionary.Choice("Standard - AI-powered agent with MCP (recommended)", value="standard", shortcut_key="s"),
        questionary.Choice("Full - Enterprise agent with all features", value="full", shortcut_key="f"),
    ]


def get_feature_choices() -> list[questionary.Choice]:
    """Get available features for custom template."""
    return [
        questionary.Choice("Middleware System (caching, retry, rate limiting)", value="middleware", checked=True),
        questionary.Choice("Multi-modal Processing (images, documents)", value="multimodal"),
        questionary.Choice("State Management (file, memory, valkey)", value="state"),
        questionary.Choice("AI Provider (ollama, openai, anthropic)", value="ai_provider"),
        questionary.Choice("Authentication (API Key, JWT, OAuth)", value="auth", checked=True),
    ]


def get_template_features(template: str = None) -> dict[str, dict[str, Any]]:
    """Get features included in each template."""
    return {
        "minimal": {
            "features": [],
            "description": "Barebone agent with text processing only - no AI, no external dependencies",
        },
        "standard": {
            "features": ["middleware", "multimodal", "ai_provider", "auth", "mcp"],
            "description": "AI-powered agent with MCP integration - recommended for most users",
        },
        "full": {
            "features": [
                "middleware",
                "multimodal",
                "state",
                "ai_provider",
                "auth",
                "mcp",
            ],
            "description": "Enterprise-ready agent with all features including multiple MCP servers",
        },
    }
