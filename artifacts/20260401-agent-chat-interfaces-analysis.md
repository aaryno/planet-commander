# Commander Agent Chat Interfaces - Comprehensive Analysis

**Date**: 2026-04-01
**Scope**: All agent chat display surfaces, features, and auto-hydration capabilities

---

## Architecture Overview

All chat interfaces are built on a shared component stack:

```
ChatMessage (message rendering, markdown, linkification)
    ^
ChatInput (message compose, status-aware, resume support)
    ^
ChatView (full chat: WebSocket streaming, history, pins, filters, summarization)
    ^
+-- ChatCard (wrapped ChatView with header badges)
+-- ChatSidebar (slide-out panel on /agents)
+-- ChatModal (centered dialog on /agents)
+-- JiraWorkspace (tabbed ticket + chat)
+-- MRAgentPane (review cockpit chat pane)
+-- AMV grid windows (lightweight per-window chat)
```

---

## Chat Surfaces

### 1. Agents Page Sidebar (`/agents`)

**Component**: `ChatSidebar` -> `ChatView`
**File**: `frontend/src/components/agents/ChatSidebar.tsx`
**Triggered by**: Clicking any agent row on the agents page

- Fixed-position right sidebar (500px overlay / 600px docked)
- Dock/undock toggle, escape-to-close
- URL state: `?agent={id}&docked={true|false}`
- Full ChatView with all features

### 2. Agents Page Modal (`/agents`)

**Component**: `ChatModal` -> `ChatView`
**File**: `frontend/src/components/agents/ChatModal.tsx`
**Triggered by**: Alternative view mode on agents page

- Centered modal (max-w-3xl, 80vh)
- Backdrop blur overlay
- "Breakout to full page" button -> `/agents/{id}/chat`

### 3. Full Page Chat (`/agents/{id}/chat`)

**Component**: `ChatView` (standalone)
**File**: `frontend/src/app/agents/[id]/chat/page.tsx`
**Triggered by**: Direct URL or breakout from modal

- Maximum screen space for chat
- Full ChatView with all features

### 4. JIRA Workspace Chat Tab

**Component**: `JiraWorkspace` -> `ChatView`
**File**: `frontend/src/components/workspace/JiraWorkspace.tsx`
**Triggered by**: Clicking a JIRA ticket in JiraSummary card

- Two-tab layout: "Ticket" | "Chat"
- Auto-finds related agents by JIRA key
- ChatInput on ticket tab for quick messages
- Can spawn new agent directly from ticket context
- Switches to chat tab on agent spawn/message
- "Add to AMV" and "Break Out" buttons in header

### 5. Review Cockpit Agent Pane (`/review`)

**Component**: `MRAgentPane` -> `ChatView`
**File**: `frontend/src/components/review/MRAgentPane.tsx`
**Triggered by**: Selecting an MR in the Review Cockpit

- Finds agent by linked JIRA key
- Empty state with prompt chips ("Explain this MR", etc.)
- Spawns agent on first message if none exists
- AI Review Summary section
- "Send to Multi-View" button

### 6. Agent Multi-View / AMV (`/multiview`)

**Component**: Custom grid windows (NOT ChatView)
**File**: `frontend/src/app/multiview/page.tsx`
**Triggered by**: "Add to AMV" from any chat, or direct navigation

- Responsive drag-and-resize grid (up to 12 columns)
- Per-window message composer
- Loads history from real agents or shows mock
- Minimize/maximize, color picker per window
- Entity badges (JIRA, branch, MR, worktree) with copy/link actions
- sessionStorage-persisted layout
- "Load Agent" picker with search

### 7. ProjectAgents Expandable Row

**Component**: `ChatCard` -> `ChatView`
**File**: `frontend/src/components/agents/ChatCard.tsx`
**Triggered by**: Expanding an agent row in ProjectAgents card

- Inline expandable within agent list
- Standardized header with project/JIRA badges
- WorkspaceActions menu

---

## Feature Comparison Table

| Feature | Sidebar | Modal | Full Page | JIRA WS | Review | AMV | Expandable |
|---------|:-------:|:-----:|:---------:|:-------:|:------:|:---:|:----------:|
| **Core Chat** | | | | | | | |
| WebSocket streaming | Y | Y | Y | Y | Y | N | Y |
| HTTP fallback | Y | Y | Y | Y | Y | Y | Y |
| Message history | Y | Y | Y | Y | Y | Y | Y |
| Send messages | Y | Y | Y | Y | Y | Y | Y |
| **Message Display** | | | | | | | |
| Markdown rendering | Y | Y | Y | Y | Y | N | Y |
| Code syntax highlight | Y | Y | Y | Y | Y | N | Y |
| URL auto-linkification | Y | Y | Y | Y | Y | N | Y |
| File path linkification | Y | Y | Y | Y | Y | N | Y |
| Tool call expansion | Y | Y | Y | Y | Y | N | Y |
| Thinking block display | Y | Y | Y | Y | Y | N | Y |
| JIRA context stripping | Y | Y | Y | Y | Y | N | Y |
| **Message Management** | | | | | | | |
| Pin/unpin messages | Y | Y | Y | Y | Y | N | Y |
| Collapse/expand msgs | Y | Y | Y | Y | Y | N | Y |
| Resizable messages | Y | Y | Y | Y | Y | N | Y |
| Message type filters | Y | Y | Y | Y | Y | N | Y |
| **Agent Lifecycle** | | | | | | | |
| Spawn new agent | N | N | N | Y | Y | Y | N |
| Resume dead agent | Y | Y | Y | Y | Y | N | Y |
| VS Code takeover | Y | Y | Y | Y | Y | N | Y |
| Processing indicator | Y | Y | Y | Y | Y | N | Y |
| **Summarization** | | | | | | | |
| AI auto-summarize | Y | Y | Y | Y | Y | N | Y |
| Phrase/short/detailed | Y | Y | Y | Y | Y | N | Y |
| **Entity Integration** | | | | | | | |
| JIRA card (pinned) | Y | Y | Y | Y | Y | N | Y |
| Extract URLs button | Y | Y | Y | Y | Y | N | Y |
| Add to AMV button | N | N | N | Y | Y | N | N |
| Breakout button | N | Y | N | Y | N | N | N |
| **Layout** | | | | | | | |
| Dock/undock | Y | N | N | N | N | N | N |
| Grid drag-resize | N | N | N | N | N | Y | N |
| Minimize/maximize | N | N | N | N | Y | Y | N |
| Color coding | N | N | N | N | N | Y | N |
| Entity badges | N | N | N | Y | N | Y | Y |
| Prompt chips | N | N | N | N | Y | N | N |

**Y** = supported, **N** = not supported

---

## Auto-Hydration & Entity Detection

### Backend: Entity Enrichment Engine

**File**: `backend/app/services/entity_enrichment.py`

Regex-based pattern detection for 7 entity types, creating `EntityLink` records:

| Entity Type | Pattern | Example | Link Type |
|-------------|---------|---------|-----------|
| JIRA Issues | `[A-Z][A-Z0-9]+-\d+` | COMPUTE-1234 | `REFERENCES_JIRA` |
| PagerDuty Incidents | URL + `PD-[A-Z0-9]{6,}` | PD-ABC123 | `REFERENCES_PAGERDUTY` |
| Slack Threads | `planet-labs.slack.com/archives/...` | Channel + timestamp | `REFERENCES_SLACK` |
| GitLab MRs | `hello.planet.com/code/.../merge_requests/\d+` + `MR !?\d+` | MR !831 | `IMPLEMENTED_BY` |
| Grafana Dashboards | `planet.grafana.net/d/[id]/` | Dashboard aavxb5g | `REFERENCES_ALERT` |
| Grafana Alerts | `[FIRING:\d+] alert-name` | Alert name | `REFERENCES_ALERT` |
| Google Docs | `docs.google.com/(document\|spreadsheets\|presentation)/d/[id]` | Doc ID + type | `DOCUMENTED_IN_GDRIVE` |

### How Hydration Works

```
1. User clicks "Extract URLs" in ChatView header
   -> POST /agents/{id}/extract-urls
   -> URLExtractor scans all messages
   -> URLClassifier identifies entity type
   -> EntityLink records created

2. Background jobs (hourly)
   -> extract_urls_from_recent_chats()
   -> PagerDuty enrichment
   -> Slack thread enrichment
   -> Incident spider correlation

3. Context resolution (on-demand)
   -> GET /contexts/by-jira/{key}
   -> ContextResolverService traverses EntityLinks
   -> Returns unified ContextResponse with all linked entities
```

### Context Resolution Output

When resolving a work context (by JIRA key, chat ID, branch, or worktree), the system returns:

```typescript
interface ContextResponse {
  jira_issues: JiraIssueInContext[]
  chats: ChatInContext[]
  branches: BranchInContext[]
  worktrees: WorktreeInContext[]
  pagerduty_incidents: PagerDutyIncident[]
  grafana_alerts: GrafanaAlertDefinition[]
  artifacts: InvestigationArtifact[]
  merge_requests: MergeRequestInContext[]
  links: EntityLinkInContext[]
  health: ContextHealth
}
```

### Frontend: Message-Level Enrichment

**File**: `frontend/src/components/agents/ChatMessage.tsx` + `RichText.tsx`

| Feature | Implementation |
|---------|---------------|
| URL auto-linking | Linkify component detects `http(s)://` |
| File path linking | Regex for `/Users/`, `~/`, `/home/`, etc. -> `file://` links |
| JIRA context strip | Removes `[Context: You are working on JIRA ticket...]` prefix |
| Markdown rendering | ReactMarkdown + GFM |
| Code blocks | Syntax highlighting + copy button |

---

## Key Backend Endpoints (Agent/Chat)

| Endpoint | Method | Purpose | File |
|----------|--------|---------|------|
| `/agents` | POST | Spawn new agent | agents.py |
| `/agents/{id}/chat` | POST | Send message (HTTP) | agents.py |
| `/agents/{id}/ws` | WS | Real-time streaming | agents.py |
| `/agents/{id}/history` | GET | Chat history | agents.py |
| `/agents/{id}/summarize` | POST | AI summary (phrase/short/detailed) | agents.py |
| `/agents/{id}/extract-urls` | POST | Extract & link entities | agents.py |
| `/agents/{id}/resume` | POST | Resume dead session | agents.py |
| `/agents/{id}/stop` | POST | Graceful stop | agents.py |
| `/agents/self` | PATCH | Agent self-registration | agents.py |
| `/agents/by-jira/{key}` | GET | Find agents by JIRA key | agents.py |
| `/contexts/by-jira/{key}` | GET | Full context resolution | contexts.py |
| `/contexts/by-chat/{id}` | GET | Context from chat | contexts.py |

---

## Key Observations

### Commonalities
- All full chat surfaces use `ChatView` as the core component
- All get WebSocket streaming, history, pins, filters, summarization for free
- JIRA context is auto-injected on message send (backend, all paths)
- Entity detection is centralized in `entity_enrichment.py`

### Differences
- **AMV** is the outlier: custom grid windows, no ChatView, no streaming, simplified rendering
- **JIRA Workspace** and **Review Cockpit** can spawn agents; sidebar/modal/full-page cannot
- **Review Cockpit** has prompt chips for quick questions; others don't
- Only **JIRA Workspace** has a chat input on the non-chat tab (ticket tab)
- **Dock/undock** is unique to the sidebar

### Gaps
- Entity detection is **on-demand** (button click or background job), not real-time during chat
- AMV lacks most ChatView features (no streaming, no pins, no tool calls)
- No reverse discovery: can't find chats FROM an external entity easily
- Auto-summarization is on-demand, not triggered on chat completion
- Google Docs detection exists in backend but no dedicated UI card in ContextPanel
