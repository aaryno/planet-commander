# Planet Commander

All-in-one agent command center for managing cross-project workflows.

## Quick Start

```bash
git clone https://github.com/aaryno/planet-commander.git
cd planet-commander
make bootstrap    # Installs everything, creates DB, seeds data
make start        # Starts backend (9000) + frontend (3000)
```

For detailed step-by-step setup, see **[ONBOARDING.md](./ONBOARDING.md)**.

For development patterns and component rules, see **[CLAUDE.md](./CLAUDE.md)**.

## Prerequisites

### Required

| Dependency | Purpose | Install |
|-----------|---------|---------|
| **Docker** | PostgreSQL database | [docker.com](https://docker.com) |
| **Node.js 18+** | Frontend | `brew install node` |
| **Python 3.11+** | Backend | `brew install python` |
| **Git** | Branch/worktree tracking | Pre-installed on macOS |

### External Services (degraded without, not blocking)

Commander integrates with external services. Each is optional — missing services disable their features gracefully.

| Service | Auth Method | Config Location | Features Affected |
|---------|------------|-----------------|-------------------|
| **Planet Ops DB** | Local PostgreSQL | `docker-compose.yml` (bundled) | Core data storage |
| **JIRA** | Config file | `~/.jira/config` (host, token, project) | Ticket summaries, sync |
| **GitLab** | glab CLI config | `~/.config/glab-cli/config.yml` | MR reviews, CI status |
| **PagerDuty** | Token file | `~/.config/pagerduty-token` | Incident tracking |
| **Grafana** | Env var or token file | `GRAFANA_API_TOKEN` env var, or `~/.config/grafana-token`, or macOS Keychain | Pipeline metrics, dashboards |
| **Slack** | Token file or Keychain | `~/tools/slack/slack-config.json` or macOS Keychain | Thread analysis, summaries |
| **Anthropic API** | Env var or Keychain | `ANTHROPIC_API_KEY` env var or macOS Keychain | Coach sessions, MR audits |
| **Google Cloud** | gcloud CLI | `gcloud auth login` | Infrastructure metrics |

### CLI Tools (optional)

These are needed only for specific features:

| Tool | Features | Install |
|------|----------|---------|
| `glab` | GitLab MR integration | `brew install glab` |
| `kubectl` | WX deployment status | [kubernetes.io](https://kubernetes.io/docs/tasks/tools/) |
| `gcloud` | GCP infrastructure metrics | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| **Claude Code** | Agent spawning from dashboard | [claude.ai/code](https://claude.ai/code) |

### Cross-Repo Data Sources (optional)

Commander reads data from other local repos/directories when available:

| Path | Purpose | Required? |
|------|---------|-----------|
| `~/tools/slack/` | Slack sync scripts + message data | No — Slack features degraded |
| `~/tools/glab/` | glab wrapper scripts | No — raw `glab` CLI works |
| `~/tools/db/` | Database sync scripts | No — background sync disabled |
| `~/.claude/` | Claude Code sessions, skills, hooks | No — agent features degraded |
| `~/claude/projects/` | Project documentation, artifacts | No — artifact indexing disabled |
| `~/code/build-deploy/planet-grafana-cloud-users/` | Grafana alert definitions | No — alert sync disabled |

## Configuration

All backend settings are configurable via environment variables with the `PLANET_OPS_` prefix.

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:

```bash
# Database (defaults work with docker-compose)
PLANET_OPS_DATABASE_URL=postgresql+asyncpg://planet_ops:planet_ops_local@localhost:9432/planet_ops

# Tokens (env vars preferred over file/keychain)
GRAFANA_API_TOKEN=your-token-here
ANTHROPIC_API_KEY=sk-ant-...

# Override any path defaults
PLANET_OPS_WORKSPACES_DIR=~/workspaces
PLANET_OPS_TOOLS_DIR=~/tools
```

## Docker Notes

The `docker-compose.yml` mounts several host directories read-only for the backend container. Missing directories are harmless — features that depend on them will return empty results.

On **Linux**, replace `host.docker.internal` with your host IP or add `--add-host=host.docker.internal:host-gateway` to your Docker run config.

## Project Structure

```
planet-commander/
├── CLAUDE.md              <- Development guide
├── frontend/              # Next.js + React + TypeScript
│   └── src/
│       ├── app/          # Pages (routing)
│       ├── components/
│       │   ├── ui/       # Shared UI primitives
│       │   ├── cards/    # Feature cards
│       │   └── ...
│       └── lib/          # API client
├── backend/               # FastAPI + SQLAlchemy
│   └── app/
│       ├── api/          # Routes
│       ├── services/     # Business logic
│       └── models/       # Database models
└── docker-compose.yml
```

## Stack

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Icons**: Lucide React

## Features

- **Multi-project dashboards**: WX, G4, Jobs, Temporal
- **Agent management**: Session tracking, chat interface
- **JIRA integration**: Ticket summaries, filters
- **GitLab MRs**: Review requests, CI status
- **Real-time data**: Kubernetes deployments, Slack activity
- **Customizable layouts**: Drag-and-drop panels
- **Work context linking**: Entity graph connecting JIRA, PagerDuty, Grafana, artifacts, MRs

## Documentation

- **[CLAUDE.md](./CLAUDE.md)** - Component development guide
- [SCROLLABLE-CARD-COMPONENT.md](./SCROLLABLE-CARD-COMPONENT.md) - Shared scrollable card pattern
- [WX-DEPLOYMENTS-IMPLEMENTATION.md](./WX-DEPLOYMENTS-IMPLEMENTATION.md) - K8s integration example
- [JIRA-SUMMARY-IMPLEMENTATION.md](./JIRA-SUMMARY-IMPLEMENTATION.md) - JIRA filters example
