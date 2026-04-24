"""Chat summarization service using Claude API."""
import logging
import json
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import Anthropic

from app.models.agent import Agent
from app.models.summary import Summary, SummaryType

logger = logging.getLogger(__name__)


class ChatSummaryService:
    """Service for generating AI summaries of chat sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = Anthropic()  # Uses ANTHROPIC_API_KEY from environment

    async def summarize_chat(self, chat_id: str, force_regenerate: bool = False) -> Dict[str, str]:
        """
        Generate a summary of a chat session.

        Args:
            chat_id: Agent ID (chat session)
            force_regenerate: Regenerate even if summary exists

        Returns:
            dict: Summary with one_liner, short, and detailed versions
        """
        # Get agent/chat
        result = await self.db.execute(
            select(Agent).where(Agent.id == chat_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Chat not found: {chat_id}")

        # Check for existing summary
        if not force_regenerate:
            existing = await self._get_existing_summary(chat_id)
            if existing:
                logger.info(f"Using existing summary for chat {chat_id}")
                return {
                    "one_liner": existing.one_liner or "",
                    "short": existing.short_summary or "",
                    "detailed": existing.detailed_summary or "",
                    "cached": True
                }

        # Load chat history
        chat_history = await self._load_chat_history(agent)

        if not chat_history:
            logger.warning(f"No chat history found for {chat_id}")
            return {
                "one_liner": "No chat history available",
                "short": "No messages found in this chat session.",
                "detailed": "This chat session has no message history to summarize.",
                "cached": False
            }

        # Generate summary with Claude
        summary_data = await self._generate_summary(agent, chat_history)

        # Save to database
        await self._save_summary(chat_id, summary_data)

        return {
            "one_liner": summary_data["one_liner"],
            "short": summary_data["short"],
            "detailed": summary_data["detailed"],
            "cached": False
        }

    async def _get_existing_summary(self, chat_id: str) -> Summary | None:
        """Get existing summary for a chat if it exists."""
        result = await self.db.execute(
            select(Summary)
            .where(
                Summary.chat_id == chat_id,
                Summary.summary_type == SummaryType.CHAT
            )
            .order_by(Summary.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def _load_chat_history(self, agent: Agent) -> str:
        """Load chat history from agent session files."""
        # For now, use a simplified approach - in production, read from session files
        # This is a placeholder that would integrate with the actual chat history storage
        messages = []

        # Simplified: Use agent metadata
        if agent.first_prompt:
            messages.append(f"User: {agent.first_prompt}")

        # TODO: Load actual chat messages from session directory
        # For MVP, we'll use available metadata
        metadata_summary = [
            f"Project: {agent.project}",
            f"Status: {agent.status}",
            f"Messages: {agent.message_count}",
            f"Total tokens: {agent.total_tokens}",
        ]

        if agent.jira_key:
            metadata_summary.append(f"JIRA: {agent.jira_key}")

        if agent.git_branch:
            metadata_summary.append(f"Branch: {agent.git_branch}")

        if agent.worktree_path:
            metadata_summary.append(f"Worktree: {agent.worktree_path}")

        return "\n".join(messages + metadata_summary)

    async def _generate_summary(self, agent: Agent, chat_history: str) -> Dict[str, str]:
        """Generate summary using Claude API."""
        prompt = f"""Please analyze this agent chat session and provide three levels of summary:

Chat Session: {agent.title or agent.id}
Project: {agent.project}
JIRA: {agent.jira_key or "None"}

Chat History:
{chat_history}

Please provide:
1. ONE_LINER: A single sentence (max 100 chars) describing what this chat accomplished
2. SHORT: 2-3 sentences summarizing the main activities and outcomes
3. DETAILED: A comprehensive paragraph covering:
   - What problem was being solved
   - Key actions taken
   - Important decisions or findings
   - Current status and next steps

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
            summary_json = json.loads(content)

            return {
                "one_liner": summary_json.get("one_liner", "")[:500],  # Truncate to DB limit
                "short": summary_json.get("short", ""),
                "detailed": summary_json.get("detailed", ""),
                "model": response.model,
                "tokens": response.usage.total_tokens if hasattr(response, "usage") else 0
            }

        except Exception as e:
            logger.error(f"Failed to generate summary with Claude: {e}", exc_info=True)
            # Fallback to simple summary
            return {
                "one_liner": f"{agent.project} chat session",
                "short": f"Chat session for {agent.jira_key or 'project work'}. {agent.message_count} messages exchanged.",
                "detailed": f"Agent session in {agent.project} project. Status: {agent.status}. Total tokens: {agent.total_tokens}.",
                "model": "fallback",
                "tokens": 0
            }

    async def _save_summary(self, chat_id: str, summary_data: Dict[str, str]) -> None:
        """Save summary to database."""
        # Check if summary already exists
        existing = await self._get_existing_summary(chat_id)

        if existing:
            # Update existing
            existing.one_liner = summary_data["one_liner"]
            existing.short_summary = summary_data["short"]
            existing.detailed_summary = summary_data["detailed"]
            existing.model_used = summary_data.get("model")
            existing.total_tokens = summary_data.get("tokens", 0)
        else:
            # Create new
            summary = Summary(
                summary_type=SummaryType.CHAT,
                chat_id=chat_id,
                one_liner=summary_data["one_liner"],
                short_summary=summary_data["short"],
                detailed_summary=summary_data["detailed"],
                model_used=summary_data.get("model"),
                total_tokens=summary_data.get("tokens", 0)
            )
            self.db.add(summary)

        await self.db.flush()
        logger.info(f"Saved summary for chat {chat_id}")

    async def get_chat_summary(self, chat_id: str) -> Dict[str, str] | None:
        """Get existing summary for a chat without generating new one."""
        existing = await self._get_existing_summary(chat_id)

        if not existing:
            return None

        return {
            "one_liner": existing.one_liner or "",
            "short": existing.short_summary or "",
            "detailed": existing.detailed_summary or "",
            "created_at": existing.created_at.isoformat(),
            "model": existing.model_used
        }
