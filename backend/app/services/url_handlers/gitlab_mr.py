"""GitLab MR URL handler."""
import logging
import re
from typing import Any

from sqlalchemy import select

from app.models import GitLabMergeRequest, JiraIssue, LinkType, LinkSourceType
from app.services.jira_cache import JiraCacheService
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class GitLabMRHandler(URLHandler):
    """Handle GitLab MR URLs - extract JIRA tickets, create links."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Extract metadata from GitLab MR and create links."""
        project = classified_url["components"]["project"]
        repo = classified_url["components"]["repo"]
        mr_id = classified_url["components"]["mr_id"]
        chat_id = context["chat_id"]
        url = classified_url["url"]

        entities_created = []
        links_created = []
        handler_metadata = {"project": project, "repo": repo, "mr_id": mr_id}

        try:
            # Find MR in database
            mr = await self._find_mr(f"{project}/{repo}", mr_id)

            if mr:
                entities_created.append(mr)

                # Create link: chat discussed_in MR
                link = await self.link_service.create_link(
                    from_type="chat",
                    from_id=str(chat_id),
                    to_type="merge_request",
                    to_id=str(mr.id),
                    link_type=LinkType.DISCUSSED_IN,
                    source_type=LinkSourceType.URL_EXTRACTED,
                    link_metadata={"url": url, "mr_id": mr_id}
                )
                links_created.append(link)

                # Extract JIRA keys from MR
                jira_keys = self._extract_jira_keys(mr.title + " " + (mr.description or ""))
                for jira_key in jira_keys:
                    jira_issue = await self._find_or_sync_jira_issue(jira_key)
                    if jira_issue:
                        entities_created.append(jira_issue)

                        # Create link: chat discussed_in JIRA
                        link = await self.link_service.create_link(
                            from_type="chat",
                            from_id=str(chat_id),
                            to_type="jira_issue",
                            to_id=str(jira_issue.id),
                            link_type=LinkType.DISCUSSED_IN,
                            source_type=LinkSourceType.URL_EXTRACTED,
                            link_metadata={
                                "url": url,
                                "via": "gitlab_mr",
                                "jira_key": jira_key,
                                "mr_id": mr_id
                            }
                        )
                        links_created.append(link)

            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"GitLabMRHandler failed for MR {mr_id}: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )

    async def _find_mr(self, repo: str, mr_id: int):
        """Find MR in database."""
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                (GitLabMergeRequest.repository == repo) &
                (GitLabMergeRequest.external_mr_id == mr_id)
            )
        )
        return result.scalar_one_or_none()

    def _extract_jira_keys(self, text: str) -> list[str]:
        """Extract JIRA keys from text."""
        if not text:
            return []
        pattern = r'\b([A-Z]+-\d+)\b'
        return list(set(re.findall(pattern, text)))

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
