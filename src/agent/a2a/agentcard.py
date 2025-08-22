import importlib.metadata

import structlog
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentCardSignature,
    AgentExtension,
    AgentProvider,
    AgentSkill,
    APIKeySecurityScheme,
    HTTPAuthSecurityScheme,
)

from agent.services.config import ConfigurationManager

logger = structlog.get_logger(__name__)

# Agent card caching - Force cache invalidation for debugging
_cached_agent_card: AgentCard | None = None
_cached_extended_agent_card: AgentCard | None = None
_cached_config_hash: str | None = None


def create_agent_card(extended: bool = False) -> AgentCard:
    """Create agent card with current configuration.

    Args:
        extended: If True, include plugins with visibility="extended" in addition to public plugins
    """
    import hashlib

    global _cached_agent_card, _cached_extended_agent_card, _cached_config_hash

    # Get configuration from the cached ConfigurationManager
    config_manager = ConfigurationManager()
    # Use the Pydantic config directly instead of model_dump()
    pydantic_config = config_manager.pydantic_config
    config = config_manager.config  # Keep for backward compatibility where needed

    # Create a hash of the configuration to detect changes
    config_str = str(sorted(config.items()))
    # Bandit issue: B324 - Using hashlib.md5() is acceptable here for caching purposes
    current_config_hash = hashlib.md5(config_str.encode()).hexdigest()  # nosec

    # Check if we can use cached version
    if _cached_config_hash == current_config_hash:
        if extended and _cached_extended_agent_card is not None:
            logger.debug("Using cached extended AgentCard")
            return _cached_extended_agent_card
        elif not extended and _cached_agent_card is not None:
            logger.debug("Using cached AgentCard")
            return _cached_agent_card

    # Cache miss - regenerate agent card
    agent_info = config.get("agent", {})
    plugins = config.get("plugins", [])

    # Only log plugins when actually regenerating (cache miss)
    logger.debug(f"Regenerating agent card - loaded {len(plugins)} plugins from config")

    # Convert plugins to A2A Skill format based on visibility
    agent_skills = []
    has_extended_plugins = False

    # Add MCP tools as skills
    agent_skills.extend(_get_mcp_skills_for_agent_card())

    # Get capability information from the plugin registry
    from agent.plugins.manager import get_plugin_registry

    registry = get_plugin_registry()
    if registry and registry.capabilities:
        # Create a lookup for plugin configurations by package name
        plugins_by_package = {}
        if isinstance(plugins, dict):
            # New dictionary structure: package name is the key
            plugins_by_package = plugins
        else:
            # Legacy list structure: extract package names
            for plugin in plugins:
                if isinstance(plugin, dict) and "package" in plugin:
                    plugins_by_package[plugin["package"]] = plugin

        # Iterate over all registered capabilities instead of plugins
        for capability_id, capability_metadata in registry.capabilities.items():
            # Find the plugin that owns this capability
            plugin_name = registry.capability_to_plugin.get(capability_id)
            # Try to find plugin config by package name (need to map plugin_name to package)
            plugin_config = None
            if plugin_name:
                # In new structure, we need to find the package that contains this plugin
                for package_name, config in plugins_by_package.items():
                    # For now, assume package name matches plugin name or contains it
                    if package_name == plugin_name or plugin_name in package_name:
                        plugin_config = config
                        break

            # Determine visibility - default to public if no plugin config
            if plugin_config:
                if hasattr(plugin_config, "visibility"):
                    plugin_visibility = plugin_config.visibility
                elif isinstance(plugin_config, dict):
                    plugin_visibility = plugin_config.get("visibility", "public")
                else:
                    plugin_visibility = "public"
            else:
                plugin_visibility = "public"

            # Track if any extended plugins exist
            if plugin_visibility == "extended":
                has_extended_plugins = True

            # Include capability in card based on visibility and card type
            if plugin_visibility == "public" or (extended and plugin_visibility == "extended"):
                # Create AgentSkill from capability metadata using A2A fields
                agent_skill = AgentSkill(
                    id=capability_metadata.id,
                    name=capability_metadata.name,
                    description=capability_metadata.description,
                    input_modes=capability_metadata.input_modes,  # Use A2A field
                    output_modes=capability_metadata.output_modes,  # Use A2A field
                    tags=capability_metadata.tags or ["general"],
                    examples=capability_metadata.examples,  # A2A field
                    security=capability_metadata.security,  # A2A field
                )
                agent_skills.append(agent_skill)

    # Create capabilities object with extensions
    extensions = []

    # Add MCP extension if enabled
    mcp_config = config.get("mcp", {})
    if mcp_config.get("enabled") and mcp_config.get("server", {}).get("enabled"):
        mcp_extension = AgentExtension(
            uri="https://modelcontextprotocol.io/mcp/1.0",
            description="Agent supports MCP for tool sharing and collaboration",
            params={
                "endpoint": "/mcp",
                "transport": "http",
                "authentication": "api_key",
            },
            required=False,
        )
        extensions.append(mcp_extension)

    pushNotifications = config.get("push_notifications", {})
    state_management = config.get("state_management", {})
    capabilities = AgentCapabilities(
        streaming=bool(
            pydantic_config.ai_provider.stream if pydantic_config.ai_provider else False
        ),
        push_notifications=pushNotifications.get("enabled", False),
        state_transition_history=state_management.get("enabled", False),
        extensions=extensions if extensions else None,
    )

    # Create security schemes based on configuration
    security_config = config.get("security", {})
    security_schemes = {}
    security_requirements = []

    # Get protocol version from a2a-sdk package
    protocol_version = _get_package_version("a2a-sdk")
    if security_config.get("enabled", False):
        auth_type = security_config.get("type", "api_key")

        if auth_type == "api_key":
            # API Key authentication
            api_key_scheme = APIKeySecurityScheme.model_validate(
                {
                    "name": "X-API-Key",
                    "description": "API key for authentication",
                    "in": "header",  # <- use the JSON alias
                    "type": "apiKey",
                }
            )
            security_schemes["X-API-Key"] = api_key_scheme.model_dump(by_alias=True)
            security_requirements.append({"X-API-Key": []})

        elif auth_type == "bearer":
            # Bearer Token authentication
            bearer_scheme = HTTPAuthSecurityScheme(
                scheme="bearer", description="Bearer token for authentication", type="http"
            )
            security_schemes["BearerAuth"] = bearer_scheme.model_dump(by_alias=True)
            security_requirements.append({"BearerAuth": []})

        elif auth_type == "oauth2":
            # OAuth2 Bearer Token authentication
            oauth2_config = security_config.get("oauth2", {})
            required_scopes = oauth2_config.get("required_scopes", [])

            oauth2_scheme = HTTPAuthSecurityScheme(
                scheme="bearer",
                description="OAuth2 Bearer token for authentication",
                type="http",
                bearer_format="JWT",  # Indicate JWT format for OAuth2
            )
            security_schemes["OAuth2"] = oauth2_scheme.model_dump(by_alias=True)
            security_requirements.append({"OAuth2": required_scopes})

    # Create the official AgentCard
    # Get version from package metadata, fallback to default
    package_version = _get_package_version("agentup")

    # Create signatures object only if we have actual signature data
    signatures = None
    signature_header = agent_info.get("signature_header")
    signature_protected = agent_info.get("signature_protected")
    signature_value = agent_info.get("signature")

    if signature_header and signature_protected and signature_value:
        signatures = AgentCardSignature(
            header=signature_header,
            protected=signature_protected,
            signature=signature_value,
        )

    agent_card = AgentCard(
        protocol_version=protocol_version,
        name=agent_info.get("name") or pydantic_config.project_name,
        description=agent_info.get("description") or pydantic_config.description,
        url=agent_info.get("url") or "http://localhost:8000",
        preferred_transport="JSONRPC",
        provider=AgentProvider(
            organization=agent_info.get("provider_organization", "AgentUp"),
            url=agent_info.get("provider_url", "http://localhost:8000"),
        ),
        icon_url=agent_info.get("icon_url")
        or "https://raw.githubusercontent.com/RedDotRocket/AgentUp/refs/heads/main/assets/icon.png",
        version=agent_info.get("version", package_version),
        documentation_url=agent_info.get("documentation_url") or "https://docs.agentup.dev",
        capabilities=capabilities,
        security=security_requirements if security_requirements else None,
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=agent_skills,
        security_schemes=security_schemes if security_schemes else None,
        signatures=[signatures] if signatures else None,
        supports_authenticated_extended_card=has_extended_plugins,
    )

    # Update cache
    _cached_config_hash = current_config_hash
    if extended:
        _cached_extended_agent_card = agent_card
    else:
        _cached_agent_card = agent_card

    return agent_card


def _get_mcp_skills_for_agent_card() -> list[AgentSkill]:
    """Convert registered MCP capabilities to AgentSkill objects.

    Only includes MCP tools from servers with expose_as_skills: true.

    Returns:
        List of AgentSkill objects representing MCP tools
    """
    from agent.capabilities.manager import get_mcp_capabilities
    from agent.services.config import ConfigurationManager

    mcp_skills = []
    try:
        # Get MCP server configuration to check expose_as_skills flags
        config_manager = ConfigurationManager()
        config = config_manager.config

        mcp_config = config.get("mcp", {})
        if not mcp_config.get("enabled"):
            return mcp_skills
        servers = mcp_config.get("servers", [])

        # Create a mapping of server names to expose_as_skills setting
        server_expose_flags = {}
        for server in servers:
            # TODO: Pydantic validation for server config
            server_name = server.get("name")
            expose_flag = server.get("expose_as_skills", False)

            server_expose_flags[server_name] = expose_flag

        mcp_capabilities = get_mcp_capabilities()

        # If no capabilities are available, return empty list
        if not mcp_capabilities:
            return mcp_skills

        for capability_id, capability_info in mcp_capabilities.items():
            # Only include capabilities from servers with expose_as_skills: true
            server_name = capability_info.server_name

            # Add server name to capability ID for uniqueness
            name = f"{server_name}:{capability_id}" if server_name else capability_id

            if server_expose_flags.get(server_name, False):
                logger.debug(
                    f"Including capability '{capability_id}' in AgentCard (server '{server_name}' has expose_as_skills=true)"
                )

                # Convert MCPCapabilityInfo to AgentSkill
                skill = AgentSkill(
                    id=capability_id,
                    name=name,
                    description=capability_info.description,
                    input_modes=["text"],
                    output_modes=["text"],
                    tags=["mcp", capability_info.server_name]
                    if capability_info.server_name
                    else ["mcp"],
                )
                mcp_skills.append(skill)
            else:
                logger.debug(
                    f"Skipping capability '{capability_id}' (server '{server_name}' has expose_as_skills={server_expose_flags.get(server_name, False)})"
                )

        if mcp_skills:
            logger.debug(
                f"Added {len(mcp_skills)} MCP tools as AgentCard skills from servers with expose_as_skills=true"
            )

    except Exception as e:
        logger.error(f"Failed to get MCP capabilities for AgentCard: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

    return mcp_skills


def _get_package_version(package_name: str) -> str:
    """Get the version of a package from metadata.

    Args:
        package_name: Name of the package to get version for

    Returns:
        Package version string or "0.0.0" if not found
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        logger.warning(f"Package '{package_name}' not found in metadata")
        return "0.0.0"
    except Exception as e:
        logger.warning(f"Failed to get version for package '{package_name}': {e}")
        return "0.0.0"


def clear_agent_card_cache() -> None:
    """Clear the agent card cache to force regeneration."""
    global _cached_agent_card, _cached_extended_agent_card, _cached_config_hash
    _cached_agent_card = None
    _cached_extended_agent_card = None
    _cached_config_hash = None
    logger.debug("Agent card cache cleared")
