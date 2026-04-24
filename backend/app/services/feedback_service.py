"""Feedback service for warning prediction learning system."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WarningEvent, WarningFeedback, FeedbackType

logger = logging.getLogger(__name__)


class FeedbackService:
    """Manage feedback on warning predictions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_prediction_feedback(
        self,
        warning_id: uuid.UUID,
        prediction_was_correct: bool,
        actual_escalated: bool,
        predicted_probability: float,
        submitted_by: str | None = None,
        comment: str | None = None,
    ) -> WarningFeedback:
        """Submit feedback on prediction accuracy.

        Args:
            warning_id: Warning event ID
            prediction_was_correct: Was the prediction correct?
            actual_escalated: Did the warning actually escalate?
            predicted_probability: What probability was predicted?
            submitted_by: User who submitted feedback
            comment: Optional comment

        Returns:
            Created WarningFeedback instance
        """
        # Check if warning exists
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning:
            raise ValueError(f"Warning {warning_id} not found")

        # Check if feedback already exists
        existing_result = await self.db.execute(
            select(WarningFeedback).where(
                (WarningFeedback.warning_event_id == warning_id)
                & (WarningFeedback.feedback_type == FeedbackType.PREDICTION_ACCURACY)
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update existing feedback
            existing.prediction_was_correct = prediction_was_correct
            existing.actual_escalated = actual_escalated
            existing.predicted_probability = predicted_probability
            existing.submitted_by = submitted_by
            existing.submitted_at = datetime.now(timezone.utc)
            if comment:
                existing.comment = comment

            await self.db.flush()
            logger.info(f"Updated prediction feedback for warning {warning_id}")
            return existing

        # Create new feedback
        feedback = WarningFeedback(
            warning_event_id=warning_id,
            feedback_type=FeedbackType.PREDICTION_ACCURACY,
            prediction_was_correct=prediction_was_correct,
            actual_escalated=actual_escalated,
            predicted_probability=predicted_probability,
            submitted_by=submitted_by,
            comment=comment,
        )

        self.db.add(feedback)
        await self.db.flush()

        logger.info(f"Created prediction feedback for warning {warning_id}")
        return feedback

    async def submit_context_usefulness_feedback(
        self,
        warning_id: uuid.UUID,
        context_was_useful: bool,
        missing_information: str | None = None,
        submitted_by: str | None = None,
        comment: str | None = None,
    ) -> WarningFeedback:
        """Submit feedback on context usefulness.

        Args:
            warning_id: Warning event ID
            context_was_useful: Was the pre-assembled context useful?
            missing_information: What information was missing?
            submitted_by: User who submitted feedback
            comment: Optional comment

        Returns:
            Created WarningFeedback instance
        """
        # Check if warning exists
        result = await self.db.execute(
            select(WarningEvent).where(WarningEvent.id == warning_id)
        )
        warning = result.scalar_one_or_none()

        if not warning:
            raise ValueError(f"Warning {warning_id} not found")

        # Check if feedback already exists
        existing_result = await self.db.execute(
            select(WarningFeedback).where(
                (WarningFeedback.warning_event_id == warning_id)
                & (WarningFeedback.feedback_type == FeedbackType.CONTEXT_USEFULNESS)
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update existing feedback
            existing.context_was_useful = context_was_useful
            existing.missing_information = missing_information
            existing.submitted_by = submitted_by
            existing.submitted_at = datetime.now(timezone.utc)
            if comment:
                existing.comment = comment

            await self.db.flush()
            logger.info(f"Updated context feedback for warning {warning_id}")
            return existing

        # Create new feedback
        feedback = WarningFeedback(
            warning_event_id=warning_id,
            feedback_type=FeedbackType.CONTEXT_USEFULNESS,
            context_was_useful=context_was_useful,
            missing_information=missing_information,
            submitted_by=submitted_by,
            comment=comment,
        )

        self.db.add(feedback)
        await self.db.flush()

        logger.info(f"Created context feedback for warning {warning_id}")
        return feedback

    async def get_feedback(self, warning_id: uuid.UUID) -> list[WarningFeedback]:
        """Get all feedback for a warning.

        Args:
            warning_id: Warning event ID

        Returns:
            List of WarningFeedback instances
        """
        result = await self.db.execute(
            select(WarningFeedback)
            .where(WarningFeedback.warning_event_id == warning_id)
            .order_by(WarningFeedback.submitted_at.desc())
        )

        return list(result.scalars().all())

    async def get_feedback_stats(self) -> dict[str, Any]:
        """Get overall feedback statistics.

        Returns:
            Dictionary with feedback stats
        """
        # Total feedback count
        total_result = await self.db.execute(select(func.count(WarningFeedback.id)))
        total_feedback = total_result.scalar() or 0

        # Prediction accuracy stats
        pred_result = await self.db.execute(
            select(func.count(WarningFeedback.id)).where(
                WarningFeedback.feedback_type == FeedbackType.PREDICTION_ACCURACY
            )
        )
        prediction_feedback_count = pred_result.scalar() or 0

        # Correct predictions
        correct_result = await self.db.execute(
            select(func.count(WarningFeedback.id)).where(
                (WarningFeedback.feedback_type == FeedbackType.PREDICTION_ACCURACY)
                & (WarningFeedback.prediction_was_correct == True)
            )
        )
        correct_predictions = correct_result.scalar() or 0

        # Context usefulness stats
        context_result = await self.db.execute(
            select(func.count(WarningFeedback.id)).where(
                WarningFeedback.feedback_type == FeedbackType.CONTEXT_USEFULNESS
            )
        )
        context_feedback_count = context_result.scalar() or 0

        # Useful contexts
        useful_result = await self.db.execute(
            select(func.count(WarningFeedback.id)).where(
                (WarningFeedback.feedback_type == FeedbackType.CONTEXT_USEFULNESS)
                & (WarningFeedback.context_was_useful == True)
            )
        )
        useful_contexts = useful_result.scalar() or 0

        return {
            "total_feedback": total_feedback,
            "prediction_accuracy": {
                "total": prediction_feedback_count,
                "correct": correct_predictions,
                "accuracy": (
                    correct_predictions / prediction_feedback_count
                    if prediction_feedback_count > 0
                    else 0.0
                ),
            },
            "context_usefulness": {
                "total": context_feedback_count,
                "useful": useful_contexts,
                "usefulness_rate": (
                    useful_contexts / context_feedback_count
                    if context_feedback_count > 0
                    else 0.0
                ),
            },
        }

    async def get_recent_feedback(self, limit: int = 10) -> list[WarningFeedback]:
        """Get recent feedback submissions.

        Args:
            limit: Maximum number of feedback items to return

        Returns:
            List of recent WarningFeedback instances
        """
        result = await self.db.execute(
            select(WarningFeedback)
            .order_by(WarningFeedback.submitted_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())
