# Release Process

This document describes the automated release process for AgentUp, including version management, quality checks, and publishing.

## Overview

AgentUp uses a centralized version management system that eliminates manual version updates across multiple files. The release process is automated through the `scripts/release.py` script, which handles:

- Version updates in `pyproject.toml`
- Synchronization across all configuration files
- Template updates for generated projects
- Quality checks (linting, formatting, type checking, security)
- Test execution
- Git tag creation
- Release preparation

## Version Management Architecture

### Single Source of Truth

The version is defined once in `pyproject.toml`:

```toml
[project]
name = "agentup"
version = "0.5.1"  # Only place version is hardcoded
```

### Centralized Version Reading

All parts of the codebase use the centralized version utility:

```python
from agent.utils.version import get_version

__version__ = get_version()  # Dynamically reads current version
```

The version utility (`src/agent/utils/version.py`) tries multiple sources:
1. **Package metadata** (production/installed mode)
2. **pyproject.toml parsing** (development mode)  
3. **Fallback version** (error conditions)

### Template Integration

All Jinja2 templates use version variables instead of hardcoded values:

```jinja2
dependencies = [
    "agentup>={{ agentup_version }}",  # Automatically current version
]
```

## Release Script Usage

The release script (`scripts/release.py`) provides a comprehensive automated workflow.

### Basic Usage

```bash
# Test a release (safe, no changes made)
python scripts/release.py --version 0.6.0 --dry-run

# Perform actual release
python scripts/release.py --version 0.6.0 --confirm
```

### Command Options

| Option | Description |
|--------|-------------|
| `--version X.Y.Z` | **Required.** New semantic version (e.g., 0.6.0) |
| `--dry-run` | Simulate the release without making changes |
| `--confirm` | Actually perform the release |
| `--skip-tests` | Skip running the test suite |
| `--skip-quality` | Skip quality checks (linting, formatting, etc.) |

### Version Format

Versions must follow [semantic versioning](https://semver.org/) format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

## Release Workflow Steps

The release script performs these steps in order:

### 1. Pre-flight Checks

- Validates version format (must be `X.Y.Z`)
- Checks that new version differs from current
- Verifies git working directory is clean (no uncommitted changes)

### 2. Version Updates

- Updates `version = "X.Y.Z"` in `pyproject.toml`
- Syncs version across all configuration files:
  - `agentup.yml` files
  - Any other YAML configs with version fields

### 3. Configuration Synchronization

The script uses `src/agent/utils/config_sync.py` to update YAML files while preserving:
- Formatting and indentation
- Comments
- Quote style (single/double quotes)

### 4. Quality Checks

Runs comprehensive code quality checks:

```bash
uv run ruff check --fix src/ tests/    # Linting with auto-fix
uv run ruff format src/ tests/         # Code formatting
uv run mypy src/                       # Type checking
uv run bandit -r src/ -ll              # Security scanning
```

### 5. Test Execution

Runs the unit test suite:

```bash
uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/ \
  -v -m "not integration and not e2e and not performance"
```

### 6. Git Tag Creation

Creates an annotated git tag:

```bash
git tag -a v0.6.0 -m "Release version 0.6.0"
```

## Post-Release Steps

After successful release preparation, perform these manual steps:

### 1. Review Changes

```bash
git diff HEAD~1  # Review all changes made by release script
git log --oneline -5  # Review recent commits
```

### 2. Push Git Tag

```bash
git push origin v0.6.0  # Push the release tag
```

### 3. Create GitHub Release

1. Go to GitHub repository releases page
2. Click "Create a new release"
3. Select the pushed tag (v0.6.0)
4. Generate release notes automatically or write custom notes
5. Publish the release

### 4. Build and Publish Package

```bash
# Build distribution packages
python -m build

# Upload to PyPI (requires PyPI credentials)
python -m twine upload dist/*
```

## Configuration File Management

### Automatic Synchronization

The release script automatically finds and updates version fields in:

- `agentup.yml` (main configuration)
- `*/agentup.yml` (nested configurations)
- Any YAML file with a `version:` field

### Manual Synchronization

You can also sync configurations manually:

```python
from agent.utils.config_sync import sync_agentup_yml, find_and_sync_all_configs

# Sync main agentup.yml
sync_agentup_yml()

# Sync all config files in project
results = find_and_sync_all_configs()
print(results)  # Shows which files were updated
```

## Template System Integration

### Project Generation

When creating new agents, templates automatically use the current AgentUp version:

```bash
agentup agent create my-agent
# Generated pyproject.toml will have: agentup>=0.5.1
```

### Plugin Generation

Plugin templates also get the correct version:

```bash
agentup plugin create my-plugin
# Generated files use current AgentUp version automatically
```

### Template Variables

Templates have access to these version-related variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{ agentup_version }}` | Current AgentUp version | `0.5.1` |
| `{{ project_version }}` | Project's own version | `1.0.0` |
| `{{ plugin_version }}` | Plugin's own version | `1.0.0` |

## Testing and Validation

### Version Consistency Tests

Run tests to ensure version consistency:

```bash
# Test version management system
uv run pytest tests/test_version_management.py -v

# Test specific version utility
uv run pytest tests/test_version_management.py::TestVersionUtility -v
```

### Manual Validation

Check version consistency manually:

```python
# All should return the same version
from agent import __version__ as main_version
from agent.security import __version__ as security_version  
from agent.utils.version import get_version

print(f"Main: {main_version}")
print(f"Security: {security_version}")
print(f"Utility: {get_version()}")
```

### CLI Version Check

```bash
agentup --version  # Should show current version
```

## Troubleshooting

### Common Issues

**"Git working directory is not clean"**
- Commit or stash all changes before running release
- Use `git status` to see uncommitted files

**"Version format invalid"**
- Ensure version follows `X.Y.Z` format
- No prefixes like "v" or suffixes like "-alpha"

**"Quality checks failed"**
- Fix linting errors: `uv run ruff check --fix src/ tests/`
- Fix formatting: `uv run ruff format src/ tests/`
- Fix type errors: `uv run mypy src/`

**"Tests failed"**
- Run tests individually to identify failures
- Fix failing tests before proceeding with release

**"Git tag already exists"**
- Delete existing tag: `git tag -d v0.6.0`
- Or choose a different version number

### Recovery

If release fails partway through:

```bash
# Reset pyproject.toml changes
git checkout pyproject.toml

# Reset any config file changes  
git checkout agentup.yml

# Delete created tag if it exists
git tag -d v0.6.0
```

## Version History and Changelog

### Maintaining CHANGELOG.md

While not automated, consider maintaining a `CHANGELOG.md` file following [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [0.6.0] - 2024-01-15

### Added
- New feature descriptions

### Changed  
- Changed feature descriptions

### Fixed
- Bug fix descriptions
```

### Version Semantics

Follow these guidelines for version increments:

- **Patch** (0.5.1 → 0.5.2): Bug fixes, small improvements
- **Minor** (0.5.1 → 0.6.0): New features, significant improvements
- **Major** (0.5.1 → 1.0.0): Breaking changes, major rewrites

## Development Workflow

### Pre-Release Development

1. Work on features in feature branches
2. Merge to main through pull requests
3. Version stays at current release during development

### Release Preparation

1. Ensure all desired features are merged
2. Update documentation if needed
3. Run full test suite
4. Use release script to create release

### Release Cadence

Consider establishing a regular release schedule:
- **Patch releases**: As needed for critical bugs
- **Minor releases**: Monthly or bi-monthly
- **Major releases**: Quarterly or when breaking changes needed

## CI/CD Integration

AgentUp uses automated GitHub Actions workflows for documentation publishing and PyPI releases.

### Documentation Publishing

The documentation build and publishing is automated via `.github/workflows/publish-docs.yml`:

**Triggers:**
- Push to `main` branch with changes to:
  - `docs/**` - Documentation content
  - `mkdocs.yml` - Documentation configuration  
  - `docker/docs/**` - Documentation Docker setup
  - `.github/workflows/publish-docs.yml` - Workflow itself
- Manual workflow dispatch

**Process:**
1. **Build Documentation**: Uses MkDocs with Material theme to build static site
2. **Create Docker Image**: Packages docs into a Docker container
3. **Publish to GHCR**: Pushes to GitHub Container Registry with tags:
   - `docs-latest` (main branch)
   - `docs-{sha}` (commit-specific)
   - `docs-{branch}-{sha}` (branch-specific)

```yaml
# Excerpt from .github/workflows/publish-docs.yml
on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'docker/docs/**'
      - '.github/workflows/publish-docs.yml'
  workflow_dispatch:

jobs:
  build:
    steps:
      - name: Build docs
        run: mkdocs build
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/docs/Dockerfile-docs
          push: true
```

**Access Documentation:**
- Container: `ghcr.io/your-org/agentup:docs-latest`
- The documentation is automatically updated when docs changes are pushed to main

### PyPI Publishing

The PyPI publishing is automated via `.github/workflows/publish.yml`:

**Triggers:**
- GitHub release is published
- Manual workflow dispatch

**Features:**
- **Trusted Publishing**: Uses OpenID Connect (no API tokens required)
- **Attestations**: Creates provenance attestations for security
- **Discord Notifications**: Automatically notifies Discord channel of releases

```yaml
# Excerpt from .github/workflows/publish.yml
on:
  workflow_dispatch:
  release:
    types: [published]

jobs:
  pypi-publish:
    permissions:
      id-token: write  # Required for trusted publishing
    steps:
      - name: Build distributions
        run: python -m build
      - name: Publish package distributions to PyPI
        uses: pypa/gh-action-pypi-publish@v1
        with:
          attestations: true  # Security attestations
```

**Complete Release Flow:**
1. Use release script: `python scripts/release.py --version X.Y.Z --confirm`
2. Push git tag: `git push origin vX.Y.Z`
3. Create GitHub release (triggers PyPI publish automatically)
4. Package is published to PyPI with attestations
5. Discord notification sent to team

### Automated Quality Gates

Set up branch protection rules requiring:
- All tests pass
- All quality checks pass
- Code review approval

This ensures main branch is always release-ready.

### GitHub Actions Integration Example

For a complete automated release, you could create an additional workflow:

```yaml
name: Automated Release
on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Release version (e.g., 0.6.0)'
        required: true
        type: string

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install UV
        run: pip install uv
      
      - name: Run Release Script
        run: |
          python scripts/release.py --version ${{ inputs.version }} --confirm
      
      - name: Push Changes
        run: |
          git push origin main
          git push origin v${{ inputs.version }}
      
      - name: Create GitHub Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: v${{ inputs.version }}
          release_name: Release v${{ inputs.version }}
          generate_release_notes: true
```

### Automated Quality Gates

Set up branch protection rules requiring:
- All tests pass
- All quality checks pass
- Code review approval

This ensures main branch is always release-ready.

## Best Practices

### Before Each Release

- [ ] Review merged pull requests since last release
- [ ] Update documentation for new features
- [ ] Run full test suite locally
- [ ] Test release script with `--dry-run`
- [ ] Verify git working directory is clean

### During Release

- [ ] Use semantic versioning appropriately
- [ ] Review all changes made by release script
- [ ] Test installation of built packages locally
- [ ] Write meaningful release notes

### After Release

- [ ] Monitor for issues in the new release
- [ ] Update any dependent projects
- [ ] Announce release to users
- [ ] Plan next release features

By following this automated release process, AgentUp maintains consistent versioning across all components while minimizing manual errors and effort.