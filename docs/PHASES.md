# Planet Ops Dashboard - Phase Overview

## Phase 0: Environment Setup [DONE]

Setup the development environment and toolchain.

- [x] Docker Compose (PostgreSQL 16 + Backend + Frontend)
- [x] Backend: FastAPI + uv + SQLAlchemy + Alembic + asyncpg
- [x] Frontend: Next.js 15 + React 19 + Tailwind + shadcn/ui
- [x] All services on 9xxx ports (9432, 9000, 9300)
- [x] Makefile for dev workflow

## Phase 1: Skeleton [DONE]

Full app shell - navigable but empty.

- [x] Sidebar nav (Dashboard, WX, G4, Jobs, Temporal, Agents, Settings)
- [x] Dashboard grid with 7 CardShell placeholders
- [x] 4 project pages with ProjectPage component + links dropdowns
- [x] Agents page with search + filter UI (empty)
- [x] Settings page with label taxonomy display
- [x] 10 backend API routers with stub responses
- [x] All database models + initial migration
- [x] Seed data: 26 labels, 31 project links, default layout

## Phase 2: Agent Discovery + Chat [DONE]

The core differentiating feature. See [PHASE2.md](./PHASE2.md) for detailed plan.

**Backend**:
- [x] `session_reader.py` - Parse sessions-index.json + JSONL conversation files
- [x] `worktree_service.py` - Git worktree detection + branch matching
- [x] `agent_service.py` - Agent sync, list, title cleaning
- [x] Real `POST /api/agents/sync` - Discovers 95 sessions
- [x] Real `GET /api/agents` - List with project/status filters
- [x] Real `GET /api/agents/{id}/history` - Parsed chat history with expand support

**Frontend**:
- [x] `AgentStatusBadge` - Live/Idle/Dead colored badges
- [x] `AgentRow` - Full agent display with metadata + labels + Chat button
- [x] `ChatMessage` - Single message with expandable tool calls + thinking
- [x] `ChatHistory` - Scrollable conversation with auto-scroll
- [x] `ChatModal` - Full modal with header, scroll area, expand toggle
- [x] `ProjectAgents` - Per-project agent list with 30s polling
- [x] Agents page with project/status filters, search, sync button
- [x] Wired into ProjectPage and Agents page

## Phase 3: Agent Actions [NEXT]

Interactive agent management.

- [ ] Chat input: Send messages to live agents via stdin relay
- [ ] Stop: Kill agent process + stop dev services (Tilt, etc.)
- [ ] Delete worktree: `git worktree remove` with confirmation
- [ ] Agent commands: /clear, /compact, /quit via stdin
- [ ] Spawn: Create new agent dialog
- [ ] Resume: Restart dead sessions with --resume
- [ ] Label management: Add/remove labels from agents

## Phase 4: Open MRs Card

GitLab merge request integration.

- [ ] `gitlab_service.py` wrapping `glab mr list` for team repos
- [ ] OpenMRs card: age, commits, author, reviewer, ticket link
- [ ] "Review" action triggering Claude auto-review
- [ ] 2-minute polling interval

## Phase 5: Remaining Data Cards

Populate the dashboard grid with real data.

- [ ] Slack Summary card (wraps `~/tools/slack/`)
- [ ] JIRA Summary card (wraps `~/tools/jira/`)
- [ ] On-Call card (PagerDuty REST API)
- [ ] Docs Search card (Google Drive local mount)
- [ ] Traffic Overview card (Grafana REST API → Recharts)
- [ ] Workload Scatter Plot (queue size vs latency)

## Phase 6: Project Full Pages

Rich project-specific pages replacing the placeholder ProjectPage.

- [ ] Per-project agents panel (already from Phase 2)
- [ ] Project-specific metrics panels
- [ ] Project-specific data cards
- [ ] Full hamburger menus with all links (git, slack, grafana, jira, docs, runbook)

## Phase 7: Management Interface

CRUD operations from the dashboard.

- [ ] JIRA: Create/update/transition tickets
- [ ] GitLab: Post review comments, approve MRs
- [ ] PagerDuty: Acknowledge, escalate, resolve incidents

## Phase 8: Intelligence Layer

Claude API-powered enrichment.

- [ ] Slack sentiment analysis
- [ ] MR auto-review generation with auto-post option
- [ ] Traffic pattern summarization
- [ ] JIRA ticket summarization
- [ ] Agent session summarization
