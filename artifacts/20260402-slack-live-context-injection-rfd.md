# RFD: Live Slack Context Injection into Agent Chats

**Date**: 2026-04-02
**Author**: Aaryn Olsson
**Status**: Draft
**Component**: Commander Dashboard — Agent Chat

---

## Problem

Agents operate on JIRA tickets and code, but the real-time state of work at Planet lives in Slack.

**Today:**

- Teammates discuss issues, post deploy updates, flag blockers, and coordinate mitigation in Slack
- Agents do not see this activity unless manually pasted by a user
- Slack context is only injected when the user sends a message

**This creates a fundamental gap:**

- Agents miss real-time operational signals
- Agents operate on stale or incomplete context
- Parallel work (debugging, rollback, mitigation) is invisible to the agent

**Even worse:**

- If the agent is idle → it misses updates
- If the agent is processing → it still misses updates
- There is no persistent mechanism to capture and deliver context

This is not just a UX issue — it is a **situational awareness failure**.

---

## Principle

> Slack is the communications lifeblood of Planet.

Therefore:

> Relevant Slack activity must be treated as **durable, first-class context** for agents — not as an optional augmentation.

From this follows a hard requirement:

> **Agents must never lose relevant Slack context.** Delivery timing may vary, but capture must be guaranteed.

---

## Goal

Ensure that agents working on a JIRA ticket, branch, or MR are:

1. **Continuously aware** of relevant Slack activity
2. **Guaranteed** to receive all relevant context
3. **Not disrupted unnecessarily** during active processing
4. **Able to act** on fresh operational signals

---

## Current Architecture

```
Slack Channels
    ↓ (launchd, every 10min)
sync-channel.py → markdown files
    ↓ (hourly)
slack_thread_sync → SlackThread records (jira_keys, gitlab_mr_refs)
    ↓ (hourly)
slack_thread_enrichment → EntityLinks (JIRA ↔ SlackThread)

Agent Chat (on user message):
    → _inject_jira_context()
    → _inject_slack_context()
    → process_manager.send_message()
```

**Key limitation:**

- Slack context is injected only on user messages
- No persistence
- No event-driven updates
- No delivery guarantees

---

## Design Options

### Option 1: Push Model (Immediate Injection)

Inject Slack updates directly into agent sessions as they occur.

**Fatal flaw:**
Messages are dropped if the agent is processing.

→ **Violates:** "Agents must never lose context"

### Option 2: Pull Model (Agent Tool)

Agent queries Slack when it chooses.

**Fatal flaw:**
Relies on agent behavior → not guaranteed.

→ **Violates:** "Capture must be guaranteed"

### Option 3: Context Queue (Deferred Push) ✅

Slack events are captured immediately and stored in a per-agent queue, then delivered at safe points.

---

## Chosen Architecture: Context Queue (Option 3)

### Core Idea

**Separate capture from delivery.**

- Capture is immediate and guaranteed
- Delivery is controlled and efficient

### Data Flow

```
Slack sync runs (every 10min)
    → Detect new relevant Slack messages
    → Match jira_key / MR to active agents
    → Append to agent_context_queue (durable)

Delivery triggers:
    1. User sends message
    2. Agent finishes processing (idle)
    3. (Optional) High-priority escalation → immediate push
```

---

## Agent Context Queue

### Properties

- Per-agent
- Durable (DB-backed)
- TTL-bound (e.g., 24h)
- Size-limited (e.g., 20–50 items)
- Ordered (time-based)

### Guarantees

- No Slack message is lost
- No race conditions with agent processing
- Context survives restarts
- Multiple updates are batched efficiently

---

## Injection Behavior

### On User Message

```
→ _inject_slack_context()
    → Drain queue
    → Prepend batched Slack updates
    → Clear queue
```

### On Agent Idle (Post-Processing)

```
→ If queue not empty:
    → Send context update turn
    → "Slack updates since last turn:"
    → Drain queue
```

### High-Priority Escalation (Hybrid)

For messages matching urgency signals:

- `SEV`, `incident`, `@here`, `@channel`, rollback alerts

```
→ Bypass queue
→ Immediate injection (Option 1 behavior)
→ Only if agent is idle
```

---

## Why This Is the Right Model

### 1. Guarantees Delivery

Unlike push or pull:

- No dropped messages
- No reliance on agent behavior

→ **Hard requirement satisfied**

### 2. Preserves Agent Stability

- No mid-processing interruptions
- No race conditions
- No rejected messages

→ **System remains predictable**

### 3. Efficient Use of Context Window

- Multiple Slack updates → single injection
- Reduces token usage
- Improves coherence

### 4. Aligns With Human Workflow

Humans don't process Slack messages one-by-one in isolation — they batch and interpret context.

Agents should behave the same way.

### 5. Enables Future Extensions

This model becomes the backbone for:

- Incident awareness
- Cross-agent coordination
- Activity timelines
- "What changed since last turn?" summaries

---

## Comparison

| Dimension | Push | Pull | Queue (Chosen) |
|-----------|:----:|:----:|:--------------:|
| **Context Loss** | ❌ Possible | ❌ Likely | ✅ Never |
| **Interruptions** | ❌ High | ✅ None | ✅ None |
| **Reliability** | ❌ Weak | ⚠️ Behavioral | ✅ Strong |
| **Cost** | ❌ High | ✅ Low | ✅ Moderate |
| **Real-Time** | ✅ Yes | ❌ No | ⚠️ Controlled |
| **Scalability** | ❌ Noisy | ⚠️ Unreliable | ✅ Clean |

---

## Open Questions

### 1. Multi-Agent Context

If multiple agents share a JIRA key:

- Default: fan-out to all agents
- Future: designate primary agent

### 2. User Visibility

Should users see pending Slack context?

- Recommendation: yes (later phase)
- "Slack updates pending (3)"
- Improves trust and debuggability

### 3. Queue Summarization

If queue grows large:

- Summarize older entries before injection
- Preserve key signals

### 4. Opt-Out

Allow:

- Per-agent toggle
- Per-session toggle

But default should be **ON**.

---

## Final Position

> Slack is not supplementary context — it is **operational truth**.

Therefore:

1. Context must be **captured immediately**
2. Context must be **delivered reliably**
3. Context must be **presented coherently**

**Option 3 (Context Queue) is the only design that satisfies all three.**

---

---

# Implementation Plan

## Overview

The implementation is divided into **5 work streams** that can be executed in parallel. Each stream is scoped to fit within a single Opus-sized chat session.

```
Stream 1: Database & Models ──────────────────┐
Stream 2: Queue Service & Capture ─────────────┤
Stream 3: Delivery (Injection + Idle Hook) ────┤──→ Integration Testing
Stream 4: High-Priority Escalation Path ───────┤
Stream 5: Frontend Queue Visibility ───────────┘
```

**Dependencies:**

- Stream 1 must complete first (other streams depend on the DB model)
- Streams 2–5 can run in parallel after Stream 1
- Stream 3 depends on Stream 2 (needs queue service to drain)

---

## Stream 1: Database & Models

**Goal**: Create the `agent_context_queue` table and SQLAlchemy model.

**Scope**: Backend only. No service logic.

### Tasks

1. **Create Alembic migration** for `agent_context_queue` table:

```sql
CREATE TABLE agent_context_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR NOT NULL,          -- agent UUID (matches Agent.id)
    jira_key VARCHAR,                   -- JIRA key that triggered the match
    source VARCHAR NOT NULL DEFAULT 'slack',  -- 'slack', future: 'pagerduty', 'gitlab'
    source_id VARCHAR,                  -- slack thread_ts or channel+ts identifier
    channel_name VARCHAR,               -- #compute-platform
    author VARCHAR,                     -- who posted the Slack message
    content TEXT NOT NULL,              -- the Slack message text (truncated)
    permalink VARCHAR,                  -- link to Slack message
    priority VARCHAR NOT NULL DEFAULT 'normal',  -- 'normal' or 'high'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ttl_expiry TIMESTAMPTZ NOT NULL,    -- auto-expire (default: created_at + 24h)
    delivered_at TIMESTAMPTZ,           -- NULL until drained

    -- Indexes
    INDEX ix_acq_agent_id (agent_id),
    INDEX ix_acq_agent_pending (agent_id, delivered_at) WHERE delivered_at IS NULL,
    INDEX ix_acq_ttl (ttl_expiry)
);
```

2. **Create SQLAlchemy model** at `backend/app/models/agent_context_queue.py`:

```python
class AgentContextQueueItem(Base):
    __tablename__ = "agent_context_queue"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    jira_key: Mapped[str | None]
    source: Mapped[str] = mapped_column(String, default="slack")
    source_id: Mapped[str | None]
    channel_name: Mapped[str | None]
    author: Mapped[str | None]
    content: Mapped[str] = mapped_column(Text, nullable=False)
    permalink: Mapped[str | None]
    priority: Mapped[str] = mapped_column(String, default="normal")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    ttl_expiry: Mapped[datetime]
    delivered_at: Mapped[datetime | None]
```

3. **Add model to `__init__.py`** exports.

4. **Add TTL cleanup job** (simple query: `DELETE FROM agent_context_queue WHERE ttl_expiry < now()`), registered as a periodic task.

### Files Modified
- `backend/app/models/agent_context_queue.py` (new)
- `backend/app/models/__init__.py`
- `backend/alembic/versions/xxxx_add_agent_context_queue.py` (new)
- `backend/app/main.py` (register cleanup job)

### Acceptance Criteria
- [ ] Migration runs without error
- [ ] Model can create/read/delete records
- [ ] TTL cleanup deletes expired records

---

## Stream 2: Queue Service & Capture

**Goal**: Build the service that enqueues Slack messages for matching agents, and wire it into the Slack sync pipeline.

**Depends on**: Stream 1 (model must exist)

### Tasks

1. **Create `AgentContextQueueService`** at `backend/app/services/agent_context_queue.py`:

```python
class AgentContextQueueService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self,
        agent_id: str,
        content: str,
        jira_key: str | None = None,
        source: str = "slack",
        source_id: str | None = None,
        channel_name: str | None = None,
        author: str | None = None,
        permalink: str | None = None,
        priority: str = "normal",
        ttl_hours: int = 24,
    ) -> AgentContextQueueItem:
        """Add an item to an agent's context queue."""

    async def drain(
        self,
        agent_id: str,
        max_items: int = 20,
    ) -> list[AgentContextQueueItem]:
        """Drain pending items for an agent (marks as delivered)."""

    async def peek(
        self,
        agent_id: str,
    ) -> int:
        """Return count of pending items without draining."""

    async def find_agents_for_jira_key(
        self,
        jira_key: str,
    ) -> list[str]:
        """Find active agent IDs that are working on a JIRA key."""

    async def cleanup_expired(self) -> int:
        """Delete items past TTL. Returns count deleted."""
```

2. **Key implementation details for `drain()`**:
   - Query: `WHERE agent_id = :id AND delivered_at IS NULL ORDER BY created_at ASC LIMIT :max`
   - Deduplicate by `source_id` (same Slack message shouldn't queue twice)
   - Mark all returned items `delivered_at = now()`
   - Return ordered list

3. **Key implementation for `find_agents_for_jira_key()`**:
   - Query Agent table: `WHERE jira_key = :key AND status IN ('live', 'idle')`
   - Return list of agent IDs

4. **Wire into Slack sync** — Modify `backend/app/jobs/slack_thread_sync.py`:

```python
# After syncing a thread that has jira_keys:
async def _enqueue_for_agents(db, thread: SlackThread):
    service = AgentContextQueueService(db)

    for jira_key in (thread.jira_key_list or []):
        agent_ids = await service.find_agents_for_jira_key(jira_key)

        if not agent_ids:
            continue

        # Get recent messages from this thread (last 5)
        recent = (thread.messages or [])[-5:]

        for msg in recent:
            source_id = f"{thread.channel_id}:{msg.get('ts', '')}"

            for agent_id in agent_ids:
                await service.enqueue(
                    agent_id=agent_id,
                    content=msg.get("text", "")[:500],
                    jira_key=jira_key,
                    source_id=source_id,
                    channel_name=thread.channel_name,
                    author=msg.get("user_name", msg.get("user", "unknown")),
                    permalink=thread.permalink,
                    priority=_detect_priority(msg),
                )

    await db.commit()


def _detect_priority(msg: dict) -> str:
    """Detect high-priority signals in a Slack message."""
    text = (msg.get("text", "") or "").lower()
    HIGH_SIGNALS = [
        "sev1", "sev2", "severity 1", "severity 2",
        "@here", "@channel",
        "incident", "outage", "rollback",
        "pages", "paging", "pagerduty",
        "critical", "urgent", "emergency",
    ]
    if any(signal in text for signal in HIGH_SIGNALS):
        return "high"
    return "normal"
```

5. **Deduplication guard**: Before enqueueing, check if `source_id` already exists for this `agent_id` (prevents re-enqueue on repeated syncs).

### Files Modified
- `backend/app/services/agent_context_queue.py` (new)
- `backend/app/jobs/slack_thread_sync.py` (add `_enqueue_for_agents` call)

### Acceptance Criteria
- [ ] `enqueue()` creates records with correct TTL
- [ ] `drain()` returns items in order and marks delivered
- [ ] `drain()` deduplicates by source_id
- [ ] Slack sync creates queue items for matching agents
- [ ] Items are not re-enqueued on subsequent syncs (source_id guard)
- [ ] `cleanup_expired()` removes old records

---

## Stream 3: Delivery (Injection + Idle Hook)

**Goal**: Replace the current `_inject_slack_context()` with queue-draining injection, and add an idle-trigger for automatic delivery.

**Depends on**: Stream 1 (model), Stream 2 (queue service)

### Tasks

1. **Replace `_inject_slack_context()`** in `backend/app/api/agents.py`:

```python
async def _inject_slack_context(message: str, agent: dict, db: AsyncSession) -> str:
    """Inject queued Slack context into agent messages.

    Drains the agent's context queue and prepends all pending
    Slack updates as a context block.
    """
    agent_id = agent.get("id")
    if not agent_id:
        return message

    from app.services.agent_context_queue import AgentContextQueueService

    service = AgentContextQueueService(db)
    items = await service.drain(agent_id, max_items=20)

    if not items:
        return message

    lines = []
    lines.append(f"[Slack Context: {len(items)} new messages since your last turn]")
    lines.append("")

    current_channel = None
    for item in items:
        # Group by channel
        if item.channel_name != current_channel:
            current_channel = item.channel_name
            lines.append(f"#{current_channel}:")

        age = _format_age(item.created_at)
        author = item.author or "unknown"
        content = item.content
        if len(content) > 300:
            content = content[:300] + "..."

        priority_marker = " [URGENT]" if item.priority == "high" else ""
        lines.append(f"  {author} ({age}){priority_marker}: {content}")

        if item.permalink:
            lines.append(f"    → {item.permalink}")

    lines.append("")
    context = "\n".join(lines) + "\n"
    return context + message


def _format_age(dt: datetime) -> str:
    """Format a datetime as a human-readable age string."""
    if not dt:
        return ""
    delta = datetime.now(timezone.utc) - dt
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"
```

2. **Add idle-trigger delivery** — When an agent finishes processing and has queued context, auto-send a context update turn.

   Modify `backend/app/services/process_manager.py` in `_run_turn()`, after processing completes:

```python
# At the end of _run_turn(), after session.is_processing = False:

# Check for queued context and send if available
asyncio.create_task(self._check_and_deliver_queued_context(session))
```

   Add method to ProcessManager:

```python
async def _check_and_deliver_queued_context(self, session: AgentSession):
    """After processing completes, check if there's queued Slack context to deliver."""
    # Small delay to let the session settle
    await asyncio.sleep(2)

    # Don't deliver if already processing again
    if session.is_processing:
        return

    try:
        async with async_session() as db:
            from app.services.agent_context_queue import AgentContextQueueService
            from app.services.agent_service import get_agents

            service = AgentContextQueueService(db)

            # Find the agent record for this session
            agents = await get_agents(db)
            agent = next(
                (a for a in agents if a["claude_session_id"] == session.session_id),
                None
            )
            if not agent:
                return

            count = await service.peek(agent["id"])
            if count == 0:
                return

            # Drain and build context message
            items = await service.drain(agent["id"], max_items=20)
            if not items:
                return

            lines = [f"[Slack Update: {len(items)} new messages while you were working]", ""]
            current_channel = None
            for item in items:
                if item.channel_name != current_channel:
                    current_channel = item.channel_name
                    lines.append(f"#{current_channel}:")
                author = item.author or "unknown"
                content = item.content[:300]
                priority_marker = " [URGENT]" if item.priority == "high" else ""
                lines.append(f"  {author}{priority_marker}: {content}")
            lines.append("")
            lines.append("Note this context. No action required unless directly relevant to your current task.")

            context_message = "\n".join(lines)

            # Send as a new turn
            await self._run_turn(session, context_message, is_new=False)

            logger.info(f"Delivered {len(items)} queued Slack context items to session {session.session_id}")

    except Exception as e:
        logger.warning(f"Failed to deliver queued context to {session.session_id}: {e}")
```

3. **Update ChatMessage frontend strip** to also strip the `[Slack Update: ...]` variant:

```typescript
// In stripInjectedContext():
cleaned = cleaned.replace(/^\[Slack Update: [^\]]*\]\n[\s\S]*?No action required unless directly relevant[^\n]*\n\n/i, '');
```

### Files Modified
- `backend/app/api/agents.py` (replace `_inject_slack_context`)
- `backend/app/services/process_manager.py` (add idle delivery hook)
- `frontend/src/components/agents/ChatMessage.tsx` (update strip function)

### Acceptance Criteria
- [ ] User message drains queue and prepends context
- [ ] Idle agent auto-receives queued context after processing completes
- [ ] Context is grouped by channel with author and age
- [ ] High-priority items are marked `[URGENT]`
- [ ] Frontend strips injected Slack context from user message display
- [ ] Idle delivery includes "no action required" guidance

---

## Stream 4: High-Priority Escalation Path

**Goal**: For incident-level Slack messages, bypass the queue and inject immediately (if agent is idle).

**Depends on**: Stream 2 (queue service, priority detection)

### Tasks

1. **Add escalation logic to queue service**:

```python
async def escalate_if_possible(
    self,
    agent_id: str,
    item: AgentContextQueueItem,
) -> bool:
    """Attempt immediate delivery for high-priority items.

    Returns True if delivered, False if queued for later.
    """
    # Check if agent session is idle
    from app.services.process_manager import process_manager
    from app.services.agent_service import get_agent_by_id

    async with async_session() as db:
        agent = await get_agent_by_id(db, agent_id)

    if not agent:
        return False

    session_id = agent.get("claude_session_id")
    session = process_manager.get(session_id)

    if not session or session.is_processing:
        return False  # Will be delivered via queue

    # Immediate delivery
    context = (
        f"[URGENT Slack Alert: #{item.channel_name}]\n"
        f"{item.author}: {item.content}\n"
        f"→ {item.permalink}\n\n"
        f"This may require your attention."
    )

    success = await process_manager.send_message(session_id, context)
    if success:
        item.delivered_at = datetime.now(timezone.utc)
        return True

    return False
```

2. **Wire into enqueue path**:

```python
# In _enqueue_for_agents():
if priority == "high":
    delivered = await service.escalate_if_possible(agent_id, item)
    if delivered:
        continue  # Skip normal enqueue
```

### Files Modified
- `backend/app/services/agent_context_queue.py` (add `escalate_if_possible`)
- `backend/app/jobs/slack_thread_sync.py` (wire escalation into enqueue)

### Acceptance Criteria
- [ ] High-priority messages attempt immediate delivery
- [ ] If agent is busy, high-priority items remain in queue (not lost)
- [ ] Escalation keywords correctly detected (SEV, incident, @here, etc.)
- [ ] Immediate delivery sends a single context turn to idle agent

---

## Stream 5: Frontend Queue Visibility

**Goal**: Show users how many Slack context items are pending for their agent.

**Depends on**: Stream 2 (queue service peek endpoint)

### Tasks

1. **Add API endpoint** `GET /agents/{id}/context-queue`:

```python
@router.get("/{agent_id}/context-queue")
async def get_context_queue(agent_id: str, db: AsyncSession = Depends(get_db)):
    from app.services.agent_context_queue import AgentContextQueueService

    service = AgentContextQueueService(db)
    count = await service.peek(agent_id)

    # Optionally return preview of items
    items = []
    if count > 0:
        pending = await service.drain(agent_id, max_items=0)  # peek without drain
        # Actually we need a peek-with-preview method

    return {"pending_count": count}
```

2. **Add peek-with-preview** to service:

```python
async def preview(self, agent_id: str, limit: int = 5) -> list[AgentContextQueueItem]:
    """Preview pending items without marking as delivered."""
    result = await self.db.execute(
        select(AgentContextQueueItem)
        .where(
            AgentContextQueueItem.agent_id == agent_id,
            AgentContextQueueItem.delivered_at.is_(None),
            AgentContextQueueItem.ttl_expiry > func.now(),
        )
        .order_by(AgentContextQueueItem.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
```

3. **Frontend: Add queue indicator to ChatView header**:

```tsx
// In ChatView, poll for queue count
const [queueCount, setQueueCount] = useState(0);

useEffect(() => {
  const interval = setInterval(async () => {
    try {
      const data = await api.agentContextQueue(agent.id);
      setQueueCount(data.pending_count);
    } catch {}
  }, 30_000); // Every 30s
  return () => clearInterval(interval);
}, [agent.id]);

// In header:
{queueCount > 0 && (
  <Badge className="bg-amber-500/20 text-amber-400 border-amber-600/30 text-[10px]">
    {queueCount} Slack update{queueCount !== 1 ? "s" : ""} pending
  </Badge>
)}
```

4. **Add API method to frontend api.ts**:

```typescript
agentContextQueue: (id: string) =>
    fetchApi<{ pending_count: number }>(`/agents/${id}/context-queue`),
```

### Files Modified
- `backend/app/api/agents.py` (add endpoint)
- `backend/app/services/agent_context_queue.py` (add `preview`)
- `frontend/src/lib/api.ts` (add method)
- `frontend/src/components/agents/ChatView.tsx` (add indicator)

### Acceptance Criteria
- [ ] API returns pending count
- [ ] ChatView header shows "N Slack updates pending" badge
- [ ] Badge disappears when queue is empty
- [ ] Polling every 30s (not too aggressive)

---

## Execution Order

```
Phase 1 (Sequential):
  └── Stream 1: Database & Models              ~1 session

Phase 2 (Parallel — launch all 4 simultaneously):
  ├── Stream 2: Queue Service & Capture         ~1 session
  ├── Stream 3: Delivery + Idle Hook            ~1 session
  ├── Stream 4: High-Priority Escalation        ~1 session (small)
  └── Stream 5: Frontend Queue Visibility       ~1 session (small)

Phase 3 (Sequential):
  └── Integration Testing                       ~1 session
      - End-to-end: Slack message → queue → agent delivery
      - Edge cases: TTL expiry, multi-agent fan-out, dedup
      - Load: 50 queued items, large Slack threads
```

**Total**: ~6 Opus-sized sessions, with 4 running in parallel.

**Estimated wall-clock time**: 3 phases × ~1 session each = ~3 session cycles.

---

## Subagent Assignment

| Stream | Subagent | Prerequisites | Can Parallel? |
|--------|----------|---------------|:---:|
| 1: DB & Models | Agent A | None | No (must go first) |
| 2: Queue Service | Agent B | Stream 1 complete | Yes |
| 3: Delivery | Agent C | Stream 1 complete | Yes (needs Stream 2 for integration) |
| 4: Escalation | Agent D | Stream 2 complete | Yes |
| 5: Frontend | Agent E | Stream 2 complete | Yes |
| Integration | Main | All streams complete | No |

**Stream 3 note**: Can start implementation in parallel with Stream 2, but needs Stream 2's `drain()` method for integration testing. Start with the `_inject_slack_context` rewrite and idle hook, stub the queue service call.

---

## Future Extensions (Post-MVP)

1. **Queue summarization** — If queue > 10 items, summarize older entries before injection
2. **Relevance scoring** — Weight messages by participant overlap, message length, reactions
3. **Cross-agent coordination** — When Agent A receives Slack context, notify Agent B if they share a JIRA key
4. **Activity timeline** — Show Slack activity timeline alongside chat history in the UI
5. **Opt-out controls** — Per-agent and per-session toggle for Slack injection
6. **Non-Slack sources** — Extend queue to capture PagerDuty updates, GitLab pipeline events, Google Doc comments
