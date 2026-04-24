"""Background jobs for Google Drive document syncing and linking."""

import logging
from typing import Dict

from app.database import async_session
from app.models import GoogleDriveDocument, JiraIssue, EntityLink, LinkType, LinkSourceType, LinkStatus
from app.services.google_drive_service import GoogleDriveService
from app.services.entity_link import EntityLinkService
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def sync_google_drive() -> Dict:
    """Sync Google Drive documents from local mount.

    Scans the Google Drive for Desktop mount for .gdoc files,
    parses metadata, and updates the database.

    Returns:
        Dictionary with scan statistics
    """
    try:
        async with async_session() as db:
            service = GoogleDriveService(db)
            logger.info("Starting Google Drive sync")

            stats = await service.scan_google_drive()

            logger.info(
                f"Google Drive sync complete: {stats['total_scanned']} scanned, "
                f"{stats['new_docs']} new, {stats['updated_docs']} updated, "
                f"{stats['unchanged_docs']} unchanged, {len(stats['errors'])} errors"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in Google Drive sync: {e}", exc_info=True)
        return {
            "total_scanned": 0,
            "new_docs": 0,
            "updated_docs": 0,
            "unchanged_docs": 0,
            "errors": [str(e)]
        }


async def link_google_drive_to_jira() -> Dict:
    """Auto-link Google Drive documents to JIRA issues.

    Creates entity links between Google Drive documents and JIRA issues based on:
    1. JIRA keys found in document filenames (e.g., PRODISSUE-574)
    2. Document kind (postmortem → postmortem_for, rfd → rfd_for)

    Returns:
        Dictionary with linking statistics
    """
    try:
        async with async_session() as db:
            link_service = EntityLinkService(db)

            logger.info("Starting Google Drive → JIRA linking")

            stats = {
                "documents_processed": 0,
                "links_created": 0,
                "links_skipped": 0,
                "errors": []
            }

            # Get all Google Drive documents with JIRA keys
            result = await db.execute(
                select(GoogleDriveDocument).where(
                    GoogleDriveDocument.jira_keys.isnot(None)
                )
            )
            documents = result.scalars().all()

            for doc in documents:
                stats["documents_processed"] += 1

                if not doc.jira_keys:
                    continue

                for jira_key in doc.jira_keys:
                    try:
                        # Check if JIRA issue exists in cache
                        jira_result = await db.execute(
                            select(JiraIssue).where(JiraIssue.key == jira_key.upper())
                        )
                        jira_issue = jira_result.scalar_one_or_none()

                        if not jira_issue:
                            logger.debug(f"JIRA issue {jira_key} not in cache, skipping")
                            stats["links_skipped"] += 1
                            continue

                        # Determine link type based on document kind
                        if doc.document_kind == "postmortem":
                            link_type = LinkType.POSTMORTEM_FOR
                        elif doc.document_kind in ("rfd", "rfc"):
                            link_type = LinkType.RFD_FOR
                        elif doc.document_kind == "meeting-notes":
                            link_type = LinkType.MEETING_NOTES_FOR
                        else:
                            link_type = LinkType.DOCUMENTED_IN_GDRIVE

                        # Create link: JIRA issue → documented in → Google Drive doc
                        created = await link_service.create_link(
                            from_type="jira_issue",
                            from_id=str(jira_issue.id),
                            to_type="google_drive_document",
                            to_id=str(doc.id),
                            link_type=link_type,
                            source_type=LinkSourceType.INFERRED,
                            confidence_score=0.9,  # High confidence for filename match
                        )

                        if created:
                            stats["links_created"] += 1
                            logger.debug(f"Linked {jira_key} → {doc.title} ({link_type.value})")
                        else:
                            stats["links_skipped"] += 1

                    except Exception as e:
                        error_msg = f"Error linking {doc.title} to {jira_key}: {e}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

            await db.commit()

            logger.info(
                f"Google Drive → JIRA linking complete: {stats['documents_processed']} docs processed, "
                f"{stats['links_created']} links created, {stats['links_skipped']} skipped, "
                f"{len(stats['errors'])} errors"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in Google Drive → JIRA linking: {e}", exc_info=True)
        return {
            "documents_processed": 0,
            "links_created": 0,
            "links_skipped": 0,
            "errors": [str(e)]
        }
