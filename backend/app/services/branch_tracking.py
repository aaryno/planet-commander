"""Git branch tracking service for Planet Commander Phase 1.

Scans and tracks git branches across repositories.
"""

import logging
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GitBranch, BranchStatus

logger = logging.getLogger(__name__)


class BranchTrackingService:
    """Track git branches across repositories."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_repo_branches(self, repo_path: str | Path, repo_name: str) -> list[GitBranch]:
        """Scan git repo for branches and sync to database.

        Args:
            repo_path: Path to git repository
            repo_name: Repository name (e.g., 'wx/wx', 'product/g4-wk/g4')

        Returns:
            List of GitBranch instances
        """
        repo_path = Path(repo_path)

        if not repo_path.exists():
            logger.warning(f"Repo path does not exist: {repo_path}")
            return []

        # Get all branches
        branches_data = self._get_all_branches(repo_path)

        synced_branches = []

        for branch_data in branches_data:
            branch = await self._sync_branch(repo_name, branch_data)
            if branch:
                synced_branches.append(branch)

        await self.db.flush()

        logger.info(f"Scanned {len(synced_branches)} branches in {repo_name}")

        return synced_branches

    async def update_branch_status(self, branch_id: uuid.UUID, repo_path: str | Path) -> GitBranch:
        """Update branch ahead/behind counts and status.

        Args:
            branch_id: GitBranch UUID
            repo_path: Path to git repository

        Returns:
            Updated GitBranch instance

        Raises:
            ValueError: If branch not found
        """
        result = await self.db.execute(select(GitBranch).where(GitBranch.id == branch_id))
        branch = result.scalar_one_or_none()

        if not branch:
            raise ValueError(f"Branch {branch_id} not found")

        repo_path = Path(repo_path)

        # Get ahead/behind counts
        ahead, behind = self._get_ahead_behind(repo_path, branch.branch_name, branch.base_branch)

        branch.ahead_count = ahead
        branch.behind_count = behind

        # Update status based on ahead/behind
        if branch.status != BranchStatus.MERGED:
            if ahead == 0 and behind > 50:
                branch.status = BranchStatus.STALE
            elif ahead == 0 and behind == 0:
                branch.status = BranchStatus.MERGED
            else:
                branch.status = BranchStatus.ACTIVE

        await self.db.flush()

        return branch

    async def _sync_branch(self, repo_name: str, branch_data: dict[str, Any]) -> GitBranch | None:
        """Sync single branch to database.

        Args:
            repo_name: Repository name
            branch_data: Branch metadata dict

        Returns:
            GitBranch instance or None if sync failed
        """
        branch_name = branch_data["name"]
        head_sha = branch_data["sha"]

        # Check if branch already exists
        result = await self.db.execute(
            select(GitBranch).where(
                (GitBranch.repo == repo_name) & (GitBranch.branch_name == branch_name)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.head_sha = head_sha
            existing.ahead_count = branch_data.get("ahead")
            existing.behind_count = branch_data.get("behind")

            # Try to extract JIRA key from branch name
            jira_key = self._extract_jira_key(branch_name)
            if jira_key:
                existing.linked_ticket_key_guess = jira_key
                existing.is_inferred = True

            return existing
        else:
            # Create new
            jira_key = self._extract_jira_key(branch_name)

            branch = GitBranch(
                repo=repo_name,
                branch_name=branch_name,
                head_sha=head_sha,
                base_branch=branch_data.get("base_branch", "main"),
                status=BranchStatus.ACTIVE,
                ahead_count=branch_data.get("ahead"),
                behind_count=branch_data.get("behind"),
                has_open_pr=False,  # Would need to query GitLab/GitHub API
                linked_ticket_key_guess=jira_key,
                is_inferred=bool(jira_key),
            )

            self.db.add(branch)
            return branch

    def _get_all_branches(self, repo_path: Path) -> list[dict[str, Any]]:
        """Get all branches from git repository.

        Args:
            repo_path: Path to git repository

        Returns:
            List of branch metadata dicts
        """
        try:
            # Get all branches with their SHAs
            result = subprocess.run(
                ["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads/"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"Git command failed in {repo_path}: {result.stderr.strip()}")
                return []

            branches = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue

                branch_name, sha = parts

                # Get ahead/behind for this branch relative to main
                ahead, behind = self._get_ahead_behind(repo_path, branch_name, "main")

                branches.append({
                    "name": branch_name,
                    "sha": sha,
                    "base_branch": "main",  # Assume main for now
                    "ahead": ahead,
                    "behind": behind,
                })

            return branches

        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out in {repo_path}")
            return []
        except Exception as e:
            logger.error(f"Failed to get branches in {repo_path}: {e}")
            return []

    def _get_ahead_behind(
        self, repo_path: Path, branch: str, base_branch: str
    ) -> tuple[int, int]:
        """Get ahead/behind counts for branch relative to base.

        Args:
            repo_path: Path to git repository
            branch: Branch name
            base_branch: Base branch name (e.g., 'main')

        Returns:
            Tuple of (ahead_count, behind_count)
        """
        try:
            result = subprocess.run(
                ["git", "rev-list", "--left-right", "--count", f"{base_branch}...{branch}"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return (0, 0)

            parts = result.stdout.strip().split()
            if len(parts) != 2:
                return (0, 0)

            behind = int(parts[0])
            ahead = int(parts[1])

            return (ahead, behind)

        except Exception:
            return (0, 0)

    def _extract_jira_key(self, branch_name: str) -> str | None:
        """Extract JIRA key from branch name.

        Args:
            branch_name: Git branch name

        Returns:
            JIRA key or None if not found
        """
        # Pattern: ao/COMPUTE-1234-description or COMPUTE-1234-description
        match = re.search(r"([A-Z]+-\d+)", branch_name)
        if match:
            return match.group(1)

        return None
