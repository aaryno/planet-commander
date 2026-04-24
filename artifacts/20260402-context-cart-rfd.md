# RFD: Context Cart — Multi-Chat Merge and Launch

**Date**: 2026-04-02
**Author**: Aaryn Olsson
**Status**: Draft
**Component**: Commander Dashboard — Agent Multi-View / Agent Lifecycle

---

## Problem

Agents accumulate deep context during their sessions — JIRA tickets, Slack threads, branch knowledge, investigation artifacts, operational decisions. But agents die, context windows fill, sessions go stale.

**Today, when you need a fresh agent that knows what 3 previous agents learned, you have two options:**

1. Manually paste summaries into a new prompt (lossy, tedious)
2. Start from scratch and re-discover everything (wasteful)

Neither preserves the **structured, rich context** that Commander already tracks: JIRA issues, EntityLinks, Slack threads, MR refs, worktree state, artifacts.

**The real need:**

> Merge N agent sessions into one coherent context, then launch a new agent that inherits everything.

This is not "session merge" — it is **context synthesis with launch**.

---

## Principle

> The new agent should start where the previous agents left off — not from zero.

This means:

1. All relevant JIRA tickets are known
2. All relevant Slack threads are queued
3. All worktree/branch state is understood
4. All investigation artifacts are referenced
5. The agent receives a synthesized summary, not raw chat dumps
6. The user chooses what carries over

---

## Goal

Build a **Context Cart** — a persistent collection surface where users add agent chats, review what they contribute, and launch a new agent that inherits the merged context.

### User Flow

```
1. User browses agents in AMV, agents list, or chat views
2. User adds chats to the Cart (icon in chat header)
3. Cart badge shows count (top-right, always visible)
4. User opens Cart to review:
   - Chats included (with summaries)
   - JIRA tickets discovered (union across all chats)
   - Slack threads linked
   - MR/branch state
   - Artifacts referenced
5. User configures launch:
   - Pick dominant JIRA ticket (for comments, context origin)
   - Pick worktree: create new or reuse existing
   - Pick model
   - Edit/approve synthesized prompt
6. User clicks "Launch"
7. New agent spawns with:
   - Full context preamble (synthesized from all chats)
   - JIRA key set (dominant ticket)
   - Worktree configured
   - Context queue pre-filled (Slack, incidents, etc.)
   - EntityLinks created (new chat → all source chats, tickets, etc.)
```

---

## Architecture

### Frontend: Context Cart State

```typescript
interface CartItem {
  agentId: string;
  addedAt: string;
}

interface CartState {
  items: CartItem[];
  dominantJiraKey: string | null;
  worktreeMode: "new" | "reuse";
  selectedWorktreeId: string | null;
}
```

**Storage**: `sessionStorage` key `"context-cart"` (mirrors AMV pattern).

**Global visibility**: Cart icon with badge count in the app shell header (not per-page). Accessible from any page.

### Cart Drawer

When opened, the Cart fetches the **resolved context** for each included agent:

```
For each agent in cart:
  GET /contexts/chat/{agent.id} → ContextResponse
```

Then presents a **union view**:

| Section | Source | Display |
|---------|--------|---------|
| **Chats** | Cart items | Agent title, status, summary, message count |
| **JIRA Tickets** | Union of all `jira_issues` across contexts | Key, title, status, assignee. Radio select for dominant. |
| **Slack Threads** | Union of all linked Slack threads | Channel, title, age, participant count |
| **Merge Requests** | Union of all linked MRs | Title, state, branch, repo |
| **Branches / Worktrees** | Union of all branches + worktrees | Branch name, worktree path, status |
| **Artifacts** | Union of all linked artifacts | Title, path, age |
| **PagerDuty Incidents** | Union of all linked incidents | Title, status, service |

### Dominant JIRA Ticket

One JIRA ticket is selected as **dominant**. This ticket:

- Becomes the new agent's `jira_key`
- Receives a comment when the agent launches (optional)
- Is the origin of the new WorkContext
- Other tickets are referenced but not primary

**Default**: The ticket that appears most frequently across the cart's chats. User can override.

### Worktree Selection

| Option | Behavior |
|--------|----------|
| **Create new** | Auto-creates worktree named `ao/{dominant-jira-key}` or user-specified. Standard flow via `create_worktree()`. |
| **Reuse existing** | Picker shows worktrees from cart's chats. User selects one. New agent starts in that directory. |

### Context Synthesis

Before launch, the system builds a **context preamble** — the initial prompt that gives the new agent full awareness.

**Structure:**

```
You are continuing work that spans multiple previous agent sessions.

## Work Context
- Primary ticket: {dominant_jira_key} — {ticket_title}
- Related tickets: {other_jira_keys}
- Branch: {branch_name}
- Worktree: {worktree_path}

## Previous Sessions

### Session 1: {agent_1_title}
{agent_1_summary}
Key outcomes:
- {bullet points from summary}

### Session 2: {agent_2_title}
{agent_2_summary}
Key outcomes:
- {bullet points from summary}

## Active Slack Context
{queued slack messages, if any}

## Related Artifacts
- {artifact_1_path}: {artifact_1_title}
- {artifact_2_path}: {artifact_2_title}

## Open Merge Requests
- !{mr_id}: {mr_title} ({mr_state})

## Your Task
{user_edited_prompt}
```

**Summary source**: Each agent already has a 3-tier summary system (phrase, short, detailed) via `POST /agents/{id}/summarize`. The Cart triggers summarization for any chat that doesn't have one yet, using the "detailed" tier.

### Backend: Launch Endpoint

```
POST /agents/cart-launch
```

**Request:**

```python
class CartLaunchRequest(BaseModel):
    agent_ids: list[str]              # Source agent UUIDs
    dominant_jira_key: str | None     # Primary JIRA ticket
    related_jira_keys: list[str]      # Other tickets to reference
    worktree_mode: str                # "new" | "reuse"
    worktree_id: str | None           # If reuse, which worktree
    worktree_branch: str | None       # If new, branch name override
    project: str                      # wx, g4, jobs, temporal, general
    model: str | None                 # opus, sonnet, haiku
    user_prompt: str | None           # User's additional instructions
    post_jira_comment: bool = True    # Comment on dominant ticket
```

**Response**: Same as `POST /agents` — `{id, session_id, pid, status, ...}`

**Backend Logic:**

1. **Resolve contexts** for all source agents
2. **Build context preamble** from summaries + entities
3. **Create/select worktree** based on mode
4. **Spawn agent** via `process_manager.spawn()` with synthesized prompt
5. **Register Agent** in DB with `jira_key = dominant_jira_key`
6. **Create EntityLinks**:
   - New agent → each source agent (`link_type = DERIVED_FROM`)
   - New agent → dominant JIRA issue (`link_type = IMPLEMENTS`)
   - New agent → each related JIRA issue (`link_type = REFERENCES`)
7. **Backfill context queue** — run `backfill_agent_context()` for Slack/MR/incident awareness
8. **Post JIRA comment** (if enabled):
   ```
   Agent session launched from merged context.
   Source sessions: {agent_1_title}, {agent_2_title}, ...
   Branch: {branch_name}
   Commander link: {dashboard_url}
   ```

---

## Data Model Changes

### No new tables required

The existing models support this:

| Model | Role in Cart Launch |
|-------|--------------------|
| `Agent` | New agent record with `jira_key`, `git_branch` |
| `WorkContext` | Created with `origin_type = MERGED` |
| `EntityLink` | `DERIVED_FROM` links to source agents |
| `AgentContextQueueItem` | Pre-filled via backfill |

### New enum values needed

```python
# WorkContext.origin_type
class OriginType(str, enum.Enum):
    ...
    MERGED = "merged"       # Already exists in the enum

# EntityLink link_type
# DERIVED_FROM already exists
# REFERENCES already exists
# IMPLEMENTS already exists
```

All required enum values already exist.

---

## Frontend Components

### 1. CartButton (Global)

**Location**: App shell header (layout.tsx or equivalent)

```tsx
<CartButton count={cartItems.length} onClick={openCartDrawer} />
```

- Shopping cart icon (lucide `ShoppingCart`)
- Badge with count (only if > 0)
- Pulsing animation when items are added

### 2. "Add to Cart" Button

**Location**: ChatView header, AgentRow actions, AMV window header

- Icon: `Plus` or `ShoppingCart`
- Toggles: shows checkmark if already in cart
- Click adds/removes from cart

### 3. CartDrawer

**Location**: Right-side drawer (similar to ChatSidebar pattern)

**Sections**:

1. **Cart Items** — List of agents with remove button, summary preview
2. **Discovered Context** — Union view of all JIRA, Slack, MRs, etc.
3. **Configuration** — Dominant ticket selector, worktree picker, model picker
4. **Preview** — Synthesized prompt (editable textarea)
5. **Launch Button** — "Launch Merged Agent"

### 4. CartProvider (React Context)

Wraps the app to provide cart state globally:

```tsx
const CartContext = createContext<{
  items: CartItem[];
  add: (agentId: string) => void;
  remove: (agentId: string) => void;
  has: (agentId: string) => boolean;
  clear: () => void;
  count: number;
}>(...);
```

---

## Sequenced Implementation

### Phase 1: Cart State + UI (Frontend only)

1. Create `CartProvider` with sessionStorage persistence
2. Add `CartButton` to app shell
3. Add "Add to Cart" button to ChatView and AgentRow
4. Build CartDrawer skeleton (list items, remove)

**Validates**: Users can collect chats into a cart and see them listed.

### Phase 2: Context Resolution (Frontend + Backend)

1. CartDrawer fetches `ContextResponse` for each cart agent
2. Build union view across all resolved contexts
3. Display JIRA tickets, Slack threads, MRs, artifacts, incidents
4. Add dominant ticket selector (radio buttons)

**Validates**: Users see the full merged context before launching.

### Phase 3: Synthesis + Launch (Full stack)

1. Add `POST /agents/cart-launch` endpoint
2. Build context preamble from agent summaries
3. Trigger summarization for agents without summaries
4. Handle worktree create/reuse
5. Create EntityLinks (`DERIVED_FROM`, `IMPLEMENTS`)
6. Backfill context queue
7. Post JIRA comment (optional)
8. Wire frontend launch button to endpoint

**Validates**: New agent spawns with full inherited context.

### Phase 4: Polish

1. Prompt preview/edit before launch
2. Selective inclusion (uncheck specific tickets, threads)
3. Cart persistence across page navigation
4. Cart count animation
5. Post-launch: auto-open new agent in AMV or chat

---

## Open Questions

### 1. Summary Quality

Agent summaries are LLM-generated. If a chat has 500+ messages, the summary may lose critical details.

**Mitigation**: Include both summary AND key artifacts/decisions. Let user edit the prompt before launch.

### 2. Context Window Budget

Merging 5 agents could produce a 20K+ token preamble.

**Mitigation**: Use "short" summary tier by default. Let user switch to "detailed" per-agent. Show token count estimate.

### 3. Worktree Conflicts

If two source agents used different worktrees on the same repo, merging code state is non-trivial.

**Mitigation**: Don't merge code. Let user pick ONE worktree. The synthesized prompt describes what the other sessions did (branches, commits) so the new agent can cherry-pick or merge as needed.

### 4. Stale Context

Source agents may be days old. Their Slack context is historical.

**Mitigation**: Backfill runs fresh at launch time, pulling latest 14 days. The preamble includes timestamps so the new agent knows what's current.

### 5. JIRA Comment Noise

Auto-commenting on tickets could be noisy if users launch many merged agents.

**Mitigation**: Make it opt-in (checkbox in CartDrawer, default on). Comment is concise: 2-3 lines with link.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Synthesis prompt too large for context window | Medium | Agent truncates early context | Token budget calculator, warn user |
| Summary generation fails for dead agents | Low | Missing summary in preamble | Fall back to `first_prompt` + title |
| EntityLink explosion (N agents x M entities) | Low | Query performance | Batch link creation, index on from_id/to_id |
| User confusion about what "dominant ticket" means | Medium | Wrong ticket selected | Clear UI copy: "This ticket will receive status comments" |
| Cart lost on page refresh (sessionStorage) | Expected | Minor annoyance | Consider localStorage for persistence, or make it ephemeral by design |

---

## Success Criteria

After implementation, users should be able to:

1. Add 2-5 agent chats to the Cart from any page
2. Open the Cart and see a unified view of all JIRA tickets, Slack threads, MRs, and artifacts across those chats
3. Select a dominant JIRA ticket and worktree
4. Review and edit the synthesized prompt
5. Launch a new agent that starts with full awareness of all previous work
6. See EntityLinks connecting the new agent to its source agents
7. (Optional) See a JIRA comment posted on the dominant ticket

**The new agent should be productive within its first turn** — no re-discovery needed.

---

## Why This Matters

This is the missing piece between "agents that do work" and "agents that build on each other's work."

Without it, every agent session is an island. With it, Commander becomes a platform where **work context is cumulative, transferable, and never lost.**

> Agents die. Context doesn't.
