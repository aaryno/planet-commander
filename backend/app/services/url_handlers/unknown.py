"""Unknown URL handler - catalogs unrecognized URLs."""
import logging
from typing import Any

from sqlalchemy import select

from app.models import UnknownURL
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class UnknownURLHandler(URLHandler):
    """Handle unknown URLs - catalog for human review."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Catalog unknown URL in database."""
        url = classified_url["url"]
        domain = classified_url["domain"]
        chat_id = context["chat_id"]

        handler_metadata = {"url": url, "domain": domain}

        try:
            # Check if already cataloged
            result = await self.db.execute(
                select(UnknownURL).where(UnknownURL.url == url)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update occurrence count
                existing.occurrence_count += 1
                existing.last_seen_at = context.get("timestamp")
                await self.db.flush()

                logger.info(f"Unknown URL seen again (count={existing.occurrence_count}): {url}")
            else:
                # Create new entry
                unknown_url = UnknownURL(
                    url=url,
                    domain=domain,
                    first_seen_in_chat_id=chat_id,
                    first_seen_at=context.get("timestamp"),
                    occurrence_count=1,
                    last_seen_at=context.get("timestamp")
                )
                self.db.add(unknown_url)
                await self.db.flush()

                logger.info(f"Cataloged new unknown URL: {url}")

            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"UnknownURLHandler failed for {url}: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )
