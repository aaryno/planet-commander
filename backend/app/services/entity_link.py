"""Entity link management service for Planet Commander Phase 1.

Manages relationships between entities (contexts, issues, chats, branches, worktrees).
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntityLink, LinkType, LinkSourceType, LinkStatus

logger = logging.getLogger(__name__)


class EntityLinkService:
    """Manage entity links (relationships between entities)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_link(
        self,
        from_type: str,
        from_id: str | uuid.UUID,
        to_type: str,
        to_id: str | uuid.UUID,
        link_type: LinkType,
        source_type: LinkSourceType = LinkSourceType.MANUAL,
        confidence_score: float | None = None,
        status: LinkStatus = LinkStatus.CONFIRMED,
        link_metadata: dict[str, Any] | None = None,
    ) -> EntityLink:
        """Create a new entity link.

        Args:
            from_type: Source entity type (context, jira_issue, chat, branch, worktree, etc.)
            from_id: Source entity ID
            to_type: Target entity type
            to_id: Target entity ID
            link_type: Type of relationship
            source_type: How the link was created (manual, inferred, imported, agent, url_extracted)
            confidence_score: Optional confidence score (0.0-1.0) for inferred links
            status: Link status (confirmed, suggested, rejected, stale)
            link_metadata: Optional metadata (e.g., URL that triggered extraction, job_id, etc.)

        Returns:
            Created EntityLink instance
        """
        # Convert UUIDs to strings
        from_id_str = str(from_id)
        to_id_str = str(to_id)

        # Check if link already exists
        result = await self.db.execute(
            select(EntityLink).where(
                (EntityLink.from_type == from_type)
                & (EntityLink.from_id == from_id_str)
                & (EntityLink.to_type == to_type)
                & (EntityLink.to_id == to_id_str)
                & (EntityLink.link_type == link_type)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(
                f"Link already exists: {from_type}:{from_id_str} --{link_type}--> {to_type}:{to_id_str}"
            )
            return existing

        # Create new link
        link = EntityLink(
            from_type=from_type,
            from_id=from_id_str,
            to_type=to_type,
            to_id=to_id_str,
            link_type=link_type,
            source_type=source_type,
            confidence_score=confidence_score,
            status=status,
            link_metadata=link_metadata,
        )

        self.db.add(link)
        await self.db.flush()  # Get ID without committing

        logger.info(
            f"Created link: {from_type}:{from_id_str} --{link_type}--> {to_type}:{to_id_str}"
        )

        return link

    async def confirm_link(self, link_id: uuid.UUID) -> EntityLink:
        """Confirm a suggested link.

        Args:
            link_id: EntityLink UUID

        Returns:
            Updated EntityLink instance

        Raises:
            ValueError: If link not found
        """
        result = await self.db.execute(select(EntityLink).where(EntityLink.id == link_id))
        link = result.scalar_one_or_none()

        if not link:
            raise ValueError(f"Link {link_id} not found")

        link.status = LinkStatus.CONFIRMED
        await self.db.flush()

        logger.info(f"Confirmed link {link_id}")

        return link

    async def reject_link(self, link_id: uuid.UUID) -> EntityLink:
        """Reject a suggested link.

        Args:
            link_id: EntityLink UUID

        Returns:
            Updated EntityLink instance

        Raises:
            ValueError: If link not found
        """
        result = await self.db.execute(select(EntityLink).where(EntityLink.id == link_id))
        link = result.scalar_one_or_none()

        if not link:
            raise ValueError(f"Link {link_id} not found")

        link.status = LinkStatus.REJECTED
        await self.db.flush()

        logger.info(f"Rejected link {link_id}")

        return link

    async def delete_link(self, link_id: uuid.UUID) -> None:
        """Delete a link.

        Args:
            link_id: EntityLink UUID

        Raises:
            ValueError: If link not found
        """
        result = await self.db.execute(select(EntityLink).where(EntityLink.id == link_id))
        link = result.scalar_one_or_none()

        if not link:
            raise ValueError(f"Link {link_id} not found")

        await self.db.delete(link)
        await self.db.flush()

        logger.info(f"Deleted link {link_id}")

    async def get_links_for_context(self, context_id: uuid.UUID) -> list[EntityLink]:
        """Get all links related to a context.

        Args:
            context_id: WorkContext UUID

        Returns:
            List of EntityLink instances
        """
        context_id_str = str(context_id)

        # Get links where context is source or target
        result = await self.db.execute(
            select(EntityLink).where(
                ((EntityLink.from_type == "context") & (EntityLink.from_id == context_id_str))
                | ((EntityLink.to_type == "context") & (EntityLink.to_id == context_id_str))
            )
        )

        return list(result.scalars().all())

    async def get_links_for_entity(
        self, entity_type: str, entity_id: str | uuid.UUID
    ) -> list[EntityLink]:
        """Get all links for a specific entity.

        Args:
            entity_type: Entity type (context, jira_issue, chat, etc.)
            entity_id: Entity ID

        Returns:
            List of EntityLink instances
        """
        entity_id_str = str(entity_id)

        # Get links where entity is source or target
        result = await self.db.execute(
            select(EntityLink).where(
                ((EntityLink.from_type == entity_type) & (EntityLink.from_id == entity_id_str))
                | ((EntityLink.to_type == entity_type) & (EntityLink.to_id == entity_id_str))
            )
        )

        return list(result.scalars().all())

    async def get_suggested_links(self) -> list[EntityLink]:
        """Get all suggested (unconfirmed) links.

        Returns:
            List of EntityLink instances with status=SUGGESTED
        """
        result = await self.db.execute(
            select(EntityLink).where(EntityLink.status == LinkStatus.SUGGESTED)
        )

        return list(result.scalars().all())

    async def batch_confirm_links(self, link_ids: list[uuid.UUID]) -> int:
        """Confirm multiple links at once.

        Args:
            link_ids: List of EntityLink UUIDs to confirm

        Returns:
            Number of links confirmed
        """
        result = await self.db.execute(select(EntityLink).where(EntityLink.id.in_(link_ids)))
        links = result.scalars().all()

        confirmed_count = 0
        for link in links:
            if link.status == LinkStatus.SUGGESTED:
                link.status = LinkStatus.CONFIRMED
                confirmed_count += 1

        await self.db.flush()

        logger.info(f"Batch confirmed {confirmed_count} links")

        return confirmed_count
