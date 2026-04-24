# Review Page: Pipeline Tab, Agent Spawn Fix, Task Notification Rendering

**Date**: 2026-04-20
**Scope**: Commander Dashboard — Review page (`/review`)
**Status**: Complete, tested against live data

---

## Changes Made

### 1. Pipeline Tab — Hierarchical Stage/Job View

**Problem**: Pipeline tab only showed a single status badge and a link to GitLab. No visibility into which stages/jobs were passing, failing, or skipped.

**Solution**: Full pipeline breakdown with hierarchical stages and jobs.

**Backend** (`backend/app/services/gitlab_service.py`):
- Added `get_mr_pipelines(project, mr_iid)` — fetches all pipelines for an MR via GitLab API (`/merge_requests/{iid}/pipelines`), then fetches jobs for the most recent pipeline (`/pipelines/{id}/jobs?per_page=100`)
- Groups jobs by stage, computes stage-level status rollup (failed > running > pending > manual > skipped > success)
- Returns `{ pipelines: [...], active_pipeline: { ...stages } }`

**Backend** (`backend/app/api/gitlab.py`):
- Added `GET /api/mrs/{project}/{mr_iid}/pipelines` endpoint

**Frontend** (`frontend/src/lib/api.ts`):
- Added types: `PipelineJob`, `PipelineStage`, `PipelineSummary`, `MRPipelinesResponse`
- Added `api.mrPipelines(project, mrIid)` method

**Frontend** (`frontend/src/components/review/MRCenterPane.tsx`):
- New `JobRow` component — status icon, job name (linked to GitLab), allow-failure badge, failure reason, duration, hover "+" button
- New `StageSection` component — collapsible, auto-expanded for failed/running stages, shows passed/failed/skipped counts
- Rewrote `PipelineTab` — shows active pipeline header with status + SHA + "Add to review" button, hierarchical stages, and a "Previous Pipelines" section for older runs
- Added `onAddToReview` prop threading from `MRCenterPaneProps` through to pipeline components

**Frontend** (`frontend/src/app/review/page.tsx`):
- Added `pendingPrompt` state and `handleAddToReview` callback
- Wired `onAddToReview` to `MRCenterPane` and `pendingPrompt`/`onPromptConsumed` to `MRAgentPane`

**Verified**: API returns real data — 6 pipelines, 6 stages, 50 jobs for WX MR !1316.

### 2. Agent Spawn Fix — ChatView Never Rendered After Spawn

**Problem**: After spawning a review agent, the code tried to find it by JIRA key lookup (`api.agentsByJira(jira)`). This failed when:
- No JIRA key was present (lookup skipped entirely, `activeAgent` never set)
- Race condition even with JIRA key (agent not indexed yet)

Result: user saw "Spawning agent..." then nothing. No ChatView, no WebSocket, no streaming.

**Solution** (`frontend/src/components/review/MRAgentPane.tsx`):
- Use the `id` from `agentSpawn` response directly: `const agent = await api.agentDetail(spawnResult.id)`
- Set `activeAgent` from the full `Agent` object, which triggers `ChatView` rendering with WebSocket connection
- Added `pendingPrompt`/`onPromptConsumed` props for pipeline "Add to review" integration

### 3. Task Notification XML Parsing in Chat Messages

**Problem**: `<task-notification>` XML blocks rendered as raw text in chat messages (both user and assistant). The XML contains structured metadata (task-id, status, summary) and a `<result>` field with markdown content — all displayed as unparsed XML.

**Solution** (`frontend/src/components/agents/ChatMessage.tsx`):

- Added `parseTaskNotification(content)` — regex parser that extracts:
  - `taskId`, `toolUseId`, `outputFile`, `status`, `summary` from XML tags
  - `result` content (multi-line markdown) from `<result>` tag
  - Returns remaining non-XML content

- Added `TaskNotificationCard` component:
  - Header: `ListTodo` icon + summary text + status badge (CheckCircle2/XCircle/Clock with green/red/amber colors)
  - Body: `<result>` content rendered via `ReactMarkdown` with GFM, code blocks, and `Linkify`
  - Footer: output file path as clickable link

- Updated user message rendering: checks for task notification first, renders card above any remaining text
- Updated assistant message rendering: same treatment for consistency
- Collapsed preview shows task summary instead of raw XML

---

## Files Modified

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `backend/app/services/gitlab_service.py` | +90 | `get_mr_pipelines()` function |
| `backend/app/api/gitlab.py` | +6 | Pipeline endpoint |
| `frontend/src/lib/api.ts` | +35 | Pipeline types + API method |
| `frontend/src/components/review/MRCenterPane.tsx` | +180, -60 | Pipeline tab rewrite, stage/job hierarchy |
| `frontend/src/app/review/page.tsx` | +10 | Wire onAddToReview + pendingPrompt |
| `frontend/src/components/review/MRAgentPane.tsx` | +12, -8 | Agent spawn fix + pendingPrompt props |
| `frontend/src/components/agents/ChatMessage.tsx` | +110, -10 | Task notification parser + card |

---

## Testing

- TypeScript: clean compile (`npx tsc --noEmit`)
- Backend: syntax valid (`py_compile`)
- Pipeline API: verified against WX MR !1316 — 6 pipelines, 6 stages (deploy, plan, publish, e2e-test, build, test), 50 jobs with real status/duration data
- Frontend + backend servers running on localhost:3000/9000
