# Planet Commander — Onboarding Guide

Step-by-step setup for a new developer or agent. After completing this guide you'll have Planet Commander running locally with a seeded database and all integrations documented.

---

## Prerequisites

Install these before starting:

| Tool | Version | Install | Verify |
|------|---------|---------|--------|
| Docker Desktop | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) | `docker --version` |
| Node.js | ≥18 | `brew install node` | `node --version` |
| Python | ≥3.13 | `brew install python` | `python3 --version` |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| Git | Any | Pre-installed on macOS | `git --version` |
| GitLab SSH | — | SSH key added to [code.earth.planet.com](https://hello.planet.com/code/-/user_settings/ssh_keys) | `ssh -T git@code.earth.planet.com` |

---

## Quick Start (Automated)

```bash
git clone https://github.com/aaryno/planet-commander.git
cd planet-commander
make bootstrap
```

This runs `scripts/bootstrap.sh` which:
1. Checks all prerequisites
2. Clones `aaryn/tools` and `aaryn/slack-tools` to `~/tools/`
3. Copies `.env.example` → `.env`
4. Installs frontend (npm) and backend (uv) dependencies
5. Starts PostgreSQL via Docker
6. Runs database migrations (Alembic)
7. Seeds the database with canonical labels, project links, and default layout

After bootstrap completes, start the app:

```bash
make start
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:9000
- API Docs: http://localhost:9000/docs

---

## Manual Setup (Step by Step)

Use this if the bootstrap script fails or you want to understand each step.

### 1. Clone the repo

```bash
git clone https://github.com/aaryno/planet-commander.git
cd planet-commander
```

### 2. Clone tools repos

Planet Commander reads from shared tooling repos for Slack sync, GitLab wrappers, and database utilities. These are mounted into Docker or referenced by the backend at runtime.

```bash
# Main tools repo
git clone git@code.earth.planet.com:aaryn/tools.git ~/tools

# Slack tools (separate repo, lives inside ~/tools/)
git clone git@code.earth.planet.com:aaryn/slack-tools.git ~/tools/slack
```

If these directories already exist, pull latest:

```bash
git -C ~/tools pull
git -C ~/tools/slack pull
```

### 3. Environment file

```bash
cp .env.example .env
```

Edit `.env` if you need to override defaults. Most values work out of the box for local development.

### 4. Install dependencies

```bash
# Frontend
cd frontend && npm install && cd ..

# Backend
cd backend && uv sync && cd ..
```

### 5. Start the database

```bash
docker compose up -d postgres
```

Wait for it to be ready:

```bash
until docker compose exec postgres pg_isready -U planet_ops; do sleep 1; done
```

### 6. Run migrations and seed

```bash
cd backend
uv run alembic upgrade head    # Apply all migrations
uv run python -m app.seed      # Seed canonical data
cd ..
```

### 7. Start the app

```bash
make start
```

Or start services individually:

```bash
make start-backend    # http://localhost:9000
make start-frontend   # http://localhost:3000
```

---

## Running Modes

Planet Commander supports three running modes:

### Native (recommended for development)

```bash
make start
```

Backend and frontend run directly on your machine. Best for debugging and agent process spawning.

### Docker (all services containerized)

```bash
make dev
```

Everything in Docker. Frontend at `:9300`, backend at `:9000`. Postgres at `:9432`.

### Hybrid (recommended for macOS with Docker Desktop)

```bash
make dev-local          # Postgres + Frontend in Docker
make dev-local-backend  # Backend native (separate terminal)
```

Backend runs natively (needed for spawning Claude Code processes), database and frontend run in Docker.

---

## Optional Integrations

None of these are required. The app runs without them — features that depend on them return empty results.

### Grafana (pipeline metrics, heartbeat dashboard)

```bash
# Option A: environment variable
export GRAFANA_API_TOKEN=your-token-here

# Option B: file
echo "your-token-here" > ~/.config/grafana-token

# Option C: macOS Keychain
security add-generic-password -s grafana-api-token -a "$USER" -w "your-token-here"
```

### PagerDuty (incident tracking)

```bash
echo "your-pd-token" > ~/.config/pagerduty-token
```

### JIRA (ticket summaries, sync)

Create `~/.jira/config`:

```json
{
  "host": "https://hello.planet.com/jira",
  "token": "your-jira-pat",
  "project": "COMPUTE"
}
```

### GitLab (MR reviews, CI status)

```bash
glab auth login --hostname hello.planet.com
```

### Slack (thread analysis, summaries)

Configure `~/tools/slack/slack-config.json` with your Slack API token. See the slack-tools repo README for details.

### Anthropic API (coach sessions, MR audits)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or via macOS Keychain:

```bash
security add-generic-password -s anthropic-api-key -a "$USER" -w "sk-ant-..."
```

---

## Architecture Overview

```
planet-commander/
├── frontend/              # Next.js 15 + React 19 + TypeScript + Tailwind
│   └── src/
│       ├── app/           # Pages (Next.js routing)
│       ├── components/    # UI components (shadcn/ui base)
│       └── lib/           # API client, utilities
│
├── backend/               # FastAPI + SQLAlchemy + PostgreSQL
│   ├── app/
│   │   ├── api/           # Route handlers
│   │   ├── services/      # Business logic
│   │   ├── models/        # SQLAlchemy models
│   │   ├── jobs/          # Background jobs (APScheduler)
│   │   ├── config.py      # Settings (env vars with PLANET_OPS_ prefix)
│   │   ├── database.py    # Async SQLAlchemy engine
│   │   ├── main.py        # App entry + job registration
│   │   └── seed.py        # Database seeding
│   ├── alembic/           # Database migrations
│   └── pyproject.toml     # Python dependencies
│
├── docker-compose.yml     # PostgreSQL + optional frontend/backend containers
├── Makefile               # All dev commands (make help)
├── scripts/
│   └── bootstrap.sh       # First-time setup script
│
├── CLAUDE.md              # Development guide (component rules, patterns)
├── ONBOARDING.md          # This file
└── README.md              # Project overview + dependency reference
```

## External Data Sources

The backend reads from several directories on the host:

| Directory | Purpose | Mounted at (Docker) |
|-----------|---------|---------------------|
| `~/tools/` | Sync scripts, CLI wrappers | `/data/tools` |
| `~/tools/slack/` | Slack messages + config | (inside `/data/tools`) |
| `~/.claude/` | Claude Code sessions | `/data/claude` |
| `~/.config/` | Auth tokens (Grafana, PD) | `/data/config` |
| `~/.jira/` | JIRA config | `/root/.jira` |

All are read-only mounts. Missing directories are harmless — features degrade gracefully.

---

## Common Commands

```bash
make help                 # Show all available commands
make start                # Start backend + frontend
make stop                 # Stop everything
make db-migrate           # Run Alembic migrations
make db-seed              # Seed database
make db-reset             # Wipe DB + re-migrate + re-seed
make dev-logs             # Docker logs (all services)
```

---

## Troubleshooting

### Port 9432 already in use

Another PostgreSQL instance is running on that port. Stop it or change the port in `docker-compose.yml`.

### Frontend can't reach backend

Ensure the backend is running on port 9000. Check with `curl http://localhost:9000/docs`.

### Migrations fail

If you get "relation already exists" errors, the database may be out of sync:

```bash
make db-reset    # Wipes DB and re-creates from scratch
```

### Docker Desktop not running

Start Docker Desktop from Applications. The bootstrap script and `docker compose` commands require the Docker daemon.

### SSH access denied to code.earth.planet.com

Ensure your SSH key is added to your GitLab profile at:
https://hello.planet.com/code/-/user_settings/ssh_keys

---

## Next Steps After Setup

1. **Explore the API**: Open http://localhost:9000/docs — interactive Swagger UI
2. **Read the dev guide**: [CLAUDE.md](./CLAUDE.md) — component rules, patterns, architecture
3. **Check dependencies**: [README.md](./README.md) — full dependency reference
4. **Add integrations**: Configure tokens above as needed for your workflow
