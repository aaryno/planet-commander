# Phase 2: Agent Discovery + Chat

**Status**: Not started
**Priority**: This is THE core feature - the reason the dashboard exists.

## Goal

Discover all Claude Code sessions from `~/.claude/projects/`, index them into PostgreSQL, display them per-project with rich metadata, and provide a chat modal to view conversation history.

## Success Criteria

1. `POST /api/agents/sync` discovers ~95 sessions from `~/.claude/`
2. `/agents` page shows all agents with status badges and labels
3. WX project page shows its ~39 agents with correct metadata
4. Clicking "Chat" opens a modal with parsed conversation history
5. Chat shows user prompts + assistant summaries (thinking/tools hidden by default)
6. Expanding an assistant message reveals thinking blocks + tool calls
7. Dead agents show "Resume" button instead of chat input

## Backend Tasks

### 2.1 Session Reader Service (`app/services/session_reader.py`)

Parse `~/.claude/projects/*/sessions-index.json` files to discover all sessions.

**Input data** (from sessions-index.json):
```json
{
  "sessionId": "abc-123",
  "firstPrompt": "review MR 2059 for queue backlog age",
  "messageCount": 42,
  "created": "2026-02-15T10:30:00Z",
  "modified": "2026-02-15T11:45:00Z",
  "gitBranch": "ao/compute-2059-queue-backlog-age",
  "projectPath": "-Users-aaryn-workspaces-wx-1"
}
```

**Session reader must**:
- Scan all `sessions-index.json` files under `~/.claude/projects/`
- Map project paths to project keys using `config.project_path_map`
- Parse JSONL conversation files for chat history
- Return structured chat messages (user prompts, assistant summaries, tool call counts, thinking block detection)

**JSONL parsing rules**:
- `type: "user"` → Extract `message.content` text
- `type: "assistant"` → Extract text blocks as summary, count tool_use blocks, detect thinking blocks
- Skip: `queue-operation`, `file-history-snapshot`
- Merge consecutive assistant messages into single turn

### 2.2 Worktree Service (`app/services/worktree_service.py`)

Detect git worktrees and match them to sessions by branch name.

**Known worktree locations**:
- `~/workspaces/wx-1/` through `~/workspaces/wx-4/`
- `~/workspaces/g4/`
- `~/workspaces/jobs/`
- `~/workspaces/temporalio/`

**Must**:
- Run `git worktree list` in each known repo
- Parse output to extract worktree paths and branch names
- Match worktrees to sessions via `gitBranch` field

### 2.3 Agent Service (`app/services/agent_service.py`)

Process detection to determine live/idle/dead status.

**Status logic**:
```python
def determine_status(session, running_pids):
    if session.claude_session_id not in running_pids:
        return "dead"
    pid_info = running_pids[session.claude_session_id]
    if pid_info.cpu_percent < 1.0 and pid_info.idle_seconds > 30:
        return "idle"
    return "live"
```

**Must**:
- Use `psutil` to find Claude Code processes
- Correlate PIDs with session IDs
- Detect idle vs active based on CPU usage

### 2.4 Agent Sync Endpoint (`POST /api/agents/sync`)

Replace the current stub in `app/api/agents.py`.

**Must**:
- Call session_reader to discover all sessions
- Upsert agents into PostgreSQL (match on `claude_session_id`)
- Call worktree_service to enrich with worktree paths
- Call agent_service for status detection
- Return count of discovered/updated/new agents

### 2.5 Agent List Endpoint (`GET /api/agents`)

Replace the current stub.

**Must**:
- Support query params: `?project=wx`, `?status=live`, `?label=code-review`
- Return agents with their labels, sorted by last_active_at desc
- Include worktree_path, git_branch, message_count, status

### 2.6 Chat History Endpoint (`GET /api/agents/{id}/history`)

Replace the current stub.

**Must**:
- Look up agent's session file path from `claude_session_id` + `claude_project_path`
- Parse JSONL file using session_reader
- Return structured messages:
  ```json
  [
    {"role": "user", "timestamp": "...", "content": "review MR 2059..."},
    {"role": "assistant", "timestamp": "...", "summary": "Started reviewing...",
     "tool_call_count": 4, "has_thinking": true}
  ]
  ```
- Support `?expand=true` to include thinking blocks + full tool call details

## Frontend Tasks

### 2.7 Agent Types (`src/lib/types.ts`)

Update the existing Agent type to match real backend response.

### 2.8 ProjectAgents Component (`src/components/agents/ProjectAgents.tsx`)

Embedded in each project page. Shows agent list for that project.

**Must**:
- Fetch `GET /api/agents?project={project}` using usePoll (30s)
- Show count badge in section header
- Render AgentRow for each agent

### 2.9 AgentRow Component (`src/components/agents/AgentRow.tsx`)

Single agent row with all metadata.

**Display**:
```
● LIVE  "review MR 2059 queue backlog age"     2h ago  [Chat] [⋮]
  🏷️ wx  code-review  COMPUTE-2059
  ⎇ ao/compute-2059-queue-backlog-age
  📂 ~/workspaces/wx-1/wx
  ▸ 3 artifacts
```

**Must**:
- Status badge: Live (green), Idle (yellow), Dead (gray)
- Title from firstPrompt, truncated
- Relative time since last activity
- Colorful label badges using existing LabelBadge system
- Git branch name
- Worktree path (if available)
- Collapsible artifact list
- Chat button → opens ChatModal
- More menu (⋮) with placeholder actions

### 2.10 AgentStatusBadge Component (`src/components/agents/AgentStatusBadge.tsx`)

Colored status indicator.

### 2.11 ChatModal Component (`src/components/agents/ChatModal.tsx`)

Full-screen modal for viewing agent conversation history.

**Layout**:
- Header: agent title, labels, status badge, close button
- Body: scrollable ChatHistory
- Footer: text input (Phase 3) or "Resume" button for dead agents

**Must**:
- Open via dialog/sheet from AgentRow
- Fetch `GET /api/agents/{id}/history` on open
- Auto-scroll to bottom

### 2.12 ChatHistory Component (`src/components/agents/ChatHistory.tsx`)

Renders the parsed conversation.

**Must**:
- User messages: full text, left-aligned or full-width
- Assistant messages: summary text only
- Expandable sections for thinking blocks + tool calls
- "N tool calls" badge that expands to show tool names + truncated inputs
- Timestamps on each message

### 2.13 Wire into ProjectPage

Update `src/components/projects/ProjectPage.tsx` to embed ProjectAgents.

### 2.14 Wire into Agents Page

Update `src/app/agents/page.tsx` to show all agents (no project filter).

## File Checklist

### New Files
- [ ] `backend/app/services/session_reader.py`
- [ ] `backend/app/services/worktree_service.py`
- [ ] `backend/app/services/agent_service.py`
- [ ] `frontend/src/components/agents/ProjectAgents.tsx`
- [ ] `frontend/src/components/agents/AgentRow.tsx`
- [ ] `frontend/src/components/agents/AgentStatusBadge.tsx`
- [ ] `frontend/src/components/agents/ChatModal.tsx`
- [ ] `frontend/src/components/agents/ChatHistory.tsx`
- [ ] `frontend/src/components/agents/ChatMessage.tsx`

### Modified Files
- [ ] `backend/app/api/agents.py` (replace stubs with real implementation)
- [ ] `frontend/src/lib/api.ts` (add agent fetch functions)
- [ ] `frontend/src/lib/types.ts` (update Agent type if needed)
- [ ] `frontend/src/components/projects/ProjectPage.tsx` (embed ProjectAgents)
- [ ] `frontend/src/app/agents/page.tsx` (wire up real agent list)

## Implementation Order

1. **session_reader.py** - Parse sessions-index.json + JSONL files
2. **agent_service.py** - Process detection
3. **worktree_service.py** - Git worktree matching
4. **agents.py API** - Replace stubs (sync, list, history)
5. **Frontend types + API client** - Update types, add fetch functions
6. **AgentStatusBadge** - Small, standalone component
7. **AgentRow** - Agent display with all metadata
8. **ChatHistory + ChatMessage** - Conversation rendering
9. **ChatModal** - Full modal wrapper
10. **ProjectAgents** - Per-project agent list
11. **Wire into ProjectPage + Agents page** - Integration

## Notes

- The backend runs in Docker with `~/.claude` mounted at `/data/claude` (read-only)
- Session reader paths must use the container mount path (`/data/claude/projects/...`)
- Process detection via psutil won't work inside the container for host processes - need to either:
  - (a) Expose a host-side agent status endpoint, or
  - (b) Mount the Docker socket + use `docker exec` for ps, or
  - (c) Accept that status detection only works for agents spawned via the dashboard, or
  - (d) Run a lightweight sidecar on the host that reports process status
  - **Decision needed at implementation time** - for MVP, option (c) is simplest, mark all discovered sessions as "dead" unless spawned via dashboard
