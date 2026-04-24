"""Agent Context Queue service — enqueue, drain, and manage context updates for agents."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_context_queue import AgentContextQueueItem

logger = logging.getLogger(__name__)


class AgentContextQueueService:
    """Manages the per-agent context queue.

    Items are enqueued when relevant Slack activity (or other sources) is
    detected for an agent's JIRA key.  They are drained and injected into
    the agent's next interaction.
    """

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
    ) -> AgentContextQueueItem | None:
        """Enqueue a context update for an agent.

        Deduplicates on (agent_id, source_id) — if an item with the same
        source_id already exists for this agent, the call is a no-op.

        The item is added to the session but NOT committed; the caller is
        responsible for committing the transaction.

        Returns:
            The newly created AgentContextQueueItem, or None if duplicate.
        """
        # Duplicate check on source_id
        if source_id:
            existing = await self.db.execute(
                select(AgentContextQueueItem).where(
                    AgentContextQueueItem.agent_id == agent_id,
                    AgentContextQueueItem.source_id == source_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.debug(
                    "Skipping duplicate context queue item: agent=%s source_id=%s",
                    agent_id,
                    source_id,
                )
                return None

        now = datetime.now(timezone.utc)
        item = AgentContextQueueItem(
            agent_id=agent_id,
            jira_key=jira_key,
            source=source,
            source_id=source_id,
            channel_name=channel_name,
            author=author,
            content=content,
            permalink=permalink,
            priority=priority,
            created_at=now,
            ttl_expiry=now + timedelta(hours=ttl_hours),
        )
        self.db.add(item)
        return item

    async def drain(
        self, agent_id: str, max_items: int = 20
    ) -> list[AgentContextQueueItem]:
        """Drain pending items for an agent, marking them as delivered.

        Returns up to *max_items* oldest pending (undelivered, non-expired)
        items.  Each returned item has its ``delivered_at`` set to now.

        The session is flushed but NOT committed.
        """
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(AgentContextQueueItem)
            .where(
                AgentContextQueueItem.agent_id == agent_id,
                AgentContextQueueItem.delivered_at.is_(None),
                AgentContextQueueItem.ttl_expiry > now,
            )
            .order_by(AgentContextQueueItem.created_at.asc())
            .limit(max_items)
        )
        items = list(result.scalars().all())

        for item in items:
            item.delivered_at = now

        await self.db.flush()
        return items

    async def peek(self, agent_id: str) -> int:
        """Return the count of pending (undelivered, non-expired) items."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(func.count())
            .select_from(AgentContextQueueItem)
            .where(
                AgentContextQueueItem.agent_id == agent_id,
                AgentContextQueueItem.delivered_at.is_(None),
                AgentContextQueueItem.ttl_expiry > now,
            )
        )
        return result.scalar_one()

    async def preview(
        self, agent_id: str, limit: int = 5
    ) -> list[AgentContextQueueItem]:
        """Preview pending items without marking them as delivered."""
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(AgentContextQueueItem)
            .where(
                AgentContextQueueItem.agent_id == agent_id,
                AgentContextQueueItem.delivered_at.is_(None),
                AgentContextQueueItem.ttl_expiry > now,
            )
            .order_by(AgentContextQueueItem.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_agents_for_jira_key(self, jira_key: str) -> list[str]:
        """Find active agents working on a given JIRA key.

        Returns a list of agent_id strings (UUIDs cast to str) for agents
        whose ``jira_key`` matches and whose status is 'live' or 'idle'.
        """
        from app.models.agent import Agent

        result = await self.db.execute(
            select(Agent.id).where(
                Agent.jira_key == jira_key,
                Agent.status.in_(["live", "idle"]),
            )
        )
        return [str(row[0]) for row in result.all()]

    async def escalate_if_possible(
        self,
        agent_id: str,
        item: AgentContextQueueItem,
    ) -> bool:
        """Attempt immediate delivery for high-priority items.

        If the agent is idle (not processing), sends the context as an
        immediate turn.  Returns True if delivered, False if the item
        should remain in the queue for later delivery.
        """
        from app.services.process_manager import process_manager
        from app.models.agent import Agent

        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent_row = result.scalar_one_or_none()
        if not agent_row or not agent_row.claude_session_id:
            return False

        session = process_manager.get(agent_row.claude_session_id)
        if not session or session.is_processing:
            return False  # Will be delivered via queue drain

        context = (
            f"[URGENT Slack Alert: #{item.channel_name or 'unknown'}]\n"
            f"{item.author or 'unknown'}: {item.content}\n"
        )
        if item.permalink:
            context += f"→ {item.permalink}\n"
        context += "\nThis may require your attention."

        success = await process_manager.send_message(
            agent_row.claude_session_id, context
        )
        if success:
            item.delivered_at = datetime.now(timezone.utc)
            await self.db.flush()
            return True

        return False

    # ── Matching Engine ──────────────────────────────────────────────

    _BRANCH_BLOCKLIST = frozenset([
        "main", "master", "develop", "staging", "production",
        "dev", "fix", "feat", "chore",
    ])

    HIGH_SIGNALS = [
        "sev", "incident", "@here", "@channel", "rollback",
        "outage", "critical", "urgent", "emergency", "pagerduty",
    ]

    async def find_agents_for_mr_ref(self, mr_ref: str) -> list[str]:
        """Find active agents linked to a merge request.

        Args:
            mr_ref: MR reference like "!847", "847", or "wx/wx!847"

        Returns list of agent_id strings.
        """
        from app.models.agent import Agent
        from app.models.gitlab_merge_request import GitLabMergeRequest

        # Parse MR number — strip repo prefix and leading "!"
        ref_str = mr_ref.rsplit("!", 1)[-1] if "!" in mr_ref else mr_ref
        try:
            mr_number = int(ref_str)
        except ValueError:
            logger.warning("Could not parse MR number from ref: %s", mr_ref)
            return []

        # Look up the MR in our database
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                GitLabMergeRequest.external_mr_id == mr_number,
            )
        )
        mrs = list(result.scalars().all())

        agent_ids: set[str] = set()

        for mr in mrs:
            # Match via JIRA keys on the MR
            if mr.jira_keys:
                for jira_key in mr.jira_keys:
                    matched = await self.find_agents_for_jira_key(jira_key)
                    agent_ids.update(matched)

            # Match via branch name — agents whose git_branch matches
            # the MR source branch
            if mr.source_branch:
                branch_result = await self.db.execute(
                    select(Agent.id).where(
                        Agent.status.in_(["live", "idle"]),
                        Agent.git_branch.isnot(None),
                        Agent.git_branch == mr.source_branch,
                    )
                )
                for row in branch_result.all():
                    agent_ids.add(str(row[0]))

        return list(agent_ids)

    async def find_agents_for_branch(self, branch_name: str) -> list[str]:
        """Find active agents working on a specific git branch.

        Matches agents whose git_branch exactly equals or ends with the
        branch name.  Filters out short/generic branch names to avoid
        false positives.
        """
        from app.models.agent import Agent

        # Guard against overly generic branch names
        if len(branch_name) < 5 or branch_name in self._BRANCH_BLOCKLIST:
            return []

        result = await self.db.execute(
            select(Agent.id, Agent.git_branch).where(
                Agent.status.in_(["live", "idle"]),
                Agent.git_branch.isnot(None),
            )
        )
        rows = result.all()

        agent_ids: list[str] = []
        for row in rows:
            agent_branch: str = row[1]
            if agent_branch == branch_name or agent_branch.endswith(f"/{branch_name}"):
                agent_ids.append(str(row[0]))

        return agent_ids

    async def find_agents_for_thread(self, thread) -> list[str]:
        """Unified matching: find all agents that should receive context
        from a Slack thread.

        Matches on:
        1. JIRA key overlap  (thread.jira_keys ∩ agent.jira_key)
        2. MR ref overlap    (thread.gitlab_mr_refs → agent via MR linkage)
        3. Branch name mention (scan thread messages for agent branch names)

        Args:
            thread: SlackThread model instance.

        Returns deduplicated list of agent_id strings.
        """
        from app.models.agent import Agent

        agent_ids: set[str] = set()

        # Step 1 — JIRA key matching
        for jira_key in (thread.jira_key_list or []):
            matched = await self.find_agents_for_jira_key(jira_key)
            agent_ids.update(matched)

        # Step 2 — MR ref matching
        for mr_ref in (thread.gitlab_mr_list or []):
            matched = await self.find_agents_for_mr_ref(mr_ref)
            agent_ids.update(matched)

        # Step 3 — Branch name mentions in message text
        messages = thread.messages or []
        if messages:
            result = await self.db.execute(
                select(Agent.id, Agent.git_branch).where(
                    Agent.status.in_(["live", "idle"]),
                    Agent.git_branch.isnot(None),
                )
            )
            branch_agents = result.all()

            # Collect all message texts into a single blob for faster scanning
            all_text = " ".join(
                msg.get("text", "") for msg in messages if isinstance(msg, dict)
            )

            for row in branch_agents:
                agent_branch: str = row[1]
                if agent_branch and agent_branch in all_text:
                    agent_ids.add(str(row[0]))

        return list(agent_ids)

    async def backfill_agent_context(self, agent_id: str) -> int:
        """Backfill context queue for an agent from existing Slack threads.

        Called when an agent's jira_key or git_branch is updated.
        Scans SlackThreads from the last 14 days and enqueues matching
        context.

        Returns count of items enqueued.
        """
        from app.models.agent import Agent
        from app.models.slack_thread import SlackThread

        # Fetch agent record
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            logger.warning("backfill_agent_context: agent %s not found", agent_id)
            return 0

        # Query recent threads (last 14 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        thread_result = await self.db.execute(
            select(SlackThread).where(SlackThread.start_time > cutoff)
        )
        threads = list(thread_result.scalars().all())

        enqueued = 0

        for thread in threads:
            matched = False

            # Match on JIRA key
            if agent.jira_key and agent.jira_key in (thread.jira_keys or []):
                matched = True

            # Match on branch mention in messages
            if not matched and agent.git_branch:
                for msg in (thread.messages or []):
                    if isinstance(msg, dict) and agent.git_branch in msg.get("text", ""):
                        matched = True
                        break

            # Match on MR ref linkage
            if not matched and (thread.gitlab_mr_refs or []):
                for mr_ref in thread.gitlab_mr_refs:
                    mr_agents = await self.find_agents_for_mr_ref(mr_ref)
                    if agent_id in mr_agents:
                        matched = True
                        break

            if not matched:
                continue

            # Enqueue last 3 messages from this thread
            messages = thread.messages or []
            recent_msgs = messages[-3:] if len(messages) > 3 else messages

            for msg in recent_msgs:
                if not isinstance(msg, dict):
                    continue

                text = msg.get("text", "")
                if not text:
                    continue

                ts = msg.get("ts", "")
                source_id = f"{thread.channel_id}:{ts}"
                author = msg.get("user_name") or msg.get("user", "unknown")

                # Detect priority
                text_lower = text.lower()
                priority = "normal"
                for signal in self.HIGH_SIGNALS:
                    if signal in text_lower:
                        priority = "high"
                        break

                item = await self.enqueue(
                    agent_id=agent_id,
                    content=text,
                    jira_key=agent.jira_key,
                    source="slack",
                    source_id=source_id,
                    channel_name=thread.channel_name,
                    author=author,
                    permalink=thread.permalink,
                    priority=priority,
                )
                if item is not None:
                    enqueued += 1

        await self.db.commit()
        return enqueued

    async def cleanup_expired(self) -> int:
        """Delete all expired queue items.

        Returns the number of rows deleted.
        """
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            delete(AgentContextQueueItem).where(
                AgentContextQueueItem.ttl_expiry < now,
            )
        )
        await self.db.flush()
        return result.rowcount
