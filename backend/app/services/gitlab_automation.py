"""GitLab automation service for MR workflows."""
import logging
import subprocess
from typing import Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class GitLabAutomationService:
    """Service for GitLab MR automation (approve, merge, etc)."""

    def __init__(self):
        pass

    async def approve_mr(
        self,
        project: str,
        mr_iid: int,
        worktree_path: str | None = None
    ) -> Dict[str, any]:
        """
        Approve a merge request.

        Args:
            project: GitLab project path (e.g., "wx/wx")
            mr_iid: MR IID (internal ID)
            worktree_path: Worktree path for context (optional)

        Returns:
            dict: Approval result
        """
        try:
            cmd = ["glab", "mr", "approve", str(mr_iid)]

            if project:
                cmd.extend(["--repo", project])

            result = subprocess.run(
                cmd,
                cwd=worktree_path if worktree_path else None,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "project": project,
                    "mr_iid": mr_iid,
                    "message": "MR approved"
                }
            else:
                return {
                    "success": False,
                    "project": project,
                    "mr_iid": mr_iid,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": "Approval timed out"
            }
        except Exception as e:
            logger.error(f"Failed to approve MR: {e}")
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": str(e)
            }

    async def merge_mr(
        self,
        project: str,
        mr_iid: int,
        when_pipeline_succeeds: bool = True,
        delete_source_branch: bool = True,
        squash: bool = False,
        worktree_path: str | None = None
    ) -> Dict[str, any]:
        """
        Merge a merge request.

        Args:
            project: GitLab project path
            mr_iid: MR IID
            when_pipeline_succeeds: Wait for pipeline (default: True)
            delete_source_branch: Delete branch after merge (default: True)
            squash: Squash commits (default: False)
            worktree_path: Worktree path for context (optional)

        Returns:
            dict: Merge result
        """
        try:
            cmd = ["glab", "mr", "merge", str(mr_iid)]

            if project:
                cmd.extend(["--repo", project])

            if when_pipeline_succeeds:
                cmd.append("--when-pipeline-succeeds")

            if delete_source_branch:
                cmd.append("--remove-source-branch")

            if squash:
                cmd.append("--squash")

            # Always auto-confirm
            cmd.append("--yes")

            result = subprocess.run(
                cmd,
                cwd=worktree_path if worktree_path else None,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "project": project,
                    "mr_iid": mr_iid,
                    "message": "MR merged" if not when_pipeline_succeeds else "MR scheduled for merge",
                    "when_pipeline_succeeds": when_pipeline_succeeds
                }
            else:
                return {
                    "success": False,
                    "project": project,
                    "mr_iid": mr_iid,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": "Merge timed out"
            }
        except Exception as e:
            logger.error(f"Failed to merge MR: {e}")
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": str(e)
            }

    async def check_mr_status(
        self,
        project: str,
        mr_iid: int,
        worktree_path: str | None = None
    ) -> Dict[str, any]:
        """
        Check MR status (pipeline, approvals, mergeable).

        Args:
            project: GitLab project path
            mr_iid: MR IID
            worktree_path: Worktree path for context (optional)

        Returns:
            dict: MR status
        """
        try:
            cmd = ["glab", "mr", "view", str(mr_iid), "--json"]

            if project:
                cmd.extend(["--repo", project])

            result = subprocess.run(
                cmd,
                cwd=worktree_path if worktree_path else None,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                import json
                mr_data = json.loads(result.stdout)

                return {
                    "success": True,
                    "project": project,
                    "mr_iid": mr_iid,
                    "state": mr_data.get("state"),
                    "mergeable": mr_data.get("mergeable", False),
                    "pipeline_status": mr_data.get("pipeline", {}).get("status"),
                    "approvals": mr_data.get("approvals", 0),
                    "has_conflicts": mr_data.get("has_conflicts", False)
                }
            else:
                return {
                    "success": False,
                    "project": project,
                    "mr_iid": mr_iid,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": "Status check timed out"
            }
        except Exception as e:
            logger.error(f"Failed to check MR status: {e}")
            return {
                "success": False,
                "project": project,
                "mr_iid": mr_iid,
                "error": str(e)
            }

    async def auto_approve_and_merge(
        self,
        project: str,
        mr_iid: int,
        worktree_path: str | None = None,
        squash: bool = False
    ) -> Dict[str, any]:
        """
        Auto-approve and merge MR (convenience method).

        Args:
            project: GitLab project path
            mr_iid: MR IID
            worktree_path: Worktree path for context
            squash: Squash commits (default: False)

        Returns:
            dict: Combined result
        """
        # Check status first
        status = await self.check_mr_status(project, mr_iid, worktree_path)

        if not status["success"]:
            return {
                "success": False,
                "step": "check_status",
                "error": status.get("error")
            }

        # Check if MR is mergeable
        if not status.get("mergeable"):
            return {
                "success": False,
                "step": "check_mergeable",
                "error": "MR is not mergeable",
                "has_conflicts": status.get("has_conflicts", False)
            }

        # Approve
        approve_result = await self.approve_mr(project, mr_iid, worktree_path)

        if not approve_result["success"]:
            return {
                "success": False,
                "step": "approve",
                "error": approve_result.get("error")
            }

        # Merge (wait for pipeline)
        merge_result = await self.merge_mr(
            project,
            mr_iid,
            when_pipeline_succeeds=True,
            delete_source_branch=True,
            squash=squash,
            worktree_path=worktree_path
        )

        if not merge_result["success"]:
            return {
                "success": False,
                "step": "merge",
                "error": merge_result.get("error")
            }

        return {
            "success": True,
            "project": project,
            "mr_iid": mr_iid,
            "approved": True,
            "merged": True,
            "when_pipeline_succeeds": True,
            "message": "MR approved and scheduled for merge"
        }
