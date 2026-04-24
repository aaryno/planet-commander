"""GitLab Merge Request model."""

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GitLabMergeRequest(Base):
    """GitLab merge request from tracked repositories."""

    __tablename__ = "gitlab_merge_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # GitLab identity
    external_mr_id: Mapped[int] = mapped_column(Integer, nullable=False)
    repository: Mapped[str] = mapped_column(String(200), nullable=False)

    # MR metadata
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # Branches
    source_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)

    # People
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Status
    approval_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ci_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)

    # Extracted metadata
    jira_keys: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    # Diff statistics (populated by MR sync enrichment)
    additions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deletions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    changed_file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    changed_files: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    merged_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    @property
    def is_approved(self) -> bool:
        """Check if MR is approved."""
        return self.approval_status == "approved"

    @property
    def is_ci_passing(self) -> bool:
        """Check if CI is passing."""
        return self.ci_status == "passed"

    @property
    def is_merged(self) -> bool:
        """Check if MR is merged."""
        return self.state == "merged"

    @property
    def is_open(self) -> bool:
        """Check if MR is still open."""
        return self.state == "opened"

    @property
    def is_stale(self) -> bool:
        """Check if MR is stale (merged/closed >30 days ago)."""
        if self.state == "opened":
            return False

        end_time = self.merged_at or self.closed_at
        if not end_time:
            return False

        days_ago = (datetime.datetime.now(datetime.timezone.utc) - end_time).days
        return days_ago > 30

    @property
    def age_days(self) -> int:
        """Days since MR was created."""
        return (datetime.datetime.now(datetime.timezone.utc) - self.created_at).days

    @property
    def has_jira_keys(self) -> bool:
        """Check if MR has JIRA keys."""
        return bool(self.jira_keys)

    @property
    def short_repository(self) -> str:
        """Get short repository name (last part)."""
        # "wx/wx" → "wx", "product/g4-wk/g4" → "g4"
        parts = self.repository.split("/")
        return parts[-1]

    @property
    def project_name(self) -> str:
        """Infer project name from repository."""
        repo_lower = self.repository.lower()
        if "wx" in repo_lower:
            return "wx"
        elif "g4" in repo_lower:
            return "g4"
        elif "jobs" in repo_lower:
            return "jobs"
        elif "temporal" in repo_lower:
            return "temporal"
        elif "eso" in repo_lower:
            return "eso"
        return "unknown"

    def __repr__(self) -> str:
        return f"<GitLabMergeRequest(repo='{self.repository}', mr={self.external_mr_id}, title='{self.title[:50]}')>"
