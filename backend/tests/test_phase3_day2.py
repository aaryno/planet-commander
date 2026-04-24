"""
Tests for Phase 3 Day 2: Escalation Prediction & Standby Context Creation

Tests:
1. EscalationMetricsService - Calculate historical escalation rates
2. StandbyContextService - Pre-assemble mitigation contexts
3. EscalationDetector - Detect warning → critical escalations
4. WarningMonitor integration - Auto-create standby contexts
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.models.warning_event import WarningEvent, WarningSeverity
from app.models.warning_escalation_metrics import WarningEscalationMetrics
from app.models.work_context import WorkContext, ContextStatus, HealthStatus
from app.models.investigation_artifact import InvestigationArtifact
from app.models.grafana_alert_definition import GrafanaAlertDefinition
from app.models.entity_link import EntityLink, LinkType, LinkSourceType
from app.services.escalation_metrics import EscalationMetricsService
from app.services.standby_context import StandbyContextService
from app.services.escalation_detector import EscalationDetector
from app.services.warning_monitor import WarningMonitorService


@pytest.mark.asyncio
async def test_escalation_metrics_calculation(db_session):
    """Test escalation metrics calculation from warning events."""
    service = EscalationMetricsService(db_session)

    # Create test warnings with different outcomes
    alert_name = "Test High CPU Alert"
    system = "wx-staging"

    # Warning 1: Escalated
    w1 = WarningEvent(
        alert_name=alert_name,
        system=system,
        channel_id="C123",
        channel_name="test-warn",
        message_ts="1234567890.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.75,
        escalated=True,
        escalated_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc) - timedelta(hours=2),
        last_seen=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    # Warning 2: Auto-cleared
    w2 = WarningEvent(
        alert_name=alert_name,
        system=system,
        channel_id="C123",
        channel_name="test-warn",
        message_ts="1234567891.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.45,
        auto_cleared=True,
        cleared_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc) - timedelta(hours=1),
        last_seen=datetime.now(timezone.utc),
    )

    # Warning 3: Escalated
    w3 = WarningEvent(
        alert_name=alert_name,
        system=system,
        channel_id="C123",
        channel_name="test-warn",
        message_ts="1234567892.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.80,
        escalated=True,
        escalated_at=datetime.now(timezone.utc),
        first_seen=datetime.now(timezone.utc) - timedelta(hours=3),
        last_seen=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    db_session.add_all([w1, w2, w3])
    await db_session.commit()

    # Calculate metrics
    metrics_dict = await service.calculate_metrics_for_alert(alert_name, system)

    # Verify metrics
    assert metrics_dict is not None
    assert metrics_dict["total_warnings"] == 3
    assert metrics_dict["escalated_count"] == 2
    assert metrics_dict["auto_cleared_count"] == 1
    assert metrics_dict["escalation_rate"] == 2 / 3  # 2 escalated, 1 cleared

    # Calculate all metrics
    stats = await service.calculate_all_metrics()
    assert stats["alerts_processed"] >= 1
    assert stats["metrics_created"] >= 1

    # Verify metrics stored in database
    result = await db_session.execute(
        select(WarningEscalationMetrics).where(
            WarningEscalationMetrics.alert_name == alert_name
        )
    )
    metrics = result.scalar_one_or_none()

    assert metrics is not None
    assert metrics.total_warnings == 3
    assert metrics.escalated_count == 2
    assert metrics.auto_cleared_count == 1
    assert abs(metrics.escalation_rate - 0.666) < 0.01  # ~66.7%


@pytest.mark.asyncio
async def test_standby_context_creation(db_session):
    """Test standby context pre-assembly for high-risk warnings."""
    service = StandbyContextService(db_session)

    # Create warning with high escalation probability
    warning = WarningEvent(
        alert_name="Database CPU High",
        system="wx-production",
        channel_id="C123",
        channel_name="compute-platform-warn",
        message_ts="1234567890.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.75,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )

    db_session.add(warning)
    await db_session.commit()
    await db_session.refresh(warning)

    # Create some artifacts to link
    artifact = InvestigationArtifact(
        filename="database-cpu-investigation.md",
        title="Database CPU High Investigation",
        description="database-cpu-investigation",
        file_path="/path/to/database-cpu-investigation.md",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(artifact)
    await db_session.commit()

    # Create alert definition
    alert_def = GrafanaAlertDefinition(
        alert_name="Database CPU High",
        file_path="/path/to/alert.yaml",
        alert_expr="cpu_usage{} > 80",
    )

    db_session.add(alert_def)
    await db_session.commit()

    # Create standby context
    context = await service.create_standby_context(warning_id=warning.id)

    assert context is not None
    assert context.title == f"Standby: {warning.alert_name}"
    assert context.status == ContextStatus.ACTIVE
    assert context.health_status == HealthStatus.YELLOW
    assert "Pre-assembled context" in context.summary_text
    assert f"{warning.escalation_probability:.0%}" in context.summary_text

    # Verify warning linked to context
    await db_session.refresh(warning)
    assert warning.standby_context_id == context.id

    # Verify artifact linked
    result = await db_session.execute(
        select(EntityLink).where(
            EntityLink.from_type == "work_context",
            EntityLink.from_id == str(context.id),
            EntityLink.to_type == "artifact",
        )
    )
    artifact_links = result.scalars().all()
    assert len(artifact_links) == 1

    # Verify alert definition linked
    result = await db_session.execute(
        select(EntityLink).where(
            EntityLink.from_type == "work_context",
            EntityLink.from_id == str(context.id),
            EntityLink.to_type == "grafana_alert",
        )
    )
    alert_links = result.scalars().all()
    assert len(alert_links) == 1


@pytest.mark.asyncio
async def test_escalation_detection(db_session):
    """Test escalation detection when warning → critical."""
    detector = EscalationDetector(db_session)

    # Create warning
    alert_name = "Database Connection Pool Warning"
    warning = WarningEvent(
        alert_name=alert_name,
        system="wx-production",
        channel_id="C123",
        channel_name="compute-platform-warn",
        message_ts="1234567890.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.60,
        first_seen=datetime.now(timezone.utc) - timedelta(minutes=30),
        last_seen=datetime.now(timezone.utc) - timedelta(minutes=30),
    )

    db_session.add(warning)
    await db_session.commit()
    await db_session.refresh(warning)

    # Simulate critical alert 30 minutes later
    critical_time = datetime.now(timezone.utc)

    # Detect escalation
    detected_warning = await detector.detect_escalation(alert_name, critical_time)

    assert detected_warning is not None
    assert detected_warning.id == warning.id
    assert detected_warning.alert_name == alert_name

    # Handle critical alert (mark as escalated)
    incident_context_id = uuid.uuid4()
    handled = await detector.handle_critical_alert(
        alert_name, critical_time, incident_context_id
    )

    assert handled is not None
    assert handled.id == warning.id

    # Verify warning marked as escalated
    await db_session.refresh(warning)
    assert warning.escalated is True
    assert warning.escalated_at is not None


@pytest.mark.asyncio
async def test_escalation_detection_no_match(db_session):
    """Test escalation detection when no matching warning exists."""
    detector = EscalationDetector(db_session)

    # Try to detect escalation for alert with no warning
    critical_time = datetime.now(timezone.utc)
    detected = await detector.detect_escalation("Nonexistent Alert", critical_time)

    assert detected is None


@pytest.mark.asyncio
async def test_escalation_detection_outside_window(db_session):
    """Test escalation detection fails outside 2-hour window."""
    detector = EscalationDetector(db_session)

    # Create warning 3 hours ago (outside window)
    alert_name = "Old Warning Alert"
    warning = WarningEvent(
        alert_name=alert_name,
        system="wx-production",
        channel_id="C123",
        channel_name="compute-platform-warn",
        message_ts="1234567890.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.75,
        first_seen=datetime.now(timezone.utc) - timedelta(hours=3),
        last_seen=datetime.now(timezone.utc) - timedelta(hours=3),
    )

    db_session.add(warning)
    await db_session.commit()

    # Try to detect escalation now (3 hours later)
    critical_time = datetime.now(timezone.utc)
    detected = await detector.detect_escalation(alert_name, critical_time)

    # Should not match (outside 2-hour window)
    assert detected is None


@pytest.mark.asyncio
async def test_warning_monitor_creates_standby_context(db_session):
    """Test WarningMonitor auto-creates standby context for high-risk warnings."""
    monitor = WarningMonitorService(db_session)

    # Create artifact to be linked
    artifact = InvestigationArtifact(
        filename="high-cpu-runbook.md",
        title="High CPU Runbook",
        description="high-cpu-runbook",
        file_path="/path/to/high-cpu-runbook.md",
        created_at=datetime.now(timezone.utc),
    )

    db_session.add(artifact)
    await db_session.commit()

    # Process high-risk warning message
    message = """
    🟡 WARNING: WX Staging Database CPU High
    System: wx-staging
    Value: 85%
    Threshold: 80%
    Time: 2026-03-20 14:30 UTC
    """

    warning = await monitor.process_message(
        message_text=message,
        channel_id="C123",
        channel_name="compute-platform-warn",
        message_ts="1234567890.123",
    )

    assert warning is not None
    assert warning.escalation_probability >= 0.5  # High risk

    # Verify standby context was created
    assert warning.standby_context_id is not None

    # Verify standby context exists
    result = await db_session.execute(
        select(WorkContext).where(WorkContext.id == warning.standby_context_id)
    )
    context = result.scalar_one_or_none()

    assert context is not None
    assert "Standby:" in context.title
    assert warning.alert_name in context.title
    assert context.status == ContextStatus.ACTIVE
    assert context.health_status == HealthStatus.YELLOW


@pytest.mark.asyncio
async def test_predicted_escalation_probability(db_session):
    """Test escalation probability prediction uses historical data."""
    service = EscalationMetricsService(db_session)

    # Create metrics with high escalation rate
    metrics = WarningEscalationMetrics(
        alert_name="Frequently Escalates Alert",
        system="wx-production",
        total_warnings=20,  # High confidence (>10)
        escalated_count=18,
        auto_cleared_count=2,
        escalation_rate=0.9,  # 90% escalation rate
    )

    db_session.add(metrics)
    await db_session.commit()

    # Pattern says 45% probability, but historical is 90%
    pattern_prob = 0.45
    predicted = await service.get_predicted_escalation_probability(
        alert_name="Frequently Escalates Alert", pattern_probability=pattern_prob
    )

    # Should weight historical rate heavily (80% weight)
    # predicted = 0.2 * 0.45 + 0.8 * 0.9 = 0.09 + 0.72 = 0.81
    assert abs(predicted - 0.81) < 0.01


@pytest.mark.asyncio
async def test_standby_context_activation(db_session):
    """Test activating standby context when warning escalates."""
    service = StandbyContextService(db_session)

    # Create warning with standby context
    warning = WarningEvent(
        alert_name="Test Alert",
        system="wx-production",
        channel_id="C123",
        channel_name="compute-platform-warn",
        message_ts="1234567890.123",
        severity=WarningSeverity.WARNING,
        escalation_probability=0.75,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )

    db_session.add(warning)
    await db_session.commit()
    await db_session.refresh(warning)

    # Create standby context
    standby_context = await service.create_standby_context(warning_id=warning.id)
    await db_session.refresh(warning)

    assert standby_context is not None

    # Create incident context
    incident_context = WorkContext(
        title="Incident: Test Alert",
        slug="incident-test-alert",
        status=ContextStatus.ACTIVE,
        health_status=HealthStatus.CRITICAL,
    )

    db_session.add(incident_context)
    await db_session.commit()
    await db_session.refresh(incident_context)

    # Activate standby context
    activated = await service.activate_standby_context(
        warning_id=warning.id, incident_context_id=incident_context.id
    )

    assert activated is not None
    assert "⚠️ ESCALATED TO INCIDENT" in activated.summary_text

    # Verify link created between standby and incident contexts
    result = await db_session.execute(
        select(EntityLink).where(
            EntityLink.from_type == "work_context",
            EntityLink.from_id == str(standby_context.id),
            EntityLink.to_type == "work_context",
            EntityLink.to_id == str(incident_context.id),
        )
    )
    link = result.scalar_one_or_none()

    assert link is not None
    assert link.link_type == LinkType.RELATED_TO
