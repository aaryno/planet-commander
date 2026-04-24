"""Summary model for AI-generated summaries."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SummaryType(str, enum.Enum):
    """Type of summary."""
    CHAT = "chat"
    CONTEXT_OVERVIEW = "context_overview"
    ARTIFACT = "artifact"


class Summary(Base):
    """
    AI-generated summaries for chats, contexts, and artifacts.

    Summaries are generated using Claude API and cached for reuse.
    """
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    summary_type: Mapped[SummaryType] = mapped_column(nullable=False, index=True)

    # What this summary is for
    context_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_contexts.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Summary content (multiple lengths)
    one_liner: Mapped[str | None] = mapped_column(String(500), nullable=True)
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # 2-3 sentences
    detailed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full analysis

    # Metadata
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True, default=0)
    input_size: Mapped[int | None] = mapped_column(nullable=True)  # Size of input data

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
