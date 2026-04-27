"""Service for GitLab merge request indexing and searching."""

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gitlab_merge_request import GitLabMergeRequest
from app.services.gitlab_api_client import get_gitlab_client
from app.services.project_config import ProjectConfigService

logger = logging.getLogger(__name__)


class GitLabMRService:
    """Service for indexing and searching GitLab merge requests."""

    # JIRA key pattern
    JIRA_KEY_PATTERN = re.compile(
        r"\b(?:COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL|ESO)-\d+\b",
        re.IGNORECASE
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_repositories(self) -> list[str]:
        """Get all repo paths from active projects in the database."""
        return await ProjectConfigService(self.db).get_all_repo_paths()

    def run_glab_command(self, args: List[str]) -> Optional[str]:
        """Run glab CLI command and return output.

        Args:
            args: Command arguments (e.g., ["mr", "list", "--repo", "wx/wx"])

        Returns:
            Command output as string, or None on error
        """
        try:
            result = subprocess.run(
                ["glab"] + args,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"glab command failed: {result.stderr}")
                return None

            return result.stdout

        except subprocess.TimeoutExpired:
            logger.error("glab command timed out")
            return None
        except Exception as e:
            logger.error(f"Error running glab command: {e}")
            return None

    def parse_mr_json(self, mr_json: Dict) -> Dict:
        """Parse MR JSON from glab output.

        Args:
            mr_json: Raw JSON object from glab

        Returns:
            Parsed MR metadata
        """
        # Extract JIRA keys from title and description
        combined_text = f"{mr_json.get('title', '')} {mr_json.get('description', '')}"
        jira_keys = list(set(self.JIRA_KEY_PATTERN.findall(combined_text)))

        # Parse timestamps
        created_at = None
        updated_at = None
        merged_at = None
        closed_at = None

        if mr_json.get("created_at"):
            created_at = datetime.fromisoformat(mr_json["created_at"].replace("Z", "+00:00"))
        if mr_json.get("updated_at"):
            updated_at = datetime.fromisoformat(mr_json["updated_at"].replace("Z", "+00:00"))
        if mr_json.get("merged_at"):
            merged_at = datetime.fromisoformat(mr_json["merged_at"].replace("Z", "+00:00"))
        if mr_json.get("closed_at"):
            closed_at = datetime.fromisoformat(mr_json["closed_at"].replace("Z", "+00:00"))

        # Extract reviewers
        reviewers = []
        for reviewer in mr_json.get("reviewers", []):
            reviewers.append({
                "username": reviewer.get("username"),
                "name": reviewer.get("name")
            })

        # Determine approval status
        approval_status = None
        if mr_json.get("detailed_merge_status"):
            status = mr_json["detailed_merge_status"]
            if "approved" in status.lower():
                approval_status = "approved"
            elif "not_approved" in status.lower():
                approval_status = "pending"
            elif "blocked" in status.lower():
                approval_status = "changes_requested"

        # Determine CI status from pipeline
        ci_status = None
        # Note: glab mr list doesn't include pipeline details
        # Would need to call glab mr view or glab ci status for full pipeline info
        # For now, we'll set it as None and potentially update in a separate call

        return {
            "external_mr_id": mr_json.get("iid"),
            "title": mr_json.get("title", ""),
            "description": mr_json.get("description", ""),
            "url": mr_json.get("web_url", ""),
            "source_branch": mr_json.get("source_branch", ""),
            "target_branch": mr_json.get("target_branch", ""),
            "author": mr_json.get("author", {}).get("username", ""),
            "reviewers": reviewers if reviewers else None,
            "approval_status": approval_status,
            "ci_status": ci_status,
            "state": mr_json.get("state", "opened"),
            "jira_keys": jira_keys if jira_keys else None,
            "created_at": created_at,
            "updated_at": updated_at,
            "merged_at": merged_at,
            "closed_at": closed_at,
        }

    async def scan_repository_mrs(
        self,
        repository: str,
        state: str = "opened",
        limit: int = 100
    ) -> Dict:
        """Scan a repository for merge requests.

        Args:
            repository: Repository path (e.g., "wx/wx")
            state: MR state ("opened", "merged", "closed", "all")
            limit: Maximum MRs to fetch

        Returns:
            Dictionary with scan statistics
        """
        logger.info(f"Scanning {repository} for {state} MRs (limit: {limit})")

        stats = {
            "repository": repository,
            "state": state,
            "total_scanned": 0,
            "new_mrs": 0,
            "updated_mrs": 0,
            "unchanged_mrs": 0,
            "errors": []
        }

        # Build glab command
        args = ["mr", "list", "--repo", repository, "--per-page", str(limit), "--output", "json"]

        if state == "merged":
            args.append("--merged")
        elif state == "closed":
            args.append("--closed")
        elif state == "all":
            args.append("--all")
        # "opened" is the default, no flag needed

        # Run glab command
        output = self.run_glab_command(args)
        if not output:
            error_msg = f"Failed to fetch MRs from {repository}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        # Parse JSON
        try:
            mrs = json.loads(output)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse glab output: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        # Process each MR
        for mr_json in mrs:
            stats["total_scanned"] += 1

            try:
                result = await self.update_mr(repository, mr_json)

                if result == "new":
                    stats["new_mrs"] += 1
                elif result == "updated":
                    stats["updated_mrs"] += 1
                elif result == "unchanged":
                    stats["unchanged_mrs"] += 1

            except Exception as e:
                await self.db.rollback()
                error_msg = f"Error processing MR !{mr_json.get('iid')}: {e}"
                logger.error(error_msg, exc_info=True)
                stats["errors"].append(error_msg)

        return stats

    async def update_mr(self, repository: str, mr_json: Dict) -> str:
        """Update or create MR from glab JSON.

        Args:
            repository: Repository path
            mr_json: Raw MR JSON from glab

        Returns:
            "new", "updated", or "unchanged"
        """
        # Parse MR data
        mr_data = self.parse_mr_json(mr_json)

        # Check if MR already exists
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                GitLabMergeRequest.repository == repository,
                GitLabMergeRequest.external_mr_id == mr_data["external_mr_id"]
            )
        )
        existing_mr = result.scalar_one_or_none()

        # If updated_at timestamp unchanged, skip update
        if existing_mr and existing_mr.updated_at and mr_data["updated_at"]:
            if abs((existing_mr.updated_at - mr_data["updated_at"]).total_seconds()) < 1:
                return "unchanged"

        if existing_mr:
            # Update existing MR
            for key, value in mr_data.items():
                setattr(existing_mr, key, value)
            existing_mr.last_synced_at = datetime.now(timezone.utc)

            await self.db.commit()
            return "updated"

        else:
            # Create new MR
            new_mr = GitLabMergeRequest(
                repository=repository,
                last_synced_at=datetime.now(timezone.utc),
                **mr_data
            )
            self.db.add(new_mr)
            await self.db.commit()
            return "new"

    async def search_mrs(
        self,
        query: Optional[str] = None,
        repository: Optional[str] = None,
        state: Optional[str] = None,
        author: Optional[str] = None,
        jira_key: Optional[str] = None,
        limit: int = 50
    ) -> List[GitLabMergeRequest]:
        """Search merge requests.

        Args:
            query: Search query (title/description)
            repository: Filter by repository
            state: Filter by state
            author: Filter by author
            jira_key: Filter by JIRA key
            limit: Maximum results

        Returns:
            List of matching GitLabMergeRequest instances
        """
        stmt = select(GitLabMergeRequest)

        # Build filters
        conditions = []

        if repository:
            conditions.append(GitLabMergeRequest.repository == repository)

        if state:
            conditions.append(GitLabMergeRequest.state == state)

        if author:
            conditions.append(GitLabMergeRequest.author == author)

        if jira_key:
            conditions.append(GitLabMergeRequest.jira_keys.contains([jira_key.upper()]))

        if query:
            query_lower = query.lower()
            conditions.append(
                or_(
                    GitLabMergeRequest.title.ilike(f"%{query}%"),
                    GitLabMergeRequest.description.ilike(f"%{query}%")
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.order_by(GitLabMergeRequest.updated_at.desc())
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_mr_by_number(
        self,
        repository: str,
        mr_number: int
    ) -> Optional[GitLabMergeRequest]:
        """Get MR by repository and number.

        Args:
            repository: Repository path
            mr_number: MR number (iid)

        Returns:
            GitLabMergeRequest instance or None
        """
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                GitLabMergeRequest.repository == repository,
                GitLabMergeRequest.external_mr_id == mr_number
            )
        )
        return result.scalar_one_or_none()

    async def get_mrs_by_jira(self, jira_key: str) -> List[GitLabMergeRequest]:
        """Get MRs mentioning a JIRA key.

        Args:
            jira_key: JIRA key (e.g., "COMPUTE-1234")

        Returns:
            List of GitLabMergeRequest instances
        """
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                GitLabMergeRequest.jira_keys.contains([jira_key.upper()])
            ).order_by(GitLabMergeRequest.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_mrs_by_branch(self, branch_name: str) -> List[GitLabMergeRequest]:
        """Get MRs by source branch name.

        Args:
            branch_name: Branch name

        Returns:
            List of GitLabMergeRequest instances
        """
        result = await self.db.execute(
            select(GitLabMergeRequest).where(
                GitLabMergeRequest.source_branch == branch_name
            ).order_by(GitLabMergeRequest.updated_at.desc())
        )
        return list(result.scalars().all())

    # ── Diff statistics enrichment ──────────────────────────────────────

    @staticmethod
    def parse_diff_stats(api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse diff statistics from a GitLab MR changes API response.

        Extracts additions, deletions, changed file count, and per-file
        details from the /merge_requests/:iid/changes response.

        Args:
            api_response: Raw JSON from GET /projects/:id/merge_requests/:iid/changes

        Returns:
            Dict with keys: additions, deletions, changed_file_count, changed_files
        """
        changes = api_response.get("changes", [])
        overflow = api_response.get("overflow", False)

        total_additions = 0
        total_deletions = 0
        file_details: List[Dict[str, Any]] = []

        for change in changes:
            # Per-file line counts come from the diff content
            # GitLab provides diff text; we count +/- lines
            diff_text = change.get("diff", "")
            file_additions = 0
            file_deletions = 0
            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    file_additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    file_deletions += 1

            total_additions += file_additions
            total_deletions += file_deletions

            file_details.append({
                "path": change.get("new_path", change.get("old_path", "")),
                "old_path": change.get("old_path", ""),
                "additions": file_additions,
                "deletions": file_deletions,
                "renamed_file": change.get("renamed_file", False),
                "new_file": change.get("new_file", False),
                "deleted_file": change.get("deleted_file", False),
            })

        return {
            "additions": total_additions,
            "deletions": total_deletions,
            "changed_file_count": len(changes),
            "changed_files": file_details,
            "overflow": overflow,
        }

    async def enrich_mr_diff_stats(
        self,
        mr: GitLabMergeRequest,
        force: bool = False,
    ) -> str:
        """Fetch and store diff statistics for a single MR.

        Calls the GitLab API to get per-file diff stats and updates the
        MR record in the database.

        Args:
            mr: The GitLabMergeRequest to enrich
            force: If True, re-fetch even if stats already populated

        Returns:
            "enriched", "skipped" (already has stats), or "error"
        """
        # Skip if already has diff stats (unless forced)
        if not force and mr.additions is not None and mr.changed_files is not None:
            return "skipped"

        client = get_gitlab_client()
        try:
            api_response = await client.get_mr_changes(
                project_path=mr.repository,
                mr_iid=mr.external_mr_id,
            )

            if api_response is None:
                logger.warning(
                    "Failed to fetch diff stats for %s !%d (API returned None)",
                    mr.repository, mr.external_mr_id,
                )
                return "error"

            # Parse the response
            diff_stats = self.parse_diff_stats(api_response)

            if diff_stats["overflow"]:
                logger.warning(
                    "Diff overflow for %s !%d — file list may be incomplete (%d files returned)",
                    mr.repository, mr.external_mr_id, diff_stats["changed_file_count"],
                )

            # Update the MR record
            mr.additions = diff_stats["additions"]
            mr.deletions = diff_stats["deletions"]
            mr.changed_file_count = diff_stats["changed_file_count"]
            mr.changed_files = diff_stats["changed_files"]

            await self.db.commit()

            logger.debug(
                "Enriched diff stats for %s !%d: +%d -%d, %d files",
                mr.repository, mr.external_mr_id,
                diff_stats["additions"], diff_stats["deletions"],
                diff_stats["changed_file_count"],
            )
            return "enriched"

        except Exception as e:
            logger.error(
                "Error enriching diff stats for %s !%d: %s",
                mr.repository, mr.external_mr_id, e,
                exc_info=True,
            )
            await self.db.rollback()
            return "error"

    async def enrich_all_diff_stats(self, force: bool = False) -> Dict[str, int]:
        """Enrich diff statistics for all MRs missing them.

        Fetches diff stats from the GitLab API for every MR that doesn't
        yet have additions/deletions/changed_files populated. Skips MRs
        that already have stats unless force=True.

        Args:
            force: If True, re-fetch stats for all MRs (not just missing ones)

        Returns:
            Dict with counts: enriched, skipped, errors, total
        """
        # Find MRs needing enrichment
        if force:
            result = await self.db.execute(select(GitLabMergeRequest))
        else:
            result = await self.db.execute(
                select(GitLabMergeRequest).where(
                    GitLabMergeRequest.additions.is_(None)
                )
            )

        mrs = list(result.scalars().all())
        logger.info(
            "Enriching diff stats for %d MRs (force=%s)", len(mrs), force
        )

        stats = {"enriched": 0, "skipped": 0, "errors": 0, "total": len(mrs)}

        for mr in mrs:
            result_status = await self.enrich_mr_diff_stats(mr, force=force)
            if result_status == "enriched":
                stats["enriched"] += 1
            elif result_status == "skipped":
                stats["skipped"] += 1
            elif result_status == "error":
                stats["errors"] += 1

        logger.info(
            "Diff stats enrichment complete: %d enriched, %d skipped, %d errors out of %d total",
            stats["enriched"], stats["skipped"], stats["errors"], stats["total"],
        )

        return stats
