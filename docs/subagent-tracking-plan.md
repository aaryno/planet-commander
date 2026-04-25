# Parent/Child Agent Tracking — Implementation Plan

**Date**: 2026-04-24
**Status**: Research complete, ready for implementation
**Effort**: ~3-4 days

---

## Problem

When a dashboard agent spawns a subagent (via the Agent tool, cart-launch, or spawn API), the subagent appears as a separate top-level entry in the All Agents view. Users cannot see which agent spawned which. Subagents should be visually nested under their parent.

## Current State

### What Already Exists

The infrastructure is partially built but not wired together:

| Component | Status | Details |
|-----------|--------|---------|
| `parent_chat_id` field on Agent model | **Exists, unused** | UUID FK to `agents.id`, added in migration `20260317_1855` |
| `resumed_from_id` field on Agent model | **Exists, used for resumes** | UUID FK to `agents.id` |
| `SPAWNED` LinkType on EntityLink | **Exists, unused** | Defined in `entity_link.py` enum |
| `DERIVED_FROM` EntityLink in cart-launch | **Exists, working** | Creates links from source agents → derived agent |
| `isSidechain` flag in Claude sessions | **Exists, used to filter OUT** | Sessions with `isSidechain=True` are skipped in `sync_agents` |
| `parent_agent_id` in spawn request | **Does not exist** | Spawn endpoint has no parent parameter |
| Frontend hierarchy rendering | **Does not exist** | Flat list of `AgentRow` components |

### Key Files

| File | Role |
|------|------|
| `backend/app/models/agent.py` | Agent model with `parent_chat_id` field (line 59) |
| `backend/app/models/entity_link.py` | EntityLink model with `SPAWNED` type |
| `backend/app/api/agents.py` | Spawn (line 373), cart-launch (line 497) endpoints |
| `backend/app/services/agent_service.py` | Session discovery, `sync_agents()` |
| `backend/app/services/session_reader.py` | Reads `sessions-index.json` + JSONL files |
| `frontend/src/app/agents/page.tsx` | Agent list page, flat rendering |
| `frontend/src/components/agents/AgentRow.tsx` | Individual agent row component |
| `frontend/src/lib/api.ts` | `Agent` interface (line 876) |

---

## Design

### Relationship Storage: Dual Approach

Use **both** the `parent_chat_id` FK (fast queries) and `EntityLink` with `SPAWNED` type (rich metadata, consistent with cart-launch pattern).

```
Agent (parent)
  └─ parent_chat_id FK ──→ Agent (child)
  └─ EntityLink { from=parent, to=child, type=SPAWNED }
```

**Why both?** The FK enables efficient single-query hierarchy loading (self-join). The EntityLink provides metadata (spawn source, timestamp) and integrates with the existing context system.

### Spawn Sources and How Parent Gets Set

| Source | How parent_agent_id arrives | Confidence |
|--------|---------------------------|------------|
| **Dashboard chat** | WebSocket handler already knows the agent_id — pass it when user says "spawn a subagent" | High — deterministic |
| **Spawn API (explicit)** | Caller passes `parent_agent_id` in request body | High — deterministic |
| **Cart-launch** | Already creates `DERIVED_FROM` links; also set `parent_chat_id` to first source agent | High — deterministic |
| **Claude Code Agent tool** | Claude creates sidechain sessions. No `parentSessionId` in session metadata. Must infer from co-location + timing. | Medium — heuristic |
| **CLI curl** | Optional `parent_agent_id` parameter | High if provided |

### Sidechain Detection Strategy

Claude Code's Agent tool creates sidechain sessions (`isSidechain=True`). Currently these are **filtered out** in `sync_agents()`. To track them:

1. **Stop filtering sidechains** — include them in sync, mark with `origin_type="sidechain"`
2. **Infer parent via heuristics** — same project dir + created within the parent's active window
3. **Store relationship** — set `parent_chat_id` and create `SPAWNED` EntityLink

**Heuristic for parent inference:**
```python
# For each sidechain session:
# 1. Find non-sidechain sessions in same project directory
# 2. Filter to sessions active at the time the sidechain was created
#    (created_at <= sidechain.created_at <= last_active_at + 5min)
# 3. Pick the most recently active one as parent
# 4. If no match, leave parent_chat_id NULL (orphaned sidechain)
```

This works because:
- Sidechains are always created in the same project directory as their parent
- The parent is always active when the sidechain is spawned
- Multiple sidechains from the same parent will share the same project + time window

---

## Implementation Steps

### Step 1: Backend — Spawn Endpoint (30 min)

**File**: `backend/app/api/agents.py`

Add `parent_agent_id` to `SpawnAgentRequest`:

```python
class SpawnAgentRequest(BaseModel):
    # ... existing fields ...
    parent_agent_id: str | None = None  # UUID of parent agent
```

In `spawn_agent()`, after creating the new agent:

```python
# Set parent relationship
if request.parent_agent_id:
    parent = await db.get(AgentModel, uuid.UUID(request.parent_agent_id))
    if parent:
        new_agent.parent_chat_id = parent.id

        # Create EntityLink
        link = EntityLink(
            from_type="chat",
            from_id=str(parent.id),
            to_type="chat",
            to_id=str(new_agent.id),
            link_type=LinkType.SPAWNED,
            source_type=LinkSourceType.SYSTEM,
            confidence_score=1.0,
            status=LinkStatus.CONFIRMED,
            link_metadata={"source": "spawn_api"},
        )
        db.add(link)
```

Also update cart-launch to set `parent_chat_id` on the new agent (first source agent):

```python
# In cart_launch, after creating new_agent:
if source_agents:
    new_agent.parent_chat_id = uuid.UUID(source_agents[0]["id"])
```

### Step 2: Backend — List Endpoint (30 min)

**File**: `backend/app/api/agents.py`

Add `parent_agent_id` and `child_count` to agent list response:

```python
# In the agent serialization (AgentResponse or dict building):
{
    ...existing fields...,
    "parent_agent_id": str(agent.parent_chat_id) if agent.parent_chat_id else None,
    "child_count": child_counts.get(agent.id, 0),
}
```

Compute child counts efficiently with a single query:

```python
# Before serializing agents:
from sqlalchemy import func
child_counts_q = await db.execute(
    select(
        AgentModel.parent_chat_id,
        func.count(AgentModel.id)
    )
    .where(AgentModel.parent_chat_id.isnot(None))
    .group_by(AgentModel.parent_chat_id)
)
child_counts = {row[0]: row[1] for row in child_counts_q}
```

Add optional query parameter to fetch children of a specific agent:

```python
@router.get("/agents/{agent_id}/children")
async def get_agent_children(agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentModel)
        .where(AgentModel.parent_chat_id == uuid.UUID(agent_id))
        .order_by(AgentModel.created_at.desc())
    )
    children = result.scalars().all()
    return {"agents": [serialize(c) for c in children], "total": len(children)}
```

### Step 3: Backend — Sidechain Sync (1 hour)

**File**: `backend/app/services/agent_service.py`

Stop filtering out sidechains. Instead, include them and infer parents:

```python
# In sync_agents(), replace:
#   if session.is_sidechain:
#       continue
# With:
if session.is_sidechain:
    agent.origin_type = "sidechain"
    # Parent inference happens in a second pass (below)
```

After the main sync loop, run parent inference for new sidechains:

```python
async def _infer_sidechain_parents(self, db: AsyncSession):
    """Infer parent agents for sidechain sessions without a parent_chat_id."""
    orphan_sidechains = await db.execute(
        select(AgentModel).where(
            AgentModel.origin_type == "sidechain",
            AgentModel.parent_chat_id.is_(None),
        )
    )

    for sidechain in orphan_sidechains.scalars():
        # Find candidate parents: same project dir, non-sidechain,
        # active around the time the sidechain was created
        candidates = await db.execute(
            select(AgentModel).where(
                AgentModel.claude_project_path == sidechain.claude_project_path,
                AgentModel.origin_type != "sidechain",
                AgentModel.created_at <= sidechain.created_at,
                AgentModel.last_active_at >= sidechain.created_at - timedelta(minutes=5),
            ).order_by(AgentModel.last_active_at.desc())
        )
        parent = candidates.scalars().first()
        if parent:
            sidechain.parent_chat_id = parent.id
            # Create EntityLink
            link = EntityLink(
                from_type="chat",
                from_id=str(parent.id),
                to_type="chat",
                to_id=str(sidechain.id),
                link_type=LinkType.SPAWNED,
                source_type=LinkSourceType.INFERRED,
                confidence_score=0.8,
                link_metadata={"source": "sidechain_inference"},
            )
            db.add(link)
```

### Step 4: Frontend — API Types (10 min)

**File**: `frontend/src/lib/api.ts`

```typescript
export interface Agent {
  // ... existing fields ...
  parent_agent_id: string | null;
  child_count: number;
  origin_type: string | null;  // "sidechain", "spawn", null
}
```

Add children fetch:
```typescript
agentChildren: async (agentId: string): Promise<{ agents: Agent[]; total: number }> => {
  const res = await fetch(`${API}/agents/${agentId}/children`);
  return res.json();
},
```

### Step 5: Frontend — Agent List Hierarchy (2-3 hours)

**File**: `frontend/src/app/agents/page.tsx`

Build a tree from the flat agent list client-side:

```typescript
interface AgentTreeNode {
  agent: Agent;
  children: AgentTreeNode[];
  expanded: boolean;
}

function buildAgentTree(agents: Agent[]): AgentTreeNode[] {
  const agentMap = new Map<string, AgentTreeNode>();
  const roots: AgentTreeNode[] = [];

  // First pass: create nodes
  for (const agent of agents) {
    agentMap.set(agent.id, { agent, children: [], expanded: false });
  }

  // Second pass: link parents to children
  for (const agent of agents) {
    const node = agentMap.get(agent.id)!;
    if (agent.parent_agent_id && agentMap.has(agent.parent_agent_id)) {
      agentMap.get(agent.parent_agent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}
```

Render with indentation:

```typescript
function renderAgentTree(nodes: AgentTreeNode[], depth: number = 0) {
  return nodes.map(node => (
    <Fragment key={node.agent.id}>
      <AgentRow
        agent={node.agent}
        depth={depth}
        childCount={node.children.length}
        expanded={node.expanded}
        onToggleExpand={() => toggleExpand(node.agent.id)}
        onAgentClick={handleAgentClick}
        onHide={handleHide}
        onUnhide={handleUnhide}
      />
      {node.expanded && node.children.length > 0 &&
        renderAgentTree(node.children, depth + 1)
      }
    </Fragment>
  ));
}
```

### Step 6: Frontend — AgentRow Indentation (1 hour)

**File**: `frontend/src/components/agents/AgentRow.tsx`

Add depth, childCount, and expand/collapse to AgentRow:

```typescript
interface AgentRowProps {
  agent: Agent;
  depth?: number;         // 0 = top-level, 1 = first child, etc.
  childCount?: number;    // number of children
  expanded?: boolean;     // whether children are shown
  onToggleExpand?: () => void;
  onAgentClick?: (agent: Agent) => void;
  onHide?: (id: string) => void;
  onUnhide?: (id: string) => void;
}
```

Visual changes:
- Left padding: `paddingLeft: depth * 24px`
- Collapse/expand chevron before the status badge (if `childCount > 0`)
- Subtle vertical connector line for children (left border on indented rows)
- Child count badge next to agent title: `(3 subagents)`
- Sidechain origin badge: small "sidechain" label in zinc-600

```tsx
<div
  className="flex items-center gap-2 p-3 rounded-lg border border-zinc-800 hover:bg-zinc-800/50 cursor-pointer"
  style={{ marginLeft: (depth ?? 0) * 24 }}
>
  {/* Expand/collapse toggle */}
  {(childCount ?? 0) > 0 && (
    <button onClick={(e) => { e.stopPropagation(); onToggleExpand?.(); }}>
      {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
    </button>
  )}
  {/* Indent spacer for childless agents at depth > 0 */}
  {(childCount ?? 0) === 0 && (depth ?? 0) > 0 && (
    <div className="w-4" /> {/* spacer to align with siblings that have chevrons */}
  )}

  {/* ...existing row content... */}
</div>
```

---

## Edge Cases

### Orphaned Subagents

Subagents whose parent is hidden, deleted, or not in the current filter results.

**Solution**: Show orphaned subagents as top-level entries with a subtle "parent: [title]" label linking to the parent. When the parent is present but collapsed, the child is hidden. When the parent is absent (filtered out), the child promotes to top-level.

### Deep Nesting

The Agent tool can theoretically nest N levels deep (agent spawns agent spawns agent).

**Solution**: Cap visual indentation at depth 3 (72px). Deeper levels still indent logically but stop adding visual padding. This prevents the row content from being squeezed too narrow.

### Sidechain Inference Accuracy

The heuristic (same project dir + overlapping time window) could mis-assign parents if two non-sidechain sessions are active simultaneously in the same project.

**Solution**: Use `confidence_score=0.8` on inferred links (vs 1.0 for explicit). Show inferred relationships with a dotted connector line instead of solid. Allow manual re-parenting via a dropdown in AgentRow's context menu.

### Cart-Launch Multi-Parent

Cart-launch creates agents with multiple sources. These are `DERIVED_FROM` relationships, not `SPAWNED`.

**Solution**: Cart-launched agents use `parent_chat_id` pointing to the first source agent. The full lineage is available via EntityLinks. In the UI, cart-launched agents appear under the first source with a badge showing "from N sessions". The context panel shows all source links.

### Session Sync Performance

Including sidechains could significantly increase the number of agents synced.

**Solution**: Sidechains are typically short-lived (few messages). Add a filter to skip sidechains with `message_count < 2` (empty or single-exchange sessions). This reduces noise without losing meaningful subagent work.

### Filter Interaction

When a parent matches the filter but children don't (or vice versa):
- **Parent matches, children don't**: Show parent with child count badge, children hidden even when expanded
- **Child matches, parent doesn't**: Promote child to top-level, show "parent: [title]" breadcrumb
- **Neither matches**: Both hidden (normal filter behavior)

---

## Implementation Order

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 1 | Add `parent_agent_id` to spawn request + set `parent_chat_id` + create EntityLink | 30 min | None |
| 2 | Update cart-launch to set `parent_chat_id` | 15 min | None |
| 3 | Add `parent_agent_id` + `child_count` to agent list response | 30 min | None |
| 4 | Add `/agents/{id}/children` endpoint | 20 min | None |
| 5 | Stop filtering sidechains in sync, add sidechain parent inference | 1 hour | None |
| 6 | Frontend: update `Agent` type, add `agentChildren` API call | 10 min | Steps 3-4 |
| 7 | Frontend: `buildAgentTree()` in agents page, expand/collapse state | 1 hour | Step 6 |
| 8 | Frontend: `AgentRow` indentation, chevron, connector lines | 1.5 hours | Step 7 |
| 9 | Handle edge cases: orphans, filter interaction, depth cap | 1 hour | Step 8 |
| 10 | Manual re-parenting UI (context menu dropdown) | 1 hour | Step 8 |

**Total estimated effort**: ~7 hours (~1 day focused work)

**No database migration needed** — `parent_chat_id` FK already exists and is indexed. The `origin_type` field also exists. Only new code changes required.

---

## Testing Plan

### Backend

```bash
# 1. Spawn with parent
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{"initial_prompt": "child task", "parent_agent_id": "<parent-uuid>"}'

# 2. Verify parent_chat_id set
curl http://localhost:8000/agents/<child-uuid>
# → parent_agent_id: <parent-uuid>

# 3. Verify EntityLink created
# SQL: SELECT * FROM entity_links WHERE link_type = 'spawned';

# 4. List with child counts
curl http://localhost:8000/agents
# → each agent has child_count field

# 5. Get children
curl http://localhost:8000/agents/<parent-uuid>/children

# 6. Sync with sidechains
curl -X POST http://localhost:8000/agents/sync
# → sidechains appear with origin_type="sidechain" and inferred parent_chat_id
```

### Frontend

- [ ] Parent agents show chevron + child count badge
- [ ] Clicking chevron expands/collapses children
- [ ] Children are indented under parent
- [ ] Max indent depth is 3 levels
- [ ] Orphaned children (parent filtered out) appear at top level
- [ ] Search/filter works correctly with hierarchy
- [ ] Sidechain agents show "sidechain" origin badge
- [ ] Cart-launched agents show "from N sessions" badge
