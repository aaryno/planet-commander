# Expandable Cards — Implementation Plan

**Goal**: Click any row in JIRA, Agents, Open MRs, or WX Deployments to expand
inline detail with rich cross-linked information.

**Key principle**: Shared components. MR status looks identical whether viewed from
a JIRA ticket, an agent, or the Open MRs list.

---

## Phase 0: Backend API Enrichment (30 min)

Before building UI, fill the data gaps. All changes are additive (no breaking changes).

### 0a. Enrich MR details response

**File**: `backend/app/services/gitlab_service.py` (`_fetch_mr_details`)

The GitLab API already returns these fields — we just aren't extracting them:

```python
# Add to the return dict in _fetch_mr_details:
"pipeline_status": data.get("pipeline", {}).get("status"),        # success/failed/running
"pipeline_web_url": data.get("pipeline", {}).get("web_url"),      # link to pipeline
"has_conflicts": data.get("has_conflicts", False),                # needs rebase
"user_notes_count": data.get("user_notes_count", 0),             # total comments
"merge_status": data.get("merge_status", ""),                     # can_be_merged / cannot_be_merged
"approvals_required": data.get("approvals_before_merge", 0),
"upvotes": data.get("upvotes", 0),                               # approvals count
"diff_refs": data.get("diff_refs", {}),                           # for diff link
```

### 0b. Add MR search-by-JIRA-key endpoint

**File**: `backend/app/api/gitlab.py`

```python
@router.get("/by-jira/{jira_key}")
async def mrs_by_jira_key(jira_key: str):
    """Find open MRs whose title contains a JIRA key."""
```

Implementation: filter the cached MR list by `jira_key in mr.title`.

### 0c. Add agents-by-JIRA-key endpoint

**File**: `backend/app/api/agents.py`

```python
@router.get("/by-jira/{jira_key}")
async def agents_by_jira_key(jira_key: str):
    """Find agents associated with a JIRA key."""
```

Implementation: `SELECT * FROM agents WHERE jira_key = :key`.

### 0d. Add agent last-prompt endpoint

**File**: `backend/app/api/agents.py`

```python
@router.get("/{agent_id}/last-prompt")
async def agent_last_prompt(agent_id: str):
    """Get the last user message from an agent's history."""
```

Implementation: read JSONL, find last `role=human` message, return content (truncated).

### 0e. Add failing CI job link

**File**: `backend/app/services/gitlab_service.py`

```python
async def get_failing_job_url(project: str, pipeline_id: int) -> str | None:
    """Get direct URL to the first failing job in a pipeline."""
```

Implementation: `glab api projects/:id/pipelines/:pid/jobs`, find first `status=failed`.

### 0f. Add deployment commit count

**File**: `backend/app/services/wx_deployment_service.py`

```python
async def commits_since_deploy(tier: str, deployed_sha: str) -> dict:
    """Count commits on main since a deployed SHA."""
```

Implementation: `git log --oneline {sha}..HEAD | wc -l` in the WX repo.

---

## Phase 1: Shared Components (1-2 hours)

All in `frontend/src/components/shared/`. Each is a pure presentational component
with no data fetching — they receive props and render.

### 1a. `ExpandableRow.tsx`

Generic wrapper that adds click-to-expand behavior to any row.

```tsx
interface ExpandableRowProps {
  summary: React.ReactNode;     // always-visible row content
  children: React.ReactNode;    // expanded detail (lazy-rendered)
  expanded?: boolean;           // controlled mode
  onToggle?: () => void;        // controlled mode callback
  className?: string;
}
```

- Smooth height animation (CSS transition on max-height or grid-rows)
- Chevron indicator (right side, rotates on expand)
- Border-bottom on expanded state
- Keyboard accessible (Enter/Space to toggle)

### 1b. `MRStatusBadge.tsx`

```tsx
interface MRStatusBadgeProps {
  status: "opened" | "closed" | "merged";
  pipelineStatus?: "success" | "failed" | "running" | "pending" | null;
  pipelineUrl?: string;         // link to pipeline
  failingJobUrl?: string;       // direct link to failing job
  hasConflicts?: boolean;       // needs rebase
  unresolvedCount?: number;     // unresolved discussions
  approved?: boolean;
  url?: string;                 // MR web URL
}
```

Renders: `open ✅ passing` or `open ❌ failing (link)` or `open ⚠️ rebase needed`

### 1c. `CIStatusLink.tsx`

```tsx
interface CIStatusLinkProps {
  status: "success" | "failed" | "running" | "pending" | null;
  pipelineUrl?: string;
  failingJobUrl?: string;       // if failed, link directly here
}
```

Renders: ✅ or ❌ (clickable to failing job) or ⏳

### 1d. `BranchBadge.tsx`

```tsx
interface BranchBadgeProps {
  branch: string;
  project?: string;             // for GitLab link
  targetBranch?: string;        // "→ main"
}
```

Renders: `ao/cost-rollup-docs → main` with copy button.

### 1e. `AgentBadge.tsx`

```tsx
interface AgentBadgeProps {
  id: string;
  title: string;
  status: "live" | "idle" | "dead";
  createdAt?: string;
  lastActivity?: string;
  messageCount?: number;
  onClick?: () => void;         // open in sidebar
}
```

Renders: `● IDLE "optimize zombie..." 3d ago, 12 prompts`

### 1f. `CommentIndicator.tsx`

```tsx
interface CommentIndicatorProps {
  count: number;
  lastActivityAt?: string;      // ISO timestamp
  unresolvedCount?: number;
}
```

Renders: `3 comments, 2 unresolved, last 2d ago`

### 1g. `ExternalLinks.tsx`

```tsx
interface ExternalLinksProps {
  links: Array<{ label: string; url: string; icon?: React.ReactNode }>;
}
```

Renders: `[JIRA ↗] [Epic ↗] [Pipeline ↗]` — compact link row.

---

## Phase 2: JIRA Expanded Card (1-2 hours)

### 2a. `JiraTicketExpanded.tsx`

Fetches detail on expand (lazy-load), uses shared components.

```
Data flow:
  Click row → expanded=true
    → fetch GET /api/jira/ticket/{key}           (description, metadata)
    → fetch GET /api/gitlab/by-jira/{key}        (linked MRs)
    → fetch GET /api/agents/by-jira/{key}        (linked agents)
  Render:
    Description (first 5-10 lines, "show more" toggle)
    Metadata grid: labels, story points, assignee, pair, sprint, epic
    CommentIndicator (count + last activity)
    For each linked MR: MRStatusBadge + BranchBadge + CIStatusLink
    For each linked agent: AgentBadge
    ExternalLinks: [JIRA ↗] [Epic ↗]
```

### 2b. Integrate into `JiraSummary.tsx`

Replace `JiraTicketCard` click behavior:
- Currently: `onTicketClick` opens workspace panel
- New: first click expands inline; expanded card has "Open" button for workspace panel

---

## Phase 3: Open MR Expanded Card (1 hour)

### 3a. `MRExpanded.tsx`

```
Data flow:
  Click row → expanded=true
    → fetch GET /api/gitlab/{project}/{iid}      (full MR details)
    → extract JIRA key from title
    → search agents by branch name
  Render:
    MRStatusBadge (status, CI, rebase, unresolved)
    BranchBadge (source → target)
    CommentIndicator
    Approval status
    JiraKeyBadge (if JIRA key found)
    AgentBadge (if agent found)
    ExternalLinks: [GitLab ↗] [Diff ↗] [Pipeline ↗]
```

### 3b. Integrate into `OpenMRs.tsx`

Replace table row with ExpandableRow wrapping the existing row + MRExpanded.

---

## Phase 4: Agent Expanded Card (1 hour)

### 4a. `AgentExpanded.tsx`

```
Data flow:
  Click row → expanded=true
    → fetch GET /api/agents/{id}/last-prompt     (last user message)
    → if jira_key: fetch linked MR via /api/gitlab/by-jira/{key}
    → if git_branch: fetch MR by branch
  Render:
    Timestamps: created, last chat
    Stats: prompt count, context size
    Last prompt (truncated, expandable)
    JiraKeyBadge (if jira_key)
    BranchBadge (if git_branch)
    MRStatusBadge (if linked MR found)
    Actions: [Join Chat] [Summarize]
```

### 4b. Integrate into `AgentRow.tsx`

- Current click: calls `onAgentClick` (opens sidebar)
- New: first click expands inline; "Join Chat" button opens sidebar
- Keep existing `onAgentClick` for non-expanded contexts (e.g., agent search results)

---

## Phase 5: WX Deployment Expanded Card (1 hour)

### 5a. `DeploymentExpanded.tsx`

```
Data flow:
  Click row → expanded=true
    → fetch GET /api/wx/deployments/{tier}/details  (new endpoint)
  Render:
    Tag label (if tagged release, e.g., v2.47.0)
    CommitsSinceDeploy: "14 commits on main since deploy"
    Deploy MR link (tier-specific):
      - prod: !807 (always-open MR, merge = deploy)
      - staging/dev: !1084
    ArgoCD status + link
    ExternalLinks: [ArgoCD ↗] [Commit ↗] [Deploy MR ↗]
```

### 5b. Deploy MR config

```typescript
const DEPLOY_MRS: Record<string, { iid: number; label: string }> = {
  "prod-us": { iid: 807, label: "Production Deploy MR" },
  "dev-01": { iid: 1084, label: "Dev Deploy MR" },
  // etc.
};
```

### 5c. Integrate into `WXDeployments.tsx`

Wrap each deployment card in ExpandableRow.

---

## Phase 6: Polish (30 min)

- Loading skeletons in expanded views (pulse animation while fetching)
- Error states (red text, retry button)
- Keyboard navigation (arrow keys between rows, Enter to expand)
- Cache expanded data (don't refetch on collapse/re-expand within 60s)
- URL state: persist which rows are expanded in URL params

---

## Dependency Graph

```
Phase 0 (backend) ─────────────────────┐
                                        │
Phase 1 (shared components) ────────────┤
                                        │
          ┌─────────────────────────────┤
          │              │              │              │
     Phase 2         Phase 3       Phase 4         Phase 5
    (JIRA)           (MR)         (Agent)       (Deployment)
          │              │              │              │
          └──────────────┴──────────────┴──────────────┘
                                        │
                                   Phase 6
                                   (Polish)
```

Phase 0 and Phase 1 can run in parallel.
Phases 2-5 can each run independently after 0+1 are done.

---

## Effort Estimate

| Phase | Scope | Estimate |
|-------|-------|----------|
| 0 | Backend API enrichment | 30 min |
| 1 | 7 shared components | 1-2 hours |
| 2 | JIRA expanded | 1-2 hours |
| 3 | MR expanded | 1 hour |
| 4 | Agent expanded | 1 hour |
| 5 | Deployment expanded | 1 hour |
| 6 | Polish | 30 min |
| **Total** | | **5-8 hours** |

---

## Files to Create

```
frontend/src/components/shared/
├── ExpandableRow.tsx
├── MRStatusBadge.tsx
├── CIStatusLink.tsx
├── BranchBadge.tsx
├── AgentBadge.tsx
├── CommentIndicator.tsx
└── ExternalLinks.tsx

frontend/src/components/expanded/
├── JiraTicketExpanded.tsx
├── MRExpanded.tsx
├── AgentExpanded.tsx
└── DeploymentExpanded.tsx
```

## Files to Modify

```
backend/app/services/gitlab_service.py     — enrich MR details
backend/app/api/gitlab.py                  — add by-jira endpoint
backend/app/api/agents.py                  — add by-jira + last-prompt endpoints
backend/app/services/wx_deployment_service.py — add commit count

frontend/src/components/cards/JiraSummary.tsx    — use ExpandableRow
frontend/src/components/cards/OpenMRs.tsx        — use ExpandableRow
frontend/src/components/agents/AgentRow.tsx      — use ExpandableRow
frontend/src/components/cards/WXDeployments.tsx  — use ExpandableRow
```
