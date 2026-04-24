"""Page layout model - stores grid layout configurations per page."""

from datetime import datetime, timezone
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PageLayout(Base):
    """Store grid layout configuration for a page."""

    __tablename__ = "page_layouts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    page: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g., "wx", "dashboard"
    layout: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Grid layout configuration
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
