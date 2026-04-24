# Planet Ops Dashboard - Quickstart

## For New Claude Sessions

When starting a new Claude Code session to work on the dashboard:

```
Read ~/claude/dashboard/docs/STATUS.md for current status.
Read ~/claude/dashboard/docs/PHASES.md for the phase overview.
Read the specific phase doc (e.g., PHASE2.md) for detailed implementation plan.
Read ~/claude/dashboard/docs/ARCHITECTURE.md for system architecture.
```

## Starting the App

```bash
cd ~/claude/dashboard

# Build and start (first time or after Dockerfile changes)
make dev

# Just start (containers already built)
docker compose up -d

# Seed database (first time only, or after db-reset)
make db-seed
```

## Service URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:9300 |
| Backend API | http://localhost:9000 |
| API Docs (Swagger) | http://localhost:9000/docs |
| PostgreSQL | `psql -h localhost -p 9432 -U planet_ops planet_ops` |

Password: `planet_ops_local`

## Common Commands

```bash
make dev          # Build + start everything
make dev-down     # Stop everything
make dev-logs     # Tail all logs
make logs-backend # Backend logs only
make logs-frontend # Frontend logs only
make db-seed      # Seed labels + project links
make db-reset     # Drop + recreate + reseed database
make rebuild-backend  # Rebuild just backend
make rebuild-frontend # Rebuild just frontend
```

## Development

- **Backend**: Edit files in `backend/app/` - uvicorn auto-reloads
- **Frontend**: Edit files in `frontend/src/` - Next.js hot reloads
- **New migration**: `docker compose exec backend uv run alembic revision --autogenerate -m "description"`
- **Run migration**: `make db-migrate` or auto-runs on backend startup

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/config.py` | All settings (env var overrides with PLANET_OPS_ prefix) |
| `backend/app/main.py` | FastAPI app, CORS, router mounting |
| `backend/app/seed.py` | Database seed data (labels, project links, layout) |
| `backend/app/models/` | SQLAlchemy models |
| `backend/app/api/` | FastAPI route handlers |
| `backend/app/services/` | Business logic (to be built in Phase 2+) |
| `frontend/src/app/` | Next.js pages |
| `frontend/src/components/` | React components |
| `frontend/src/lib/api.ts` | Backend API client |
| `frontend/src/lib/polling.ts` | usePoll() hook |
| `frontend/next.config.ts` | API proxy config (→ backend:9000 in Docker) |

## Docker Notes

- Backend connects to postgres via Docker network (`postgres:5432` internally)
- Frontend proxies `/api/*` to backend via Docker network (`backend:9000` internally)
- Host paths are mounted read-only into backend at `/data/*`
- Environment variables with `PLANET_OPS_` prefix override config.py defaults
