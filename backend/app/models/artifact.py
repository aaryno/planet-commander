"""Artifact model for extracted content from chats."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ArtifactType(str, enum.Enum):
    """Type of extracted artifact."""
    CODE_SNIPPET = "code_snippet"
    COMMAND = "command"
    CONFIG = "config"
    SQL_QUERY = "sql_query"
    ERROR_MESSAGE = "error_message"
    URL = "url"
    FILE_PATH = "file_path"
    DECISION = "decision"


class Artifact(Base):
    """
    Extracted artifacts from chat sessions.

    Artifacts are key pieces of information extracted from chats:
    - Code snippets
    - Commands run
    - Configuration changes
    - Important decisions
    - File paths referenced
    """
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    artifact_type: Mapped[ArtifactType] = mapped_column(nullable=False, index=True)

    # What chat this came from
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Link to context if available
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_contexts.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Artifact content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)  # For code snippets

    # Metadata
    message_index: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Which message in chat
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Associated file
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1-5 scale

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
