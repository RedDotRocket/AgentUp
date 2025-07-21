# Installation Guide

Get AgentUp installed and configured on your system.

!!! Prerequisites
    - **Python 3.10 or higher** - Check with `python --version`
    - **pip** package manager - Usually included with Python
    - **uv** - If you're building from source, plan to contribute etc
    - **Git** (recommended) - For cloning examples and contributing

### Supported Platforms
  - **Linux** (Ubuntu 20.04+, CentOS 8+, others)
  - **macOS** (10.15+)
  - **Windows** (10, 11)

### Installation Methods

=== "pip install"

    ```bash
    pip install agentup
    ```
=== "git clone (uv)"

    ```bash
    git clone https://github.com/RedDotRocket/AgentUp.git
    cd AgentUp

    # Create virtual environment
    uv sync --active

    # Install in development mode (omit `e` for fixed install)
    pip install -e .
    ```

### Verify Installation

```bash
# Check AgentUp version
agentup --version
```

<div class="next-page-cta">
    <div class="next-page-content">
        <span class="next-page-label">Next Step</span>
        <a href="../first-agent" class="next-page-link">
            <span class="next-page-title">First Agent</span>
            <span class="next-page-arrow">→</span>
        </a>
    </div>
</div>
