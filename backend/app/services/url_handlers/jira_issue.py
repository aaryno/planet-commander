"""JIRA issue URL handler."""
import logging
from typing import Any

from sqlalchemy import select

from app.models import JiraIssue, LinkType, LinkSourceType
from app.services.jira_cache import JiraCacheService
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class JiraIssueHandler(URLHandler):
    """Handle JIRA issue URLs."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Link chat to JIRA issue."""
        jira_key = classified_url["components"]["jira_key"]
        chat_id = context["chat_id"]
        url = classified_url["url"]

        entities_created = []
        links_created = []
        handler_metadata = {"jira_key": jira_key}

        try:
            # Find or sync JIRA issue
            issue = await self._find_or_sync_jira_issue(jira_key)

            if issue:
                entities_created.append(issue)

                # Create link: chat discussed_in JIRA
                link = await self.link_service.create_link(
                    from_type="chat",
                    from_id=str(chat_id),
                    to_type="jira_issue",
                    to_id=str(issue.id),
                    link_type=LinkType.DISCUSSED_IN,
                    source_type=LinkSourceType.URL_EXTRACTED,
                    link_metadata={"url": url, "jira_key": jira_key}
                )
                links_created.append(link)

            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"JiraIssueHandler failed for {jira_key}: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )

    async def _find_or_sync_jira_issue(self, jira_key: str):
        """Find or sync JIRA issue."""
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        issue = result.scalar_one_or_none()
        if issue:
            return issue

        try:
            jira_cache = JiraCacheService(self.db)
            return await jira_cache.sync_issue(jira_key)
        except Exception as e:
            logger.warning(f"Failed to sync JIRA {jira_key}: {e}")
            return None
