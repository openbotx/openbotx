.PHONY: help setup dev-install install build clean clean-venv reset lint format webclient-install webclient-build webclient-dev dev publish-test publish version bump-patch bump-minor bump-major

BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

PACKAGE_NAME := openbotx
VERSION := $(shell uv run python -c "from openbotx.version import __version__; print(__version__)" 2>/dev/null || echo "0.0.0")

help: ## Show this help message
	@echo "$(BLUE)OpenBotX — AI Assistant Platform$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'

# setup

setup: ## First time setup: create venv and install
	@if [ ! -d ".venv" ]; then uv venv .venv; fi
	uv pip install -e ".[dev]"
	@echo "$(GREEN)Setup complete! Run: source .venv/bin/activate$(RESET)"

dev-install: ## Install in editable mode
	uv pip install -e ".[dev]"

install: ## Install package
	uv pip install .

# webclient

webclient-install: ## Install webclient dependencies
	cd webclient && npm install

webclient-build: ## Build webclient for production
	cd webclient && npm run build

webclient-dev: ## Start webclient dev server
	cd webclient && npm run dev

# development

dev: ## Start backend dev server with reload
	uvicorn openbotx.server.app:app --reload --host 0.0.0.0 --port 8000

# build

build: clean webclient-build ## Build the package
	uv run python -m build

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .eggs/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/
	rm -rf openbotx/webclient/

clean-venv: ## Remove virtual environment
	rm -rf .venv/

reset: clean-venv setup ## Reset environment

# code quality

lint: ## Run linter
	uv run ruff check openbotx/

format: ## Format code
	uv run ruff format openbotx/
	uv run ruff check --fix openbotx/

# publishing

publish-test: build ## Publish to TestPyPI
	uv run python -m twine upload --repository testpypi dist/*

publish: build ## Publish to PyPI
	@echo "$(RED)WARNING: Publishing to PyPI!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	uv run python -m twine upload dist/*

# versioning

version: ## Show current version
	@echo "$(VERSION)"

bump-patch: ## Bump patch version
	@uv run python -c "import re; \
		v = '$(VERSION)'.split('.'); \
		v[2] = str(int(v[2]) + 1); \
		new_v = '.'.join(v); \
		content = open('openbotx/version.py').read(); \
		content = re.sub(r'__version__ = \".*\"', f'__version__ = \"{new_v}\"', content); \
		open('openbotx/version.py', 'w').write(content); \
		print(f'Version bumped to {new_v}')"

bump-minor: ## Bump minor version
	@uv run python -c "import re; \
		v = '$(VERSION)'.split('.'); \
		v[1] = str(int(v[1]) + 1); \
		v[2] = '0'; \
		new_v = '.'.join(v); \
		content = open('openbotx/version.py').read(); \
		content = re.sub(r'__version__ = \".*\"', f'__version__ = \"{new_v}\"', content); \
		open('openbotx/version.py', 'w').write(content); \
		print(f'Version bumped to {new_v}')"

bump-major: ## Bump major version
	@uv run python -c "import re; \
		v = '$(VERSION)'.split('.'); \
		v[0] = str(int(v[0]) + 1); \
		v[1] = '0'; \
		v[2] = '0'; \
		new_v = '.'.join(v); \
		content = open('openbotx/version.py').read(); \
		content = re.sub(r'__version__ = \".*\"', f'__version__ = \"{new_v}\"', content); \
		open('openbotx/version.py', 'w').write(content); \
		print(f'Version bumped to {new_v}')"
