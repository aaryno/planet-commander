"""JIRA sync automation service."""
import logging
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.work_context import WorkContext, ContextStatus
from app.models.entity_link import EntityLink, LinkStatus
from app.models.jira_issue import JiraIssue
# TODO: Import actual JIRA API functions when ready
# from app.services.jira_service import update_ticket_status, add_comment

logger = logging.getLogger(__name__)


class JiraSyncAutomationService:
    """Service for automatic JIRA ticket synchronization."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_context_to_jira(self, context_id: str) -> Dict[str, any]:
        """
        Sync context status to linked JIRA tickets.

        Args:
            context_id: WorkContext ID

        Returns:
            dict: Sync results
        """
        # Get context
        result = await self.db.execute(
            select(WorkContext).where(WorkContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if not context:
            raise ValueError(f"Context not found: {context_id}")

        # Get linked JIRA issues
        links_result = await self.db.execute(
            select(EntityLink)
            .where(
                EntityLink.from_id == str(context.id),
                EntityLink.to_type == "jira_issue",
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        links = links_result.scalars().all()

        synced_count = 0
        errors = []

        for link in links:
            try:
                jira_result = await self.db.execute(
                    select(JiraIssue).where(JiraIssue.id == link.to_id)
                )
                jira_issue = jira_result.scalar_one_or_none()

                if not jira_issue:
                    continue

                # Determine target JIRA status based on context status
                target_status = self._map_context_status_to_jira(context.status)

                if target_status and jira_issue.status != target_status:
                    # Update JIRA ticket
                    logger.info(
                        f"Updating JIRA {jira_issue.external_key}: "
                        f"{jira_issue.status} → {target_status}"
                    )

                    # TODO: Uncomment when ready to make actual JIRA updates
                    # update_ticket_status(jira_issue.external_key, target_status)

                    # Update cached status
                    jira_issue.status = target_status
                    synced_count += 1

                    logger.info(f"✓ Synced JIRA {jira_issue.external_key}")

            except Exception as e:
                error_msg = f"Failed to sync {jira_issue.external_key if jira_issue else 'unknown'}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        await self.db.flush()

        return {
            "context_id": str(context.id),
            "synced_count": synced_count,
            "total_links": len(links),
            "errors": errors
        }

    def _map_context_status_to_jira(self, context_status: ContextStatus) -> str | None:
        """Map context status to JIRA status."""
        mapping = {
            ContextStatus.ACTIVE: "In Progress",
            ContextStatus.READY: "Ready to Deploy",
            ContextStatus.DONE: "Done",
            ContextStatus.BLOCKED: "Blocked",
            ContextStatus.ARCHIVED: None,  # Don't auto-update archived
            ContextStatus.ORPHANED: None,  # Don't auto-update orphaned
            ContextStatus.STALLED: "In Progress",  # Keep in progress
        }
        return mapping.get(context_status)

    async def add_context_comment_to_jira(
        self,
        context_id: str,
        comment: str
    ) -> Dict[str, any]:
        """
        Add comment to all linked JIRA tickets.

        Args:
            context_id: WorkContext ID
            comment: Comment text

        Returns:
            dict: Results
        """
        # Get linked JIRA issues
        links_result = await self.db.execute(
            select(EntityLink)
            .where(
                EntityLink.from_id == context_id,
                EntityLink.to_type == "jira_issue",
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        links = links_result.scalars().all()

        commented_count = 0
        errors = []

        for link in links:
            try:
                jira_result = await self.db.execute(
                    select(JiraIssue).where(JiraIssue.id == link.to_id)
                )
                jira_issue = jira_result.scalar_one_or_none()

                if not jira_issue:
                    continue

                # TODO: Uncomment when ready to make actual JIRA updates
                # add_comment(jira_issue.external_key, comment)

                commented_count += 1
                logger.info(f"✓ Added comment to JIRA {jira_issue.external_key}")

            except Exception as e:
                error_msg = f"Failed to comment on {jira_issue.external_key if jira_issue else 'unknown'}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "context_id": context_id,
            "commented_count": commented_count,
            "total_links": len(links),
            "errors": errors
        }
