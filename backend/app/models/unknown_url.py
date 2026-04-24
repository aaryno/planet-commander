"""Unknown URL model - catalog of unrecognized URLs."""
import datetime
import uuid

from sqlalchemy import DateTime, String, Text, Boolean, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UnknownURL(Base):
    """Catalog of URLs we don't know how to handle.

    Tracks unrecognized URLs for human review and pattern promotion.
    """
    __tablename__ = "unknown_urls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # URL info
    url: Mapped[str] = mapped_column(String(2000), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # Context - where was it first seen
    first_seen_in_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Occurrence tracking
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Review status
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Pattern promotion
    promoted_to_pattern: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_pattern_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Ignore flag (for spam/one-offs)
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
