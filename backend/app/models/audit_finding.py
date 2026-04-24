"""Audit Finding model for Planet Commander audit system."""
import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as SAEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FindingSeverity(str, enum.Enum):
    """Severity level of a finding."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingCategory(str, enum.Enum):
    """Category of a finding."""
    CODE_QUALITY = "code-quality"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    ADVERSARIAL = "adversarial"
    READINESS = "readiness"
    CHANGE_RISK = "change-risk"
    STALENESS = "staleness"
    SYSTEM = "system"
    CONTEXT = "context"


class FindingStatus(str, enum.Enum):
    """Status of a finding."""
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    AUTO_FIXED = "auto_fixed"


class AuditFinding(Base):
    """
    Individual audit finding.

    Represents a single finding from an audit run, with code, category,
    severity, actionability flags, and status tracking.
    """
    __tablename__ = "audit_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Finding identity
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum("code-quality", "security", "architecture", "performance",
               "adversarial", "readiness", "change-risk", "staleness",
               "system", "context",
               name="findingcategory", create_type=False),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        SAEnum("error", "warning", "info",
               name="findingseverity", create_type=False),
        nullable=False,
    )
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, server_default="high")

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Actionability
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    auto_fixable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        SAEnum("open", "resolved", "deferred", "rejected", "auto_fixed",
               name="findingstatus", create_type=False),
        nullable=False,
        server_default="open",
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Linkage
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Source metadata
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditFinding(code='{self.code}', severity='{self.severity}', status='{self.status}')>"
