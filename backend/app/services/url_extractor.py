"""URL extraction service for chat messages."""
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent

logger = logging.getLogger(__name__)


class URLExtractor:
    """Extract URLs from text and chat messages."""

    # URL regex pattern - matches http(s):// URLs
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def extract_urls(text: str) -> list[str]:
        """Extract all URLs from text using regex.

        Args:
            text: Text content to scan

        Returns:
            List of URLs found
        """
        if not text:
            return []

        urls = URLExtractor.URL_PATTERN.findall(text)
        # Clean up URLs (remove trailing punctuation that's not part of URL)
        cleaned = []
        for url in urls:
            # Remove trailing punctuation
            url = url.rstrip('.,;:!?)')
            # Remove trailing brackets
            if url.endswith(']'):
                url = url.rstrip(']')
            cleaned.append(url)

        return cleaned

    async def extract_from_chat(
        self,
        agent_id: uuid.UUID,
        limit_messages: int | None = None
    ) -> list[dict[str, Any]]:
        """Extract all URLs from a chat's messages.

        Args:
            agent_id: Agent/chat UUID
            limit_messages: Optional limit on messages to scan (default: all)

        Returns:
            List of dicts: [{"url": str, "message_index": int, "timestamp": datetime}, ...]
        """
        # Get agent
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            return []

        # Load messages from conversation.jsonl
        messages = await self._load_chat_messages(agent, limit_messages)

        urls_found = []

        for idx, message in enumerate(messages):
            # Extract timestamp
            timestamp = message.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    timestamp = None

            # Extract text from message
            text = self._extract_message_text(message)
            if not text:
                continue

            # Extract URLs from text
            urls = self.extract_urls(text)

            for url in urls:
                urls_found.append({
                    "url": url,
                    "message_index": idx,
                    "timestamp": timestamp,
                    "message_type": message.get("type", "unknown"),
                    "sender": message.get("sender", "unknown")
                })

        logger.info(f"Extracted {len(urls_found)} URLs from {len(messages)} messages in chat {agent_id}")
        return urls_found

    async def _load_chat_messages(
        self,
        agent: Agent,
        limit: int | None = None
    ) -> list[dict]:
        """Load chat messages from conversation.jsonl file.

        Args:
            agent: Agent model
            limit: Optional limit on messages to load

        Returns:
            List of message dicts
        """
        # Try multiple possible paths:
        # 1. Dashboard sessions: ~/.claude/sessions/{session_id}/conversation.jsonl
        # 2. VSCode sessions: ~/.claude/projects/{project}/{session_id}.jsonl

        possible_paths = []

        # Path 1: Dashboard format
        session_path = Path.home() / ".claude" / "sessions" / str(agent.id)
        conv_file = session_path / "conversation.jsonl"
        possible_paths.append(conv_file)

        # Path 2: VSCode format - search for {session_id}.jsonl
        claude_projects = Path.home() / ".claude" / "projects"
        if claude_projects.exists():
            # Search all project directories
            for project_dir in claude_projects.iterdir():
                if project_dir.is_dir():
                    vscode_conv_file = project_dir / f"{agent.id}.jsonl"
                    possible_paths.append(vscode_conv_file)

        # Find first existing path
        conv_file = None
        for path in possible_paths:
            if path.exists():
                conv_file = path
                logger.debug(f"Found conversation file: {conv_file}")
                break

        if not conv_file:
            logger.debug(f"Conversation file not found for agent {agent.id}")
            logger.debug(f"Tried paths: {[str(p) for p in possible_paths[:3]]}")
            return []

        messages = []

        try:
            import json
            with open(conv_file, 'r') as f:
                for line_num, line in enumerate(f):
                    if limit and line_num >= limit:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        message = json.loads(line)
                        messages.append(message)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse message at line {line_num}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Failed to load conversation file {conv_file}: {e}")
            return []

        return messages

    def _extract_message_text(self, message: dict) -> str:
        """Extract text content from a message.

        Handles different message formats:
        - Direct text field
        - Content blocks with text/thinking
        - Tool results

        Args:
            message: Message dict

        Returns:
            Extracted text or empty string
        """
        # Direct text field
        if "text" in message:
            return message["text"]

        # Content blocks (Claude messages)
        if "content" in message:
            content = message["content"]

            # String content
            if isinstance(content, str):
                return content

            # List of content blocks
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        # Text block
                        if block.get("type") == "text" and "text" in block:
                            text_parts.append(block["text"])
                        # Thinking block
                        elif block.get("type") == "thinking" and "thinking" in block:
                            text_parts.append(block["thinking"])
                        # Tool use block (extract input)
                        elif block.get("type") == "tool_use" and "input" in block:
                            # Recursively extract text from input
                            input_text = str(block["input"])
                            text_parts.append(input_text)
                return "\n".join(text_parts)

        # Tool result
        if "tool_result" in message and isinstance(message["tool_result"], dict):
            result = message["tool_result"]
            if "content" in result:
                # Recursively extract
                return self._extract_message_text({"content": result["content"]})

        return ""
