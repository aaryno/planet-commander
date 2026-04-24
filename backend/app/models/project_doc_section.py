"""Project documentation section model."""

import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProjectDocSection(Base):
    """Individual section from project documentation."""

    __tablename__ = "project_doc_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Reference to parent project doc
    project_doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_docs.id", ondelete="CASCADE"), nullable=False)

    # Section identity
    section_name: Mapped[str] = mapped_column(String(200), nullable=False)
    heading_level: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    project_doc: Mapped["ProjectDoc"] = relationship("ProjectDoc", back_populates="doc_sections")

    def __repr__(self) -> str:
        return f"<ProjectDocSection(section_name='{self.section_name}', heading_level={self.heading_level}, order={self.order_index})>"
