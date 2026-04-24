# Commander Dashboard — Complete System Audit

**Generated**: 2026-04-02
**Purpose**: Full documentation for new agents + gap identification + consistency plan

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Backend: Models](#2-backend-models)
3. [Backend: Services](#3-backend-services)
4. [Backend: Background Jobs](#4-backend-background-jobs)
5. [Backend: API Endpoints](#5-backend-api-endpoints)
6. [Backend: Process Manager](#6-backend-process-manager)
7. [Frontend: Pages](#7-frontend-pages)
8. [Frontend: Chat System](#8-frontend-chat-system)
9. [Frontend: AMV (Multi-View)](#9-frontend-amv)
10. [Frontend: Component Library](#10-frontend-component-library)
11. [Context & Enrichment Pipeline](#11-context--enrichment-pipeline)
12. [Agent Context Queue](#12-agent-context-queue)
13. [Data Flow Diagrams](#13-data-flow-diagrams)
14. [Critical Bugs & Broken Flows](#14-critical-bugs--broken-flows)
15. [Gaps & Missing Features](#15-gaps--missing-features)
16. [Consistency Issues](#16-consistency-issues)
17. [Recommended Fix Priority](#17-recommended-fix-priority)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Next.js 15 + React 19 + TypeScript + Tailwind)    │
│ Port 3000                                                    │
├─────────────────────────────────────────────────────────────┤
│ Pages: Dashboard, Agents, Multi-View, Context, WX, G4,     │
│        Jobs, Temporal, Review, Warnings, Settings, Sync     │
│ Components: ChatView, JiraSummary, OpenMRs, SlackSummary,   │
│            ContextPanel, AgentRow, AMV views (4 modes)      │
│ State: URL params, localStorage, sessionStorage, React      │
│ Data: usePoll hook (30s-1h intervals) + WebSocket           │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│ Backend (FastAPI + SQLAlchemy async)                         │
│ Port 9000                                                    │
├─────────────────────────────────────────────────────────────┤
│ API: 40 routers, 28 mounted                                 │
│ Services: 58 modules                                        │
│ Jobs: 25 scheduled (APScheduler)                            │
│ Process Manager: per-turn claude CLI invocation             │
│ Context Injection: JIRA + Slack auto-prepend                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ PostgreSQL (localhost:9432/planet_ops)                       │
│ 23 tables, ~1.3M rows                                       │
│ Key tables: agents, jira_issues, slack_threads,             │
│            entity_links, pagerduty_incidents,               │
│            agent_context_queue, work_contexts               │
└─────────────────────────────────────────────────────────────┘
```

**Key External Systems:**
- Claude Code CLI (`claude -p --resume`)
- Slack API + launchd sync (10min)
- JIRA API (via `jira-py`)
- PagerDuty API
- GitLab API (`glab`)
- Grafana API
- Google Drive (mounted filesystem)

---

## 2. Backend: Models

### Core Models (23 tables)

| Model | Table | Rows | Purpose |
|-------|-------|------|---------|
| Agent | `agents` | ~248 | Claude Code sessions (VS Code + dashboard) |
| AgentContextQueueItem | `agent_context_queue` | ~1 | Durable Slack context queue |
| EntityLink | `entity_links` | ~7.2K | Cross-entity relationships (62 link types) |
| WorkContext | `work_contexts` | varies | Primary work abstraction |
| JiraIssue | `jira_issues` | ~53.6K | Cached JIRA tickets |
| SlackThread | `slack_threads` | ~1M | Cached Slack threads |
| PagerDutyIncident | `pagerduty_incidents` | ~140K | Cached PD incidents |
| GitLabMergeRequest | `gitlab_merge_requests` | varies | Cached MRs |
| GitBranch | `git_branches` | varies | Branch tracking |
| Worktree | `worktrees` | varies | Git worktree state |
| GrafanaAlertDefinition | `grafana_alert_definitions` | ~108 | Alert configs |
| InvestigationArtifact | `investigation_artifacts` | varies | Analysis docs |
| GoogleDriveDocument | `google_drive_documents` | varies | Drive files |
| WarningEvent | `warning_events` | varies | Incident predictions |
| Summary | `summaries` | varies | AI-generated summaries |

### Agent Model (Key Fields)

```
id, claude_session_id, project, status (live|idle|dead),
managed_by (vscode|dashboard), title, first_prompt,
working_directory, git_branch, worktree_path, jira_key,
message_count, total_tokens, num_prompts,
created_at, last_active_at, hidden_at,
context_id (FK → work_contexts)
```

### EntityLink Model

```
from_type, from_id → to_type, to_id
link_type (62 enum values)
source_type: manual | inferred | imported | agent | url_extracted
confidence_score: 0.0-1.0
status: confirmed | suggested | rejected | stale
```

---

## 3. Backend: Services

### Critical Services

| Service | File | Purpose |
|---------|------|---------|
| ProcessManager | `process_manager.py` | Claude CLI session lifecycle |
| ContextResolverService | `context_resolver.py` | Resolve work contexts from any entity |
| AgentContextQueueService | `agent_context_queue.py` | Durable context queue management |
| AgentService | `agent_service.py` | Agent discovery, sync, status |
| EntityLinkService | `entity_link.py` | Create/manage entity relationships |
| SlackThreadService | `slack_thread_service.py` | Slack thread parsing, cross-ref detection |
| EntityEnrichmentService | `entity_enrichment.py` | Pattern detection (7 entity types) |
| SessionReader | `session_reader.py` | Parse Claude JSONL session files |
| WorktreeService | `worktree_service.py` | Git worktree management |
| SlackService | `slack_service.py` | Slack channel sync, message retrieval |

### Entity Detection Patterns (entity_enrichment.py)

| Entity | Regex Pattern | Example |
|--------|--------------|---------|
| JIRA | `[A-Z][A-Z0-9]+-\d+` | COMPUTE-1234 |
| PagerDuty | URL + `PD-[A-Z0-9]{6,}` | PD-ABC123 |
| Slack | `planet-labs.slack.com/archives/...` | Thread URL |
| GitLab MR | URL + `MR !?\d+` | !847 |
| Grafana | `planet.grafana.net/d/[id]/` | Dashboard |
| Google Docs | `docs.google.com/.../d/[id]` | Document |

---

## 4. Backend: Background Jobs

### 25 Scheduled Jobs

| Job | Frequency | Purpose |
|-----|-----------|---------|
| `jira_sync` | 15m | Sync JIRA cache |
| `warning_monitoring` | 5m | Monitor warning channels (near-real-time) |
| `git_scanner` | 30m | Scan git repos for branches/worktrees |
| `pagerduty_incident_sync` | 30m | Sync PD incidents (7 days) |
| `gitlab_mr_sync` | 30m | Sync GitLab MRs |
| `gitlab_mr_jira_linking` | 30m | Link MRs to JIRA |
| `incident_spider` | 30m | Spider incident references |
| `slack_thread_sync` | 1h | Sync Slack threads from JIRA descriptions |
| `slack_thread_enrichment` | 1h | Create EntityLinks for Slack threads |
| `jira_enrichment` | 1h | Enrich JIRA tickets |
| `link_inference` | 1h | Infer entity links |
| `pagerduty_enrichment` | 1h | Enrich PD references |
| `artifact_indexing` | 1h | Index investigation artifacts |
| `artifact_jira_linking` | 1h | Link artifacts to JIRA |
| `grafana_alert_sync` | 1h | Sync alert definitions |
| `alert_jira_linking` | 1h | Link alerts to JIRA |
| `project_doc_sync` | 1h | Sync project docs |
| `project_doc_linking` | 1h | Link projects to entities |
| `url_extraction` | 1h | Extract URLs from chats |
| `skill_suggestion_refresh` | 2h | Refresh skill suggestions |
| `context_queue_cleanup` | 6h | TTL cleanup for context queue |
| `escalation_metrics_update` | 6h | Update escalation prediction models |
| `health_audit` | 6h | System health audit |
| `google_drive_sync` | 6h | Sync Google Drive files |
| `google_drive_jira_linking` | 6h | Link Drive docs to JIRA |

---

## 5. Backend: API Endpoints

### Key Routers

| Router | Prefix | Key Endpoints |
|--------|--------|---------------|
| agents | `/api/agents` | GET list, POST spawn, POST chat, WS stream, POST stop/resume, GET history, POST summarize, POST extract-urls, GET context-queue, PATCH update |
| contexts | `/api/contexts` | POST resolve/jira/{key}, POST resolve/chat/{id}, POST resolve/branch/{id}, GET {id} |
| jira | `/api/jira` | GET ticket/{key}, GET search, GET summary, GET my-tickets |
| slack | `/api/slack` | GET teams, GET messages, POST sync, POST summarize |
| slack_threads | `/api/slack/threads` | POST parse-jira/{key}, POST parse-url, GET threads, GET threads/{id}, POST refresh |
| mrs | `/api/mrs` | GET list, GET details, POST approve, POST review |
| worktrees | `/api/worktrees` | GET list, POST create |

---

## 6. Backend: Process Manager

### Per-Turn Architecture

Each user message spawns a new process:
```bash
claude -p --output-format stream-json --verbose \
  [--model sonnet|opus|haiku] \
  [--session-id UUID | --resume UUID] \
  "message text"
```

### Context Injection Pipeline

```
User message
  → _inject_jira_context()    # "[Context: You are working on JIRA ticket X...]"
  → _inject_slack_context()   # "[Slack Context: N new messages...]" (drains queue)
  → process_manager.send_message()
  → claude CLI subprocess
```

### Idle Hook

After each turn completes:
```
session.is_processing = False
  → broadcast "idle" status to WebSocket
  → asyncio.create_task(_deliver_queued_context())
     → if queue not empty, auto-send context turn
```

---

## 7. Frontend: Pages

| Route | Page | Key Components |
|-------|------|----------------|
| `/` | Dashboard | DashboardGrid, SlackSummary, OpenMRs, JiraSummary, WXDeployments |
| `/agents` | Agent List | AgentRow, ChatSidebar (docked), SpawnAgentDialog, filters |
| `/agents/{id}/chat` | Full Chat | ChatView (fullscreen) |
| `/multiview` | AMV | 4 view modes (tiled/stacked/tabs/floating), AgentWindow |
| `/context/{id}` | Work Context | ContextPanel (JIRA, chats, PD, Grafana, MRs, artifacts) |
| `/context/jira/{key}` | JIRA Context | ContextPanel (resolved from JIRA key) |
| `/wx`, `/g4`, `/jobs` | Project | ProjectPage wrapper + ProjectAgents |
| `/temporal` | Temporal | KeyHealth, UnansweredSlack, TemporalJira, TemporalMRs |
| `/review` | MR Review | MRAgentPane, MRCenterPane |
| `/warnings` | Predictions | WarningMonitor, PredictionAccuracy, EscalationTrends |
| `/sync` | Data Sync | Sync status dashboard |
| `/settings` | Settings | Terminal app preference |

---

## 8. Frontend: Chat System

### 7 Chat Surfaces (all built on ChatView)

| Surface | Component | Spawns? | Streaming? | Unique Feature |
|---------|-----------|:-------:|:----------:|----------------|
| Agent Sidebar | ChatSidebar | No | Yes | Dock/undock |
| Agent Modal | ChatModal | No | Yes | Breakout to full page |
| Full Page | ChatView | No | Yes | Max space |
| JIRA Workspace | JiraWorkspace | Yes | Yes | Chat from ticket tab |
| Review Cockpit | MRAgentPane | Yes | Yes | Prompt chips |
| AMV Grid | AgentWindow→ChatView | No | Yes | Multi-agent layout |
| Expandable Row | ChatCard | No | Yes | Inline in agent list |

### ChatView Features

- WebSocket streaming + HTTP fallback
- Message dedup (role + content[:300])
- Message management: pin, collapse, resize, filter (user/claude/tools/thinking)
- JIRA card: auto-open, pinnable, resizable
- AI summarization: phrase/short/detailed
- URL extraction → EntityLinks
- VS Code takeover (resume dead sessions)
- Processing indicator (whimsical verbs)
- Slack queue badge (polls 30s)

### ChatInput Features

- Model selector: Opus (violet) / Sonnet (blue) / Haiku (green)
- Message queue: when processing, messages queue with clock icon
- Stop button: red cancel during processing
- Queue display: shows pending messages with remove buttons
- Resume button: for dead VS Code sessions

---

## 9. Frontend: AMV

### 4 View Modes

| Mode | Layout | Features |
|------|--------|----------|
| Tiled | Auto grid (1-3 cols) | Responsive, min-height 350px |
| Stacked | Vertical full-width | 1-2 agents fill viewport, 3+ scroll |
| Tabs | Tab bar + single pane | Rename tabs (long-press), close tabs |
| Floating | Free-positioned | Drag, resize, z-index controls |

### AgentWindow

- Color-coded top border (8 colors)
- Header: title, JIRA badge, branch badge
- Minimize/maximize, color picker, close
- Full ChatView inside (with `hideAMVButton`)
- Session storage persistence

---

## 10. Frontend: Component Library

### Shared UI (shadcn/ui)

Button, Badge, Card, Input, Tabs, Dialog, DropdownMenu, Separator, Toast, Tooltip

### Commander Custom

- `ScrollableCard`: sticky header + scrollable content (used everywhere)
- `ExpandableRow`: click-to-expand rows
- `DashboardGrid`: react-grid-layout wrapper with localStorage persistence

### Integration Components

| Directory | Components |
|-----------|-----------|
| `/context/` | ContextPanel, ContextHeader, HealthStrip, RelationshipList |
| `/pagerduty/` | PagerDutyIncidentsGrid, PagerDutyIncidentCard |
| `/grafana/` | AlertDefinitionCard, AlertSection |
| `/gitlab/` | GitLabMRsGrid, GitLabMRCard, JiraMRsSection |
| `/artifacts/` | ArtifactCard, ArtifactSection |
| `/slack/` | SlackThreadCard, SlackThreadSummary, JiraSlackThreadsSection |
| `/warnings/` | WarningMonitor, PredictionAccuracy, EscalationTrends |

---

## 11. Context & Enrichment Pipeline

### Entity Link Graph

62 link types connecting:
- JIRA issues ↔ Slack threads, PagerDuty incidents, GitLab MRs, Artifacts, Google Docs
- Agents ↔ JIRA issues, branches, worktrees
- PagerDuty ↔ Slack threads
- Grafana alerts ↔ JIRA issues

### Context Resolution

```
Any entity (JIRA key, chat ID, branch ID, worktree ID)
  → ContextResolverService
  → Find/create WorkContext
  → Traverse EntityLinks
  → Return: jira_issues, chats, branches, worktrees,
            pagerduty_incidents, grafana_alerts,
            artifacts, merge_requests, links
```

### Enrichment Pipeline

```
Raw data (JIRA, Slack, PD, GitLab, Grafana, Drive)
  → Sync jobs (ingest to local DB)
  → Enrichment jobs (detect cross-references)
  → Link creation jobs (create EntityLinks)
  → Context resolution (on-demand traversal)
```

---

## 12. Agent Context Queue

### Architecture

```
Slack sync → detect JIRA/MR/branch refs → match to active agents → enqueue

Delivery triggers:
  1. User sends message → drain queue → prepend context
  2. Agent finishes processing → idle hook → auto-deliver
  3. High-priority → immediate delivery (if agent idle)
```

### Matching (Unified)

```python
find_agents_for_thread(thread):
  1. JIRA key: thread.jira_keys ∩ agent.jira_key
  2. MR ref: thread.gitlab_mr_refs → GitLabMergeRequest → agent via jira_key
  3. Branch: scan thread messages for agent.git_branch text
  → Union + deduplicate
```

### Backfill

On `PATCH /agents/{id}` with `jira_key` or `git_branch` change:
- Scan last 14 days of SlackThreads
- Match via unified matcher
- Enqueue last 3 messages per matching thread

---

## 13. Data Flow Diagrams

### Slack → Agent Context

```
Slack channels (10min launchd sync)
  → sync-channel.py → markdown files
  → sync-all-to-db.py (24h) → SlackThread records [⚠️ NO MESSAGES]

JIRA descriptions (1h slack_thread_sync)
  → extract Slack URLs → fetch via Slack API → SlackThread records [✓ WITH MESSAGES]

SlackThread records
  → slack_thread_enrichment (1h) → EntityLinks
  → _enqueue_for_agents → agent_context_queue

agent_context_queue
  → _inject_slack_context (on user message) → prepend to prompt
  → _deliver_queued_context (on agent idle) → auto-send turn
```

### Agent Chat Flow

```
User types message in ChatInput
  → ChatView.handleSend()
  → If processing: queue message
  → If WS connected: ws.sendMessage()
  → Else: api.agentChat(id, message, model)

Backend receives message
  → _inject_jira_context()
  → _inject_slack_context() (drain queue)
  → process_manager.send_message()
  → _run_turn() → spawn claude CLI
  → Stream stdout as JSON → WebSocket broadcast
  → On complete: _deliver_queued_context()

Frontend receives
  → useAgentChat hook (WebSocket)
  → Merge with historicalMessages
  → Deduplicate
  → Render via ChatMessage
```

---

## 14. Critical Bugs & Broken Flows

### BUG 1: Slack Messages Are NULL (CRITICAL)

**Impact**: Entire context matching pipeline is blind to 99.8% of Slack threads.

**Root cause**: `~/tools/db/sync-all-to-db.py` creates SlackThread records with title/metadata but **never populates the `messages` JSONB column**. 667 of 668 recent threads have NULL messages.

**Consequence**:
- `detect_cross_references()` has nothing to scan
- `find_agents_for_thread()` branch matching finds nothing
- `backfill_agent_context()` text scanning fails
- `_inject_slack_context()` returns empty context

**Fix**: Store message text in `messages` JSONB during sync + backfill existing records.

### BUG 2: URL Extraction Services Don't Exist (HIGH)

**Impact**: `POST /agents/{id}/extract-urls` crashes at runtime.

**Root cause**: `url_extraction.py` references `URLExtractor`, `URLClassifier`, `URLHandlerRegistry` — classes that are never defined.

**Fix**: Implement the three service classes or simplify to regex-based extraction.

### BUG 3: PagerDuty ID Parsed as UUID (HIGH)

**Impact**: Context resolution crashes when PagerDuty incidents are linked.

**Root cause**: `context_resolver.py` line 416: `uuid.UUID(link.to_id)` — but PD IDs are strings like "PQRST123", not UUIDs.

**Fix**: Use string IDs consistently (don't parse as UUID).

### BUG 4: Grafana Alert Link Direction May Be Wrong (MEDIUM)

**Impact**: Grafana alerts may not appear in context resolution.

**Root cause**: `context_resolver.py` assumes alerts link FROM themselves TO work, but the actual link direction may be reversed.

**Fix**: Verify and document link direction for all entity types.

---

## 15. Gaps & Missing Features

### Data Gaps

| Gap | Status | Impact |
|-----|--------|--------|
| Slack `messages` NULL | Not fixed | Blocks all Slack matching |
| Slack `gitlab_mr_refs` NULL | Not fixed | MR refs in Slack invisible |
| No channel-based matching | Not implemented | Agent on "wx" doesn't see #wx-dev activity |
| No environment/service name matching | Not implemented | "wx-dev-02" never matches |
| No semantic relevance | Not implemented | Only literal string matching |
| JIRA comments not scanned | TODO in code | Misses references in comments |

### Feature Gaps

| Gap | Status | Impact |
|-----|--------|--------|
| Human vs bot signal classification | Not implemented | Bot noise overwhelms |
| Cross-source deduplication | Not implemented | Same event appears multiple times |
| Queue compaction/summarization | Not implemented | Queue grows unbounded |
| Thread state extraction | Not implemented | Raw messages, no status tracking |
| MR/branch lifecycle events | Not implemented | No awareness of merge/pipeline events |
| Entity alias system | Not implemented | Services/environments not mapped |

### UI Gaps

| Gap | Status |
|-----|--------|
| HealthStrip visual rendering | Field exists, UI not rendering |
| v2_docs integration | Stub method, not connected |
| Agent audit system | Fields exist, no implementation |
| Summary generation | Model exists, generation incomplete |

---

## 16. Consistency Issues

### Naming Inconsistencies

| Issue | Examples |
|-------|---------|
| Mixed ID types | EntityLink uses string IDs, ContextResolver tries to parse as UUID |
| Mixed timestamp handling | Some use `datetime.utcnow()` (naive), some use `datetime.now(timezone.utc)` (aware) |
| Inconsistent link direction | No documentation of which entity is "from" vs "to" |

### Architecture Inconsistencies

| Issue | Details |
|-------|---------|
| Two Slack ingestion paths | `sync-all-to-db.py` (bulk, no messages) vs `slack_thread_sync` (API, with messages) — different data quality |
| Context injection in 2 places | HTTP chat (agents.py) and WebSocket (agents.py WS handler) — duplicated logic |
| Agent matching in 2 places | `find_agents_for_jira_key` (simple) and `find_agents_for_thread` (unified) — old callers may use simple version |
| Multiple polling patterns | Frontend uses `usePoll` hook, but some components use raw `setInterval` |

### Dead Code / Unused

| Item | Location |
|------|----------|
| `LinkType.PROJECT_CONTEXT` | Defined but never created |
| `LinkStatus.STALE` | Defined but never set |
| `WorkContext.health_status` | Computed but never displayed |
| Many Phase 1 Agent fields | `external_chat_id`, `workspace_or_source`, `generation_index`, etc. — added but unused |

---

## 17. Recommended Fix Priority

### P0 — CRITICAL (Blocks core functionality)

1. **Fix `sync-all-to-db.py` Slack messages** — populate `messages` JSONB + `gitlab_mr_refs`
2. **Backfill existing threads** — SQL update for last 14 days
3. **Fix PagerDuty ID parsing** — string not UUID in context_resolver.py

### P1 — HIGH (Functional gaps)

4. **Implement URL extraction services** — URLExtractor, URLClassifier, URLHandlerRegistry
5. **Add channel-based matching** — agent project → channels mapping
6. **Document link direction** — create reference table for all 62 link types
7. **Fix context resolver link traversal** — validate direction for all entity types

### P2 — MEDIUM (Quality improvements)

8. **Unify timestamp handling** — all `datetime.now(timezone.utc)`
9. **Remove dead code** — unused Phase 1 fields, unused LinkTypes
10. **Human vs bot classification** — filter Slack bot noise
11. **Queue compaction** — summarize when queue > 10 items
12. **Cross-source deduplication** — detect same event across Slack/MR/PD

### P3 — LOW (Future enhancements)

13. **Semantic relevance scoring** — LLM-based message relevance
14. **Entity alias system** — map services/environments to agents
15. **MR/branch lifecycle events** — push pipeline/merge events to queue
16. **Thread state extraction** — track resolution status
17. **Health strip rendering** — visual indicators in UI
