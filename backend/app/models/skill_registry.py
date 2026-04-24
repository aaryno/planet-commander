"""Skill Registry model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SkillRegistry(Base):
    """Registry of available skills with trigger conditions."""

    __tablename__ = "skill_registry"

    # Primary key
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Skill metadata
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    skill_path: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trigger conditions (from SKILL.md)
    trigger_keywords = Column(JSONB)  # ["task failure", "lease expiration"]
    trigger_labels = Column(JSONB)    # ["wx", "workexchange"]
    trigger_systems = Column(JSONB)   # ["wxctl", "kubectl", "Grafana"]
    trigger_patterns = Column(JSONB)  # [{"type": "regex", "pattern": "..."}]

    # Metadata
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    complexity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Usage stats
    invocation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_invoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tracking
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Computed properties

    @property
    def trigger_keyword_list(self) -> List[str]:
        """Safe accessor for trigger keywords."""
        return self.trigger_keywords if self.trigger_keywords else []

    @property
    def trigger_label_list(self) -> List[str]:
        """Safe accessor for trigger labels."""
        return self.trigger_labels if self.trigger_labels else []

    @property
    def trigger_system_list(self) -> List[str]:
        """Safe accessor for trigger systems."""
        return self.trigger_systems if self.trigger_systems else []

    @property
    def trigger_pattern_list(self) -> List[dict]:
        """Safe accessor for trigger patterns."""
        return self.trigger_patterns if self.trigger_patterns else []

    @property
    def has_triggers(self) -> bool:
        """Check if skill has any trigger conditions defined."""
        return any([
            self.trigger_keywords and len(self.trigger_keywords) > 0,
            self.trigger_labels and len(self.trigger_labels) > 0,
            self.trigger_systems and len(self.trigger_systems) > 0,
            self.trigger_patterns and len(self.trigger_patterns) > 0,
        ])
