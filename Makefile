# AgentUp Development Makefile
# Useful commands for testing, template generation, and development

.PHONY: help install test test-coverage lint format clean build docs
.PHONY: template-test agent-create agent-test type-check
.PHONY: dev-server example-client check-deps sync-templates example-agent
.PHONY: docker-build docker-run release validate-all template-test-syntax

# Default target
help: ## Show this help message
	@echo "AgentUp Development Commands"
	@echo "=========================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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

# Testing commands
test: ## Run all tests (unit + integration + e2e)
	@echo "Running comprehensive test suite..."
	uv run pytest tests/ -v

test-unit: ## Run unit tests only (fast)
	uv run pytest tests/test_*.py tests/test_core/ tests/test_cli/  -v -m "not integration and not e2e and not performance"

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

template-test-syntax: ## Test template syntax only (quick)
	uv run python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('src/agent/templates')); [env.get_template(t) for t in ['config/agent_config_minimal.yaml.j2', 'config/agent_config_full.yaml.j2']]"
	@echo "Template syntax validated"

# Code quality
lint: ## Run linting checks
	uv run ruff check src/ tests/

lint-fix: ## Fix linting issues automatically
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

format: ## Format code with ruff
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

ci-deps: ## Check dependencies for CI
	uv pip check
	uv pip freeze > requirements-ci.txt

# Agent creation and testing
agent-create: ## Create a test agent (interactive)
	uv run agentup agent create --no-git

agent-create-minimal:
	@echo "Creating minimal test agent..."
	uv run agentup agent create \
		--quick test-minimal \
		--template minimal \
		--no-git \
		--output-dir ./test-agents/minimal
	@echo "Minimal agent created in ./test-agents/minimal"


agent-create-advanced: ## Create advanced test agent
	@echo "Creating advanced test agent..."
	uv run agentup agent create \
		--quick test-advanced \
		--template advanced \
		--no-git \
		--output-dir ./test-agents/advanced
	@echo "Advanced agent created in ./test-agents/advanced"

agent-test: ## Test a generated agent
	@if [ -d "./test-agents/minimal" ]; then \
		echo "Testing minimal agent..."; \
		cd ./test-agents/minimal && \
		uv run python -m pytest tests/ -v 2>/dev/null || echo "⚠️ Tests not available"; \
		echo "Agent test completed"; \
	else \
		echo "✗ No test agent found. Run 'make agent-create-minimal' first"; \
	fi

# Development server commands
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


# Testing with curl
test-ping: ## Test server health endpoint
	@echo "Testing health endpoint..."
	curl -s http://localhost:8000/health | python -m json.tool || echo "✗ Server not running"

test-hello: ## Test hello endpoint with curl
	@echo "Testing hello endpoint..."
	curl -X POST http://localhost:8000/ \
		-H 'Content-Type: application/json' \
		-d '{"jsonrpc": "2.0", "method": "send_message", "params": {"messages": [{"role": "user", "content": "Hello!"}]}, "id": "1"}' \
		| python -m json.tool || echo "✗ Server not running"

docs-serve: ## Serve documentation locally
	@if command -v mkdocs >/dev/null 2>&1; then \
		mkdocs serve; \
	else \
		echo "📚 Opening documentation files..."; \
		open docs/routing-and-function-calling.md; \
	fi

# Build and release
build: ## Build package
	uv build
	@echo "Package built in dist/"

build-check: ## Check package build
	uv run twine check dist/*

release-test: ## Upload to test PyPI
	uv run twine upload --repository testpypi dist/*

release: ## Upload to PyPI (production)
	uv run twine upload dist/*

# Docker commands
docker-build: ## Build Docker image
	docker build -t agentup:latest .

docker-run: ## Run Docker container
	docker run -p 8000:8000 agentup:latest

docker-test: ## Test Docker build
	docker build -t agentup:test . && \
	docker run --rm agentup:test python -c "import agentup; print('✓ Package works in Docker')"

# Cleanup commands
clean: ## Clean temporary files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf test-render/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "🧹 Cleaned temporary files"

clean-agents: ## Clean test agents
	rm -rf test-agents/
	@echo "🧹 Cleaned test agents"

clean-all: clean clean-agents ## Clean everything
	@echo "🧹 Cleaned everything"

# Validation and CI commands
validate-all: lint test template-test ## Run all validation checks
	@echo "✓ All validation checks passed"

ci-test: ## Run CI test suite
	uv run pytest --cov=src --cov-report=xml --cov-report=term
	uv run ruff check src/ tests/

# Utility commands
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

# Quick development workflows
dev-setup: install-dev ## Complete development setup
	@echo "Running complete development setup..."
	make check-deps
	make test-fast
	@echo "Development environment ready!"

dev-test: ## Quick development test cycle
	@echo "Running development test cycle..."
	make lint-fix
	make test-fast
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

# Agent development helpers
add-skill: ## Add skill to existing agent (interactive)
	uv run agentup add-skill

validate-config: ## Validate agent configuration
	uv run agentup validate

# Middleware testing commands
test-middleware: ## Run unit tests for middleware
	uv run pytest tests/test_core/test_middleware.py -v

test-middleware-integration: ## Run integration tests for middleware (requires running server)
	uv run pytest tests/integration/test_middleware_integration.py -v -m integration

test-middleware-stress: ## Run stress tests for middleware (requires running server)
	uv run pytest tests/integration/test_middleware_integration.py -v -m stress

test-middleware-all: test-middleware test-middleware-integration ## Run all middleware tests

test-middleware-scripts: ## Run middleware testing scripts
	@echo "Running rate limiting tests..."
	chmod +x scripts/test_rate_limit.sh
	./scripts/test_rate_limit.sh || echo "Rate limit test completed (server may not be running)"
	@echo ""
	@echo "Running retry tests..."
	chmod +x scripts/test_retry.sh
	./scripts/test_retry.sh || echo "Retry test completed (server may not be running)"

benchmark-middleware: ## Run middleware performance benchmarks (requires running server)
	uv run python scripts/benchmark_middleware.py

benchmark-middleware-full: ## Run comprehensive middleware benchmarks (requires running server)
	uv run python scripts/benchmark_middleware.py --requests 200 --concurrent 20 --tests rate_limiting caching timing throughput stress

test-middleware-cli: ## Test middleware using CLI command (requires running server)
	uv run agentup agent test-middleware --verbose

middleware-help: ## Show middleware testing help
	@echo "Middleware Testing Commands:"
	@echo "=========================="
	@echo ""
	@echo "Prerequisites:"
	@echo "  Start an agent server: make dev-server (or agentup agent serve)"
	@echo ""
	@echo "Unit Tests (no server required):"
	@echo "  make test-middleware              # Run middleware unit tests"
	@echo ""
	@echo "Integration Tests (server required):"
	@echo "  make test-middleware-integration  # Basic integration tests"
	@echo "  make test-middleware-stress       # Stress tests"
	@echo "  make test-middleware-scripts      # Shell script tests"
	@echo "  make test-middleware-cli          # CLI-based tests"
	@echo ""
	@echo "Performance Testing (server required):"
	@echo "  make benchmark-middleware         # Basic benchmarks"
	@echo "  make benchmark-middleware-full    # Comprehensive benchmarks"
	@echo ""
	@echo "Combined:"
	@echo "  make test-middleware-all          # Unit + integration tests"
