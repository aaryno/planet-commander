# Planet Commander — Standalone Product and Technical Spec

## Purpose

Planet Commander is a context-aware engineering operations system for partially structured work. It is designed for environments where work may begin from a Jira issue, a chat, a branch, a worktree, or a manual investigation, and where humans and agents collaborate at different levels of adoption.

The system must make work:

* traceable
* linkable
* auditable
* summarizable
* agent-operable

Planet Commander is not just a ticket dashboard or agent launcher. It is the system that turns evolving engineering work into a coherent, inspectable, and operable work context.

---

## Product goals

Planet Commander must allow users to:

1. open any relevant engineering artifact and understand the surrounding work
2. see how tickets, chats, branches, worktrees, summaries, audits, PRs, and agent runs relate to each other
3. summarize single chats or merge multiple chats into reusable summaries
4. run targeted audits on issues, branches, worktrees, chats, or full contexts
5. use an overview agent to inspect a context, determine what is missing, recommend audits, dispatch sub-agents, and return a concise summary
6. support work that starts in chat and later becomes a ticket
7. support work that starts as a ticket and accumulates multiple chats and multiple execution attempts over time
8. preserve strong execution discipline and auditability without assuming every workflow is fully agent-driven

---

## Core design principles

### 1. Work Context is the primary user-facing abstraction

A single unit of work may include:

* one or more Jira issues
* one or more chats
* one or more branches
* one or more worktrees
* one or more summaries
* one or more audits
* one or more PRs
* one or more agent runs

The system must not assume that a ticket is always the root object. A work context may originate from:

* a Jira issue
* a chat
* a branch
* a worktree
* a manual user-created context
* a merged context composed from multiple prior artifacts

### 2. Deterministic traceability

Every meaningful action should make it possible to answer:

* what caused this change?
* which context does this belong to?
* which issue or chat initiated it?
* which branch and worktree were involved?
* which agent ran?
* what audits were performed?
* what PR or deployment resulted from it?

### 3. Explicit lifecycle states

All major artifacts must have explicit lifecycle states rather than relying on implied or inferred status.

### 4. Auditability is first-class

Audits must be typed, stored, attributable, and re-runnable. Audit results must not be ephemeral prompt outputs.

### 5. Chat is a first-class origin of work

Work often begins in exploratory discussion before there is a ticket. The system must support this explicitly.

### 6. Human and agent collaboration must both work

Planet Commander must remain valuable in mixed-adoption environments where some work is done by humans, some by agents, and much of it is only partially structured.

### 7. The system should improve structure over time

Planet Commander should help users move work from messy to structured by suggesting links, summaries, audits, and next actions.

---

## Scope of the system

Planet Commander covers:

* context resolution and relationship visualization
* issue, chat, branch, worktree, summary, audit, PR, and agent linkage
* summary extraction and multi-chat merge workflows
* targeted audits and overview orchestration
* worktree health and execution-state visibility
* inferred links and orphan detection
* next-best-action suggestions

It does not replace Jira, Git hosting, chat systems, or CI/CD systems. It sits above them and unifies their operational context.

---

## Domain model

### Primary entities

Planet Commander must model the following first-class entities:

* WorkContext
* JiraIssue
* Chat
* GitBranch
* Worktree
* PullRequest
* Summary
* Audit
* AgentRun
* EntityLink
* ContextSnapshot

---

## WorkContext

### Purpose

A WorkContext is the canonical user-facing bundle that represents a coherent unit of work regardless of how that work originated.

### Required fields

* `id`
* `title`
* `slug`
* `origin_type` — one of `jira`, `chat`, `branch`, `worktree`, `manual`, `merged`
* `primary_jira_issue_id` nullable
* `primary_chat_id` nullable
* `status` — one of `active`, `blocked`, `stalled`, `ready`, `done`, `orphaned`, `archived`
* `health_status` — one of `green`, `yellow`, `red`, `unknown`
* `summary_text`
* `last_overview_summary_id` nullable
* `last_agent_run_id` nullable
* `owner` nullable
* `created_at`
* `updated_at`
* `archived_at` nullable

### Derived values exposed in API and UI

* linked issue count
* linked chat count
* linked branch count
* linked worktree count
* linked summary count
* linked audit count
* active worktree count
* unresolved audit count
* open PR count
* suggested link count

---

## JiraIssue

### Required fields

* `id`
* `external_key` such as `COMPUTE-2059`
* `title`
* `status`
* `priority`
* `assignee`
* `labels`
* `fix_versions`
* `description`
* `acceptance_criteria`
* `url`
* `source_last_synced_at`

### Additional fields for Commander

* `agent_ready` nullable
* `context_id` nullable
* `last_context_audit_id` nullable
* `last_acceptance_audit_id` nullable

---

## Chat

### Required fields

* `id`
* `external_chat_id`
* `title`
* `workspace_or_source`
* `status` — one of `active`, `idle`, `closed`, `archived`
* `created_at`
* `updated_at`
* `last_message_at`
* `message_count`
* `token_count_estimate` nullable
* `contains_code` boolean
* `contains_ticket_reference` boolean
* `contains_worktree_reference` boolean

### Additional fields for Commander

* `generation_index` nullable
* `parent_chat_id` nullable
* `merged_into_summary_id` nullable
* `context_id` nullable
* `origin_type` — one of `ticket_spawned`, `chat_spawned`, `manual`, `agent_spawned`

### Chat-specific requirements

A chat may:

* exist without a ticket
* reference multiple tickets
* spawn a ticket later
* be one of multiple generations of work around the same context
* be merged with other chats into a reusable summary artifact

---

## GitBranch

### Required fields

* `id`
* `repo`
* `branch_name`
* `head_sha`
* `base_branch`
* `status` — one of `active`, `merged`, `stale`, `abandoned`
* `ahead_count` nullable
* `behind_count` nullable
* `has_open_pr` boolean
* `pr_id` nullable

### Additional fields for Commander

* `context_id` nullable
* `linked_ticket_key_guess` nullable
* `is_inferred` boolean default false

---

## Worktree

### Required fields

* `id`
* `repo`
* `path`
* `branch_id`
* `status` — one of `active`, `dirty`, `clean`, `stale`, `merged`, `abandoned`, `orphaned`
* `created_at`
* `updated_at`
* `last_seen_at`
* `is_active` boolean
* `has_uncommitted_changes` boolean
* `has_untracked_files` boolean
* `is_rebasing` boolean
* `is_out_of_date` boolean

### Worktree policy

The system should support:

* one branch to many worktrees over time
* zero or one active worktree per branch at a given time
* explicit visibility of stale, abandoned, dirty, and orphaned worktrees

The system must not permanently assume one branch has exactly one worktree.

---

## PullRequest

### Required fields

* `id`
* `repo`
* `number`
* `title`
* `url`
* `status` — one of `open`, `merged`, `closed`, `draft`
* `source_branch_id`
* `target_branch_name`
* `created_at`
* `updated_at`
* `merged_at` nullable

### Additional linkage fields

* `context_id` nullable
* `primary_issue_id` nullable
* `agent_run_id` nullable
* `latest_merge_readiness_audit_id` nullable

---

## Summary

### Purpose

Summaries are reusable structured artifacts produced from chats, contexts, issues, audits, or mixed sources.

### Required fields

* `id`
* `title`
* `kind` — one of `session`, `handoff`, `implementation`, `lessons_learned`, `merged`, `issue_digest`, `audit_brief`, `overview`
* `body_markdown`
* `structured_json`
* `source_type` — one of `chat`, `context`, `issue`, `agent_run`, `mixed`
* `created_by_type` — one of `user`, `agent`, `system`
* `created_by_id` nullable
* `created_at`
* `context_id` nullable

### Recommended `structured_json` fields

* `decisions`
* `risks`
* `blockers`
* `next_steps`
* `referenced_issues`
* `referenced_branches`
* `referenced_worktrees`
* `acceptance_criteria_status`
* `files_changed` nullable
* `deploy_notes` nullable

### Required summary capabilities

The system must support:

* summarize a single chat
* summarize the latest N messages of a chat
* summarize a full work context
* merge multiple chats into one summary
* create a handoff summary
* create a lessons-learned summary
* create an implementation summary
* create an issue-centric digest
* create an audit brief

---

## Audit

### Purpose

Audits are typed evaluative artifacts that assess a target object or full context and produce structured findings and recommendations.

### Required fields

* `id`
* `kind`
* `target_type`
* `target_id`
* `context_id` nullable
* `status` — one of `queued`, `running`, `passed`, `failed`, `warning`, `cancelled`
* `summary`
* `findings_json`
* `recommendations_json`
* `created_by_type` — one of `user`, `agent`, `system`
* `created_by_id` nullable
* `created_at`
* `completed_at` nullable

### Required audit kinds

Planet Commander must support at least the following audit types:

* `acceptance_criteria`
* `jira_scope`
* `chat_alignment`
* `branch_health`
* `worktree_state`
* `merge_readiness`
* `deployment_readiness`
* `monitoring_coverage`
* `context_completeness`
* `orphan_asset`
* `cross_context_consistency`
* `summary_consistency`
* `ticket_missing_from_chat_context`
* `worktree_missing_from_execution_context`
* `multi_chat_merge_quality`

### Audit requirements

Every audit must be:

* typed
* independently runnable
* storable
* attributable
* timestamped
* re-runnable
* composable into overview results

### Recommended `findings_json` shape

* severity
* code
* message
* target_type
* target_id
* optional location or artifact reference

### Recommended `recommendations_json` shape

* action identifier
* display label
* target object
* optional confidence

---

## AgentRun

### Purpose

An AgentRun represents a single agent execution session against a target or context.

### Required fields

* `id`
* `agent_type`
* `purpose`
* `context_id` nullable
* `primary_target_type`
* `primary_target_id`
* `status` — one of `queued`, `running`, `completed`, `failed`, `cancelled`
* `started_at`
* `ended_at` nullable
* `summary`
* `actions_log_json`
* `parent_agent_run_id` nullable

### Required run categories

Planet Commander must support agent runs for:

* overview
* audit dispatch
* single-audit execution
* chat summarization
* chat merge summarization
* link suggestion
* issue extraction from chat
* orphan detection

### Sub-agent support

Agent runs must support parent-child relationships so that one overview run can dispatch multiple child runs and return a synthesized result.

---

## EntityLink

### Purpose

EntityLink provides a generic relationship graph between all core entities.

### Required fields

* `id`
* `from_type`
* `from_id`
* `to_type`
* `to_id`
* `link_type`
* `source_type` — one of `manual`, `inferred`, `imported`, `agent`
* `confidence_score` nullable
* `status` — one of `confirmed`, `suggested`, `rejected`, `stale`
* `created_at`
* `updated_at`

### Required example link types

* `implements`
* `discussed_in`
* `references`
* `worked_in`
* `checked_out_as`
* `summarized_by`
* `recommends`
* `spawned`
* `derived_from`
* `related_to`
* `blocked_by`
* `follow_up_to`
* `supersedes`
* `same_context_as`

---

## ContextSnapshot

### Purpose

A ContextSnapshot stores the resolved state of a work context at a point in time for explainability, change tracking, and auditability.

### Required fields

* `id`
* `context_id`
* `captured_at`
* `resolved_entity_ids_json`
* `health_status`
* `overview_summary_id` nullable
* `recommended_actions_json`
* `unresolved_audit_ids_json`
* `active_worktree_ids_json`

### Use cases

* compare how a context changed over time
* explain why an overview recommendation changed
* support historical debugging of agent behavior

---

## Cardinality rules

Planet Commander must support the following relationship cardinalities:

* one Jira issue to zero or more branches
* one Jira issue to zero or more chats
* one Jira issue to zero or more summaries
* one Jira issue to zero or more audits
* one branch to zero or more worktrees over time
* one branch to zero or one active worktree at a time
* one worktree to zero or more chats
* one worktree to zero or more agent runs
* one chat to zero or more Jira issues
* one chat to zero or more summaries
* one chat to zero or more audits
* one context to zero or more of any core entity type
* one summary to one or more sources
* one overview agent run to zero or more child audit or summarization runs

---

## Context resolution

### ContextResolver service

Planet Commander requires a backend service that, given any entity, resolves the surrounding work context.

### Valid resolver inputs

* Jira issue key
* chat id
* branch id
* worktree id
* summary id
* audit id
* agent run id

### Resolver outputs

* primary context
* directly linked entities
* suggested links
* missing expected links
* health indicators
* recommended actions
* recent summaries
* recent audits
* active execution artifacts

### Resolution priority

1. explicit confirmed links
2. direct `context_id` association
3. high-confidence inferred links
4. bounded transitive graph resolution
5. fallback singleton context creation or display

### Example behavior

If the user opens a chat, the resolver should attempt to find:

* linked Jira issue or issues
* linked branch or branches
* linked worktree or worktrees
* summaries derived from that chat
* audits run on that chat or its surrounding context
* related chats in the same work context

---

## Linking model

### Manual linking requirements

Users must be able to:

* link a chat to an issue
* link a branch to an issue
* link a worktree to a branch
* link a summary to a context
* link a chat directly to a worktree
* move an entity to a different context if the original association was wrong

### Inferred linking requirements

The system must suggest likely links using heuristics such as:

* issue key in branch name
* issue key in chat title
* issue URL or key referenced in chat text
* summary references to issues or branches
* worktree path matching branch or issue naming
* repeated co-occurrence across sessions
* shared repo or artifact references

### Link statuses

Suggested links must be reviewable and marked as:

* confirmed
* suggested
* rejected
* stale

### Link review UI requirements

Users must be able to:

* confirm
* reject
* snooze or defer if implemented later

---

## Summary workflows

### Required summary modes

Planet Commander must support the following summary workflows:

* summarize a single chat
* summarize latest messages from a chat
* summarize a work context
* summarize by issue
* summarize by worktree
* create handoff
* create lessons learned
* create implementation summary
* create audit brief

### Multi-chat merge modes

Merging chats must not be simple concatenation. The user must be able to choose an explicit merge mode:

* `timeline`
* `implementation`
* `handoff`
* `issue_centric`
* `lessons_learned`
* `risk_digest`

### Summary usage

Summary artifacts should feed:

* context display
* overview agent input
* ticket creation drafts
* audit recommendations
* handoff workflows
* future session grounding

---

## Audit framework

### Required audit behavior

The system must support:

* single audit execution against a specific target
* multiple audit dispatch from overview
* storing all audit outputs
* rerunning prior audits
* showing pass, warning, fail, and unresolved states

### Key audit categories

#### 1. Context completeness audit

Checks whether the current context is sufficiently linked and structured.

Example findings:

* issue exists but no linked chat
* active worktree exists but no linked chat
* multiple chats exist but no merged handoff summary
* branch exists but no context association

#### 2. Chat alignment audit

Checks whether chat intent aligns with linked issue scope, summaries, and execution artifacts.

#### 3. Acceptance criteria coverage audit

Checks whether issue acceptance criteria are represented in summaries, execution state, or linked findings.

#### 4. Branch health audit

Checks branch freshness, ahead/behind status, PR state, and stale conditions.

#### 5. Worktree state audit

Checks dirty state, untracked files, rebase state, out-of-date state, or context mismatch.

#### 6. Monitoring coverage audit

Checks whether observability, alerts, metrics, or operational readiness implied by the work are actually represented.

#### 7. Orphan asset audit

Detects:

* branches with no context
* worktrees with no active linked context
* chats referencing issues but not linked
* summaries with no attached context

#### 8. Cross-context consistency audit

Detects contradictions such as:

* ticket says ready while worktree is dirty
* summary says monitoring complete while monitoring audit fails
* chat says implementation is done but no linked branch exists

---

## Agent orchestration

### Overview agent

Planet Commander requires a top-level overview agent that inspects a context and returns a concise operational picture.

### Overview agent responsibilities

* inspect the selected context
* detect missing links
* identify likely risks
* recommend or dispatch audits
* produce an overview summary
* surface next-best actions

### Overview agent inputs

* issue metadata
* linked chats
* linked summaries
* linked branches
* linked worktrees
* recent audits
* PR state
* deployment state where available

### Overview agent outputs

* status summary
* confidence estimate if implemented
* missing links
* recommended audits
* suggested links
* next actions
* child agent run references

### Sub-agent model

The overview agent must be able to dispatch child runs for:

* issue analysis
* chat summarization
* link suggestion
* branch audit
* worktree audit
* monitoring audit
* orphan detection
* summary merge synthesis

### One-click orchestration actions

The UI and backend must support:

* `Run Overview`
* `Run Recommended Audits`
* `Summarize Latest Chat`
* `Merge Selected Chats`
* `Create Handoff`
* `Extract Jira Issues from Chat`
* `Link Suggested Entities`
* `Find Orphaned Context`
* `Open Active Worktree`

---

## Execution discipline and worktree policy

Planet Commander should make execution-state visible and auditable even in mixed-adoption environments.

### Required worktree rules

* execution work should be associated with worktrees where applicable
* dirty worktrees must be visible
* stale worktrees must be visible
* orphaned worktrees must be detectable
* rebasing or broken worktree states must be visible
* worktrees must link to branch, context, and optionally chats and agent runs

### Required worktree health indicators

* dirty state
* untracked files
* rebasing state
* behind-main state
* abandoned state
* last seen recency
* context mismatch

---

## PR and deployment linkage

### Required PR linkage

PRs should be linked into the work context and related, when possible, to:

* issue
* branch
* agent run
* audits
* summaries

### Required PR visibility in context

The context view should show:

* open PRs
* draft PRs
* merged PRs
* merge-readiness audit status
* relationship between PR scope and issue or summary scope where available

### Deployment integration

Where deployment information exists, it should be resolvable into context and used by:

* overview summaries
* deployment readiness audits
* health display

---

## Backend architecture changes

### New tables required

* `work_contexts`
* `entity_links`
* `summaries`
* `audits`
* `agent_runs`
* `context_snapshots`

### Existing data structures that require extension

* Jira issue cache or sync table
* branch tracking table
* worktree tracking table
* PR cache or sync table
* agent session or chat metadata tables

### Core backend services required

#### `ContextResolverService`

Resolves a selected entity into a coherent work context.

#### `LinkInferenceService`

Generates high-confidence suggested links.

#### `SummaryService`

Creates, stores, and retrieves summary artifacts.

#### `AuditService`

Runs and stores typed audits.

#### `OverviewService`

Orchestrates overview runs and child dispatch.

#### `ContextHealthService`

Computes health indicators and context coverage.

#### `OrphanDetectionService`

Finds stale or unlinked artifacts.

---

## API surface

### Context endpoints

* `GET /contexts/:id`
* `GET /jira/:key/context`
* `GET /chats/:id/context`
* `GET /branches/:id/context`
* `GET /worktrees/:id/context`

### Link endpoints

* `POST /links`
* `POST /links/confirm`
* `POST /links/reject`
* `POST /links/suggest`
* `GET /contexts/:id/links`

### Summary endpoints

* `POST /summaries/extract`
* `POST /summaries/merge`
* `GET /summaries/:id`
* `GET /contexts/:id/summaries`

### Audit endpoints

* `POST /audits/run`
* `POST /audits/run-overview`
* `GET /audits/:id`
* `GET /contexts/:id/audits`

### Agent run endpoints

* `POST /agents/overview`
* `POST /agents/dispatch-audits`
* `GET /agent-runs/:id`
* `GET /contexts/:id/agent-runs`

### Health and orphan endpoints

* `GET /contexts/:id/health`
* `GET /orphaned`
* `GET /suggested-links`

---

## Frontend UX changes

### Replace the ticket detail card with a Context Panel

The current right-side ticket detail view should evolve into a multi-section Context Panel that can render from any selected entity.

### Required sections in the Context Panel

* Overview
* Actions
* Linked Context
* Chats
* Summaries
* Audits
* Relationships
* Agent Runs

### Required top-of-panel content

* entity or context title
* context health strip
* current state and origin
* linked artifact counts
* quick actions

### Required health strip indicators

* ticket linked yes or no
* branch linked yes or no
* active worktree yes or no
* chats present yes or no
* summaries current yes or no
* audits passing yes or no

### Required quick actions

* Run Overview
* Summarize Latest Chat
* Merge Chats
* Run Audits
* Create Handoff
* Open Active Worktree
* Confirm Suggested Links

### Required reusable frontend components

* `ActionBar`
* `EntityHeader`
* `RelationshipList`
* `LinkBadge`
* `HealthStrip`
* `SummaryCard`
* `AuditCard`
* `AgentRunCard`
* `SuggestedLinkList`
* `ContextPanel`
* `ContextOverview`
* `ContextLinkedEntities`
* `ChatMergeDialog`
* `SummaryComposer`
* `AuditLauncher`
* `OverviewResultPanel`
* `RelationshipMiniMap`

---

## Required context entry modes

Planet Commander must support at least two distinct but unified entry experiences.

### 1. Work Context view

Used when work is already reasonably linked and structured.

Should emphasize:

* overview status
* linked execution artifacts
* summaries
* audits
* next actions

### 2. Chat Context view

Used when work is exploratory or originates in chat.

Should emphasize:

* extracted issues
* suggested links
* possible ticket creation
* related branches and worktrees
* summary extraction
* context-building suggestions

Both views must resolve to the same underlying context model rather than creating separate systems.

---

## Data storage recommendations

### Storage model

Use relational storage in PostgreSQL with:

* dedicated entity tables
* a generic `entity_links` table for graph relationships
* denormalized counts on `work_contexts`
* optional materialized views for fast context resolution if needed

A graph database is not required initially.

### Why this model

This preserves:

* strong operational structure
* easy auditability
* flexible relationships
* compatibility with the existing backend stack

---

## Rollout phases

### Phase 1 — context foundation

Implement:

* work contexts
* entity links
* context resolver
* context panel shell
* manual linking
* issue, chat, branch, and worktree linkage display

### Success condition

Users can open any primary entity and see a coherent linked context.

### Phase 2 — summaries

Implement:

* summary object model
* summarize single chat
* merge multiple chats
* handoff and issue-centric summaries
* summaries section in context panel

### Success condition

Chats can be transformed into reusable operational artifacts.

### Phase 3 — audits

Implement:

* audit object model
* context completeness audit
* branch health audit
* worktree state audit
* chat alignment audit
* monitoring coverage audit

### Success condition

Contexts become auditable, not just visible.

### Phase 4 — overview orchestration

Implement:

* overview agent
* child agent dispatch
* recommended audits
* synthesized result view
* next-best-action section

### Success condition

Users can run one command to get status, gaps, and recommended follow-up.

### Phase 5 — inference and polish

Implement:

* inferred links
* orphan detection
* relationship minimap
* stale context detection
* saved audit bundles
* auto-link rules if desired later

### Success condition

The system reduces manual linking burden and helps structure work over time.

---

## Non-goals

The first version of this evolution should not require:

* a graph database
* fully autonomous issue generation by default
* mandatory strict linkage before any UI value is delivered
* replacement of Jira as the issue system of record
* fully automated worktree cleanup
* requiring every user to adopt an agent-first workflow

Planet Commander must remain useful in partially structured, partially instrumented environments.

---

## Acceptance criteria

Planet Commander should be considered successfully evolved when all of the following are true.

### Context resolution

* opening an issue, chat, branch, or worktree can resolve a usable context view

### Linking

* users can manually link artifacts
* the system can suggest likely links
* confirmed and suggested links are clearly distinguished

### Summaries

* users can summarize a single chat
* users can merge multiple chats into a structured summary
* summaries are stored as first-class objects

### Audits

* typed audits can run against issues, chats, branches, worktrees, and contexts
* overview can recommend or dispatch audits
* audit results are visible and reusable

### Overview orchestration

* one-click overview can produce current state, missing links, risks, and recommended actions

### Worktree visibility

* active, dirty, stale, and orphaned worktree states are visible in context
* worktree state influences context health

### Mixed-origin support

* chat-first work can become ticket-linked later
* issue-first work can accumulate multiple chats and summaries over time
* both flows resolve to the same work context model

---

## Final product definition

Planet Commander should become:

> a work context commander that links, summarizes, audits, and orchestrates engineering work across tickets, chats, branches, worktrees, summaries, PRs, and agent runs.

The core rule is:

> every important artifact should be linkable, summarizable, auditable, and operable within a shared work context.
