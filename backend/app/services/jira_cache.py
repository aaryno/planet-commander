"""JIRA issue caching service for Planet Commander Phase 1.

Extends the existing jira_service with database caching to JiraIssue model.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JiraIssue
from app.services import jira_service

logger = logging.getLogger(__name__)


class JiraCacheService:
    """Cache JIRA issues locally in database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_issue_to_cache(self, jira_key: str) -> JiraIssue:
        """Fetch issue from JIRA API and cache locally.

        Args:
            jira_key: JIRA issue key (e.g., COMPUTE-2059)

        Returns:
            JiraIssue instance

        Raises:
            ValueError: If issue not found in JIRA
        """
        # 1. Fetch from JIRA API
        results = await jira_service.search_tickets(query=jira_key, limit=1)

        if not results:
            raise ValueError(f"JIRA issue {jira_key} not found")

        issue_data = results[0]

        # 2. Upsert to jira_issues table
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.title = issue_data["summary"]
            existing.status = issue_data["status"]
            existing.priority = issue_data.get("priority")
            existing.assignee = issue_data.get("assignee")
            existing.labels = issue_data.get("labels", [])
            existing.fix_versions = issue_data.get("fix_versions", [])
            existing.description = issue_data.get("description")
            # Note: acceptance_criteria not in standard JIRA response
            # Would need custom field mapping or separate extraction
            existing.source_last_synced_at = datetime.now(timezone.utc)

            logger.info(f"Updated cached JIRA issue {jira_key}")
            jira_issue = existing
        else:
            # Create new
            # Build JIRA URL
            cfg = jira_service._load_config()
            jira_url = f"https://{cfg['JIRA_HOST']}/browse/{jira_key}"

            jira_issue = JiraIssue(
                external_key=jira_key,
                title=issue_data["summary"],
                status=issue_data["status"],
                priority=issue_data.get("priority"),
                assignee=issue_data.get("assignee"),
                labels=issue_data.get("labels", []),
                fix_versions=issue_data.get("fix_versions", []),
                description=issue_data.get("description"),
                url=jira_url,
                source_last_synced_at=datetime.now(timezone.utc),
            )

            self.db.add(jira_issue)
            logger.info(f"Cached new JIRA issue {jira_key}")

        await self.db.flush()  # Get ID without committing

        return jira_issue

    async def get_cached_issue(
        self, jira_key: str, max_age_minutes: int = 60
    ) -> JiraIssue | None:
        """Get cached issue if fresh enough, else sync from JIRA.

        Args:
            jira_key: JIRA issue key
            max_age_minutes: Maximum cache age in minutes (default: 60)

        Returns:
            JiraIssue instance or None if not found
        """
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        issue = result.scalar_one_or_none()

        if not issue:
            # Not in cache, sync from JIRA
            try:
                return await self.sync_issue_to_cache(jira_key)
            except ValueError:
                logger.warning(f"JIRA issue {jira_key} not found in API")
                return None

        # Check cache age
        age = datetime.now(timezone.utc) - issue.source_last_synced_at
        if age > timedelta(minutes=max_age_minutes):
            # Cache stale, refresh from JIRA
            try:
                return await self.sync_issue_to_cache(jira_key)
            except ValueError:
                logger.warning(f"Failed to refresh {jira_key}, returning stale cache")
                return issue

        return issue

    async def batch_sync_issues(self, jira_keys: list[str]) -> list[JiraIssue]:
        """Sync multiple JIRA issues to cache.

        Args:
            jira_keys: List of JIRA issue keys

        Returns:
            List of JiraIssue instances (may be fewer than input if some not found)
        """
        issues = []

        for jira_key in jira_keys:
            try:
                issue = await self.sync_issue_to_cache(jira_key)
                issues.append(issue)
            except ValueError:
                logger.warning(f"Skipping {jira_key}, not found in JIRA")
                continue

        return issues

    async def get_issues_by_context(self, context_id: uuid.UUID) -> list[JiraIssue]:
        """Get all cached JIRA issues for a context.

        Args:
            context_id: WorkContext UUID

        Returns:
            List of JiraIssue instances
        """
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.context_id == context_id)
        )

        return list(result.scalars().all())
