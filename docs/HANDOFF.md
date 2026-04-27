# Planet Commander — Handoff Document

**Date**: 2026-04-27
**Repo**: `aaryno/planet-commander` (GitHub)
**Local**: `~/code/aaryn/planet-commander/`
**38 commits** since extraction on 2026-04-24

---

## What Was Built

### Repo Extraction & Portability
Commander was extracted from `~/claude/dashboard/` into a standalone GitHub repo. All 44+ hardcoded `/Users/aaryn` paths replaced with `Path.home()` or env vars. Bootstrap script (`make bootstrap`) handles first-time setup: clones tools repos, installs deps, creates DB, seeds.

### Project Generalization
Projects are now a first-class DB entity. Any user or agent can add a project via `POST /api/projects` with repos, JIRA keys, Slack channels, Grafana dashboards, deployment config, and links — all as JSONB fields.

**Key files**:
- `backend/app/models/project.py` — Project model
- `backend/app/api/projects.py` — Full CRUD API
- `frontend/src/components/projects/ProjectDashboard.tsx` — Generic dashboard (replaced WXDashboard)
- `frontend/src/app/projects/[key]/page.tsx` — Dynamic route
- `frontend/src/app/projects/[key]/settings/page.tsx` — Config UI
- `frontend/src/app/projects/new/page.tsx` — Creation wizard
- `docs/project-onboarding.md` — Agent-readable onboarding spec

**Status**: WX, G4, Jobs use ProjectDashboard. Temporal still has custom page (see TODOs).

### Permission Management
Agents spawn with `--permission-mode auto --allowedTools <list>` from `backend/agent-permissions.txt`. When a tool is denied:
1. Backend broadcasts `permission-denied` via WebSocket
2. Frontend shows a dialog with pattern options (exact/wildcard/full tool)
3. User clicks "Add Rule" → backend adds to permissions + auto-resumes all blocked agents

**Key files**:
- `backend/agent-permissions.txt` — Allowed tools list
- `backend/app/api/permissions.py` — CRUD API
- `frontend/src/components/agents/PermissionDialog.tsx` — Denial dialog
- `frontend/src/app/settings/permissions/page.tsx` — Settings editor

### Agent Intelligence
- **Context packs** (`backend/app/services/context_packs.py`): Rich preambles assembled from Project entity, JIRA ticket details, MR metadata, Slack threads. Injected at spawn time.
- **File tracking**: Write/Edit tool calls captured from stream-json, stored as `files_changed` JSONB on Agent model. Backfilled from session JSONL during sync.
- **MR extraction**: GitLab MR URLs extracted from sessions, stored as `mr_references` JSONB. Enriched on-demand from DB with title, diff stats, CI/approval status.
- **Title parsing** (`frontend/src/lib/parse-title.ts`): Strips `[Commander: ...]`, `[Context: ...]` boilerplate from agent titles. Extracts JIRA keys and MR references into clickable badges.

### UI Polish
- Dynamic sidebar nav from `/api/projects`
- Radix Tooltip popovers (replaced browser `title` attributes)
- File changed badges (green=created, blue=edited) on agent rows and chat header
- MR badges with enriched hover popovers (title, diff stats, CI, approval)
- Configurable JIRA label filters + full-text ticket search
- Native OS directory picker for agent spawn dialog

---

## What's Running

```bash
# Start everything
cd ~/code/aaryn/planet-commander
make start          # Backend :9000 + Frontend :3000

# Or separately
make start-backend  # http://localhost:9000
make start-frontend # http://localhost:3000
```

Database: PostgreSQL on `localhost:9432` (docker container `planet-ops-db`, likely already running from previous setup).

---

## Pending Work (Prioritized)

### 1. Backend Services → Project Entity (6-7 hrs)
**Plan**: `docs/TODO-backend-services-generalization.md`

Replace hardcoded project lists so adding a project via API automatically starts scanning its repos, syncing JIRA, and tracking MRs.

| Phase | What | Effort | Impact |
|-------|------|--------|--------|
| **A** | `config_service.get_repos_to_scan()` + `jira_service._default_project()` | 1 hr | New projects auto-scanned |
| **B** | `gitlab_service.PROJECTS` dict + `project_path_map` | 3-4 hrs | MR ops work for any project |
| **C** | Background jobs iterate Project rows | 2 hrs | Full dynamic scanning |

**Start here** — Phase A is low-risk and makes the generalization real.

### 2. Temporal Migration (4-6 hrs)
**Plan**: `docs/TODO-temporal-migration.md`

Convert `TemporalCommandCenter` to use `ProjectDashboard`. Keep 5 Temporal-specific cards as extras, generalize 2, remove 2 (replaced by standard JIRA/MR cards).

**Key decision**: Add `customCards` prop to ProjectDashboard for project-specific cards.

### 3. Slack Summary Overhaul (agent-estimated)
**Plan**: `docs/slack-summary-overhaul-plan.md` (616 lines, agent-generated)

Rich Slack message rendering: markdown, emoji, thread expansion, user detection, filters, search. Currently raw text in a modal.

### 4. Subagent Tracking (agent-estimated)
**Plan**: `docs/subagent-tracking-plan.md` (17K, agent-generated)

Parent/child agent nesting in the UI. `parent_chat_id` FK already exists on Agent model (line 59). Needs: spawn API to pass parent_id, agent list UI to indent children, session discovery to infer relationships.

---

## Database State

```
Projects table: 4 rows (wx, g4, jobs, temporal) + commander
Agents table: ~412 rows, ~107 with files_changed, ~91 with mr_references
Migrations: up to f1a2b3c4 (mr_references on agents)
```

To add a project:
```bash
curl -X POST http://localhost:9000/api/projects -H "Content-Type: application/json" -d '{
  "key": "my-project",
  "name": "My Project",
  "repositories": [{"path": "group/repo", "name": "Main"}],
  "jira_project_keys": ["MYPROJ"]
}'
```

---

## Architecture Quick Reference

```
planet-commander/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes (agents, projects, permissions, fs, jira, slack, ...)
│   │   ├── models/        # SQLAlchemy (Agent, Project, WorkContext, EntityLink, ...)
│   │   ├── services/      # Business logic (context_packs, process_manager, agent_service, ...)
│   │   ├── jobs/          # Background jobs (git_scanner, jira_sync, ...)
│   │   ├── config.py      # Settings (PLANET_OPS_ env prefix)
│   │   └── main.py        # App + job registration
│   ├── agent-permissions.txt  # Allowed tools for spawned agents
│   └── alembic/           # DB migrations
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages (/agents, /projects/[key], /settings, ...)
│   │   ├── components/    # UI (ProjectDashboard, AgentRow, ChatView, PermissionDialog, ...)
│   │   ├── hooks/         # useAgentChat, useDirectoryHistory, useSettings
│   │   └── lib/           # api.ts, parse-title.ts, status-colors.ts
├── docs/                  # Plans and TODOs
├── scripts/bootstrap.sh   # First-time setup
├── CLAUDE.md              # Dev guide
├── ONBOARDING.md          # Setup guide
└── docker-compose.yml     # PostgreSQL + optional services
```

### Key Patterns
- **Project config drives everything**: cards rendered, filters applied, repos scanned
- **Agent spawning**: CLI subprocess via `process_manager.py` with `--permission-mode auto`
- **Context injection**: `context_packs.py` builds preambles from Project + JIRA + MR + Slack
- **Stream-json parsing**: `_run_turn()` captures tool calls, files changed, permission denials
- **Auto-save UI**: Settings pages debounce and save on change (600ms-1s)

### Important Conventions
- `parseTitle()` in `lib/parse-title.ts` — used everywhere titles display, strips context blocks
- Files changed stored as `{path: action}` dict, MR refs as `[{repo, iid, url}]` array
- Badge colors: green=created, blue=edited, violet=MR, amber=JIRA, cyan=commander
