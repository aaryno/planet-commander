"""Entity Link model for Planet Commander Phase 1."""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, Float, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LinkType(str, enum.Enum):
    """Type of relationship between entities."""
    IMPLEMENTS = "implements"
    DISCUSSED_IN = "discussed_in"
    REFERENCES = "references"
    MENTIONED_IN = "mentioned_in"              # Generic mention (e.g., URL in chat)
    WORKED_IN = "worked_in"
    CHECKED_OUT_AS = "checked_out_as"
    SUMMARIZED_BY = "summarized_by"
    RECOMMENDS = "recommends"
    SPAWNED = "spawned"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    BLOCKED_BY = "blocked_by"
    FOLLOW_UP_TO = "follow_up_to"
    SUPERSEDES = "supersedes"
    SAME_CONTEXT_AS = "same_context_as"
    # PagerDuty enrichment
    REFERENCES_PAGERDUTY = "references_pagerduty"
    DISCUSSED_IN_PAGERDUTY = "discussed_in_pagerduty"
    TRIGGERED_BY = "triggered_by"        # Alert → PD incident
    ESCALATED_TO = "escalated_to"        # JIRA → PD incident
    INCIDENT_FOR = "incident_for"        # PD incident → JIRA ticket
    # Investigation artifact enrichment
    REFERENCES_ARTIFACT = "references_artifact"
    MENTIONED_IN_ARTIFACT = "mentioned_in_artifact"
    # Grafana alert enrichment
    TRIGGERED_ALERT = "triggered_alert"
    DISCUSSED_ALERT = "discussed_alert"
    REFERENCES_ALERT = "references_alert"
    # Project documentation enrichment
    PROJECT_CONTEXT = "project_context"
    DOCUMENTED_IN = "documented_in"
    REFERENCES_PROJECT = "references_project"
    # Google Drive enrichment
    DOCUMENTED_IN_GDRIVE = "documented_in_gdrive"
    POSTMORTEM_FOR = "postmortem_for"
    RFD_FOR = "rfd_for"
    MEETING_NOTES_FOR = "meeting_notes_for"
    # GitLab MR enrichment
    IMPLEMENTED_BY = "implemented_by"        # JIRA → MR (inverse of IMPLEMENTS)
    REVIEWED_IN = "reviewed_in"              # Branch → MR
    MERGED_TO_BRANCH = "merged_to_branch"    # MR → Branch
    # Slack thread enrichment
    DISCUSSED_IN_SLACK = "discussed_in_slack"  # JIRA/PD/MR → Slack thread
    REFERENCES_SLACK = "references_slack"      # Any entity → Slack thread
    ESCALATED_FROM = "escalated_from"          # Incident → originating Slack thread
    # Product/dashboard enrichment
    MONITORS_DASHBOARD = "monitors_dashboard"  # Entity → Grafana dashboard (with product context)
    # Audit system
    AUDITED_BY = "audited_by"          # Entity → AuditRun
    HAS_FINDING = "has_finding"        # AuditRun → AuditFinding (redundant with FK, enables graph traversal)
    FINDING_FOR = "finding_for"        # AuditFinding → Entity (reverse)


class LinkSourceType(str, enum.Enum):
    """Source of the link."""
    MANUAL = "manual"
    INFERRED = "inferred"
    IMPORTED = "imported"
    AGENT = "agent"
    URL_EXTRACTED = "url_extracted"           # Extracted from URL in message


class LinkStatus(str, enum.Enum):
    """Status of the link."""
    CONFIRMED = "confirmed"
    SUGGESTED = "suggested"
    REJECTED = "rejected"
    STALE = "stale"


class EntityLink(Base):
    """
    Generic relationship graph between all core entities.

    Provides flexible many-to-many relationships between contexts, issues,
    chats, branches, worktrees, PRs, summaries, and audits.

    Entity types: 'context', 'jira_issue', 'chat', 'branch', 'worktree',
    'pr', 'summary', 'audit', 'agent_run', 'pagerduty_incident'
    """
    __tablename__ = "entity_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    from_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_id: Mapped[str] = mapped_column(String(200), nullable=False)

    to_type: Mapped[str] = mapped_column(String(50), nullable=False)
    to_id: Mapped[str] = mapped_column(String(200), nullable=False)

    link_type: Mapped[LinkType] = mapped_column(
        SAEnum(LinkType, values_callable=lambda e: [m.value for m in e],
               name="linktype", create_type=False),
        nullable=False,
    )
    source_type: Mapped[LinkSourceType] = mapped_column(
        SAEnum(LinkSourceType, values_callable=lambda e: [m.value for m in e],
               name="linksourcetype", create_type=False),
        nullable=False,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Context data (e.g., URL that triggered extraction, job_id, etc.)
    link_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[LinkStatus] = mapped_column(
        SAEnum(LinkStatus, values_callable=lambda e: [m.value for m in e],
               name="linkstatus", create_type=False),
        nullable=False, default=LinkStatus.CONFIRMED,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Note: We use string IDs instead of foreign keys because entities can be
    # of different types (UUID for most, but potentially strings for external IDs).
    # Polymorphic relationships are handled in the ContextResolverService.
