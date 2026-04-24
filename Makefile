.PHONY: help bootstrap start start-backend start-frontend stop dev dev-up dev-down dev-logs dev-build dev-local dev-local-up dev-local-backend dev-local-down db-migrate db-seed db-reset agents-sync test setup migrate-and-restart restart-local restart-backend-local restart-frontend-local

# First-time setup — clones tools, installs deps, creates DB, seeds
bootstrap:
	@bash scripts/bootstrap.sh

# Show available commands
help:
	@echo "Planet Commander - Quick Reference"
	@echo ""
	@echo "Quick Start (Native - No Docker):"
	@echo "  make start          - Start backend (port 9000) + frontend (port 3000) together"
	@echo "  make start-backend  - Start backend only on port 9000"
	@echo "  make start-frontend - Start frontend only on port 3000"
	@echo "  make stop           - Stop all running services"
	@echo ""
	@echo "Docker Mode:"
	@echo "  make dev            - Build and start all services in Docker"
	@echo "  make dev-local      - Start Postgres+Frontend in Docker, backend native"
	@echo "  make dev-down       - Stop Docker services"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate     - Run database migrations"
	@echo "  make db-seed        - Seed database with test data"
	@echo "  make db-reset       - Reset database (wipes all data)"
	@echo ""
	@echo "URLs:"
	@echo "  Backend:   http://localhost:9000"
	@echo "  API Docs:  http://localhost:9000/docs"
	@echo "  Frontend:  http://localhost:3000 (native) or :9300 (Docker)"
	@echo "  Database:  postgresql://postgres:postgres@localhost:9432/planet_ops"

# Start both backend and frontend (native, no Docker)
start:
	@echo "Starting Planet Commander..."
	@echo ""
	@echo "Backend:  http://localhost:9000"
	@echo "API Docs: http://localhost:9000/docs"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	@echo "Press Ctrl+C to stop both services"
	@echo ""
	@trap 'kill 0' EXIT; \
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload & \
	cd frontend && npm run dev & \
	wait

# Start backend only (native)
start-backend:
	@echo "Starting backend on http://localhost:9000"
	@echo "API Docs: http://localhost:9000/docs"
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload

# Start frontend only (native)
start-frontend:
	@echo "Starting frontend on http://localhost:3000"
	cd frontend && npm run dev

# Stop all services (native + Docker)
stop:
	@echo "Stopping all services..."
	-@pkill -f "uvicorn app.main:app" 2>/dev/null || true
	-@pkill -f "next dev" 2>/dev/null || true
	-@lsof -ti:9000 | xargs kill -9 2>/dev/null || true
	-@lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	-@docker compose down 2>/dev/null || true
	@echo "All services stopped"

# Start everything (build + up)
dev: dev-build dev-up
	@echo "Planet Ops Dashboard running:"
	@echo "  Frontend: http://localhost:9300"
	@echo "  Backend:  http://localhost:9000"
	@echo "  Postgres: localhost:9432"

# Build containers
dev-build:
	docker compose build

# Start all services
dev-up:
	docker compose up -d
	@echo "Waiting for services..."
	@until docker compose exec postgres pg_isready -U planet_ops > /dev/null 2>&1; do sleep 1; done
	@echo "All services ready."

# Stop all services
dev-down:
	docker compose down

# --- Local development mode (backend on host, postgres+frontend in Docker) ---

# Start local development (recommended for macOS)
dev-local:
	@echo "Starting local development mode..."
	@echo "  - PostgreSQL + Frontend in Docker"
	@echo "  - Backend running natively on macOS"
	@echo ""
	@$(MAKE) dev-local-up
	@echo ""
	@echo "Now run in a separate terminal:"
	@echo "  make dev-local-backend"
	@echo ""
	@echo "This allows the backend to spawn Claude processes."

# Start only postgres + frontend (for local backend mode)
dev-local-up:
	docker compose up -d postgres frontend
	@echo "Waiting for postgres..."
	@until docker compose exec postgres pg_isready -U planet_ops > /dev/null 2>&1; do sleep 1; done
	@echo "✓ PostgreSQL ready at localhost:9432"
	@echo "✓ Frontend running at http://localhost:9300"

# Run backend locally on host (separate terminal)
dev-local-backend:
	cd backend && ./run-local.sh

# Stop local development
dev-local-down:
	docker compose down

# View logs (all services)
dev-logs:
	docker compose logs -f

# View logs (specific service)
logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

logs-db:
	docker compose logs -f postgres

# Database management
db-migrate:
	@if docker compose ps backend | grep -q Up; then \
		docker compose exec backend uv run alembic upgrade head; \
	else \
		cd backend && uv run alembic upgrade head; \
	fi

db-seed:
	docker compose exec backend uv run python -m app.seed

db-reset:
	docker compose down -v
	@$(MAKE) dev-up
	@sleep 2
	@$(MAKE) db-seed

# Agent management
agents-sync:
	curl -s -X POST http://localhost:9000/api/agents/sync | python3 -m json.tool

# Process sync (for agent status detection on macOS)
processes-sync:
	python3 scripts/sync-processes.py

processes-sync-loop:
	@echo "Starting process sync loop (Ctrl+C to stop)..."
	@scripts/sync-processes-loop.sh

# Rebuild a specific service
rebuild-%:
	docker compose build $*
	docker compose up -d $*

# Testing
test:
	docker compose exec backend uv run pytest

# Setup (first time)
setup: dev-build dev-up
	@sleep 3
	@$(MAKE) db-seed
	@echo "Setup complete!"
	@echo "  Frontend: http://localhost:9300"
	@echo "  Backend:  http://localhost:9000"
	@echo "  Postgres: localhost:9432"

# --- Migration and Restart Workflow ---

# Migrate database and restart local services
migrate-and-restart: db-migrate restart-local
	@echo "✓ Migration complete and services restarted"

# Restart both backend and frontend (local mode)
restart-local: restart-backend-local restart-frontend-local
	@echo "✓ Backend running on http://localhost:9000"
	@echo "✓ Frontend running on http://localhost:9300"

# Restart only backend (local mode)
restart-backend-local:
	@echo "Stopping backend..."
	@lsof -ti:9000 | xargs kill -9 2>/dev/null || true
	@sleep 1
	@echo "Starting backend..."
	@cd backend && nohup ./run-local.sh > /tmp/dashboard-backend.log 2>&1 &
	@sleep 3
	@tail -3 /tmp/dashboard-backend.log

# Restart only frontend (local mode)
restart-frontend-local:
	@echo "Stopping frontend..."
	@lsof -ti:9300 | xargs kill -9 2>/dev/null || true
	@sleep 1
	@echo "Starting frontend on port 9300..."
	@cd frontend && nohup sh -c 'PORT=9300 npm exec next dev --turbopack' > /tmp/dashboard-frontend.log 2>&1 &
	@sleep 4
	@tail -3 /tmp/dashboard-frontend.log
