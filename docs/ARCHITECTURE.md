# Planet Ops Dashboard - Architecture

## Overview

A local operations platform for managing Claude Code agents and consolidating operational data across the Planet Compute Platform team's projects (WX, G4, Jobs, Temporal).

## System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│              Next.js Frontend (localhost:9300)               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ │
│  │Dashboard│ │Project │ │ All    │ │Manage  │ │ Settings │ │
│  │  Grid   │ │ Pages  │ │Agents  │ │(JIRA,  │ │ (Layout, │ │
│  │ (Cards) │ │WX/G4/..│ │ View   │ │Git,PD) │ │  Labels) │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └──────────┘ │
│         ↕ HTTP polling (30s-5min)  ↕ Chat via API           │
├─────────────────────────────────────────────────────────────┤
│              FastAPI Backend (localhost:9000)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐ │
│  │ Data APIs │ │  Agent   │ │  Claude  │ │ Session       │ │
│  │ Slack,MR, │ │ Manager  │ │ Enricher │ │ Reader +      │ │
│  │ JIRA,Grfn │ │ + Chat   │ │          │ │ Indexer       │ │
│  └─────┬────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘ │
│        │           │            │                │          │
│  ┌─────▼────┐ ┌────▼─────┐ ┌───▼──────┐ ┌──────▼───────┐ │
│  │ Existing │ │ Claude   │ │ Claude   │ │ ~/.claude/   │ │
│  │ Python   │ │ Code CLI │ │ API      │ │ projects/    │ │
│  │ Tools    │ │ (spawn)  │ │ (Anthro) │ │ (95 sessions)│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘ │
│                    ↕                                        │
│           ┌──────────────┐                                  │
│           │  PostgreSQL  │                                  │
│           │  (Docker)    │                                  │
│           └──────────────┘                                  │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js (App Router) + React | 15 / 19 |
| UI Components | shadcn/ui + Tailwind CSS | v4 |
| Charts | Recharts | 3.x |
| Drag-and-drop | react-grid-layout | 2.x |
| Backend | FastAPI | 0.135+ |
| Python | via uv | 3.13 |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy (async) + Alembic | 2.0 |
| Process mgmt | psutil | 7.x |
| Claude API | anthropic SDK | 0.84+ |

## Docker Compose Services

All services run in Docker Compose with hot reload for development.

| Service | Container | Host Port | Internal Port |
|---------|-----------|-----------|---------------|
| PostgreSQL | planet-ops-db | 9432 | 5432 |
| Backend | planet-ops-backend | 9000 | 9000 |
| Frontend | planet-ops-frontend | 9300 | 3000 |

### Volume Mounts (Backend)

The backend container mounts host directories for access to session data and tools:

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./backend` | `/app` | rw | Source code (hot reload) |
| `~/.claude` | `/data/claude` | ro | Claude Code session data |
| `~/workspaces` | `/data/workspaces` | ro | Git worktrees |
| `~/tools` | `/data/tools` | ro | Existing Python tools |
| `~/claude` | `/data/claude-docs` | ro | Documentation repo |
| `~/.config` | `/data/config` | ro | Auth tokens |

## Directory Structure

```
~/claude/dashboard/
├── docker-compose.yml
├── Makefile
├── docs/                    # Planning & tracking docs
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml       # uv-managed
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py          # FastAPI app + CORS
│   │   ├── config.py        # Settings (env var overrides)
│   │   ├── database.py      # Async SQLAlchemy
│   │   ├── seed.py          # Seed data loader
│   │   ├── models/          # SQLAlchemy models
│   │   ├── api/             # FastAPI routers (10 modules)
│   │   └── services/        # Business logic (to be built)
│   └── tests/
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts       # API proxy to backend
    └── src/
        ├── app/             # Next.js pages (7 routes)
        ├── components/      # UI components
        │   ├── layout/      # Sidebar
        │   ├── cards/       # Dashboard cards
        │   ├── projects/    # Project page components
        │   ├── agents/      # Agent management (Phase 2)
        │   └── ui/          # shadcn/ui primitives
        └── lib/             # API client, types, utilities
```

## Database Schema

### Core Tables

- **agents** - Claude Code sessions (uuid PK, session_id, project, status, title, branch, worktree, timestamps)
- **labels** - Canonical label taxonomy (name, category, color, is_canonical)
- **agent_labels** - M2M linking agents to labels
- **agent_artifacts** - Files/branches/commits created by agents
- **agent_search_index** - Full-text search (tsvector) across session content

### Dashboard Tables

- **dashboard_layouts** - Drag-and-drop grid layout config (JSONB)
- **project_links** - Per-project link registry (git, slack, grafana, jira, docs)

## API Routes

| Prefix | Module | Purpose |
|--------|--------|---------|
| `/api/agents` | agents.py | Agent CRUD, sync, chat, history |
| `/api/labels` | labels.py | Label taxonomy CRUD |
| `/api/layout` | layout.py | Dashboard layout config |
| `/api/slack` | slack.py | Slack message summaries |
| `/api/mrs` | gitlab.py | GitLab merge requests |
| `/api/jira` | jira.py | JIRA tickets + sprint |
| `/api/metrics` | grafana.py | Grafana traffic/workload data |
| `/api/oncall` | pagerduty.py | PagerDuty on-call + incidents |
| `/api/docs` | docs.py | Google Drive doc search |
| `/api/projects` | projects.py | Project link registry |

## Service Integration Map

| Service | Backend Wraps | Polling |
|---------|--------------|---------|
| Claude Sessions | `~/.claude/projects/*/sessions-index.json` + `.jsonl` | 30s |
| Git Worktrees | `git worktree list` across known repos | 1 min |
| Slack | `~/tools/slack/sync-channel.py` | 5 min |
| GitLab MRs | `glab mr list` + `~/tools/glab/` | 2 min |
| JIRA | `~/tools/jira/jira/client.py` (direct import) | 5 min |
| Grafana | REST API + `~/.config/grafana-token` | 30s-5min |
| PagerDuty | REST API + `~/.config/pagerduty-token` | 1 min |
| Google Drive | Local mount scan | On-demand |
| Claude API | `anthropic` Python SDK | On-demand |

## Key Design Decisions

1. **Agents per-project** - Embedded in project cards, not a separate silo
2. **Discover existing sessions** - Retroactively indexes 95+ Claude Code sessions
3. **Chat hides reasoning** - Shows prompts + summaries, expand for full details
4. **Colorful labels** - Deterministic category→color mapping
5. **Wrap existing tools** - Import JIRA/Slack Python clients, never reimplement
6. **JSONL parsing** - Read conversation files directly, no Claude Code API dependency
7. **PostgreSQL FTS** - tsvector is sufficient for local single-user search
8. **Polling not WebSockets** - 30s-5min intervals, simpler to debug
9. **Docker Compose** - All services containerized, 9xxx port range
