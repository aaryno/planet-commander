"""PR/MR automation service."""
import logging
import subprocess
from typing import Dict
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.agent import Agent
from app.models.work_context import WorkContext
from app.models.entity_link import EntityLink, LinkStatus
from app.models.git_branch import GitBranch
from app.services.chat_summary import ChatSummaryService

logger = logging.getLogger(__name__)


class PRAutomationService:
    """Service for automatic PR/MR creation from chats."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pr_from_chat(
        self,
        chat_id: str,
        target_branch: str = "main",
        auto_push: bool = False
    ) -> Dict[str, any]:
        """
        Create a merge request from a chat session.

        Args:
            chat_id: Agent ID (chat session)
            target_branch: Target branch for MR (default: main)
            auto_push: Automatically push branch (default: False)

        Returns:
            dict: PR creation results
        """
        # Get agent/chat
        result = await self.db.execute(
            select(Agent).where(Agent.id == chat_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Chat not found: {chat_id}")

        # Check if chat has a branch
        if not agent.git_branch:
            raise ValueError(f"Chat {chat_id} has no associated git branch")

        if not agent.worktree_path:
            raise ValueError(f"Chat {chat_id} has no associated worktree")

        # Get branch info
        branch_result = await self.db.execute(
            select(GitBranch)
            .where(
                GitBranch.branch_name == agent.git_branch,
                GitBranch.repo_path.like(f"%{Path(agent.worktree_path).parent}%")
            )
        )
        branch = branch_result.scalar_one_or_none()

        if not branch:
            raise ValueError(f"Branch {agent.git_branch} not found in database")

        # Generate MR title and description from chat
        mr_title, mr_description = await self._generate_mr_content(agent)

        # Check if branch has commits
        has_commits = await self._check_branch_has_commits(agent.worktree_path, agent.git_branch)

        if not has_commits:
            return {
                "status": "error",
                "message": "Branch has no commits to create MR from",
                "chat_id": chat_id,
                "branch": agent.git_branch
            }

        # Push branch if requested
        if auto_push:
            push_result = await self._push_branch(agent.worktree_path, agent.git_branch)
            if not push_result["success"]:
                return {
                    "status": "error",
                    "message": f"Failed to push branch: {push_result['error']}",
                    "chat_id": chat_id,
                    "branch": agent.git_branch
                }

        # Create MR using glab
        mr_result = await self._create_mr_with_glab(
            agent.worktree_path,
            mr_title,
            mr_description,
            target_branch
        )

        return {
            "status": "success" if mr_result["success"] else "error",
            "message": mr_result.get("message", ""),
            "mr_url": mr_result.get("url"),
            "mr_iid": mr_result.get("iid"),
            "chat_id": chat_id,
            "branch": agent.git_branch,
            "target_branch": target_branch
        }

    async def _generate_mr_content(self, agent: Agent) -> tuple[str, str]:
        """Generate MR title and description from chat."""
        # Get chat summary if available
        summary_service = ChatSummaryService(self.db)
        summary = await summary_service.get_chat_summary(str(agent.id))

        # Generate title
        if agent.jira_key:
            title = f"{agent.jira_key}: {agent.title[:50]}"
        else:
            title = agent.title[:70] if len(agent.title) <= 70 else agent.title[:67] + "..."

        # Generate description
        description_parts = ["## Summary\n"]

        if summary:
            # Use AI-generated summary
            description_parts.append(summary.get("short", agent.title))
        else:
            # Fallback to basic info
            description_parts.append(agent.title)

        description_parts.append("\n\n## Context\n")
        description_parts.append(f"- **Project**: {agent.project}")

        if agent.jira_key:
            description_parts.append(f"- **JIRA**: {agent.jira_key}")

        description_parts.append(f"- **Branch**: {agent.git_branch}")
        description_parts.append(f"- **Messages**: {agent.message_count}")

        description_parts.append("\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)")

        description = "\n".join(description_parts)

        return title, description

    async def _check_branch_has_commits(self, worktree_path: str, branch_name: str) -> bool:
        """Check if branch has commits ahead of target."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/main..{branch_name}"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                count = int(result.stdout.strip())
                return count > 0
            else:
                logger.warning(f"Failed to count commits: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error checking commits: {e}")
            return False

    async def _push_branch(self, worktree_path: str, branch_name: str) -> Dict[str, any]:
        """Push branch to remote."""
        try:
            # Push with -u flag to set upstream
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Push timed out after 60 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_mr_with_glab(
        self,
        worktree_path: str,
        title: str,
        description: str,
        target_branch: str
    ) -> Dict[str, any]:
        """Create MR using glab CLI."""
        try:
            # Create MR with glab
            result = subprocess.run(
                [
                    "glab", "mr", "create",
                    "--title", title,
                    "--description", description,
                    "--target-branch", target_branch,
                    "--fill"  # Auto-fill from commits
                ],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse MR URL from output
                output = result.stdout
                url_match = None
                iid_match = None

                # Try to extract URL and IID from output
                for line in output.split("\n"):
                    if "hello.planet.com" in line:
                        url_match = line.strip()
                    if "!" in line and line.strip().startswith("!"):
                        try:
                            iid_match = int(line.strip().strip("!"))
                        except:
                            pass

                return {
                    "success": True,
                    "url": url_match,
                    "iid": iid_match,
                    "message": "MR created successfully"
                }
            else:
                return {
                    "success": False,
                    "message": result.stderr,
                    "error": result.stderr
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "MR creation timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_pr_from_context(
        self,
        context_id: str,
        target_branch: str = "main"
    ) -> Dict[str, any]:
        """
        Create MR from a work context (uses primary chat if available).

        Args:
            context_id: WorkContext ID
            target_branch: Target branch for MR

        Returns:
            dict: PR creation results
        """
        # Get context
        result = await self.db.execute(
            select(WorkContext).where(WorkContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if not context:
            raise ValueError(f"Context not found: {context_id}")

        # Find primary chat or any chat with branch
        if context.primary_chat_id:
            chat_id = str(context.primary_chat_id)
        else:
            # Find any linked chat with a branch
            links_result = await self.db.execute(
                select(EntityLink)
                .where(
                    EntityLink.from_id == str(context.id),
                    EntityLink.to_type == "chat",
                    EntityLink.status == LinkStatus.CONFIRMED
                )
            )
            links = links_result.scalars().all()

            chat_id = None
            for link in links:
                agent_result = await self.db.execute(
                    select(Agent).where(
                        Agent.id == link.to_id,
                        Agent.git_branch.isnot(None)
                    )
                )
                agent = agent_result.scalar_one_or_none()
                if agent:
                    chat_id = str(agent.id)
                    break

            if not chat_id:
                raise ValueError(f"No chat with branch found for context {context_id}")

        # Create PR from chat
        return await self.create_pr_from_chat(chat_id, target_branch=target_branch)
