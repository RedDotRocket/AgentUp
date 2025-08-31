import questionary


def get_feature_choices() -> list[questionary.Choice]:
    return [
        questionary.Choice("Authentication Method (API Key, Bearer(JWT), OAuth2)", value="auth", checked=True),
        questionary.Choice(
            "Context-Aware Middleware (caching, retry, rate limiting)", value="middleware", checked=True
        ),
        questionary.Choice("State Management (conversation persistence)", value="state_management", checked=True),
        questionary.Choice("AI Provider (ollama, openai, anthropic)", value="ai_provider"),
        questionary.Choice("MCP Integration (Model Context Protocol)", value="mcp", checked=True),
        questionary.Choice("Push Notifications (webhooks)", value="push_notifications"),
        questionary.Choice("Development Features (filesystem plugins, debug mode)", value="development"),
        questionary.Choice("Deployment (Kubernetes, Helm Charts)", value="deployment"),
    ]
