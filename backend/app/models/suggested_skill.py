"""Suggested Skill model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SuggestedSkill(Base):
    """Skill suggestion for a work context."""

    __tablename__ = "suggested_skills"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Link to work context
    work_context_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey('work_contexts.id', ondelete='CASCADE'),
        nullable=True
    )

    # Suggested skill
    skill_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey('skill_registry.id', ondelete='CASCADE'),
        nullable=True
    )
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Confidence and reasoning
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_reasons = Column(JSONB)  # [{"type": "keyword", "value": "task failure", "weight": 0.3}]

    # User interaction
    user_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking
    suggested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Computed properties

    @property
    def match_reason_list(self) -> List[dict]:
        """Safe accessor for match reasons."""
        return self.match_reasons if self.match_reasons else []

    @property
    def is_actioned(self) -> bool:
        """Check if user has acted on this suggestion."""
        return self.user_action is not None

    @property
    def confidence_percent(self) -> int:
        """Confidence as percentage (0-100)."""
        return int(self.confidence_score * 100)

    @property
    def confidence_tier(self) -> str:
        """Confidence tier: high, medium, low."""
        if self.confidence_score >= 0.7:
            return "high"
        elif self.confidence_score >= 0.5:
            return "medium"
        else:
            return "low"
