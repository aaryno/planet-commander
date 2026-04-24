"""Google Doc URL handler."""
import logging
from typing import Any

from sqlalchemy import select

from app.models import GoogleDriveDocument, LinkType, LinkSourceType
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class GoogleDocHandler(URLHandler):
    """Handle Google Doc/Sheet/Slide URLs."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Link chat to Google Drive document."""
        url_type = classified_url["type"]
        chat_id = context["chat_id"]
        url = classified_url["url"]

        # Extract doc_id (field name varies)
        components = classified_url["components"]
        doc_id = components.get("doc_id") or components.get("sheet_id") or components.get("slide_id") or components.get("file_id")

        entities_created = []
        links_created = []
        handler_metadata = {"doc_id": doc_id, "url_type": url_type.value}

        try:
            # Find doc in database
            doc = await self._find_document(doc_id)

            if doc:
                entities_created.append(doc)

                # Create link: chat references doc
                link = await self.link_service.create_link(
                    from_type="chat",
                    from_id=str(chat_id),
                    to_type="google_drive_document",
                    to_id=str(doc.id),
                    link_type=LinkType.REFERENCES,
                    source_type=LinkSourceType.URL_EXTRACTED,
                    link_metadata={"url": url, "doc_id": doc_id}
                )
                links_created.append(link)

            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"GoogleDocHandler failed for {doc_id}: {e}")
            return HandlerResult(
                entities_created=[],
                links_created=[],
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )

    async def _find_document(self, doc_id: str):
        """Find Google Drive document in database."""
        result = await self.db.execute(
            select(GoogleDriveDocument).where(GoogleDriveDocument.external_id == doc_id)
        )
        return result.scalar_one_or_none()
