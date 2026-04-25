import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True
    )
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    icon: Mapped[str | None] = mapped_column(String(50))

    jira_project_keys: Mapped[list] = mapped_column(JSONB, default=list)
    jira_default_filters: Mapped[dict] = mapped_column(JSONB, default=dict)

    repositories: Mapped[list] = mapped_column(JSONB, default=list)

    grafana_dashboards: Mapped[list] = mapped_column(JSONB, default=list)
    pagerduty_service_ids: Mapped[list] = mapped_column(JSONB, default=list)

    slack_channels: Mapped[list] = mapped_column(JSONB, default=list)

    deployment_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    links: Mapped[list] = mapped_column(JSONB, default=list)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
