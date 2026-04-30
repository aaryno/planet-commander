"""Git repository scanning background job"""
import logging
from datetime import datetime
from pathlib import Path

from app.database import async_session
from app.services.branch_tracking import BranchTrackingService
from app.services.worktree_tracking import WorktreeTrackingService
from app.services.config_service import config, get_repos_to_scan_from_db

logger = logging.getLogger(__name__)


async def scan_git_repositories():
    """Scan all configured git repositories for branches and worktrees

    Returns:
        dict: Results with records_processed count
    """
    start_time = datetime.utcnow()
    logger.info("Starting git repository scan")

    total_branches = 0
    total_worktrees = 0
    repos_scanned = 0

    async with async_session() as db:
        try:
            db_repos = await get_repos_to_scan_from_db(db)
            repos_to_scan = [r["path"] for r in db_repos if r.get("path")]
        except Exception as e:
            logger.warning("Failed to load repos from DB, falling back to config: %s", e)
            repos_to_scan = config.get_repos_to_scan()
        try:
            branch_service = BranchTrackingService(db)
            worktree_service = WorktreeTrackingService(db)

            for repo_path_str in repos_to_scan:
                repo_path = Path(repo_path_str)

                # Skip if repo doesn't exist
                if not repo_path.exists():
                    logger.warning(f"Repository not found: {repo_path}")
                    continue

                # Skip if not a git repo
                if not (repo_path / ".git").exists():
                    logger.warning(f"Not a git repository: {repo_path}")
                    continue

                logger.info(f"Scanning repository: {repo_path}")

                try:
                    # Scan branches
                    branches = await branch_service.scan_repo_branches(str(repo_path))
                    total_branches += len(branches)
                    logger.debug(f"  Found {len(branches)} branches")

                    # Scan worktrees
                    worktrees = await worktree_service.scan_worktrees(str(repo_path))
                    total_worktrees += len(worktrees)
                    logger.debug(f"  Found {len(worktrees)} worktrees")

                    repos_scanned += 1

                except Exception as e:
                    logger.error(f"Failed to scan {repo_path}: {e}", exc_info=True)
                    continue

            # Commit all changes
            await db.commit()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Git scan complete: {repos_scanned} repos, {total_branches} branches, "
                f"{total_worktrees} worktrees in {duration:.1f}s"
            )

            return {
                "records_processed": total_branches + total_worktrees,
                "repos_scanned": repos_scanned,
                "branches": total_branches,
                "worktrees": total_worktrees,
            }

        except Exception as e:
            logger.error(f"Git scan failed: {e}", exc_info=True)
            await db.rollback()
            raise
