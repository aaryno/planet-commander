"""Base URL handler class."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntityLink
from app.services.entity_link import EntityLinkService

logger = logging.getLogger(__name__)


@dataclass
class HandlerResult:
    """Result from URL handler processing."""

    # List of entities that were fetched or created (for logging/tracking)
    entities_created: list[Any]

    # List of EntityLinks that were created
    links_created: list[EntityLink]

    # Handler-specific metadata (e.g., branch name, MR ID, job ID)
    handler_metadata: dict[str, Any]

    # Success flag
    success: bool

    # Error message (if any)
    error: str | None = None


class URLHandler(ABC):
    """Base class for URL type handlers."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.link_service = EntityLinkService(db)

    @abstractmethod
    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Handle a classified URL and create entity links.

        Args:
            classified_url: Output from URLClassifier with:
                - type: URLType
                - confidence: float
                - components: dict (extracted parts)
                - url: str
                - domain: str

            context: Extraction context with:
                - chat_id: uuid.UUID (where URL was found)
                - message_index: int
                - timestamp: datetime

        Returns:
            HandlerResult with entities and links created
        """
        pass
