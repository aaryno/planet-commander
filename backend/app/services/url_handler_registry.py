"""URL Handler Registry - routes classified URLs to appropriate handlers."""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.url_type import URLType
from app.services.url_handlers import (
    GitLabJobHandler,
    GitLabMRHandler,
    GitLabBranchHandler,
    JiraIssueHandler,
    GoogleDocHandler,
    UnknownURLHandler,
    HandlerResult,
)

logger = logging.getLogger(__name__)


class URLHandlerRegistry:
    """Registry of URL type handlers - routes URLs to appropriate handler."""

    def __init__(self, db: AsyncSession):
        self.db = db

        # Initialize all handlers
        self.handlers = {
            URLType.GITLAB_JOB: GitLabJobHandler(db),
            URLType.GITLAB_MR: GitLabMRHandler(db),
            URLType.GITLAB_BRANCH: GitLabBranchHandler(db),
            URLType.JIRA_ISSUE: JiraIssueHandler(db),
            URLType.GOOGLE_DOC: GoogleDocHandler(db),
            URLType.GOOGLE_SHEET: GoogleDocHandler(db),  # Reuse GoogleDocHandler
            URLType.GOOGLE_SLIDE: GoogleDocHandler(db),  # Reuse GoogleDocHandler
            URLType.GOOGLE_DRIVE: GoogleDocHandler(db),  # Reuse GoogleDocHandler
            # Unknown handler is special - invoked for unrecognized URLs
        }

        self.unknown_handler = UnknownURLHandler(db)

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Route classified URL to appropriate handler.

        Args:
            classified_url: Output from URLClassifier with:
                - type: URLType
                - confidence: float
                - components: dict
                - url: str
                - domain: str

            context: Extraction context with:
                - chat_id: uuid.UUID
                - message_index: int
                - timestamp: datetime

        Returns:
            HandlerResult with entities and links created
        """
        url_type = classified_url["type"]
        url = classified_url["url"]

        # Handle unknown URLs
        if url_type == URLType.UNKNOWN:
            logger.info(f"Unknown URL: {url}")
            return await self.unknown_handler.handle(classified_url, context)

        # Get handler for this URL type
        handler = self.handlers.get(url_type)

        if not handler:
            logger.warning(f"No handler registered for {url_type.value}, treating as unknown")
            return await self.unknown_handler.handle(classified_url, context)

        # Handle with appropriate handler
        try:
            result = await handler.handle(classified_url, context)
            logger.info(
                f"Handled {url_type.value}: "
                f"{len(result.links_created)} links, "
                f"success={result.success}"
            )
            return result

        except Exception as e:
            logger.error(f"Handler failed for {url_type.value}: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata={"url_type": url_type.value},
                success=False,
                error=str(e)
            )

    async def handle_batch(
        self,
        classified_urls: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[HandlerResult]:
        """Handle multiple URLs in batch.

        Args:
            classified_urls: List of classified URLs
            context: Shared extraction context

        Returns:
            List of HandlerResults
        """
        results = []

        for classified_url in classified_urls:
            result = await self.handle(classified_url, context)
            results.append(result)

        # Summary logging
        total_links = sum(len(r.links_created) for r in results)
        successes = sum(1 for r in results if r.success)

        logger.info(
            f"Batch handled {len(classified_urls)} URLs: "
            f"{successes} successes, {total_links} links created"
        )

        return results
