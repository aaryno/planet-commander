"""Learning service for warning prediction model tuning.

Uses collected feedback to improve prediction accuracy over time.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_, case, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WarningEvent, WarningFeedback, FeedbackType

logger = logging.getLogger(__name__)


class LearningService:
    """Manage prediction model learning and tuning."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_alert_performance(
        self, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get performance metrics for each alert type.

        Args:
            days: Number of days to analyze

        Returns:
            List of alert performance metrics sorted by improvement potential
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Query warning events with feedback
        result = await self.db.execute(
            select(
                WarningEvent.alert_name,
                WarningEvent.system,
                func.count(WarningEvent.id).label("total_warnings"),
                func.count(
                    case(
                        (WarningEvent.escalated == True, 1),
                        else_=None,
                    )
                ).label("escalated_count"),
                func.avg(WarningEvent.escalation_probability).label(
                    "avg_predicted_probability"
                ),
                func.count(WarningFeedback.id).label("feedback_count"),
                func.count(
                    case(
                        (WarningFeedback.prediction_was_correct == True, 1),
                        else_=None,
                    )
                ).label("correct_predictions"),
                func.count(
                    case(
                        (
                            and_(
                                WarningFeedback.prediction_was_correct == False,
                                WarningFeedback.actual_escalated == True,
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("false_negatives"),
                func.count(
                    case(
                        (
                            and_(
                                WarningFeedback.prediction_was_correct == False,
                                WarningFeedback.actual_escalated == False,
                            ),
                            1,
                        ),
                        else_=None,
                    )
                ).label("false_positives"),
            )
            .outerjoin(
                WarningFeedback,
                and_(
                    WarningFeedback.warning_event_id == WarningEvent.id,
                    WarningFeedback.feedback_type == "prediction_accuracy",
                ),
            )
            .where(WarningEvent.first_seen >= cutoff)
            .group_by(WarningEvent.alert_name, WarningEvent.system)
        )

        alerts = []
        for row in result.all():
            # Calculate metrics
            feedback_count = row.feedback_count or 0
            correct = row.correct_predictions or 0
            false_negatives = row.false_negatives or 0
            false_positives = row.false_positives or 0

            # Calculate accuracy (only if we have feedback)
            accuracy = (correct / feedback_count) if feedback_count > 0 else None

            # Calculate escalation rate
            escalated = row.escalated_count or 0
            total = row.total_warnings or 0
            escalation_rate = (escalated / total) if total > 0 else 0

            # Calculate improvement potential
            # Higher potential = more feedback + lower accuracy + high false negative/positive rate
            if feedback_count > 0 and accuracy is not None:
                error_rate = 1.0 - accuracy
                improvement_potential = (
                    error_rate * feedback_count
                )  # Weight by sample size
            else:
                improvement_potential = 0.0

            alerts.append(
                {
                    "alert_name": row.alert_name,
                    "system": row.system,
                    "total_warnings": total,
                    "escalated_count": escalated,
                    "escalation_rate": escalation_rate,
                    "avg_predicted_probability": float(row.avg_predicted_probability or 0),
                    "feedback_count": feedback_count,
                    "correct_predictions": correct,
                    "false_negatives": false_negatives,
                    "false_positives": false_positives,
                    "accuracy": accuracy,
                    "improvement_potential": improvement_potential,
                }
            )

        # Sort by improvement potential (highest first)
        alerts.sort(key=lambda x: x["improvement_potential"], reverse=True)

        return alerts

    async def get_accuracy_trend(
        self, days: int = 30, window_days: int = 7
    ) -> list[dict[str, Any]]:
        """Get prediction accuracy trend over time.

        Args:
            days: Total number of days to analyze
            window_days: Size of rolling window for accuracy calculation

        Returns:
            List of accuracy measurements by time window
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all feedback with timestamps
        result = await self.db.execute(
            select(
                WarningFeedback.submitted_at,
                WarningFeedback.prediction_was_correct,
            )
            .where(
                and_(
                    WarningFeedback.feedback_type == "prediction_accuracy",
                    WarningFeedback.submitted_at >= cutoff,
                )
            )
            .order_by(WarningFeedback.submitted_at)
        )

        feedback_items = list(result.all())

        if not feedback_items:
            return []

        # Calculate rolling accuracy
        trend = []
        now = datetime.now(timezone.utc)

        # Create windows from oldest to newest
        start_date = cutoff
        while start_date < now:
            window_start = start_date
            window_end = start_date + timedelta(days=window_days)

            # Count feedback in this window
            window_feedback = [
                f
                for f in feedback_items
                if window_start <= f.submitted_at < window_end
            ]

            if len(window_feedback) >= 3:  # Need minimum sample size
                correct = sum(1 for f in window_feedback if f.prediction_was_correct)
                total = len(window_feedback)
                accuracy = correct / total if total > 0 else 0

                trend.append(
                    {
                        "date": window_start.isoformat(),
                        "window_start": window_start.isoformat(),
                        "window_end": window_end.isoformat(),
                        "total_feedback": total,
                        "correct_predictions": correct,
                        "accuracy": accuracy,
                    }
                )

            start_date += timedelta(days=window_days)

        return trend

    async def suggest_alert_tuning(
        self, alert_name: str, system: str | None = None
    ) -> dict[str, Any]:
        """Analyze feedback for specific alert and suggest probability adjustments.

        Args:
            alert_name: Alert name to analyze
            system: Optional system filter

        Returns:
            Tuning suggestions with analysis
        """
        # Get all feedback for this alert
        query = select(
            WarningEvent.escalation_probability,
            WarningEvent.escalated,
            WarningFeedback.prediction_was_correct,
            WarningFeedback.actual_escalated,
            WarningFeedback.predicted_probability,
        ).join(
            WarningFeedback,
            and_(
                WarningFeedback.warning_event_id == WarningEvent.id,
                WarningFeedback.feedback_type == "prediction_accuracy",
            ),
        ).where(
            WarningEvent.alert_name == alert_name
        )

        if system:
            query = query.where(WarningEvent.system == system)

        result = await self.db.execute(query)
        feedback_items = list(result.all())

        if not feedback_items:
            return {
                "alert_name": alert_name,
                "system": system,
                "has_feedback": False,
                "suggestion": "No feedback data available yet",
            }

        # Analyze feedback patterns
        total = len(feedback_items)
        correct = sum(1 for f in feedback_items if f.prediction_was_correct)
        false_positives = sum(
            1
            for f in feedback_items
            if not f.prediction_was_correct and not f.actual_escalated
        )
        false_negatives = sum(
            1
            for f in feedback_items
            if not f.prediction_was_correct and f.actual_escalated
        )

        accuracy = correct / total if total > 0 else 0

        # Calculate actual escalation rate
        actual_escalations = sum(1 for f in feedback_items if f.actual_escalated)
        actual_rate = actual_escalations / total if total > 0 else 0

        # Calculate average predicted probability
        avg_predicted = (
            sum(f.predicted_probability for f in feedback_items) / total
            if total > 0
            else 0
        )

        # Determine adjustment
        if false_positives > false_negatives:
            # Over-predicting escalations - reduce probability
            adjustment = "decrease"
            suggested_probability = max(0.1, avg_predicted - 0.15)
            reason = f"High false positive rate ({false_positives}/{total}). Alert is less likely to escalate than predicted."
        elif false_negatives > false_positives:
            # Under-predicting escalations - increase probability
            adjustment = "increase"
            suggested_probability = min(0.95, avg_predicted + 0.15)
            reason = f"High false negative rate ({false_negatives}/{total}). Alert is more likely to escalate than predicted."
        else:
            # Balanced - fine-tune to actual rate
            adjustment = "fine_tune"
            suggested_probability = actual_rate
            reason = f"Balanced prediction. Fine-tune to match actual escalation rate ({actual_rate:.1%})."

        return {
            "alert_name": alert_name,
            "system": system,
            "has_feedback": True,
            "total_feedback": total,
            "accuracy": accuracy,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "actual_escalation_rate": actual_rate,
            "avg_predicted_probability": avg_predicted,
            "adjustment": adjustment,
            "suggested_probability": suggested_probability,
            "reason": reason,
            "confidence": "high" if total >= 10 else "medium" if total >= 5 else "low",
        }

    async def get_learning_summary(self) -> dict[str, Any]:
        """Get overall learning system summary.

        Returns:
            Summary of learning system status and improvements
        """
        # Get overall accuracy trend
        trend = await self.get_accuracy_trend(days=30, window_days=7)

        # Calculate improvement if we have enough data
        improvement = None
        if len(trend) >= 2:
            first_accuracy = trend[0]["accuracy"]
            last_accuracy = trend[-1]["accuracy"]
            improvement = last_accuracy - first_accuracy

        # Get alert performance
        alerts = await self.get_alert_performance(days=30)

        # Count alerts by tuning status
        high_potential = [a for a in alerts if a["improvement_potential"] > 0.5]
        well_tuned = [
            a
            for a in alerts
            if a["accuracy"] is not None and a["accuracy"] >= 0.8
        ]

        # Get total feedback count
        feedback_result = await self.db.execute(
            select(func.count(WarningFeedback.id)).where(
                WarningFeedback.feedback_type == "prediction_accuracy"
            )
        )
        total_feedback = feedback_result.scalar() or 0

        return {
            "total_feedback": total_feedback,
            "total_alerts_analyzed": len(alerts),
            "alerts_with_feedback": len([a for a in alerts if a["feedback_count"] > 0]),
            "well_tuned_alerts": len(well_tuned),
            "high_potential_alerts": len(high_potential),
            "accuracy_improvement": improvement,
            "current_accuracy": trend[-1]["accuracy"] if trend else None,
            "trend_windows": len(trend),
        }
