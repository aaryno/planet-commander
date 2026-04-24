"""Artifact extraction service using Claude API."""
import logging
import json
import re
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from anthropic import Anthropic

from app.models.agent import Agent
from app.models.artifact import Artifact, ArtifactType

logger = logging.getLogger(__name__)


class ArtifactExtractionService:
    """Service for extracting artifacts from chat sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = Anthropic()

    async def extract_artifacts(self, chat_id: str, force_reextract: bool = False) -> Dict[str, any]:
        """
        Extract artifacts from a chat session.

        Args:
            chat_id: Agent ID (chat session)
            force_reextract: Re-extract even if artifacts exist

        Returns:
            dict: Extraction results
        """
        # Get agent/chat
        result = await self.db.execute(
            select(Agent).where(Agent.id == chat_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise ValueError(f"Chat not found: {chat_id}")

        # Check for existing artifacts
        if not force_reextract:
            existing_count = await self._count_existing_artifacts(chat_id)
            if existing_count > 0:
                logger.info(f"Chat {chat_id} already has {existing_count} artifacts")
                return {
                    "chat_id": chat_id,
                    "extracted": 0,
                    "total": existing_count,
                    "cached": True
                }

        # Load chat history
        chat_history = await self._load_chat_history(agent)

        if not chat_history:
            logger.warning(f"No chat history found for {chat_id}")
            return {
                "chat_id": chat_id,
                "extracted": 0,
                "total": 0,
                "cached": False
            }

        # Extract artifacts with Claude
        artifacts_data = await self._extract_with_claude(agent, chat_history)

        # Save to database
        saved_count = await self._save_artifacts(chat_id, artifacts_data)

        return {
            "chat_id": chat_id,
            "extracted": saved_count,
            "total": saved_count,
            "cached": False
        }

    async def _count_existing_artifacts(self, chat_id: str) -> int:
        """Count existing artifacts for a chat."""
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count(Artifact.id))
            .where(Artifact.chat_id == chat_id)
        )
        return result.scalar() or 0

    async def _load_chat_history(self, agent: Agent) -> str:
        """Load chat history from agent session files."""
        # Simplified placeholder - in production, read from session files
        messages = []

        if agent.first_prompt:
            messages.append(f"User: {agent.first_prompt}")

        # TODO: Load actual chat messages from session directory
        metadata = [
            f"Project: {agent.project}",
            f"Messages: {agent.message_count}",
        ]

        if agent.jira_key:
            metadata.append(f"JIRA: {agent.jira_key}")

        if agent.git_branch:
            metadata.append(f"Branch: {agent.git_branch}")

        return "\n".join(messages + metadata)

    async def _extract_with_claude(self, agent: Agent, chat_history: str) -> List[Dict]:
        """Extract artifacts using Claude API."""
        prompt = f"""Please analyze this chat session and extract key artifacts.

Chat: {agent.title or agent.id}
Project: {agent.project}

History:
{chat_history}

Please identify and extract:
1. CODE_SNIPPET: Any code blocks (with language)
2. COMMAND: Shell commands that were run
3. CONFIG: Configuration changes or settings
4. SQL_QUERY: SQL queries
5. ERROR_MESSAGE: Important error messages
6. URL: Important URLs referenced
7. FILE_PATH: File paths that were modified or discussed
8. DECISION: Important technical decisions made

For each artifact, provide:
- type: One of the types above
- title: Brief description (max 100 chars)
- content: The actual content
- language: Programming language (for code snippets)
- importance: 1-5 scale (5=critical, 1=minor)

Format your response as JSON array:
[
  {{
    "type": "CODE_SNIPPET",
    "title": "Authentication middleware",
    "content": "def authenticate(request): ...",
    "language": "python",
    "importance": 4
  }},
  ...
]

Only include artifacts that are actually present in the chat. If none found, return empty array.
"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            # Extract JSON from response (might have markdown wrapper)
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                artifacts_json = json.loads(json_match.group(0))
                return artifacts_json
            else:
                logger.warning("No artifacts found in Claude response")
                return []

        except Exception as e:
            logger.error(f"Failed to extract artifacts with Claude: {e}", exc_info=True)
            # Fallback: Try simple pattern matching
            return self._extract_with_patterns(chat_history)

    def _extract_with_patterns(self, chat_history: str) -> List[Dict]:
        """Fallback: Extract artifacts using simple patterns."""
        artifacts = []

        # Extract code blocks
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', chat_history, re.DOTALL)
        for lang, code in code_blocks[:5]:  # Limit to 5
            artifacts.append({
                "type": "CODE_SNIPPET",
                "title": f"{lang or 'code'} snippet",
                "content": code.strip(),
                "language": lang or "text",
                "importance": 3
            })

        # Extract commands (lines starting with $)
        commands = re.findall(r'^\$\s+(.+)$', chat_history, re.MULTILINE)
        for cmd in commands[:5]:  # Limit to 5
            artifacts.append({
                "type": "COMMAND",
                "title": f"Command: {cmd[:50]}",
                "content": cmd,
                "language": "bash",
                "importance": 3
            })

        # Extract URLs
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', chat_history)
        for url in list(set(urls))[:5]:  # Unique, limit to 5
            artifacts.append({
                "type": "URL",
                "title": f"URL: {url[:50]}",
                "content": url,
                "language": None,
                "importance": 2
            })

        return artifacts

    async def _save_artifacts(self, chat_id: str, artifacts_data: List[Dict]) -> int:
        """Save extracted artifacts to database."""
        if not artifacts_data:
            return 0

        saved_count = 0

        for artifact_data in artifacts_data:
            try:
                # Map type string to enum
                artifact_type = ArtifactType(artifact_data.get("type", "").lower())

                artifact = Artifact(
                    artifact_type=artifact_type,
                    chat_id=chat_id,
                    title=artifact_data.get("title", "Untitled")[:500],
                    content=artifact_data.get("content", ""),
                    language=artifact_data.get("language"),
                    importance=artifact_data.get("importance", 3)
                )

                self.db.add(artifact)
                saved_count += 1

            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid artifact: {e}")
                continue

        await self.db.flush()
        logger.info(f"Saved {saved_count} artifacts for chat {chat_id}")

        return saved_count

    async def get_artifacts(self, chat_id: str, artifact_type: ArtifactType | None = None) -> List[Dict]:
        """Get artifacts for a chat, optionally filtered by type."""
        query = select(Artifact).where(Artifact.chat_id == chat_id)

        if artifact_type:
            query = query.where(Artifact.artifact_type == artifact_type)

        query = query.order_by(Artifact.importance.desc(), Artifact.created_at.desc())

        result = await self.db.execute(query)
        artifacts = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "type": a.artifact_type.value,
                "title": a.title,
                "content": a.content,
                "language": a.language,
                "importance": a.importance,
                "created_at": a.created_at.isoformat()
            }
            for a in artifacts
        ]

    async def get_context_artifacts(self, context_id: str) -> List[Dict]:
        """Get all artifacts from all chats in a context."""
        query = (
            select(Artifact)
            .where(Artifact.context_id == context_id)
            .order_by(Artifact.importance.desc(), Artifact.created_at.desc())
        )

        result = await self.db.execute(query)
        artifacts = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "type": a.artifact_type.value,
                "title": a.title,
                "content": a.content,
                "language": a.language,
                "importance": a.importance,
                "chat_id": str(a.chat_id),
                "created_at": a.created_at.isoformat()
            }
            for a in artifacts
        ]
