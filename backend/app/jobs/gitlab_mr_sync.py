"""Background jobs for GitLab MR syncing, enrichment, and linking."""

import logging
from typing import Dict

from app.database import async_session
from app.models import GitLabMergeRequest, JiraIssue, EntityLink, LinkType, LinkSourceType, LinkStatus
from app.services.gitlab_mr_service import GitLabMRService
from app.services.entity_link import EntityLinkService
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def sync_gitlab_mrs() -> Dict:
    """Sync GitLab merge requests from tracked repositories.

    Scans all tracked repositories for open MRs using glab CLI,
    parses metadata, and updates the database.

    Returns:
        Dictionary with scan statistics
    """
    try:
        async with async_session() as db:
            service = GitLabMRService(db)
            logger.info("Starting GitLab MR sync")

            # Scan all default repositories
            all_stats = {
                "total_scanned": 0,
                "new_mrs": 0,
                "updated_mrs": 0,
                "unchanged_mrs": 0,
                "errors": []
            }

            for repository in await service.get_repositories():
                logger.info(f"Scanning {repository}")
                stats = await service.scan_repository_mrs(
                    repository,
                    state="opened",
                    limit=100
                )

                # Aggregate stats
                all_stats["total_scanned"] += stats["total_scanned"]
                all_stats["new_mrs"] += stats["new_mrs"]
                all_stats["updated_mrs"] += stats["updated_mrs"]
                all_stats["unchanged_mrs"] += stats["unchanged_mrs"]
                all_stats["errors"].extend(stats["errors"])

            logger.info(
                f"GitLab MR sync complete: {all_stats['total_scanned']} scanned, "
                f"{all_stats['new_mrs']} new, {all_stats['updated_mrs']} updated, "
                f"{all_stats['unchanged_mrs']} unchanged, {len(all_stats['errors'])} errors"
            )

            return all_stats

    except Exception as e:
        logger.error(f"Error in GitLab MR sync: {e}", exc_info=True)
        return {
            "total_scanned": 0,
            "new_mrs": 0,
            "updated_mrs": 0,
            "unchanged_mrs": 0,
            "errors": [str(e)]
        }


async def link_mrs_to_jira() -> Dict:
    """Auto-link GitLab MRs to JIRA issues.

    Creates entity links between GitLab MRs and JIRA issues based on:
    1. JIRA keys found in MR title/description (e.g., COMPUTE-1234)
    2. Link type: implemented_by (JIRA → MR) and implements (MR → JIRA)

    Returns:
        Dictionary with linking statistics
    """
    try:
        async with async_session() as db:
            link_service = EntityLinkService(db)

            logger.info("Starting GitLab MR → JIRA linking")

            stats = {
                "mrs_processed": 0,
                "links_created": 0,
                "links_skipped": 0,
                "errors": []
            }

            # Get all MRs with JIRA keys
            result = await db.execute(
                select(GitLabMergeRequest).where(
                    GitLabMergeRequest.jira_keys.isnot(None)
                )
            )
            mrs = result.scalars().all()

            for mr in mrs:
                stats["mrs_processed"] += 1

                if not mr.jira_keys:
                    continue

                for jira_key in mr.jira_keys:
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

                        # Create link: JIRA issue → implemented by → MR
                        created = await link_service.create_link(
                            from_type="jira_issue",
                            from_id=str(jira_issue.id),
                            to_type="gitlab_merge_request",
                            to_id=str(mr.id),
                            link_type=LinkType.IMPLEMENTED_BY,
                            source_type=LinkSourceType.INFERRED,
                            confidence_score=0.95,  # High confidence for title/description match
                        )

                        if created:
                            stats["links_created"] += 1
                            logger.debug(f"Linked {jira_key} → !{mr.external_mr_id} ({mr.repository})")
                        else:
                            stats["links_skipped"] += 1

                    except Exception as e:
                        error_msg = f"Error linking !{mr.external_mr_id} to {jira_key}: {e}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

            await db.commit()

            logger.info(
                f"GitLab MR → JIRA linking complete: {stats['mrs_processed']} MRs processed, "
                f"{stats['links_created']} links created, {stats['links_skipped']} skipped, "
                f"{len(stats['errors'])} errors"
            )

            return stats

    except Exception as e:
        logger.error(f"Error in GitLab MR → JIRA linking: {e}", exc_info=True)
        return {
            "mrs_processed": 0,
            "links_created": 0,
            "links_skipped": 0,
            "errors": [str(e)]
        }


async def enrich_mr_diff_stats(force: bool = False) -> Dict:
    """Enrich GitLab MRs with diff statistics from the GitLab API.

    For each MR that doesn't yet have additions/deletions/changed_files
    populated, fetches diff stats from GET /projects/:id/merge_requests/:iid/changes
    and stores them. Skips MRs that already have stats unless force=True.

    This should run after sync_gitlab_mrs() so that new MRs are in the
    database before enrichment.

    Args:
        force: If True, re-fetch stats for all MRs (not just missing ones)

    Returns:
        Dictionary with enrichment statistics
    """
    try:
        async with async_session() as db:
            service = GitLabMRService(db)
            logger.info("Starting GitLab MR diff stats enrichment (force=%s)", force)

            stats = await service.enrich_all_diff_stats(force=force)

            logger.info(
                "GitLab MR diff stats enrichment complete: "
                "%d enriched, %d skipped, %d errors out of %d total",
                stats["enriched"], stats["skipped"],
                stats["errors"], stats["total"],
            )

            return stats

    except Exception as e:
        logger.error(f"Error in GitLab MR diff stats enrichment: {e}", exc_info=True)
        return {
            "enriched": 0,
            "skipped": 0,
            "errors": 1,
            "total": 0,
            "error_detail": str(e),
        }
