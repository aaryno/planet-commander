"""Context overview generation service."""
import logging
import json
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import Anthropic

from app.models.work_context import WorkContext
from app.models.summary import Summary, SummaryType
from app.models.entity_link import EntityLink, LinkStatus
from app.models.jira_issue import JiraIssue
from app.models.agent import Agent
from app.models.git_branch import GitBranch

logger = logging.getLogger(__name__)


class ContextOverviewService:
    """Service for generating comprehensive context overviews."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = Anthropic()

    async def generate_overview(self, context_id: str, force_regenerate: bool = False) -> Dict[str, str]:
        """
        Generate comprehensive overview of a work context.

        Args:
            context_id: WorkContext ID
            force_regenerate: Regenerate even if summary exists

        Returns:
            dict: Overview with one_liner, short, and detailed versions
        """
        # Get context
        result = await self.db.execute(
            select(WorkContext).where(WorkContext.id == context_id)
        )
        context = result.scalar_one_or_none()

        if not context:
            raise ValueError(f"Context not found: {context_id}")

        # Check for existing summary
        if not force_regenerate:
            existing = await self._get_existing_overview(context_id)
            if existing:
                logger.info(f"Using existing overview for context {context_id}")
                return {
                    "one_liner": existing.one_liner or "",
                    "short": existing.short_summary or "",
                    "detailed": existing.detailed_summary or "",
                    "cached": True
                }

        # Gather context data
        context_data = await self._gather_context_data(context)

        # Generate overview with Claude
        overview_data = await self._generate_overview(context, context_data)

        # Save to database
        await self._save_overview(context_id, overview_data)

        return {
            "one_liner": overview_data["one_liner"],
            "short": overview_data["short"],
            "detailed": overview_data["detailed"],
            "cached": False
        }

    async def _get_existing_overview(self, context_id: str) -> Summary | None:
        """Get existing overview for a context if it exists."""
        result = await self.db.execute(
            select(Summary)
            .where(
                Summary.context_id == context_id,
                Summary.summary_type == SummaryType.CONTEXT_OVERVIEW
            )
            .order_by(Summary.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def _gather_context_data(self, context: WorkContext) -> Dict:
        """Gather all related data for a context."""
        data = {
            "title": context.title,
            "status": context.status.value,
            "health": context.health_status.value,
            "origin": context.origin_type.value,
            "jira_issues": [],
            "chats": [],
            "branches": [],
            "worktrees": []
        }

        # Get linked entities
        links_result = await self.db.execute(
            select(EntityLink)
            .where(
                EntityLink.from_id == str(context.id),
                EntityLink.status == LinkStatus.CONFIRMED
            )
        )
        links = links_result.scalars().all()

        # Fetch JIRA issues
        for link in links:
            if link.to_type == "jira_issue":
                jira_result = await self.db.execute(
                    select(JiraIssue).where(JiraIssue.id == link.to_id)
                )
                jira = jira_result.scalar_one_or_none()
                if jira:
                    data["jira_issues"].append({
                        "key": jira.external_key,
                        "summary": jira.summary,
                        "status": jira.status
                    })

            elif link.to_type == "chat":
                chat_result = await self.db.execute(
                    select(Agent).where(Agent.id == link.to_id)
                )
                chat = chat_result.scalar_one_or_none()
                if chat:
                    data["chats"].append({
                        "title": chat.title,
                        "messages": chat.message_count,
                        "status": chat.status.value
                    })

            elif link.to_type == "branch":
                branch_result = await self.db.execute(
                    select(GitBranch).where(GitBranch.id == link.to_id)
                )
                branch = branch_result.scalar_one_or_none()
                if branch:
                    data["branches"].append({
                        "name": branch.branch_name,
                        "status": branch.status.value
                    })

        return data

    async def _generate_overview(self, context: WorkContext, context_data: Dict) -> Dict[str, str]:
        """Generate overview using Claude API."""
        prompt = f"""Please analyze this work context and provide a comprehensive overview:

Title: {context_data['title']}
Status: {context_data['status']}
Health: {context_data['health']}
Origin: {context_data['origin']}

JIRA Issues: {len(context_data['jira_issues'])}
{json.dumps(context_data['jira_issues'], indent=2)}

Chats: {len(context_data['chats'])}
{json.dumps(context_data['chats'], indent=2)}

Branches: {len(context_data['branches'])}
{json.dumps(context_data['branches'], indent=2)}

Please provide:
1. ONE_LINER: A single sentence (max 100 chars) describing what this context is about
2. SHORT: 2-3 sentences summarizing the work being done and current state
3. DETAILED: A comprehensive overview covering:
   - Problem/goal being addressed
   - Related JIRA tickets and their status
   - Development work (branches, chats)
   - Current health and completeness
   - Recommended next steps

Format your response as JSON:
{{
  "one_liner": "...",
  "short": "...",
  "detailed": "..."
}}
"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            overview_json = json.loads(content)

            return {
                "one_liner": overview_json.get("one_liner", "")[:500],
                "short": overview_json.get("short", ""),
                "detailed": overview_json.get("detailed", ""),
                "model": response.model,
                "tokens": response.usage.total_tokens if hasattr(response, "usage") else 0
            }

        except Exception as e:
            logger.error(f"Failed to generate overview with Claude: {e}", exc_info=True)
            # Fallback to simple overview
            return {
                "one_liner": context_data["title"][:100],
                "short": f"Work context with {len(context_data['jira_issues'])} JIRA issues, {len(context_data['chats'])} chats, and {len(context_data['branches'])} branches. Status: {context_data['status']}.",
                "detailed": f"Context: {context_data['title']}. Health: {context_data['health']}. Contains {len(context_data['jira_issues'])} linked JIRA issues and {len(context_data['chats'])} agent sessions.",
                "model": "fallback",
                "tokens": 0
            }

    async def _save_overview(self, context_id: str, overview_data: Dict[str, str]) -> None:
        """Save overview to database."""
        # Check if overview already exists
        existing = await self._get_existing_overview(context_id)

        if existing:
            # Update existing
            existing.one_liner = overview_data["one_liner"]
            existing.short_summary = overview_data["short"]
            existing.detailed_summary = overview_data["detailed"]
            existing.model_used = overview_data.get("model")
            existing.total_tokens = overview_data.get("tokens", 0)
        else:
            # Create new
            summary = Summary(
                summary_type=SummaryType.CONTEXT_OVERVIEW,
                context_id=context_id,
                one_liner=overview_data["one_liner"],
                short_summary=overview_data["short"],
                detailed_summary=overview_data["detailed"],
                model_used=overview_data.get("model"),
                total_tokens=overview_data.get("tokens", 0)
            )
            self.db.add(summary)

        await self.db.flush()
        logger.info(f"Saved overview for context {context_id}")
