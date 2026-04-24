"""Background jobs for syncing project documentation."""

import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.project_doc import ProjectDoc
from app.models.entity_link import EntityLink, LinkType, LinkSourceType, LinkStatus
from app.models.jira_issue import JiraIssue
from app.models.agent import Agent
from app.services.project_doc_service import ProjectDocService

logger = logging.getLogger(__name__)


async def sync_project_docs() -> Dict:
    """Sync project docs from ~/claude/projects/.

    Runs every 1 hour.
    Scans for *-notes/*-claude.md files.
    Updates docs if content hash changed.

    Returns:
        Dict with sync statistics
    """
    logger.info("Starting project docs sync")

    async with async_session() as db:
        service = ProjectDocService(db)

        try:
            stats = await service.scan_project_docs()

            logger.info(
                f"Project docs sync complete: {stats['total_scanned']} scanned, "
                f"{stats['new_docs']} new, {stats['updated_docs']} updated, "
                f"{stats['unchanged_docs']} unchanged, {len(stats.get('errors', []))} errors"
            )

            return stats

        except Exception as e:
            logger.error(f"Project docs sync failed: {e}", exc_info=True)
            return {
                "total_scanned": 0,
                "new_docs": 0,
                "updated_docs": 0,
                "unchanged_docs": 0,
                "errors": [str(e)],
            }


async def link_projects_to_entities() -> Dict:
    """Auto-link project docs to work contexts.

    Runs every 1 hour.

    Links created:
    1. JIRA issue (label "wx") → PROJECT_CONTEXT → wx-notes
    2. Agent chat (cwd ~/code/wx/) → PROJECT_CONTEXT → wx-notes
    3. Artifact (path mentions wx) → PROJECT_CONTEXT → wx-notes

    Returns:
        Dict with linking statistics
    """
    logger.info("Starting project → entity auto-linking")

    async with async_session() as db:
        service = ProjectDocService(db)

        try:
            # Get all project docs
            docs_result = await db.execute(select(ProjectDoc))
            docs = docs_result.scalars().all()

            links_created = 0

            # Link 1: JIRA issues → Project docs (by label)
            jira_result = await db.execute(select(JiraIssue))
            jira_issues = jira_result.scalars().all()

            for issue in jira_issues:
                if not issue.labels:
                    continue

                # Check if any label matches a project name
                project_name = await service.infer_project_from_context(
                    jira_labels=issue.labels
                )

                if project_name:
                    # Find matching project doc
                    doc = next((d for d in docs if d.project_name == project_name), None)
                    if doc:
                        # Check if link already exists
                        existing_link = await db.execute(
                            select(EntityLink).where(
                                EntityLink.from_type == "jira_issue",
                                EntityLink.from_id == str(issue.id),
                                EntityLink.to_type == "project_doc",
                                EntityLink.to_id == str(doc.id),
                            )
                        )

                        if not existing_link.scalar_one_or_none():
                            # Create link
                            link = EntityLink(
                                from_type="jira_issue",
                                from_id=str(issue.id),
                                to_type="project_doc",
                                to_id=str(doc.id),
                                link_type=LinkType.PROJECT_CONTEXT,
                                source_type=LinkSourceType.INFERRED,
                                status=LinkStatus.CONFIRMED,
                            )
                            db.add(link)
                            links_created += 1
                            logger.debug(f"Linked JIRA {issue.jira_key} → project {project_name}")

            # Link 2: Agent chats → Project docs (by working directory)
            agents_result = await db.execute(select(Agent))
            agents = agents_result.scalars().all()

            for agent in agents:
                if not agent.working_directory:
                    continue

                # Infer project from working directory
                project_name = await service.infer_project_from_context(
                    working_dir=agent.working_directory
                )

                if project_name:
                    # Find matching project doc
                    doc = next((d for d in docs if d.project_name == project_name), None)
                    if doc:
                        # Check if link already exists
                        existing_link = await db.execute(
                            select(EntityLink).where(
                                EntityLink.from_type == "agent",
                                EntityLink.from_id == str(agent.id),
                                EntityLink.to_type == "project_doc",
                                EntityLink.to_id == str(doc.id),
                            )
                        )

                        if not existing_link.scalar_one_or_none():
                            # Create link
                            link = EntityLink(
                                from_type="agent",
                                from_id=str(agent.id),
                                to_type="project_doc",
                                to_id=str(doc.id),
                                link_type=LinkType.PROJECT_CONTEXT,
                                source_type=LinkSourceType.INFERRED,
                                status=LinkStatus.CONFIRMED,
                            )
                            db.add(link)
                            links_created += 1
                            logger.debug(f"Linked agent {agent.id} → project {project_name}")

            await db.commit()

            logger.info(f"Project → entity linking complete: {links_created} links created")

            return {
                "projects_processed": len(docs),
                "jira_issues_processed": len(jira_issues),
                "agents_processed": len(agents),
                "links_created": links_created,
            }

        except Exception as e:
            logger.error(f"Project → entity linking failed: {e}", exc_info=True)
            return {
                "projects_processed": 0,
                "jira_issues_processed": 0,
                "agents_processed": 0,
                "links_created": 0,
                "error": str(e),
            }
