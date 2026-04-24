"""
Warnings API - Proactive Incident Response

Endpoints for viewing warning events, standby contexts, and escalation metrics.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.warning_event import WarningEvent, WarningSeverity
from app.models.warning_escalation_metrics import WarningEscalationMetrics
from app.models.work_context import WorkContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/warnings", tags=["warnings"])


# Response Models


class WarningEventResponse(BaseModel):
    """Warning event in API response."""

    id: str
    alert_name: str
    system: Optional[str] = None
    channel_name: str
    severity: str
    escalation_probability: float
    escalation_reason: Optional[str] = None
    escalated: bool
    auto_cleared: bool
    first_seen: datetime
    last_seen: datetime
    escalated_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    age_minutes: int
    has_standby_context: bool
    standby_context_id: Optional[str] = None
    incident_context_id: Optional[str] = None


class StandbyContextResponse(BaseModel):
    """Standby context in API response."""

    id: str
    title: str
    summary_text: Optional[str] = None
    health_status: str
    created_at: datetime
    artifact_count: int
    alert_definition_count: int


class EscalationMetricsResponse(BaseModel):
    """Escalation metrics in API response."""

    alert_name: str
    system: Optional[str] = None
    total_warnings: int
    escalated_count: int
    auto_cleared_count: int
    escalation_rate: Optional[float] = None
    avg_time_to_escalation_seconds: Optional[int] = None
    avg_time_to_clear_seconds: Optional[int] = None
    last_seen: Optional[datetime] = None
    last_escalated: Optional[datetime] = None


class WarningsSummaryResponse(BaseModel):
    """Summary statistics for warnings."""

    active_warnings: int
    high_risk_warnings: int  # >50% escalation probability
    escalated_today: int
    auto_cleared_today: int
    avg_escalation_probability: float


# API Endpoints


@router.get("/", response_model=List[WarningEventResponse])
async def list_warnings(
    active_only: bool = Query(True, description="Only show active warnings"),
    db: AsyncSession = Depends(get_db),
) -> List[WarningEventResponse]:
    """
    List warning events.

    Query params:
    - active_only: If true, only show warnings not escalated or cleared
    """
    query = select(WarningEvent)

    if active_only:
        query = query.where(
            and_(
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
            )
        )

    query = query.order_by(WarningEvent.first_seen.desc()).limit(100)

    result = await db.execute(query)
    warnings = result.scalars().all()

    return [
        WarningEventResponse(
            id=str(w.id),
            alert_name=w.alert_name,
            system=w.system,
            channel_name=w.channel_name,
            severity=w.severity.value,
            escalation_probability=w.escalation_probability,
            escalation_reason=w.escalation_reason,
            escalated=w.escalated,
            auto_cleared=w.auto_cleared,
            first_seen=w.first_seen,
            last_seen=w.last_seen,
            escalated_at=w.escalated_at,
            cleared_at=w.cleared_at,
            age_minutes=w.age_minutes,
            has_standby_context=w.standby_context_id is not None,
            standby_context_id=str(w.standby_context_id)
            if w.standby_context_id
            else None,
            incident_context_id=str(w.incident_context_id)
            if w.incident_context_id
            else None,
        )
        for w in warnings
    ]


@router.get("/summary", response_model=WarningsSummaryResponse)
async def get_warnings_summary(
    db: AsyncSession = Depends(get_db),
) -> WarningsSummaryResponse:
    """Get summary statistics for warnings."""

    # Active warnings
    active_result = await db.execute(
        select(func.count())
        .select_from(WarningEvent)
        .where(
            and_(
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
            )
        )
    )
    active_warnings = active_result.scalar() or 0

    # High-risk warnings (>50% probability)
    high_risk_result = await db.execute(
        select(func.count())
        .select_from(WarningEvent)
        .where(
            and_(
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
                WarningEvent.escalation_probability > 0.5,
            )
        )
    )
    high_risk_warnings = high_risk_result.scalar() or 0

    # Escalated today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    escalated_result = await db.execute(
        select(func.count())
        .select_from(WarningEvent)
        .where(
            and_(
                WarningEvent.escalated == True,
                WarningEvent.escalated_at >= today_start,
            )
        )
    )
    escalated_today = escalated_result.scalar() or 0

    # Auto-cleared today
    cleared_result = await db.execute(
        select(func.count())
        .select_from(WarningEvent)
        .where(
            and_(
                WarningEvent.auto_cleared == True,
                WarningEvent.cleared_at >= today_start,
            )
        )
    )
    auto_cleared_today = cleared_result.scalar() or 0

    # Average escalation probability of active warnings
    avg_prob_result = await db.execute(
        select(func.avg(WarningEvent.escalation_probability)).where(
            and_(
                WarningEvent.escalated == False,
                WarningEvent.auto_cleared == False,
            )
        )
    )
    avg_prob = avg_prob_result.scalar() or 0.0

    return WarningsSummaryResponse(
        active_warnings=active_warnings,
        high_risk_warnings=high_risk_warnings,
        escalated_today=escalated_today,
        auto_cleared_today=auto_cleared_today,
        avg_escalation_probability=float(avg_prob),
    )



# CRITICAL: Specific routes must come before /{warning_id}


class TrendDataPoint(BaseModel):
    """Single data point in trend chart."""

    date: str  # YYYY-MM-DD
    warnings: int
    escalated: int
    auto_cleared: int


class EscalationTrendsResponse(BaseModel):
    """Escalation trends over time."""

    trends: List[TrendDataPoint]
    period_days: int


@router.get("/trends", response_model=EscalationTrendsResponse)
async def get_escalation_trends(
    days: int = Query(7, description="Number of days to include"),
    db: AsyncSession = Depends(get_db),
) -> EscalationTrendsResponse:
    """
    Get escalation trends over time.

    Returns daily counts of warnings, escalations, and clears.
    """
    # Calculate date range
    end_date = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_date = end_date - timedelta(days=days - 1)

    # Query warnings grouped by date
    # For now, simplified: get all warnings and group in Python
    # TODO: Optimize with SQL GROUP BY
    result = await db.execute(
        select(WarningEvent).where(WarningEvent.first_seen >= start_date)
    )
    warnings = result.scalars().all()

    # Group by date
    trends_by_date = {}
    for warning in warnings:
        date_key = warning.first_seen.date().isoformat()
        if date_key not in trends_by_date:
            trends_by_date[date_key] = {"warnings": 0, "escalated": 0, "auto_cleared": 0}

        trends_by_date[date_key]["warnings"] += 1
        if warning.escalated:
            trends_by_date[date_key]["escalated"] += 1
        if warning.auto_cleared:
            trends_by_date[date_key]["auto_cleared"] += 1

    # Fill in missing dates with zeros
    trends = []
    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.date().isoformat()
        data = trends_by_date.get(
            date_key, {"warnings": 0, "escalated": 0, "auto_cleared": 0}
        )
        trends.append(
            TrendDataPoint(
                date=date_key,
                warnings=data["warnings"],
                escalated=data["escalated"],
                auto_cleared=data["auto_cleared"],
            )
        )
        current_date += timedelta(days=1)

    return EscalationTrendsResponse(trends=trends, period_days=days)

class PredictionAccuracyResponse(BaseModel):
    """Prediction accuracy metrics."""

    total_predictions: int
    correct_predictions: int
    accuracy: float  # 0.0 - 1.0
    false_positives: int  # Predicted high, didn't escalate
    false_negatives: int  # Predicted low, did escalate


@router.get("/accuracy", response_model=PredictionAccuracyResponse)
async def get_prediction_accuracy(
    days: int = Query(30, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> PredictionAccuracyResponse:
    """
    Get prediction accuracy over time period.

    Accuracy = (correct predictions) / (total resolved warnings)
    - Correct: Predicted high (>50%) and escalated, OR predicted low and cleared
    - False positive: Predicted high but cleared
    - False negative: Predicted low but escalated
    """
    # Calculate date range
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Get resolved warnings (escalated or cleared)
    result = await db.execute(
        select(WarningEvent).where(
            and_(
                WarningEvent.first_seen >= start_date,
                (WarningEvent.escalated == True) | (WarningEvent.auto_cleared == True),
            )
        )
    )
    warnings = result.scalars().all()

    if not warnings:
        return PredictionAccuracyResponse(
            total_predictions=0,
            correct_predictions=0,
            accuracy=0.0,
            false_positives=0,
            false_negatives=0,
        )

    # Calculate accuracy
    correct = 0
    false_positives = 0
    false_negatives = 0

    for warning in warnings:
        predicted_high = warning.escalation_probability > 0.5

        if warning.escalated:
            # Actually escalated
            if predicted_high:
                correct += 1  # Correctly predicted escalation
            else:
                false_negatives += 1  # Missed escalation
        elif warning.auto_cleared:
            # Actually cleared
            if not predicted_high:
                correct += 1  # Correctly predicted clear
            else:
                false_positives += 1  # False alarm

    total = len(warnings)
    accuracy = correct / total if total > 0 else 0.0

    return PredictionAccuracyResponse(
        total_predictions=total,
        correct_predictions=correct,
        accuracy=accuracy,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


# Feedback Endpoints


class PredictionFeedbackRequest(BaseModel):
    """Request to submit prediction accuracy feedback."""

    prediction_was_correct: bool
    actual_escalated: bool
    predicted_probability: float
    submitted_by: str | None = None
    comment: str | None = None


class ContextFeedbackRequest(BaseModel):
    """Request to submit context usefulness feedback."""

    context_was_useful: bool
    missing_information: str | None = None
    submitted_by: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    """Response for feedback submission."""

    id: str
    warning_event_id: str
    feedback_type: str
    submitted_at: str


class FeedbackStatsResponse(BaseModel):
    """Overall feedback statistics."""

    total_feedback: int
    prediction_accuracy: dict
    context_usefulness: dict


@router.get("/{warning_id}", response_model=WarningEventResponse)
async def get_warning(
    warning_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WarningEventResponse:
    """Get single warning event by ID."""

    result = await db.execute(
        select(WarningEvent).where(WarningEvent.id == warning_id)
    )
    warning = result.scalar_one_or_none()

    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")

    return WarningEventResponse(
        id=str(warning.id),
        alert_name=warning.alert_name,
        system=warning.system,
        channel_name=warning.channel_name,
        severity=warning.severity.value,
        escalation_probability=warning.escalation_probability,
        escalation_reason=warning.escalation_reason,
        escalated=warning.escalated,
        auto_cleared=warning.auto_cleared,
        first_seen=warning.first_seen,
        last_seen=warning.last_seen,
        escalated_at=warning.escalated_at,
        cleared_at=warning.cleared_at,
        age_minutes=warning.age_minutes,
        has_standby_context=warning.standby_context_id is not None,
        standby_context_id=str(warning.standby_context_id)
        if warning.standby_context_id
        else None,
        incident_context_id=str(warning.incident_context_id)
        if warning.incident_context_id
        else None,
    )


@router.get("/{warning_id}/standby", response_model=StandbyContextResponse)
async def get_standby_context(
    warning_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StandbyContextResponse:
    """Get standby context for a warning."""

    # Get warning
    warning_result = await db.execute(
        select(WarningEvent).where(WarningEvent.id == warning_id)
    )
    warning = warning_result.scalar_one_or_none()

    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")

    if not warning.standby_context_id:
        raise HTTPException(
            status_code=404, detail="Warning has no standby context"
        )

    # Get standby context
    context_result = await db.execute(
        select(WorkContext).where(WorkContext.id == warning.standby_context_id)
    )
    context = context_result.scalar_one_or_none()

    if not context:
        raise HTTPException(status_code=404, detail="Standby context not found")

    # TODO: Count linked artifacts and alert definitions via EntityLink
    # For now, return 0 (would need to join with entity_links table)

    return StandbyContextResponse(
        id=str(context.id),
        title=context.title,
        summary_text=context.summary_text,
        health_status=context.health_status.value,
        created_at=context.created_at,
        artifact_count=0,  # TODO: Count via EntityLink
        alert_definition_count=0,  # TODO: Count via EntityLink
    )


@router.get("/metrics/all", response_model=List[EscalationMetricsResponse])
async def list_escalation_metrics(
    db: AsyncSession = Depends(get_db),
) -> List[EscalationMetricsResponse]:
    """List escalation metrics for all alerts."""

    result = await db.execute(
        select(WarningEscalationMetrics).order_by(
            WarningEscalationMetrics.escalation_rate.desc()
        )
    )
    metrics = result.scalars().all()

    return [
        EscalationMetricsResponse(
            alert_name=m.alert_name,
            system=m.system,
            total_warnings=m.total_warnings,
            escalated_count=m.escalated_count,
            auto_cleared_count=m.auto_cleared_count,
            escalation_rate=m.escalation_rate,
            avg_time_to_escalation_seconds=m.avg_time_to_escalation_seconds,
            avg_time_to_clear_seconds=m.avg_time_to_clear_seconds,
            last_seen=m.last_seen,
            last_escalated=m.last_escalated,
        )
        for m in metrics
    ]


@router.get("/metrics/{alert_name}", response_model=EscalationMetricsResponse)
async def get_escalation_metrics(
    alert_name: str,
    db: AsyncSession = Depends(get_db),
) -> EscalationMetricsResponse:
    """Get escalation metrics for specific alert."""

    result = await db.execute(
        select(WarningEscalationMetrics).where(
            WarningEscalationMetrics.alert_name == alert_name
        )
    )
    metrics = result.scalar_one_or_none()

    if not metrics:
        raise HTTPException(
            status_code=404, detail="No metrics found for this alert"
        )

    return EscalationMetricsResponse(
        alert_name=metrics.alert_name,
        system=metrics.system,
        total_warnings=metrics.total_warnings,
        escalated_count=metrics.escalated_count,
        auto_cleared_count=metrics.auto_cleared_count,
        escalation_rate=metrics.escalation_rate,
        avg_time_to_escalation_seconds=metrics.avg_time_to_escalation_seconds,
        avg_time_to_clear_seconds=metrics.avg_time_to_clear_seconds,
        last_seen=metrics.last_seen,
        last_escalated=metrics.last_escalated,
    )


# Metrics Visualization Endpoints




@router.post("/{warning_id}/feedback/prediction", response_model=FeedbackResponse)
async def submit_prediction_feedback(
    warning_id: uuid.UUID,
    request: PredictionFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Submit feedback on prediction accuracy.

    Args:
        warning_id: Warning event ID
        request: Feedback data
        db: Database session

    Returns:
        Created feedback instance
    """
    from app.services.feedback_service import FeedbackService

    service = FeedbackService(db)

    try:
        feedback = await service.submit_prediction_feedback(
            warning_id=warning_id,
            prediction_was_correct=request.prediction_was_correct,
            actual_escalated=request.actual_escalated,
            predicted_probability=request.predicted_probability,
            submitted_by=request.submitted_by,
            comment=request.comment,
        )

        await db.commit()

        return FeedbackResponse(
            id=str(feedback.id),
            warning_event_id=str(feedback.warning_event_id),
            feedback_type=feedback.feedback_type.value,
            submitted_at=feedback.submitted_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{warning_id}/feedback/context", response_model=FeedbackResponse)
async def submit_context_feedback(
    warning_id: uuid.UUID,
    request: ContextFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Submit feedback on context usefulness.

    Args:
        warning_id: Warning event ID
        request: Feedback data
        db: Database session

    Returns:
        Created feedback instance
    """
    from app.services.feedback_service import FeedbackService

    service = FeedbackService(db)

    try:
        feedback = await service.submit_context_usefulness_feedback(
            warning_id=warning_id,
            context_was_useful=request.context_was_useful,
            missing_information=request.missing_information,
            submitted_by=request.submitted_by,
            comment=request.comment,
        )

        await db.commit()

        return FeedbackResponse(
            id=str(feedback.id),
            warning_event_id=str(feedback.warning_event_id),
            feedback_type=feedback.feedback_type.value,
            submitted_at=feedback.submitted_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(
    db: AsyncSession = Depends(get_db),
) -> FeedbackStatsResponse:
    """Get overall feedback statistics.

    Returns:
        Feedback statistics including accuracy and usefulness rates
    """
    from app.services.feedback_service import FeedbackService

    service = FeedbackService(db)
    stats = await service.get_feedback_stats()

    return FeedbackStatsResponse(**stats)


# ============================================================================
# Learning System Endpoints
# ============================================================================


class AlertPerformanceResponse(BaseModel):
    """Alert performance metrics for learning."""

    alert_name: str
    system: Optional[str] = None
    total_warnings: int
    escalated_count: int
    escalation_rate: float
    avg_predicted_probability: float
    feedback_count: int
    correct_predictions: int
    false_negatives: int
    false_positives: int
    accuracy: Optional[float] = None
    improvement_potential: float


class AccuracyTrendResponse(BaseModel):
    """Accuracy trend over time."""

    date: str
    window_start: str
    window_end: str
    total_feedback: int
    correct_predictions: int
    accuracy: float


class AlertTuningResponse(BaseModel):
    """Alert tuning suggestions."""

    alert_name: str
    system: Optional[str] = None
    has_feedback: bool
    total_feedback: Optional[int] = None
    accuracy: Optional[float] = None
    false_positives: Optional[int] = None
    false_negatives: Optional[int] = None
    actual_escalation_rate: Optional[float] = None
    avg_predicted_probability: Optional[float] = None
    adjustment: Optional[str] = None
    suggested_probability: Optional[float] = None
    reason: Optional[str] = None
    confidence: Optional[str] = None
    suggestion: Optional[str] = None


class LearningSummaryResponse(BaseModel):
    """Learning system summary."""

    total_feedback: int
    total_alerts_analyzed: int
    alerts_with_feedback: int
    well_tuned_alerts: int
    high_potential_alerts: int
    accuracy_improvement: Optional[float] = None
    current_accuracy: Optional[float] = None
    trend_windows: int


@router.get("/learning/alerts", response_model=List[AlertPerformanceResponse])
async def get_alert_performance(
    days: int = Query(30, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> List[AlertPerformanceResponse]:
    """Get performance metrics for each alert type.

    Returns alerts sorted by improvement potential (highest first).

    Args:
        days: Number of days to analyze (default: 30)

    Returns:
        List of alert performance metrics
    """
    from app.services.learning_service import LearningService

    service = LearningService(db)
    alerts = await service.get_alert_performance(days=days)

    return [AlertPerformanceResponse(**alert) for alert in alerts]


@router.get("/learning/accuracy-trend", response_model=List[AccuracyTrendResponse])
async def get_accuracy_trend(
    days: int = Query(30, description="Total days to analyze"),
    window_days: int = Query(7, description="Rolling window size in days"),
    db: AsyncSession = Depends(get_db),
) -> List[AccuracyTrendResponse]:
    """Get prediction accuracy trend over time.

    Args:
        days: Total number of days to analyze (default: 30)
        window_days: Size of rolling window (default: 7)

    Returns:
        List of accuracy measurements by time window
    """
    from app.services.learning_service import LearningService

    service = LearningService(db)
    trend = await service.get_accuracy_trend(days=days, window_days=window_days)

    return [AccuracyTrendResponse(**window) for window in trend]


@router.get("/learning/tune/{alert_name}", response_model=AlertTuningResponse)
async def get_alert_tuning(
    alert_name: str,
    system: Optional[str] = Query(None, description="Optional system filter"),
    db: AsyncSession = Depends(get_db),
) -> AlertTuningResponse:
    """Get tuning suggestions for specific alert.

    Args:
        alert_name: Name of alert to analyze
        system: Optional system filter

    Returns:
        Tuning suggestions with analysis
    """
    from app.services.learning_service import LearningService

    service = LearningService(db)
    suggestion = await service.suggest_alert_tuning(alert_name, system=system)

    return AlertTuningResponse(**suggestion)


@router.get("/learning/summary", response_model=LearningSummaryResponse)
async def get_learning_summary(
    db: AsyncSession = Depends(get_db),
) -> LearningSummaryResponse:
    """Get overall learning system summary.

    Returns:
        Summary of learning system status and improvements
    """
    from app.services.learning_service import LearningService

    service = LearningService(db)
    summary = await service.get_learning_summary()

    return LearningSummaryResponse(**summary)
