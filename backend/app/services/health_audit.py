"""Health audit service for assessing work context quality and completeness."""
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, List

from app.models.work_context import WorkContext, HealthStatus, ContextStatus
from app.models.entity_link import EntityLink, LinkStatus
from app.models.jira_issue import JiraIssue
from app.models.git_branch import GitBranch
from app.models.worktree import Worktree
from app.models.agent import Agent

logger = logging.getLogger(__name__)


class HealthAuditService:
    """Service for auditing work context health and completeness."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def audit_context_health(self, context_id: str) -> Dict[str, any]:
        """
        Audit health of a single work context.

        Returns:
            dict: Health audit results with score, status, issues
        """
        result = await self.db.execute(
            select(WorkContext).where(WorkContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if not context:
            raise ValueError(f"Context not found: {context_id}")

        # Calculate health score
        score = await self._calculate_health_score(context)

        # Determine health status
        health_status = self._score_to_health_status(score)

        # Identify issues
        issues = await self._identify_health_issues(context)

        # Update context health
        context.health_status = health_status
        await self.db.flush()

        return {
            "context_id": str(context.id),
            "score": score,
            "health_status": health_status.value,
            "issues": issues,
            "updated_at": datetime.utcnow().isoformat()
        }

    async def _calculate_health_score(self, context: WorkContext) -> float:
        """
        Calculate health score (0.0 - 1.0) based on completeness.

        Factors:
        - Has primary entity (JIRA or chat): +0.3
        - Has linked entities: +0.2
        - Has active branch: +0.2
        - Has active worktree: +0.1
        - Has recent activity: +0.2
        """
        score = 0.0

        # Has primary entity (JIRA or chat)
        if context.primary_jira_issue_id or context.primary_chat_id:
            score += 0.3

        # Count linked entities
        link_result = await self.db.execute(
            select(func.count(EntityLink.id))
            .where(
                EntityLink.from_id == str(context.id),
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        link_count = link_result.scalar() or 0

        if link_count > 0:
            score += 0.2

        # Has active branch
        branch_result = await self.db.execute(
            select(func.count(EntityLink.id))
            .where(
                EntityLink.from_type == "context",
                EntityLink.from_id == str(context.id),
                EntityLink.to_type == "branch",
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        branch_count = branch_result.scalar() or 0

        if branch_count > 0:
            score += 0.2

        # Has active worktree
        worktree_result = await self.db.execute(
            select(func.count(EntityLink.id))
            .where(
                EntityLink.from_type == "context",
                EntityLink.from_id == str(context.id),
                EntityLink.to_type == "worktree",
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        worktree_count = worktree_result.scalar() or 0

        if worktree_count > 0:
            score += 0.1

        # Has recent activity (updated in last 7 days)
        days_since_update = (datetime.utcnow() - context.updated_at.replace(tzinfo=None)).days
        if days_since_update < 7:
            score += 0.2

        return min(score, 1.0)

    def _score_to_health_status(self, score: float) -> HealthStatus:
        """Convert numeric score to health status."""
        if score >= 0.8:
            return HealthStatus.GREEN
        elif score >= 0.5:
            return HealthStatus.YELLOW
        else:
            return HealthStatus.RED

    async def _identify_health_issues(self, context: WorkContext) -> List[str]:
        """Identify specific health issues with the context."""
        issues = []

        # Missing primary entity
        if not context.primary_jira_issue_id and not context.primary_chat_id:
            issues.append("No primary entity (JIRA or chat)")

        # No linked entities
        link_result = await self.db.execute(
            select(func.count(EntityLink.id))
            .where(
                EntityLink.from_id == str(context.id),
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        link_count = link_result.scalar() or 0

        if link_count == 0:
            issues.append("No linked entities")

        # Stale (no updates in 30+ days)
        days_since_update = (datetime.utcnow() - context.updated_at.replace(tzinfo=None)).days
        if days_since_update >= 30:
            issues.append(f"Stale: no updates in {days_since_update} days")

        # Orphaned status
        if context.status == ContextStatus.ORPHANED:
            issues.append("Marked as orphaned")

        # No active branch
        branch_result = await self.db.execute(
            select(func.count(EntityLink.id))
            .where(
                EntityLink.from_type == "context",
                EntityLink.from_id == str(context.id),
                EntityLink.to_type == "branch",
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        branch_count = branch_result.scalar() or 0

        if branch_count == 0:
            issues.append("No linked branch")

        return issues

    async def audit_all_contexts(self) -> Dict[str, any]:
        """
        Audit health of all active work contexts.

        Returns:
            dict: Summary results with total contexts, health distribution
        """
        logger.info("Starting health audit of all contexts")

        result = await self.db.execute(
            select(WorkContext).where(
                WorkContext.status != ContextStatus.ARCHIVED
            )
        )
        contexts = result.scalars().all()

        health_counts = {
            "green": 0,
            "yellow": 0,
            "red": 0,
            "unknown": 0
        }

        audited = 0

        for context in contexts:
            try:
                audit_result = await self._calculate_health_score(context)
                health_status = self._score_to_health_status(audit_result)
                context.health_status = health_status
                health_counts[health_status.value] += 1
                audited += 1
            except Exception as e:
                logger.error(f"Failed to audit context {context.id}: {e}")
                continue

        await self.db.flush()

        logger.info(
            f"Health audit complete: {audited} contexts, "
            f"green={health_counts['green']}, yellow={health_counts['yellow']}, "
            f"red={health_counts['red']}"
        )

        return {
            "total_contexts": len(contexts),
            "audited": audited,
            "health_distribution": health_counts
        }

    async def detect_stale_contexts(self, days_threshold: int = 30) -> List[Dict[str, any]]:
        """
        Detect stale contexts (no updates in N days).

        Args:
            days_threshold: Number of days without updates to consider stale

        Returns:
            list: Stale contexts with metadata
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)

        result = await self.db.execute(
            select(WorkContext)
            .where(
                WorkContext.status != ContextStatus.ARCHIVED,
                WorkContext.updated_at < cutoff_date
            )
            .order_by(WorkContext.updated_at)
        )
        stale_contexts = result.scalars().all()

        logger.info(f"Found {len(stale_contexts)} stale contexts (>{days_threshold} days)")

        return [
            {
                "id": str(ctx.id),
                "title": ctx.title,
                "status": ctx.status.value,
                "days_since_update": (datetime.utcnow() - ctx.updated_at.replace(tzinfo=None)).days,
                "last_updated": ctx.updated_at.isoformat()
            }
            for ctx in stale_contexts
        ]

    async def detect_orphaned_entities(self) -> Dict[str, List[Dict[str, any]]]:
        """
        Detect orphaned entities (not linked to any context).

        Returns:
            dict: Orphaned entities by type (branches, worktrees, chats, jira)
        """
        orphaned = {
            "branches": [],
            "worktrees": [],
            "chats": [],
            "jira_issues": []
        }

        # Orphaned branches
        branch_result = await self.db.execute(
            select(GitBranch)
            .outerjoin(
                EntityLink,
                EntityLink.to_id == GitBranch.id.cast(String)
            )
            .where(EntityLink.id.is_(None))
            .limit(100)
        )
        orphaned_branches = branch_result.scalars().all()
        orphaned["branches"] = [
            {
                "id": str(b.id),
                "name": b.branch_name,
                "repo": b.repo_path
            }
            for b in orphaned_branches
        ]

        # Orphaned worktrees
        worktree_result = await self.db.execute(
            select(Worktree)
            .outerjoin(
                EntityLink,
                EntityLink.to_id == Worktree.id.cast(String)
            )
            .where(EntityLink.id.is_(None))
            .limit(100)
        )
        orphaned_worktrees = worktree_result.scalars().all()
        orphaned["worktrees"] = [
            {
                "id": str(w.id),
                "path": w.path
            }
            for w in orphaned_worktrees
        ]

        # Orphaned chats (agents with JIRA keys but no links)
        chat_result = await self.db.execute(
            select(Agent)
            .outerjoin(
                EntityLink,
                EntityLink.from_id == Agent.id.cast(String)
            )
            .where(
                Agent.jira_key.isnot(None),
                EntityLink.id.is_(None)
            )
            .limit(100)
        )
        orphaned_chats = chat_result.scalars().all()
        orphaned["chats"] = [
            {
                "id": str(a.id),
                "name": a.name,
                "jira_key": a.jira_key
            }
            for a in orphaned_chats
        ]

        # Orphaned JIRA issues
        jira_result = await self.db.execute(
            select(JiraIssue)
            .outerjoin(
                EntityLink,
                EntityLink.to_id == JiraIssue.id.cast(String)
            )
            .where(EntityLink.id.is_(None))
            .limit(100)
        )
        orphaned_jira = jira_result.scalars().all()
        orphaned["jira_issues"] = [
            {
                "id": str(j.id),
                "key": j.external_key,
                "summary": j.summary
            }
            for j in orphaned_jira
        ]

        total = sum(len(v) for v in orphaned.values())
        logger.info(
            f"Detected {total} orphaned entities: "
            f"branches={len(orphaned['branches'])}, "
            f"worktrees={len(orphaned['worktrees'])}, "
            f"chats={len(orphaned['chats'])}, "
            f"jira={len(orphaned['jira_issues'])}"
        )

        return orphaned

    async def mark_stale_as_orphaned(self, days_threshold: int = 60) -> int:
        """
        Mark contexts as orphaned if they haven't been updated in N days.

        Args:
            days_threshold: Number of days to consider for orphaned status

        Returns:
            int: Number of contexts marked as orphaned
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)

        result = await self.db.execute(
            select(WorkContext)
            .where(
                WorkContext.status == ContextStatus.ACTIVE,
                WorkContext.updated_at < cutoff_date
            )
        )
        stale_contexts = result.scalars().all()

        marked_count = 0
        for ctx in stale_contexts:
            ctx.status = ContextStatus.ORPHANED
            marked_count += 1

        await self.db.flush()

        logger.info(f"Marked {marked_count} contexts as orphaned (>{days_threshold} days stale)")

        return marked_count
