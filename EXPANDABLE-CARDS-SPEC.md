# Expandable Cards Specification

## Overview

Every card row in JIRA, Agents, Open MRs, and WX Deployments should be click-expandable
to show rich detail inline. Shared UI components are reused across card types.

## Shared Components

These components appear in multiple card expansions and MUST be implemented once,
then reused everywhere.

### `MRStatusBadge`
Shows MR lifecycle state in a compact badge.
- Status: open/closed/merged (color-coded)
- Unresolved discussions count (if >0, red badge)
- CI status: passing/failing/pending
- Rebase needed indicator
- Click: opens MR in GitLab

### `CIStatusLink`
Compact CI pass/fail indicator with direct link.
- Green check or red X
- If failing: links directly to the failing job URL (not the pipeline overview)
- Tooltip: pipeline status + job name

### `BranchBadge`
Branch name with actions.
- Truncated branch name in monospace
- Copy to clipboard button
- Link to GitLab branch

### `AgentBadge`
Compact agent reference.
- Status dot (live/idle/dead)
- Agent title (truncated)
- Created/last-used timestamps
- Prompt count + context size
- Click: opens agent in sidebar

### `JiraKeyBadge`
Already exists — cyan badge with ticket key. Click opens JIRA.

### `CommentIndicator`
- Comment count
- "Last activity Xd ago"

### `CommitsSinceDeploy`
- "N commits on main since last deploy"
- Tag label if on tagged version

## Card Type Expansions

### JIRA Ticket (expanded)

```
┌──────────────────────────────────────────────────────────────┐
│ COMPUTE-2202  Selected for Development  High  Task           │ <- existing row
├──────────────────────────────────────────────────────────────┤
│ Description (first 5-10 lines, expandable)                   │
│                                                              │
│ Labels: jobs, zombie-killer    Story Points: 5               │
│ Assignee: Ryan Cleere          Pair: —                       │
│ Sprint: Sprint 47              Epic: COMPUTE-1800            │
│                                                              │
│ Activity: 3 comments, last 2d ago                            │
│                                                              │
│ Linked MRs:                                                  │
│   !1279 ao/optimize-zombie-checks  ✅ passing  open          │
│   !1282 ao/zombie-killer           ❌ failing   open         │
│                                                              │
│ Agents:                                                      │
│   ● IDLE "optimize zombie worker pre-filter" 3d ago, 12 prompts │
│                                                              │
│ Links: [JIRA ↗] [Epic ↗]                                    │
└──────────────────────────────────────────────────────────────┘
```

Data sources:
- `GET /api/jira/ticket/{key}` — description, labels, story points, assignee, comments
- `GET /api/gitlab` filtered by JIRA key — linked MRs
- Agent list filtered by `jira_key` — linked agents
- EntityLinks from context resolver

### Open MR (expanded)

```
┌──────────────────────────────────────────────────────────────┐
│ !1284 docs: cost rollup user doc  bohannan  1d ago           │ <- existing row
├──────────────────────────────────────────────────────────────┤
│ Status: open  Draft: no  Approved: yes (1/1)                 │
│ Branch: ao/cost-rollup-docs → main                           │
│ CI: ✅ passing (all 4 jobs)                                  │
│ Unresolved: 0   Comments: 2   Last activity: 12h ago         │
│ Rebase: not needed                                           │
│                                                              │
│ JIRA: COMPUTE-2250                                           │
│ Agent: ● DEAD "cost rollup docs" 1d ago, 8 prompts          │
│                                                              │
│ Links: [GitLab ↗] [Diff ↗] [Pipeline ↗]                     │
└──────────────────────────────────────────────────────────────┘
```

Data sources:
- `GET /api/gitlab/{project}/{mr_iid}` — full MR details
- Extract JIRA key from title
- Agent list filtered by branch name

### Agent (expanded)

```
┌──────────────────────────────────────────────────────────────┐
│ ● IDLE  optimize zombie worker pre-filter  3d ago            │ <- existing row
├──────────────────────────────────────────────────────────────┤
│ Created: Mar 28 14:30   Last chat: Mar 28 16:45              │
│ Prompts: 12   Context: 45K tokens                            │
│                                                              │
│ Last prompt: "now check if the zombie detection threshold..." │
│                                                              │
│ JIRA: COMPUTE-2202                                           │
│ Branch: ao/optimize-zombie-checks                            │
│ MR: !1279 open ✅ passing  0 unresolved                     │
│                                                              │
│ [Join Chat] [Summarize]                                      │
└──────────────────────────────────────────────────────────────┘
```

Data sources:
- Agent model (already has timestamps, prompt count, jira_key, git_branch)
- `GET /api/gitlab` filtered by branch — linked MR
- Last prompt from `GET /api/agents/{id}/history`

### WX Deployment (expanded)

```
┌──────────────────────────────────────────────────────────────┐
│ PROD-US  PROD  94df7a41  6d ago                              │ <- existing row
├──────────────────────────────────────────────────────────────┤
│ Tag: v2.47.0   Commits since: 14                             │
│ Deploy MR: !807 (merge to deploy)                            │
│                                                              │
│ ArgoCD: synced   Health: Healthy                             │
│ Last sync: 6d ago                                            │
│                                                              │
│ Links: [ArgoCD ↗] [Commit ↗] [Deploy MR ↗]                  │
└──────────────────────────────────────────────────────────────┘
```

Data sources:
- Existing deployment data from WX service
- Git log for commits since tag
- Hardcoded deploy MR URLs per tier

## Implementation Order

1. **Shared components** (MRStatusBadge, CIStatusLink, BranchBadge, AgentBadge, CommentIndicator)
2. **ExpandableRow wrapper** — generic click-to-expand with smooth animation
3. **JIRA expanded** — highest value, most data available
4. **MR expanded** — reuses shared components
5. **Agent expanded** — reuses shared components
6. **WX Deployment expanded** — simplest, mostly links

## API Gaps

| Need | Current API | Gap |
|------|-------------|-----|
| JIRA linked MRs | No direct query | Add: search MRs by JIRA key in title |
| JIRA linked agents | No direct query | Add: search agents by jira_key |
| MR CI details | `get_mr_details` returns pipeline | Need: direct link to failing job |
| Agent last prompt | `agentHistory` | Need: last user message only |
| Deployment commits since | Not available | Add: git log --oneline tag..HEAD |
| Deployment MR URLs | Not in API | Hardcode or add to deploy config |
