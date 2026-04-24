"""Git worktree tracking service for Planet Commander Phase 1.

Scans and tracks git worktrees across repositories, including dirty state and health.
"""

import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Worktree, WorktreeStatus, GitBranch

logger = logging.getLogger(__name__)


class WorktreeTrackingService:
    """Track git worktrees across repositories."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_worktrees(self, repo_path: str | Path, repo_name: str) -> list[Worktree]:
        """Scan git worktrees and sync to database.

        Args:
            repo_path: Path to git repository
            repo_name: Repository name (e.g., 'wx/wx')

        Returns:
            List of Worktree instances
        """
        repo_path = Path(repo_path)

        if not repo_path.exists():
            logger.warning(f"Repo path does not exist: {repo_path}")
            return []

        # Get all worktrees from git
        worktrees_data = self._get_all_worktrees(repo_path)

        synced_worktrees = []

        for wt_data in worktrees_data:
            worktree = await self._sync_worktree(repo_name, wt_data)
            if worktree:
                synced_worktrees.append(worktree)

        await self.db.flush()

        logger.info(f"Scanned {len(synced_worktrees)} worktrees in {repo_name}")

        return synced_worktrees

    async def update_worktree_status(self, worktree_id: uuid.UUID) -> Worktree:
        """Check worktree dirty state, uncommitted changes, etc.

        Args:
            worktree_id: Worktree UUID

        Returns:
            Updated Worktree instance

        Raises:
            ValueError: If worktree not found
        """
        result = await self.db.execute(
            select(Worktree)
            .options(selectinload(Worktree.branch))
            .where(Worktree.id == worktree_id)
        )
        worktree = result.scalar_one_or_none()

        if not worktree:
            raise ValueError(f"Worktree {worktree_id} not found")

        worktree_path = Path(worktree.path)

        # Check if worktree still exists
        if not worktree_path.exists():
            worktree.is_active = False
            worktree.status = WorktreeStatus.ORPHANED
            await self.db.flush()
            return worktree

        # Get worktree health
        health = self._check_worktree_health(worktree_path)

        # Update worktree fields
        worktree.has_uncommitted_changes = health["has_uncommitted_changes"]
        worktree.has_untracked_files = health["has_untracked_files"]
        worktree.is_rebasing = health["is_rebasing"]
        worktree.is_out_of_date = health["is_out_of_date"]
        worktree.last_seen_at = datetime.now(timezone.utc)

        # Determine status
        if health["is_rebasing"]:
            worktree.status = WorktreeStatus.DIRTY
        elif health["has_uncommitted_changes"] or health["has_untracked_files"]:
            worktree.status = WorktreeStatus.DIRTY
        elif health["is_out_of_date"]:
            worktree.status = WorktreeStatus.STALE
        else:
            worktree.status = WorktreeStatus.CLEAN

        await self.db.flush()

        return worktree

    async def _sync_worktree(
        self, repo_name: str, worktree_data: dict[str, Any]
    ) -> Worktree | None:
        """Sync single worktree to database.

        Args:
            repo_name: Repository name
            worktree_data: Worktree metadata dict

        Returns:
            Worktree instance or None if sync failed
        """
        wt_path = worktree_data["path"]
        branch_name = worktree_data["branch"]

        # Find or create GitBranch
        result = await self.db.execute(
            select(GitBranch).where(
                (GitBranch.repo == repo_name) & (GitBranch.branch_name == branch_name)
            )
        )
        branch = result.scalar_one_or_none()

        if not branch:
            # Branch not tracked yet - create it
            logger.warning(f"Branch {branch_name} not found for worktree {wt_path}, skipping")
            return None

        # Check if worktree already exists
        result = await self.db.execute(select(Worktree).where(Worktree.path == wt_path))
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.branch_id = branch.id
            existing.is_active = True
            existing.last_seen_at = datetime.now(timezone.utc)
            return existing
        else:
            # Create new
            worktree = Worktree(
                repo=repo_name,
                path=wt_path,
                branch_id=branch.id,
                status=WorktreeStatus.ACTIVE,
                is_active=True,
                last_seen_at=datetime.now(timezone.utc),
            )

            self.db.add(worktree)
            return worktree

    def _get_all_worktrees(self, repo_path: Path) -> list[dict[str, Any]]:
        """Get all worktrees from git repository.

        Args:
            repo_path: Path to git repository

        Returns:
            List of worktree metadata dicts
        """
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Git worktree list failed in {repo_path}: {result.stderr.strip()}")
                return []

            return self._parse_worktree_list(result.stdout)

        except subprocess.TimeoutExpired:
            logger.warning(f"Git worktree list timed out in {repo_path}")
            return []
        except Exception as e:
            logger.error(f"Failed to get worktrees in {repo_path}: {e}")
            return []

    def _parse_worktree_list(self, output: str) -> list[dict[str, Any]]:
        """Parse git worktree list --porcelain output.

        Args:
            output: Porcelain format output

        Returns:
            List of worktree metadata dicts
        """
        worktrees = []
        current: dict[str, Any] = {}

        for line in output.split("\n"):
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue

            if line.startswith("worktree "):
                current["path"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                # Format: branch refs/heads/branch-name
                branch_ref = line.split(" ", 1)[1]
                current["branch"] = branch_ref.replace("refs/heads/", "")
            elif line.startswith("HEAD "):
                current["head"] = line.split(" ", 1)[1]
            elif line == "bare":
                current["is_bare"] = True
            elif line == "detached":
                current["is_detached"] = True

        # Add last worktree if exists
        if current:
            worktrees.append(current)

        return worktrees

    def _check_worktree_health(self, worktree_path: Path) -> dict[str, bool]:
        """Check health of a worktree.

        Args:
            worktree_path: Path to worktree

        Returns:
            Dict with health indicators
        """
        health = {
            "has_uncommitted_changes": False,
            "has_untracked_files": False,
            "is_rebasing": False,
            "is_out_of_date": False,
        }

        try:
            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "diff", "--quiet"],
                cwd=str(worktree_path),
                capture_output=True,
                timeout=5,
            )
            health["has_uncommitted_changes"] = result.returncode != 0

            # Check for untracked files
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            health["has_untracked_files"] = bool(result.stdout.strip())

            # Check if rebasing
            rebase_dir = worktree_path / ".git" / "rebase-merge"
            rebase_apply = worktree_path / ".git" / "rebase-apply"
            health["is_rebasing"] = rebase_dir.exists() or rebase_apply.exists()

            # Check if out of date (behind remote)
            # This would require fetching first, which is expensive
            # For Phase 1, we'll skip this check
            health["is_out_of_date"] = False

        except Exception as e:
            logger.warning(f"Failed to check worktree health for {worktree_path}: {e}")

        return health
