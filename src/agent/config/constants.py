
# General dumping ground for stuff that is going to stay constant across the project.

# Default model configurations
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "ollama": "llama3",
}

# API Endpoints
DEFAULT_API_ENDPOINTS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://localhost:11434",
}

# Database configurations
DEFAULT_DATABASE_URL = "sqlite:///./agent.db"
DEFAULT_VALKEY_URL = "valkey://localhost:6379"

# Server configuration
# WARNING: "0.0.0.0" binds to all network interfaces, making the agent accessible
# from any network interface. For production, consider:
# - Use "127.0.0.1" for localhost-only access
# - Use specific IP addresses for controlled access
# - Ensure proper firewall rules and authentication are in place
DEFAULT_SERVER_HOST = "0.0.0.0"  # nosec B104 - intentional for development
DEFAULT_SERVER_PORT = 8000

# Timeouts and limits
DEFAULT_HTTP_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_CACHE_TTL = 300

# User agent
DEFAULT_USER_AGENT = "AgentUp-Agent/1.0"

# Environment variable names
ENV_VARS = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
    "OLLAMA_BASE_URL": "OLLAMA_BASE_URL",
    "VALKEY_URL": "VALKEY_URL",
    "DATABASE_URL": "DATABASE_URL",
    "AGENT_CONFIG_PATH": "AGENT_CONFIG_PATH",
    "SERVER_HOST": "SERVER_HOST",
    "SERVER_PORT": "SERVER_PORT",
}


# Security defaults
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_API_KEY_LENGTH = 32
DEFAULT_JWT_SECRET_LENGTH = 64
