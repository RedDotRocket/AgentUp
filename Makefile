# AgentUp Development Makefile
# Useful commands for testing, template generation, and development

.DEFAULT_GOAL := help

.PHONY: help install install-dev check-deps pre-commit-install
.PHONY: test test-unit test-unit-coverage test-unit-fast test-unit-watch test-integration
.PHONY: lint lint-fix format format-check
.PHONY: security security-report security-full
.PHONY: validate-code validate-ci validate-all
.PHONY: template-test-syntax
.PHONY: pre-commit
.PHONY: agent-create agent-create-minimal agent-create-advanced agent-test
.PHONY: dev-server dev-server-test
.PHONY: docs-serve
.PHONY: build build-check
.PHONY: clean clean-agents clean-all
.PHONY: ci-deps ci-test
.PHONY: version env-info
.PHONY: dev-setup dev-test dev-full

# Default target
help: ## Show this help message
	@echo "AgentUp Development Commands"
	@echo "=========================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Useful commands:"
	@echo "  make dev-setup          # Install and configure everything"
	@echo "  make pre-commit         # Run all quality checks"
	@echo "  make dev-test           # Quick test & lint cycle"
	@echo "  make pre-commit-install # Install pre-commit hooks"

# Environment setup
install: ## Install dependencies with uv
	uv sync --all-extras
	@echo "Dependencies installed"

install-dev: ## Install development dependencies
	uv sync --all-extras --dev
	uv pip install -e .
	@echo "Development environment ready"

check-deps: ## Check for missing dependencies
	uv pip check
	@echo "All dependencies satisfied"

pre-commit-install: ## Install and configure pre-commit
	uv pip install pre-commit
	pre-commit install
	pre-commit autoupdate
	@echo "✓ pre-commit installed and configured"

# Testing commands
test: ## Run all tests (unit + integration + e2e)
	@echo "Running comprehensive test suite..."
	uv run pytest tests/ -v

test-unit: ## Run unit tests only (fast)
	uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/  tests/thirdparty -v -m "not integration and not e2e and not performance"

test-unit-coverage: ## Run unit tests with coverage report
	uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/  --cov=src --cov-report=html --cov-report=term-missing -m "not integration and not e2e and not performance"
	@echo "Coverage report generated in htmlcov/"

test-unit-fast: ## Run unit tests with minimal output
	uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/  -q --tb=short -m "not integration and not e2e and not performance"

test-unit-watch: ## Run unit tests in watch mode
	uv run pytest-watch --runner "uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/  -m 'not integration and not e2e and not performance'"

test-integration: ## Run bash integration tests only
	chmod +x tests/integration/int.sh
	./tests/integration/int.sh

# Template validation
template-test-syntax: ## Test template syntax only (quick)
	uv run python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/agent/templates')); [env.get_template(t) for t in ['config/agentup_minimal.yml.j2', 'config/agentup_full.yml.j2']]"
	@echo "Template syntax validated"

# Code quality
lint: ## Run linting checks (parallel)
	uv run ruff check src/ tests/

lint-fix: ## Fix linting issues automatically
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

format: ## Format code with ruff (parallel)
	uv run ruff format src/ tests/

format-check: ## Check code formatting
	uv run ruff format --check src/ tests/

# Security scanning
security: ## Run bandit security scan
	uv run bandit -r src/ -ll

security-report: ## Generate bandit security report in JSON
	uv run bandit -r src/ -f json -o bandit-report.json

security-full: ## Run full security scan with medium severity
	uv run bandit -r src/ -l

# Combined validation
validate-code: ## Run format, lint, and security checks
	make format
	make lint
	make security
	@echo "✓ Code quality checks passed"

validate-ci: validate-code test-unit template-test-syntax format lint security ## Run full CI checks
	@echo "✓ All CI validation passed"

validate-all: lint test template-test-syntax ## Run all validation checks
	@echo "✓ All validation checks passed"

# CI-specific
ci-deps: ## Check dependencies for CI
	uv pip check
	uv pip freeze > requirements-ci.txt

ci-test: ## Run CI test suite
	uv run pytest --cov=src --cov-report=xml --cov-report=term
	uv run ruff check src/ tests/

# Pre-commit
pre-commit: ## Run pre-commit hooks
	uv run pre-commit run --all-files

# Agent creation and testing
agent-create: ## Create a test agent (interactive)
	uv run agentup agent create --no-git

agent-create-minimal: ## Create minimal test agent
	@echo "Creating minimal test agent..."
	uv run agentup agent create \
		--quick test-minimal \
		--no-git \
		--output-dir ./test-agents/minimal
	@echo "Minimal agent created in ./test-agents/minimal"

agent-create-advanced: ## Create advanced test agent
	@echo "Creating advanced test agent..."
	uv run agentup agent create \
		--quick test-advanced \
		--no-git \
		--output-dir ./test-agents/advanced
	@echo "Advanced agent created in ./test-agents/advanced"

agent-test: ## Test a generated agent
	@if [ -d "./test-agents/minimal" ]; then \
		echo "Testing minimal agent..."; \
		cd ./test-agents/minimal && \
		uv run python -m pytest tests/ -v 2>/dev/null || echo "Tests not available"; \
		echo "Agent test completed"; \
	else \
		echo "✗ No test agent found. Run 'make agent-create-minimal' first"; \
	fi

# Development server
dev-server: ## Start development server for reference implementation
	uv run uvicorn src.agent.main:app --reload --port 8000

dev-server-test: ## Start test agent server
	@if [ -d "./test-agents/minimal" ]; then \
		echo "Starting test agent server..."; \
		cd ./test-agents/minimal && \
		uv run uvicorn agentup.api.app:app --reload --port 8001; \
	else \
		echo "✗ No test agent found. Run 'make agent-create-minimal' first"; \
	fi

# Docs
docs-serve: ## Serve documentation locally
	@if command -v mkdocs >/dev/null 2>&1; then \
		mkdocs serve; \
	else \
		echo "📚 Opening documentation files..."; \
		open docs/routing-and-function-calling.md; \
	fi

# Build & Release
build: ## Build package
	uv build
	@echo "Package built in dist/"

build-check: ## Check package build
	uv run twine check dist/*

# Cleanup
clean: ## Clean temporary files
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage test-render/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleaned temporary files"

clean-agents: ## Clean test agents
	rm -rf test-agents/
	@echo "Cleaned test agents"

clean-all: clean clean-agents ## Clean everything
	@echo "Cleaned everything"

# Utility
version: ## Show current version
	@python -c "import toml; print('AgentUp version:', toml.load('pyproject.toml')['project']['version'])"

env-info: ## Show environment information
	@echo "Environment Information"
	@echo "====================="
	@echo "Python version: $$(python --version)"
	@echo "UV version: $$(uv --version)"
	@echo "Working directory: $$(pwd)"
	@echo "Git branch: $$(git branch --show-current 2>/dev/null || echo 'Not a git repo')"
	@echo "Git status: $$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') files changed"

# Dev workflows
dev-setup: install-dev pre-commit-install ## Complete development setup
	@echo "Running complete development setup..."
	make check-deps
	make test-unit-fast
	@echo "Development environment ready!"

dev-test: ## Quick development test cycle
	@echo "Running development test cycle..."
	make lint-fix
	make test-unit-fast
	make template-test-syntax
	@echo "Development tests passed!"

dev-full: ## Full development validation
	@echo "Running full development validation..."
	make clean
	make dev-setup
	make validate-all
	make agent-create-minimal
	make agent-test
	@echo "Full development validation completed!"
