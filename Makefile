PYTHON ?= python
NPM ?= npm
BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.DEFAULT_GOAL := help

.PHONY: install uninstall clean dev backend frontend lint build test help

install:
	@echo "Installing AXI Semantic Layer..."
	@echo "→ Upgrading pip and build tools..."
	$(PYTHON) -m pip install --upgrade pip hatchling
	@echo "→ Installing backend package (axi-semantic)..."
	$(PYTHON) -m pip install -e backend
	@echo "→ Installing CLI package (axi-cli)..."
	$(PYTHON) -m pip install -e axi-cli
	@echo "→ Installing frontend dependencies..."
	cd frontend && $(NPM) install
	@echo "✓ Installation complete!"
	@echo ""
	@echo "Available commands:"
	@echo "  axi          - Run the AXI CLI"
	@echo "  axi-api      - Start the backend API server"
	@echo "  make dev     - Start both backend and frontend in dev mode"

dev:
	BACKEND_HOST=$(BACKEND_HOST) BACKEND_PORT=$(BACKEND_PORT) FRONTEND_PORT=$(FRONTEND_PORT) bash scripts/dev.sh

backend:
	cd backend && $(PYTHON) -m uvicorn axi.api.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

frontend:
	cd frontend && $(NPM) run dev -- --host --port $(FRONTEND_PORT)

lint:
	cd frontend && $(NPM) run lint

build:
	cd frontend && $(NPM) run build

uninstall:
	@echo "Uninstalling AXI packages..."
	-$(PYTHON) -m pip uninstall -y axi-cli axi-semantic axi-monorepo
	@echo "✓ Uninstall complete!"

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	cd frontend && rm -rf dist node_modules/.vite 2>/dev/null || true
	@echo "✓ Clean complete!"

test:
	@echo "Running backend tests..."
	cd backend && $(PYTHON) -m pytest tests/ -v
	@echo "Running frontend tests..."
	cd frontend && $(NPM) test

help:
	@echo "AXI Semantic Layer - Development Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install     - Install all packages (backend, CLI, frontend)"
	@echo "  make uninstall   - Uninstall AXI packages"
	@echo "  make clean       - Clean build artifacts"
	@echo ""
	@echo "Development:"
	@echo "  make dev         - Start backend and frontend in dev mode"
	@echo "  make backend     - Start only the backend server"
	@echo "  make frontend    - Start only the frontend dev server"
	@echo ""
	@echo "Quality:"
	@echo "  make lint        - Run linter on frontend"
	@echo "  make test        - Run all tests"
	@echo "  make build       - Build frontend for production"
	@echo ""
	@echo "CLI Commands (after install):"
	@echo "  axi              - Run the AXI CLI"
	@echo "  axi-api          - Start the backend API server"
