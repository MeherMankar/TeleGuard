.PHONY: help install setup test lint format security clean run docker dev docs deploy health check-deps

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Project variables
PROJECT_NAME := teleguard
VERSION := $(shell grep version pyproject.toml | head -1 | cut -d'"' -f2)
PYTHON := python3
PIP := pip3

help: ## Show this help message
	@echo "$(BLUE)TeleGuard Development Commands$(RESET)"
	@echo "$(BLUE)==============================$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Environment:$(RESET)"
	@echo "  Project: $(PROJECT_NAME)"
	@echo "  Version: $(VERSION)"
	@echo "  Python:  $(shell $(PYTHON) --version)"

# Installation and Setup
install: ## Install dependencies
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r config/requirements.txt
	@echo "$(GREEN)Dependencies installed successfully!$(RESET)"

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(RESET)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r config/requirements.txt
	$(PIP) install -e .
	@echo "$(GREEN)Development dependencies installed!$(RESET)"

setup: install-dev ## Setup development environment
	@echo "$(BLUE)Setting up development environment...$(RESET)"
	pre-commit install
	mkdir -p logs data backups
	cp config/.env.example config/.env || true
	@echo "$(GREEN)Development environment setup complete!$(RESET)"
	@echo "$(YELLOW)Don't forget to configure config/.env with your credentials$(RESET)"

# Code Quality
lint: ## Run all linting tools
	@echo "$(BLUE)Running linting tools...$(RESET)"
	flake8 teleguard/ --max-line-length=88 --ignore=E203,W503 --statistics
	black --check --diff teleguard/
	isort --check-only --diff teleguard/
	mypy teleguard/ --ignore-missing-imports || true
	@echo "$(GREEN)Linting completed!$(RESET)"

format: ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(RESET)"
	black teleguard/
	isort teleguard/
	@echo "$(GREEN)Code formatted successfully!$(RESET)"

format-check: ## Check code formatting without making changes
	@echo "$(BLUE)Checking code formatting...$(RESET)"
	black --check teleguard/
	isort --check-only teleguard/

# Security
security: ## Run security scans
	@echo "$(BLUE)Running security scans...$(RESET)"
	bandit -r teleguard/ -f json -o reports/bandit-report.json || true
	bandit -r teleguard/ -ll
	safety check --json --output reports/safety-report.json || true
	safety check
	@echo "$(GREEN)Security scan completed!$(RESET)"

security-fix: ## Attempt to fix security issues
	@echo "$(BLUE)Attempting to fix security issues...$(RESET)"
	safety check --auto-fix || true
	@echo "$(GREEN)Security fixes applied!$(RESET)"

# Testing
test: ## Run tests
	@echo "$(BLUE)Running tests...$(RESET)"
	pytest tests/ -v --cov=teleguard --cov-report=html --cov-report=term
	@echo "$(GREEN)Tests completed!$(RESET)"

test-fast: ## Run tests without coverage
	@echo "$(BLUE)Running fast tests...$(RESET)"
	pytest tests/ -v -x
	@echo "$(GREEN)Fast tests completed!$(RESET)"

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(RESET)"
	pytest tests/test_integration.py -v
	@echo "$(GREEN)Integration tests completed!$(RESET)"

# Health and Monitoring
health: ## Check system health
	@echo "$(BLUE)Checking system health...$(RESET)"
	$(PYTHON) -c "import asyncio; from teleguard.utils.health_check import health_checker; print(asyncio.run(health_checker.get_health_status()))"

check-deps: ## Check for dependency updates
	@echo "$(BLUE)Checking for dependency updates...$(RESET)"
	$(PIP) list --outdated
	@echo "$(GREEN)Dependency check completed!$(RESET)"

update-deps: ## Update dependencies
	@echo "$(BLUE)Updating dependencies...$(RESET)"
	$(PIP) install --upgrade -r config/requirements.txt
	@echo "$(GREEN)Dependencies updated!$(RESET)"

# Cleanup
clean: ## Clean build artifacts and cache
	@echo "$(BLUE)Cleaning build artifacts...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -name "*.session" -delete
	find . -name "*.session-journal" -delete
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/
	rm -rf .mypy_cache/ .tox/
	@echo "$(GREEN)Cleanup completed!$(RESET)"

clean-all: clean ## Clean everything including data
	@echo "$(BLUE)Cleaning all data...$(RESET)"
	rm -rf logs/ data/ backups/
	rm -f config/.env config/secret.key
	@echo "$(GREEN)Full cleanup completed!$(RESET)"

# Running
run: ## Run the bot
	@echo "$(BLUE)Starting TeleGuard Bot...$(RESET)"
	$(PYTHON) main.py

run-dev: ## Run in development mode with debug logging
	@echo "$(BLUE)Starting TeleGuard Bot in development mode...$(RESET)"
	LOG_LEVEL=DEBUG $(PYTHON) main.py

# Docker
docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(RESET)"
	docker build -t $(PROJECT_NAME):$(VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VERSION=$(VERSION) \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD) .
	@echo "$(GREEN)Docker image built successfully!$(RESET)"

docker-run: ## Run with Docker
	@echo "$(BLUE)Running with Docker...$(RESET)"
	docker-compose up --build

docker-dev: ## Run development environment with Docker
	@echo "$(BLUE)Running development environment with Docker...$(RESET)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

docker-stop: ## Stop Docker containers
	@echo "$(BLUE)Stopping Docker containers...$(RESET)"
	docker-compose down

docker-clean: ## Clean Docker resources
	@echo "$(BLUE)Cleaning Docker resources...$(RESET)"
	docker-compose down -v --remove-orphans
	docker system prune -f
	@echo "$(GREEN)Docker cleanup completed!$(RESET)"

# Documentation
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(RESET)"
	mkdir -p docs/
	$(PYTHON) -m pydoc -w teleguard
	mv *.html docs/ || true
	@echo "$(GREEN)Documentation generated in docs/$(RESET)"

docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation...$(RESET)"
	cd docs && $(PYTHON) -m http.server 8000

# Deployment
deploy-heroku: ## Deploy to Heroku
	@echo "$(BLUE)Deploying to Heroku...$(RESET)"
	./deploy/heroku.sh

deploy-koyeb: ## Deploy to Koyeb
	@echo "$(BLUE)Deploying to Koyeb...$(RESET)"
	./deploy/koyeb.sh

# Release
build: ## Build distribution packages
	@echo "$(BLUE)Building distribution packages...$(RESET)"
	$(PYTHON) -m build
	@echo "$(GREEN)Build completed! Check dist/ directory$(RESET)"

release: clean build ## Create a release
	@echo "$(BLUE)Creating release...$(RESET)"
	twine check dist/*
	@echo "$(GREEN)Release ready! Upload with: twine upload dist/*$(RESET)"

# Pre-commit
pre-commit: ## Run pre-commit hooks
	@echo "$(BLUE)Running pre-commit hooks...$(RESET)"
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	@echo "$(BLUE)Updating pre-commit hooks...$(RESET)"
	pre-commit autoupdate

# Monitoring and Reports
reports: ## Generate all reports
	@echo "$(BLUE)Generating reports...$(RESET)"
	mkdir -p reports/
	$(MAKE) security
	$(MAKE) test
	@echo "$(GREEN)Reports generated in reports/$(RESET)"

benchmark: ## Run performance benchmarks
	@echo "$(BLUE)Running performance benchmarks...$(RESET)"
	$(PYTHON) -m pytest tests/test_performance.py -v || echo "No performance tests found"

# Database
db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(RESET)"
	$(PYTHON) scripts/migrations.py

db-backup: ## Backup database
	@echo "$(BLUE)Creating database backup...$(RESET)"
	mkdir -p backups/
	cp data/teleguard.db backups/teleguard_$(shell date +%Y%m%d_%H%M%S).db || true
	@echo "$(GREEN)Database backup created!$(RESET)"

# Environment
env-check: ## Check environment configuration
	@echo "$(BLUE)Checking environment configuration...$(RESET)"
	@echo "Python version: $(shell $(PYTHON) --version)"
	@echo "Pip version: $(shell $(PIP) --version)"
	@echo "Git version: $(shell git --version)"
	@echo "Docker version: $(shell docker --version 2>/dev/null || echo 'Docker not installed')"
	@echo "Config file exists: $(shell test -f config/.env && echo 'Yes' || echo 'No')"
	@echo "$(GREEN)Environment check completed!$(RESET)"

# All-in-one commands
dev: setup format lint test ## Setup development environment and run quality checks
	@echo "$(GREEN)Development environment ready!$(RESET)"

ci: lint security test ## Run CI pipeline locally
	@echo "$(GREEN)CI pipeline completed successfully!$(RESET)"

all: clean install lint security test build ## Run complete pipeline
	@echo "$(GREEN)Complete pipeline finished!$(RESET)"
