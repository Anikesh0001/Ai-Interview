# InterviewForge developer commands. Requires Python 3.11+ and Node 20+.
# Prefer a Python with prebuilt wheels for every dependency (3.12/3.13/3.11); override with `make install PY=...`.
PY ?= $(shell command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3)
VENV := backend/.venv
# Always run tools as `python -m <tool>`: venv console scripts hard-code the venv's absolute path in their
# shebang and break if the project folder is moved; the venv's python itself keeps working.
VPY := $(abspath $(VENV))/bin/python

.PHONY: help install venv dev backend frontend test test-backend test-frontend e2e lint format typecheck build fixtures serve docker clean

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-15s %s\n", $$1, $$2}'

venv: ## Create backend/.venv, or rebuild it if it is missing, broken or too old
	@if $(VPY) -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then \
		echo "Using existing virtualenv ($$($(VPY) --version))"; \
	else \
		echo "Creating virtualenv with $(PY)"; \
		$(PY) -m venv --clear $(VENV) || { \
			echo ""; echo "Could not create a virtualenv. On Debian/Ubuntu install the venv package, e.g.:"; \
			echo "  sudo apt install python3-venv   (or python3.12-venv)"; exit 1; }; \
	fi

install: venv ## Install backend (venv) and frontend dependencies + Playwright browser
	$(VPY) -m pip install -q --upgrade pip
	$(VPY) -m pip install -q -r backend/requirements-dev.txt
	cd frontend && npm ci
	cd frontend && npx playwright install chromium

dev: ## Run backend + frontend with hot reload
	./scripts/dev.sh

backend: ## Run only the API on :8000
	cd backend && $(VPY) -m uvicorn app.main:app --reload --port 8000

frontend: ## Run only the Vite dev server on :5173
	cd frontend && npx vite

test: test-backend test-frontend ## Run unit + API + frontend tests

test-backend: ## pytest (unit + API), deterministic TEST_MODE
	cd backend && $(VPY) -m pytest

test-frontend: ## Vitest component tests
	cd frontend && npx vitest run

e2e: ## Playwright end-to-end tests (starts its own servers in TEST_MODE)
	cd frontend && npx playwright test

lint: ## Ruff + ESLint + Prettier check
	cd backend && $(VPY) -m ruff check app tests && $(VPY) -m ruff format --check app tests
	cd frontend && npx eslint . && npx prettier --check "src/**/*.{ts,tsx,css}" "e2e/**/*.ts"

format: ## Auto-format backend and frontend
	cd backend && $(VPY) -m ruff format app tests && $(VPY) -m ruff check --fix app tests
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}" "e2e/**/*.ts"

typecheck: ## TypeScript type check
	cd frontend && npx tsc -b

build: ## Production build of the frontend (served by the backend afterwards)
	cd frontend && npm run build

serve: build ## Single-process mode: backend serves the built frontend on :8000
	cd backend && $(VPY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000

fixtures: ## Regenerate binary test fixtures (PDF/DOCX/scanned/corrupt)
	$(VPY) scripts/generate_fixtures.py

docker: ## Build and run with Docker Compose (Ollama on the host)
	docker compose up --build

clean: ## Remove build artefacts and caches (keeps your data)
	rm -rf frontend/dist frontend/test-results frontend/playwright-report backend/.pytest_cache backend/.ruff_cache data/e2e
