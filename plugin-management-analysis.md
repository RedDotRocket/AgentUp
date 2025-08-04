# Plugin Management in agentup.yml: Analysis and Implementation Strategy

## Executive Summary

Moving plugin management from Python entry points to agentup.yml configuration would transform AgentUp into a more Docker-like experience where `agentup run` instantiates everything portably. This analysis examines the current system, identifies the path forward, and outlines implementation strategies.

## Current Plugin Architecture

### Discovery Mechanism
- **Entry Points**: Uses Python's `importlib.metadata.entry_points()` with group `"agentup.plugins"`
- **Installation**: Plugins are pip/uv installed as separate packages
- **Discovery Flow**: 
  1. Scan entry points for `agentup.plugins` group
  2. Load plugin classes from entry points
  3. Validate against allowlist in agentup.yml
  4. Register capabilities and apply configuration

### Current agentup.yml Plugin Configuration
```yaml
plugins:
  - plugin_id: hello
    name: Hello Plugin
    package: hello  # Used for allowlist validation
    capabilities:
      - capability_id: hello
        required_scopes: ["api:read"]
        enabled: true
```

### Plugin System Components
1. **PluginRegistry** (`src/agent/plugins/manager.py`): Core plugin discovery and management
2. **SecurePluginInstaller** (`src/agent/plugins/installer.py`): Handles pip/uv installation with security
3. **Configuration Models** (`src/agent/config/model.py`): Pydantic models for plugin config
4. **Plugin Base Classes**: Abstract base for plugin implementation

## Vision: Docker-like Plugin Management

### Target Experience
```bash
# Clone agent configuration
git clone https://github.com/myorg/my-agent.git
cd my-agent

# Everything installs and runs instantly
agentup run
```

### Target agentup.yml Configuration
```yaml
plugins:
  - plugin_id: file_ops
    source: "pypi:agentup-file-plugin==1.2.0"
    auto_install: true
    capabilities:
      - capability_id: file_read
        enabled: true
        required_scopes: ["files:read"]
  
  - plugin_id: custom_logic  
    source: "git:https://github.com/myorg/custom-plugin.git@v1.0.0"
    auto_install: true
    
  - plugin_id: local_dev
    source: "path:./plugins/local_dev"
    auto_install: false  # For development
```

## Implementation Strategy

### Phase 1: Enhanced Plugin Configuration Model

**Extend PluginConfig in `src/agent/config/model.py`:**
```python
class PluginSource(BaseModel):
    type: Literal["pypi", "git", "path", "entry_point"]
    location: str
    version: str | None = None
    branch: str | None = None
    tag: str | None = None

class PluginConfig(BaseModel):
    # Existing fields...
    source: PluginSource | str | None = None  # New field
    auto_install: bool = True
    install_args: list[str] = Field(default_factory=list)
    install_timeout: int = 300
```

### Phase 2: Unified Plugin Manager

**Create `UnifiedPluginManager` that handles both discovery patterns:**

```python
class UnifiedPluginManager:
    async def discover_plugins(self) -> None:
        """Discover plugins from multiple sources"""
        for plugin_config in self.config.plugins:
            if plugin_config.source:
                # New: Install and load from configured source
                await self._handle_configured_plugin(plugin_config)
            else:
                # Legacy: Load from entry points
                await self._handle_entry_point_plugin(plugin_config)
    
    async def _handle_configured_plugin(self, config: PluginConfig):
        """Install and load plugin from configured source"""
        # Parse source (pypi:package==1.0.0, git:url@tag, path:./dir)
        source = self._parse_plugin_source(config.source)
        
        # Auto-install if needed
        if config.auto_install and not self._is_plugin_installed(source):
            await self._install_plugin(source, config)
        
        # Load plugin module
        plugin_module = await self._load_plugin_module(source, config)
        
        # Register plugin
        await self._register_plugin(config.plugin_id, plugin_module, config)
```

### Phase 3: Source Handlers

**Implement handlers for different plugin sources:**

```python
class PluginSourceHandler(ABC):
    @abstractmethod
    async def install(self, source: PluginSource, config: PluginConfig) -> bool: ...
    
    @abstractmethod 
    async def load_module(self, source: PluginSource, config: PluginConfig) -> ModuleType: ...

class PyPISourceHandler(PluginSourceHandler):
    async def install(self, source: PluginSource, config: PluginConfig) -> bool:
        # Use existing SecurePluginInstaller
        package_spec = f"{source.location}=={source.version}" if source.version else source.location
        result = await self.installer.install_plugin(package_spec, force=False)
        return result["success"]
    
    async def load_module(self, source: PluginSource, config: PluginConfig) -> ModuleType:
        # Load via entry points (existing mechanism)
        return await self._load_from_entry_points(config.plugin_id)

class GitSourceHandler(PluginSourceHandler):
    async def install(self, source: PluginSource, config: PluginConfig) -> bool:
        # Clone repo to temp location
        # Install with pip/uv from local path
        temp_dir = await self._clone_repository(source.location, source.tag or source.branch)
        result = await self.installer._install_package(temp_dir, None)
        return result["success"]

class PathSourceHandler(PluginSourceHandler):
    async def install(self, source: PluginSource, config: PluginConfig) -> bool:
        if config.auto_install:
            # Install in development mode
            result = await self.installer._install_package(source.location, None, dev_mode=True)
            return result["success"]
        return True  # Skip install for local development
    
    async def load_module(self, source: PluginSource, config: PluginConfig) -> ModuleType:
        # Direct filesystem loading (existing filesystem plugin mechanism)
        return await self._load_from_filesystem(Path(source.location))
```

### Phase 4: Dependency Resolution and Caching

**Add intelligent dependency management:**

```python
class PluginDependencyResolver:
    def __init__(self):
        self.dependency_graph = {}
        self.installation_cache = {}
    
    async def resolve_dependencies(self, plugins: list[PluginConfig]) -> list[PluginConfig]:
        """Resolve plugin dependencies and return installation order"""
        # Build dependency graph
        # Detect circular dependencies  
        # Return topologically sorted list
        
    async def install_with_caching(self, plugin: PluginConfig) -> bool:
        """Install plugin with caching to avoid duplicate installs"""
        cache_key = self._generate_cache_key(plugin)
        if cache_key in self.installation_cache:
            return self.installation_cache[cache_key]
        
        result = await self._install_plugin(plugin)
        self.installation_cache[cache_key] = result
        return result
```

### Phase 5: Backwards Compatibility

**Maintain compatibility with existing entry point plugins:**

```python
class BackwardCompatibilityLayer:
    async def migrate_entry_point_config(self, config: PluginConfig) -> PluginConfig:
        """Migrate old-style config to new format"""
        if not config.source and config.package:
            # Auto-detect source from package name
            if self._is_pypi_package(config.package):
                config.source = f"pypi:{config.package}"
            elif self._is_installed_locally(config.package):
                config.source = "entry_point"  # Use legacy mechanism
        
        return config
    
    def supports_legacy_entry_points(self) -> bool:
        """Check if system should fall back to entry points"""
        return os.getenv("AGENTUP_LEGACY_PLUGINS", "true").lower() == "true"
```

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Extend PluginConfig model with source configuration
- [ ] Add source parsing utilities
- [ ] Create plugin source handler interface
- [ ] Update configuration validation

### Phase 2: Core Handlers (Week 3-4)  
- [ ] Implement PyPISourceHandler (leveraging existing installer)
- [ ] Implement PathSourceHandler (leveraging existing filesystem loading)
- [ ] Implement GitSourceHandler
- [ ] Add source handler registry

### Phase 3: Integration (Week 5-6)
- [ ] Create UnifiedPluginManager
- [ ] Integrate with existing PluginRegistry
- [ ] Add dependency resolution
- [ ] Implement installation caching

### Phase 4: User Experience (Week 7-8)
- [ ] Add `agentup plugin install` command for auto-updating agentup.yml
- [ ] Add `agentup sync` command for installing all configured plugins
- [ ] Enhance `agentup run` to auto-install missing plugins
- [ ] Add progress indicators and better error messages

### Phase 5: Advanced Features (Week 9-10)
- [ ] Plugin version constraints and conflict resolution
- [ ] Plugin update management (`agentup plugin update`)
- [ ] Plugin environment isolation (optional virtual environments)
- [ ] Plugin registry integration for discovery

## Benefits of this Approach

### Developer Experience
- **Portable Configurations**: Share complete agent setups via version control
- **Zero Setup Time**: `agentup run` installs everything needed
- **Environment Consistency**: Same plugins, same versions, everywhere
- **Development Workflow**: Mix local development plugins with published ones

### Operations Benefits  
- **Reproducible Deployments**: Configuration defines exact plugin versions
- **Easy Rollbacks**: Version control plugin configurations
- **Dependency Clarity**: All dependencies explicit in configuration
- **CI/CD Integration**: Automated testing with exact plugin versions

### Ecosystem Growth
- **Lower Barrier to Entry**: No need to understand Python packaging
- **Plugin Discovery**: Built-in registry integration
- **Version Management**: Automatic updates and conflict resolution

## Technical Considerations

### Security
- **Trust Verification**: Extend existing trust system to all source types
- **Sandboxing**: Consider plugin isolation for untrusted sources
- **Audit Trail**: Log all plugin installations and sources

### Performance
- **Lazy Loading**: Only load plugins when needed
- **Parallel Installation**: Install multiple plugins concurrently
- **Caching**: Cache installations to avoid redundant work

### Compatibility
- **Entry Point Support**: Maintain existing entry point mechanism
- **Migration Path**: Automatic detection and migration of old configs
- **Gradual Adoption**: Both systems can coexist

## Risks and Mitigations

### Risk 1: Installation Complexity
**Mitigation**: Leverage existing SecurePluginInstaller, add comprehensive testing

### Risk 2: Dependency Hell
**Mitigation**: Implement proper dependency resolution, clear error messages

### Risk 3: Security Concerns
**Mitigation**: Extend existing trust verification, add source validation

### Risk 4: Performance Impact
**Mitigation**: Intelligent caching, lazy loading, parallel execution

## Success Metrics

- **Developer Adoption**: % of projects using agentup.yml plugin management
- **Setup Time**: Time from `git clone` to `agentup run` working
- **Plugin Discovery**: Number of plugins published with source info
- **Error Reduction**: Decrease in plugin-related support issues

## Conclusion

Moving plugin management to agentup.yml configuration is not only feasible but would significantly improve the AgentUp developer experience. The existing plugin architecture provides a solid foundation, and the phased implementation approach minimizes risk while maintaining backward compatibility.

The key insight is that AgentUp already has most of the infrastructure needed - secure installation, plugin loading, configuration management, and trust verification. The main work is creating a unified interface that can handle multiple plugin sources while maintaining the security and reliability of the current system.

This change would position AgentUp as a truly Docker-like AI agent platform where configurations are portable, deployments are reproducible, and the developer experience is frictionless.