# RFD: Live Agent Context Matching — Slack, Branches, and Merge Requests

**Date**: 2026-04-02
**Author**: Aaryn Olsson
**Status**: Draft
**Component**: Commander Dashboard — Agent Context Queue
**Depends on**: [Slack Live Context Injection (Context Queue RFD)](./20260402-slack-live-context-injection-rfd.md)

---

## Problem

The Context Queue guarantees delivery of Slack updates to agents, but the **matching and relevance system** is incomplete.

**Today:**

- Matching is JIRA-only
- Slack context is message-level, not thread-level
- Agents miss context tied to:
  - branches
  - merge requests
  - services / environments
- There is no backfill
- There is no filtering or prioritization of signal vs noise

**At the same time:**

> Slack is the communications lifeblood of Planet, but it contains both high-signal operational context and large volumes of noise.

**Additionally:**

> The true state of work is not just in Slack — it also lives in branches, merge requests, pipelines, and deploy systems.

---

## Principle

> **Agents must stay fully abreast of operational reality.**

This requires:

1. **Capture broadly** — do not miss relevant context
2. **Match correctly** — connect context to the right agents
3. **Deliver selectively** — prioritize signal over noise
4. **Unify sources** — Slack, branches, and MRs are one system

---

## Goal

Build a system that:

1. **Matches context** from:
   - Slack threads
   - Git branches
   - Merge requests
2. **Guarantees delivery** via the Context Queue
3. **Surfaces**:
   - what changed
   - who is doing what
   - what is broken / fixed
4. **Avoids overwhelming agents** with noise

---

## Current Gaps

### Gap 1: JIRA-Only Matching

Agents only receive Slack context if messages contain a JIRA key.

**Missing:**
- MR references (`!847`)
- Branch mentions (`ao/compute-2292`)

→ Agents miss relevant conversations entirely

### Gap 2: No Backfill on Agent Update

When `jira_key` or `git_branch` is added later:

- Existing Slack discussions are not recovered
- Agent starts with zero historical context

### Gap 3: Message-Level Matching

Only messages containing the key are matched.

→ Entire thread context is lost

### Gap 4: No Branch / MR Awareness

Branches and MRs are:

- Primary execution artifacts
- Frequently referenced in Slack
- Completely ignored in matching

### Gap 5: No Human vs Bot Signal Distinction

Slack contains:

- human coordination
- deploy bots
- CI/CD notifications
- repetitive status messages

System treats all equally.

→ Important human decisions get buried

### Gap 6: No Deduplication Across Sources

Same event appears multiple times:

- Slack bot
- MR event
- human message

→ Agents may receive redundant context

### Gap 7: No Actionability / Relevance Scoring

System cannot distinguish:

- "rollback staging now" (critical)
- vs "pipeline passed" (routine)

### Gap 8: No Thread State Understanding

Threads are delivered as raw messages, but agents need:

- current status
- ownership
- resolution state

### Gap 9: No Channel Awareness

Not all Slack channels are equal:

- incident / deploy channels → high signal
- general chatter → low signal

### Gap 10: No Entity Matching Beyond JIRA

Important references:

- environments (`wx-dev-02`)
- services (`scene-processor`)
- pipelines

→ Not matched at all

### Gap 11: No Lifecycle Awareness (Branches / MRs)

Agents are not aware of:

- MR opened / updated / merged
- pipeline failures
- review states

### Gap 12: No Queue Compaction / Delivery Budget

With expanded matching:

- queue size will grow rapidly
- no mechanism to:
  - dedupe
  - summarize
  - prioritize

---

## Scope

### Phase 1 (This RFD — Implement Now)

- Extended matching:
  - JIRA keys
  - MR refs
  - branch names
- Thread-level enqueue
- Backfill on agent update

### Phase 2 (Next)

- Human vs bot classification
- Channel weighting
- Deduplication across sources
- Queue size limits + compaction

### Phase 3 (Future)

- Entity alias mapping (services, environments)
- Thread state extraction
- Semantic relevance scoring
- MR / branch lifecycle tracking

---

## Proposed Matching Architecture

### Unified Matching Function

```python
async def find_agents_for_thread(thread: SlackThread) -> list[str]:
```

Matches on:

| Match Type | Thread Field | Agent Field | Confidence |
|-----------|-------------|-------------|:----------:|
| JIRA key | `jira_keys` | `jira_key` | High |
| MR ref | `gitlab_mr_refs` | linked MRs (via EntityLink) | High |
| Branch | message text | `git_branch` | Medium |

Union of all matches → deduplicated agent list

### Thread-Level Matching

When a thread matches:

→ Enqueue last **N = 5** messages

**NOT** just the matching message

### Backfill on Agent Update

Trigger on:

```
PATCH /agents/{id}
```

If `jira_key` or `git_branch` changes:

1. Scan SlackThreads (last 14 days)
2. Match via unified matching
3. Enqueue last 3 messages per thread
4. Deduplicate via `source_id`

---

## Branch + MR Integration (New)

### First-Class Requirement

> Agents must stay aware of execution artifacts, not just conversation.

### Additions

Agents should receive context from:

**Merge Requests:**
- opened
- updated
- approved
- merged
- pipeline failed

**Branch Activity:**
- branch created
- force push
- deploy from branch
- rollback tied to branch

These should enter the **same context queue** as Slack events.

---

## Data Flow (Unified)

```
Slack Threads ─────┐
                   │
MR Events ─────────┼──→ Matching Engine ─→ Context Queue
                   │
Branch Events ─────┘
```

All sources:

1. normalized
2. matched
3. deduplicated (future)
4. queued

---

## Implementation Plan

### Stream A: Extended Matching

- JIRA key match
- MR ref match
- branch match
- unified `find_agents_for_thread`

### Stream B: Thread-Level Enqueue

- enqueue last 5 messages per thread

### Stream C: Backfill

- trigger on agent update
- scan 14 days
- enqueue matches

### Stream D (New): MR + Branch Event Ingestion

- hook into GitLab / repo events
- normalize into context events
- enqueue alongside Slack

---

## Future System Enhancements

### 1. Signal Classification

Classify messages:

- human decision
- human coordination
- bot alert
- bot noise

### 2. Deduplication Layer

Detect same event across:

- Slack
- MR events
- branch activity

### 3. Queue Compaction

Before delivery:

- collapse duplicates
- summarize threads
- enforce token budget

### 4. Thread State Extraction

Maintain:

- current status
- owner
- resolution
- last meaningful update

### 5. Entity Alias System

Map:

- services
- environments
- pipelines

→ to agents and work

---

## Final Position

> This is not a Slack feature.
>
> This is a **live operational context system**.

Agents must:

1. **see** what humans are saying
2. **understand** what systems are doing
3. **track** what code is changing

All in one coherent flow.

---

## Core Design Principle

> **Capture broadly. Deliver selectively.**

- Never miss important context
- Never overwhelm the agent
