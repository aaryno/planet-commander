# Makefile Targets Reference

## Development Modes

### Docker Development
```bash
make dev              # Build and start all services in Docker
make dev-build        # Build Docker images
make dev-up           # Start services
make dev-down         # Stop services
make dev-logs         # View all logs
```

### Local Development (Recommended for macOS)
```bash
make dev-local        # Start postgres + frontend in Docker
make dev-local-backend # Run backend natively (separate terminal)
make dev-local-down   # Stop local development
```

**Why local development?**
- Backend runs natively, allowing it to spawn Claude processes
- Better performance on macOS
- Easier debugging

## Database Management

```bash
make db-migrate       # Run database migrations (works in both modes)
make db-seed          # Seed database with initial data
make db-reset         # Reset database (drop volumes and reseed)
```

## New: Migration & Restart Workflow

### migrate-and-restart
Run database migrations and restart local services in one command:
```bash
make migrate-and-restart
```

Equivalent to:
```bash
make db-migrate
make restart-local
```

### restart-local
Restart both backend and frontend (local mode):
```bash
make restart-local
```

### restart-backend-local
Restart only the backend:
```bash
make restart-backend-local
```

### restart-frontend-local
Restart only the frontend:
```bash
make restart-frontend-local
```

## Service URLs (Local Mode)

- **Frontend**: http://localhost:9300
- **Backend**: http://localhost:9000
- **PostgreSQL**: localhost:9432

## Logs

Logs are written to `/tmp/` when running locally:
- Backend: `/tmp/dashboard-backend.log`
- Frontend: `/tmp/dashboard-frontend.log`

```bash
tail -f /tmp/dashboard-backend.log
tail -f /tmp/dashboard-frontend.log
```

## Agent Management

```bash
make agents-sync      # Sync agent data from database
make processes-sync   # Sync process status (macOS)
```

## Testing

```bash
make test             # Run backend tests
```

## First Time Setup

```bash
make setup            # Build, start, and seed database
```

## Common Workflows

### After updating backend code
```bash
make restart-backend-local
```

### After updating frontend code
```bash
make restart-frontend-local
```

### After adding a database migration
```bash
make migrate-and-restart
```

### After pulling changes that include migrations
```bash
make migrate-and-restart
```

### Full restart of local environment
```bash
make dev-local-down
make dev-local
# In separate terminal:
make dev-local-backend
```
