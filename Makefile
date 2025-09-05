.PHONY: install run test clean lint format setup

# Installation
install:
	pip install -r config/requirements.txt

install-dev:
	pip install -r config/requirements.txt
	pip install pytest pytest-asyncio black flake8 mypy

# Running
run:
	python main.py

run-dev:
	python main.py --debug

# Testing
test:
	python -m pytest tests/ -v

test-coverage:
	python -m pytest tests/ --cov=src --cov-report=html

# Code Quality
lint:
	flake8 src/ tests/
	mypy src/

format:
	black src/ tests/ main.py

format-check:
	black --check src/ tests/ main.py

# Setup
setup:
	python setup.py install

setup-dev:
	python setup.py develop

# Database
migrate:
	python scripts/migrations.py
	python scripts/fullclient_migrations.py

migrate-sessions:
	python scripts/migrate_to_session_backup.py

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf build/ dist/ *.egg-info/

# Docker
docker-build:
	docker build -t telegram-account-manager .

docker-run:
	docker run --env-file config/.env telegram-account-manager