"""GitLab branch URL handler."""
import logging
from typing import Any

from sqlalchemy import select

from app.models import GitBranch, LinkType, LinkSourceType
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class GitLabBranchHandler(URLHandler):
    """Handle GitLab branch URLs."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Link chat to git branch."""
        project = classified_url["components"]["project"]
        repo = classified_url["components"]["repo"]
        branch = classified_url["components"]["branch"]
        chat_id = context["chat_id"]
        url = classified_url["url"]

        entities_created = []
        links_created = []
        handler_metadata = {"project": project, "repo": repo, "branch": branch}

        try:
            # Find branch in database
            branch_entity = await self._find_branch(f"{project}/{repo}", branch)

            if branch_entity:
                entities_created.append(branch_entity)

                # Create link: chat mentioned_in branch
                link = await self.link_service.create_link(
                    from_type="chat",
                    from_id=str(chat_id),
                    to_type="branch",
                    to_id=str(branch_entity.id),
                    link_type=LinkType.MENTIONED_IN,
                    source_type=LinkSourceType.URL_EXTRACTED,
                    link_metadata={"url": url, "branch": branch}
                )
                links_created.append(link)

            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"GitLabBranchHandler failed: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )

    async def _find_branch(self, repo: str, branch_name: str):
        """Find git branch in database."""
        result = await self.db.execute(
            select(GitBranch).where(
                (GitBranch.repo == repo) & (GitBranch.branch_name == branch_name)
            )
        )
        return result.scalar_one_or_none()
