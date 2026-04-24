"""Background job for artifact indexing and auto-linking."""

import logging
from sqlalchemy import select
from app.database import async_session
from app.services.artifact_service import ArtifactService
from app.models.investigation_artifact import InvestigationArtifact
from app.models.jira_issue import JiraIssue
from app.models.entity_link import EntityLink, LinkType, LinkSourceType, LinkStatus

logger = logging.getLogger(__name__)


async def index_artifacts():
    """Scan filesystem for artifacts and index to database.

    Runs every 1 hour to pick up new/modified artifacts.

    Returns:
        Dict with scan statistics
    """
    async with async_session() as db:
        service = ArtifactService(db)

        logger.info("Starting artifact indexing scan")

        # Scan all artifact directories
        stats = await service.scan_artifacts()

        logger.info(
            f"Artifact indexing complete: {stats['total_scanned']} scanned, "
            f"{stats['new_artifacts']} new, {stats['updated_artifacts']} updated"
        )

        if stats["errors"]:
            logger.warning(f"{len(stats['errors'])} errors during scan")
            for error in stats["errors"][:5]:  # Log first 5 errors
                logger.error(f"  {error['file']}: {error['error']}")

        return stats


async def link_artifacts_to_jira():
    """Auto-link artifacts to JIRA issues based on JIRA keys in filenames/content.

    Runs after artifact indexing to create entity_links.

    Returns:
        Dict with link creation statistics
    """
    async with async_session() as db:
        logger.info("Starting artifact → JIRA auto-linking")

        # Get all artifacts with JIRA keys
        result = await db.execute(
            select(InvestigationArtifact).where(
                InvestigationArtifact.jira_keys.isnot(None),
                InvestigationArtifact.deleted_at.is_(None),
            )
        )
        artifacts = result.scalars().all()

        links_created = 0
        links_skipped = 0

        for artifact in artifacts:
            if not artifact.jira_keys:
                continue

            for jira_key in artifact.jira_keys:
                # Find JIRA issue
                jira_result = await db.execute(
                    select(JiraIssue).where(JiraIssue.external_key == jira_key)
                )
                jira_issue = jira_result.scalar_one_or_none()

                if not jira_issue:
                    logger.debug(f"JIRA issue {jira_key} not found in cache")
                    continue

                # Check if link already exists
                link_result = await db.execute(
                    select(EntityLink).where(
                        EntityLink.from_type == "jira_issue",
                        EntityLink.from_id == str(jira_issue.id),
                        EntityLink.to_type == "artifact",
                        EntityLink.to_id == str(artifact.id),
                    )
                )
                existing_link = link_result.scalar_one_or_none()

                if existing_link:
                    links_skipped += 1
                    continue

                # Create entity link
                link = EntityLink(
                    from_type="jira_issue",
                    from_id=str(jira_issue.id),
                    to_type="artifact",
                    to_id=str(artifact.id),
                    link_type=LinkType.REFERENCES_ARTIFACT,
                    source_type=LinkSourceType.INFERRED,
                    confidence_score=0.90,  # High confidence from filename/content
                    status=LinkStatus.CONFIRMED,
                )

                db.add(link)
                links_created += 1
                logger.debug(f"Linked artifact {artifact.filename} → {jira_key}")

        await db.commit()
        logger.info(
            f"Artifact auto-linking complete: {links_created} links created, "
            f"{links_skipped} skipped (already exist)"
        )

        return {"links_created": links_created, "links_skipped": links_skipped}
