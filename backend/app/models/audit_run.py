"""Audit Run model for Planet Commander audit system."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as SAEnum, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditVerdict(str, enum.Enum):
    """Verdict of an audit run."""
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class AuditSource(str, enum.Enum):
    """Source type of an audit."""
    DETERMINISTIC = "deterministic"
    AGENT_REVIEW = "agent_review"
    HYBRID = "hybrid"


class AuditRun(Base):
    """
    Audit execution record.

    Represents a single audit run against a target entity (JIRA issue,
    GitLab MR, or work context). Stores verdict, confidence, aggregate
    metrics, and optional dimension/risk scores.
    """
    __tablename__ = "audit_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    # What was audited
    audit_family: Mapped[str] = mapped_column(String(100), nullable=False)
    audit_tier: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    source: Mapped[str] = mapped_column(
        SAEnum("deterministic", "agent_review", "hybrid",
               name="auditsource", create_type=False),
        nullable=False,
    )

    # Target entity
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # Verdict
    verdict: Mapped[str] = mapped_column(
        SAEnum("approved", "changes_required", "blocked", "unverified", "unknown",
               name="auditverdict", create_type=False),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")

    # Aggregate metrics
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    blocking_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    auto_fixable_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Dimension scores (for readiness audits)
    dimension_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Risk score (for change-risk audits)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Execution metadata
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")

    # Raw output (for debugging)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditRun(family='{self.audit_family}', target='{self.target_type}:{self.target_id}', verdict='{self.verdict}')>"
