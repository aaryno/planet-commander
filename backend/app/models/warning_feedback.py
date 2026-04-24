"""Warning feedback model for learning system."""
import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackType(str, enum.Enum):
    """Type of feedback on a warning."""

    PREDICTION_ACCURACY = "prediction_accuracy"
    CONTEXT_USEFULNESS = "context_usefulness"
    ESCALATION_TIMING = "escalation_timing"  # Future


class WarningFeedback(Base):
    """
    User feedback on warning predictions and mitigation contexts.

    Enables learning system to improve prediction accuracy over time.
    """

    __tablename__ = "warning_feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Link to warning event
    warning_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warning_events.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Feedback type
    feedback_type: Mapped[FeedbackType] = mapped_column(
        PG_ENUM(
            "prediction_accuracy",
            "context_usefulness",
            "escalation_timing",
            name="feedbacktype",
            create_type=False
        ),
        nullable=False
    )

    # Prediction accuracy feedback
    prediction_was_correct: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    actual_escalated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    predicted_probability: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Context usefulness feedback
    context_was_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    missing_information: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Escalation timing feedback (future)
    escalation_timing_accurate: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    actual_escalation_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # User info
    submitted_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Optional comment
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
