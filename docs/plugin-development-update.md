# Plugin Development Update

## Changes Made

We've simplified the plugin development workflow by removing the local `skills/` directory loading mechanism and standardizing on Python's `pip install -e .` for development.

### What Changed

1. **Removed Local Skills Directory Loading**
   - Deleted `_load_local_plugins()` and `_load_local_plugin()` methods from `PluginManager`
   - Removed references to `./skills/` directory from `discover_plugins()`
   - Plugins are now loaded only through Python entry points

2. **Updated Documentation**
   - Modified `docs/plugins/index.md` to show only two plugin discovery methods:
     - Development Mode: `pip install -e .`
     - Production Mode: `pip install package-name`
   - Removed the confusing "copy to skills/" workflow

### Why This Change?

1. **Consistency**: Plugins are always loaded the same way (via entry points), whether in development or production
2. **Standards**: Uses Python's standard development practices (`pip install -e`)
3. **Simplicity**: No ambiguity about file structures or discovery mechanisms
4. **Testing**: Developers test with the exact same loading mechanism that production will use
5. **Dependencies**: Proper dependency resolution during development

### New Development Workflow

```bash
# Create a plugin anywhere
cd ~/my-projects
agentup plugin create weather-plugin

# Navigate to plugin
cd weather-plugin

# Install in development mode
pip install -e .

# Plugin is now available to all agents
# Make changes and they take effect immediately
agentup agent serve
```

### Benefits

- **No special directories**: Work anywhere on your filesystem
- **Standard Python tooling**: Use pip, uv, poetry, etc.
- **Proper isolation**: Each plugin is a proper Python package
- **Live reloading**: Changes take effect without reinstalling
- **Dependency management**: Requirements are properly resolved

### Migration for Existing Users

If you were using the `skills/` directory approach:

```bash
# Old way (no longer supported)
cp -r my-plugin skills/

# New way
cd my-plugin
pip install -e .
```

This change makes AgentUp plugin development more aligned with standard Python practices and removes a source of confusion about plugin loading mechanisms.