# Planet Ops Dashboard - Status Tracker

**Last updated**: 2026-03-02

## Quick Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | DONE | Environment setup (docker, nvm, uv, next.js, shadcn) |
| Phase 1 | DONE | Skeleton (all pages, routes, models, seed data) |
| Phase 2 | DONE | Agent Discovery + Chat (the core feature) |
| Phase 3 | **NEXT** | Agent Actions (chat input, stop, spawn, resume) |
| Phase 4 | --- | Open MRs Card (GitLab integration) |
| Phase 5 | --- | Remaining Data Cards (Slack, JIRA, Grafana, PD) |
| Phase 6 | --- | Project Full Pages (WX, G4, Jobs, Temporal) |
| Phase 7 | --- | Management Interface (JIRA/Git/PD CRUD) |
| Phase 8 | --- | Intelligence Layer (Claude API enrichment) |

## Running the App

```bash
cd ~/claude/dashboard

# Start everything
make dev

# Or step by step
docker compose build
docker compose up -d

# First time only - seed the database and sync agents
make db-seed
curl -X POST http://localhost:9000/api/agents/sync
```

| Service | URL | Port |
|---------|-----|------|
| Frontend | http://localhost:9300 | 9300 |
| Backend API | http://localhost:9000 | 9000 |
| PostgreSQL | localhost:9432 | 9432 |

## What's Built (Phase 0+1+2)

### Infrastructure
- [x] Docker Compose with all 3 services (postgres, backend, frontend)
- [x] All ports on 9xxx range (9432, 9000, 9300)
- [x] Backend hot reload via volume mount + uvicorn --reload
- [x] Frontend hot reload via source mount + next dev
- [x] Alembic migrations auto-run on backend startup
- [x] Makefile with dev, build, logs, seed, reset commands

### Backend (FastAPI on :9000)
- [x] 10 API routers mounted (agents, labels, layout, slack, gitlab, jira, grafana, pagerduty, docs, projects)
- [x] PostgreSQL models: Agent, Label, AgentLabel, AgentArtifact, AgentSearchIndex, DashboardLayout, ProjectLink
- [x] Seed script: 26 canonical labels (5 categories) + 31 project links + default layout
- [x] **session_reader.py**: Parses sessions-index.json + JSONL conversation files
- [x] **agent_service.py**: Agent sync (discover + upsert), list with filters, title cleaning
- [x] **worktree_service.py**: Git worktree detection (14 worktrees across 3 repos) + branch/cwd matching
- [x] **sync_scheduler.py**: Background sync with active (60s) / idle (15m) modes + activity tracking
- [x] Activity tracking middleware (web requests) + agent change detection
- [x] `POST /api/agents/sync` - Discovers 131 sessions from ~/.claude/ (indexed + unindexed JSONL)
- [x] `GET /api/agents?project=wx` - Lists agents with project/status filters
- [x] `GET /api/agents/{id}/history` - Parsed chat history (user prompts + assistant summaries)
- [x] JSONL parsing: filters out tool_result noise, merges consecutive assistant turns
- [x] Title cleaning: strips IDE-injected prefixes, marks IDE-only sessions

### Frontend (Next.js on :9300)
- [x] 7 pages: Dashboard, WX, G4, Jobs, Temporal, Agents, Settings
- [x] Sidebar navigation with project color coding
- [x] CardShell component with collapsible sections + hamburger menus
- [x] ProjectPage with embedded ProjectAgents component
- [x] **AgentStatusBadge**: Live (green pulse) / Idle (yellow) / Dead (gray)
- [x] **AgentRow**: Status, title, labels, branch, worktree, message count, Chat button
- [x] **ChatModal**: Full conversation viewer with expand toggle for thinking/tools
- [x] **ChatHistory**: Scrollable message list with auto-scroll
- [x] **ChatMessage**: User messages + assistant summaries with expandable tool calls
- [x] **ProjectAgents**: Per-project agent list with 30s polling + refresh
- [x] **Agents page**: Global agent list with project/status filters + search + sync button
- [x] Label color system (deterministic category→color mapping)
- [x] usePoll() hook for interval-based data fetching

### Database (PostgreSQL on :9432)
- [x] Initial Alembic migration applied
- [x] All tables created
- [x] Seed data loaded (labels + project links + default layout)
- [x] 131 agent sessions indexed across 5 projects (scans both index + unindexed JSONL files)

### Agent Counts by Project
| Project | Agents |
|---------|--------|
| WX | 56 |
| General | 23 |
| Temporal | 23 |
| G4 | 18 |
| Jobs | 11 |

## What's Next (Phase 3)

Agent Actions - interactive agent management:
- Chat input: Send messages to live agents via stdin relay
- Stop: Kill agent process + stop dev services
- Delete worktree: `git worktree remove` with confirmation
- Agent commands: /clear, /compact, /quit via stdin
- Spawn: Create new agent dialog
- Resume: Restart dead sessions with --resume
- Label management: Add/remove labels from agents

See [PHASES.md](./PHASES.md) for the full roadmap.
