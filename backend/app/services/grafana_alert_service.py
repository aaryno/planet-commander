"""Grafana alert definition service for parsing and indexing alerts."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grafana_alert_definition import GrafanaAlertDefinition

logger = logging.getLogger(__name__)


class GrafanaAlertService:
    """Service for parsing and indexing Grafana alert definitions.

    NOTE: Alert definitions in planet-grafana-cloud-users are stored in Terraform (.tf)
    files, not YAML. Terraform parsing is complex and deferred to a future phase.

    For Phase 1, we support:
    1. Manual alert creation (from Slack firing messages)
    2. Basic metadata extraction from alert names
    3. Team/project inference from directory structure

    Future Phase (Terraform parsing):
    - Parse .tf files using python-hcl2 or terraform-config-inspect
    - Extract alert rules from Terraform modules
    - Link to source .tf files
    """

    # Alert repository location
    REPO_PATH = Path("~/code/build-deploy/planet-grafana-cloud-users").expanduser()
    MODULES_PATH = REPO_PATH / "modules"

    # Team directory pattern: {team}-team-{project}-alerts
    # Examples: compute-team-jobs-alerts, compute-team-wx-alerts
    TEAM_DIR_PATTERN = re.compile(r"^([a-z]+)-team-([a-z0-9]+)-alerts$")

    # Alert name pattern for inferring project (lowercase-with-dashes)
    # Examples: jobs-scheduler-low-runs, wx-task-lease-expiration
    ALERT_NAME_PATTERN = re.compile(r"^([a-z0-9]+)-")

    def __init__(self, db: AsyncSession):
        """Initialize alert service.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db

    def infer_alert_metadata(self, alert_name: str) -> Dict:
        """Infer alert metadata from alert name.

        Uses alert naming conventions to infer team, project, severity.

        Args:
            alert_name: Alert name (e.g., "jobs-scheduler-low-runs")

        Returns:
            Dict with inferred metadata

        Examples:
            >>> service.infer_alert_metadata("jobs-scheduler-low-runs")
            {"team": "compute", "project": "jobs", "severity": None}
            >>> service.infer_alert_metadata("wx-task-lease-expiration")
            {"team": "compute", "project": "wx", "severity": None}
        """
        metadata = {
            "team": None,
            "project": None,
            "severity": None,
        }

        # Infer project from alert name prefix
        match = self.ALERT_NAME_PATTERN.match(alert_name)
        if match:
            prefix = match.group(1)
            # Known project prefixes
            if prefix in ["jobs", "wx", "g4", "temporal", "eso"]:
                metadata["project"] = prefix
                # All these projects are owned by compute team
                metadata["team"] = "compute"

        # Infer severity from alert name keywords
        name_lower = alert_name.lower()
        if any(kw in name_lower for kw in ["critical", "down", "unavailable", "failed"]):
            metadata["severity"] = "critical"
        elif any(kw in name_lower for kw in ["warning", "warn", "low", "high"]):
            metadata["severity"] = "warning"

        return metadata

    async def create_alert_from_name(
        self,
        alert_name: str,
        summary: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> GrafanaAlertDefinition:
        """Create alert definition from alert name with inferred metadata.

        Useful for creating alerts discovered in Slack firing messages
        before we have full Terraform parsing.

        Args:
            alert_name: Alert name
            summary: Optional alert summary
            severity: Optional severity override

        Returns:
            Created GrafanaAlertDefinition

        Examples:
            >>> alert = await service.create_alert_from_name("jobs-scheduler-low-runs")
            >>> alert.project
            'jobs'
        """
        # Check if already exists
        existing = await self.get_alert_by_name(alert_name)
        if existing:
            return existing

        # Infer metadata
        metadata = self.infer_alert_metadata(alert_name)

        # Override with provided values
        if severity:
            metadata["severity"] = severity

        # Create alert
        alert = GrafanaAlertDefinition(
            alert_name=alert_name,
            file_path="",  # Unknown - from Slack
            team=metadata["team"],
            project=metadata["project"],
            alert_expr="",  # Unknown - will be populated later
            alert_for=None,
            labels={"severity": metadata["severity"]} if metadata["severity"] else {},
            annotations={},
            severity=metadata["severity"],
            runbook_url=None,
            summary=summary,
            file_modified_at=None,
        )

        self.db.add(alert)
        await self.db.commit()
        logger.info(f"Created alert from name: {alert_name} (project={metadata['project']})")

        return alert

    def _parse_team_project(self, path: Path) -> tuple[Optional[str], Optional[str]]:
        """Extract team and project from directory structure.

        Args:
            path: Path to alert directory or file

        Returns:
            Tuple of (team, project) or (None, None) if parsing fails

        Examples:
            modules/compute-team-jobs-alerts/ -> ("compute", "jobs")
            modules/compute-team-wx-alerts/ -> ("compute", "wx")
            modules/datapipeline-team-alerts/ -> ("datapipeline", None)
        """
        # Get directory name (handle both files and directories)
        if path.is_file():
            dir_name = path.parent.name
        else:
            dir_name = path.name

        # Try standard pattern: {team}-team-{project}-alerts
        match = self.TEAM_DIR_PATTERN.match(dir_name)
        if match:
            team = match.group(1)
            project = match.group(2)
            return (team, project)

        # Fallback: try to extract team from directory name
        # Examples: compute-alerts, datapipeline-alerts
        if "-alerts" in dir_name:
            parts = dir_name.replace("-alerts", "").split("-")
            team = parts[0] if parts else None
            project = parts[1] if len(parts) > 1 else None
            return (team, project)

        logger.debug(f"Could not parse team/project from directory: {dir_name}")
        return (None, None)

    async def get_alert_by_name(self, alert_name: str) -> Optional[GrafanaAlertDefinition]:
        """Get alert definition by name.

        Args:
            alert_name: Alert name (e.g., "jobs-scheduler-low-runs")

        Returns:
            GrafanaAlertDefinition or None
        """
        result = await self.db.execute(
            select(GrafanaAlertDefinition).where(
                GrafanaAlertDefinition.alert_name == alert_name
            )
        )
        return result.scalar_one_or_none()

    async def get_alert_by_id(self, alert_id: UUID) -> Optional[GrafanaAlertDefinition]:
        """Get alert definition by ID.

        Args:
            alert_id: Alert UUID

        Returns:
            GrafanaAlertDefinition or None
        """
        result = await self.db.execute(
            select(GrafanaAlertDefinition).where(GrafanaAlertDefinition.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def search_alerts(
        self,
        team: Optional[str] = None,
        project: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[GrafanaAlertDefinition]:
        """Search alert definitions by criteria.

        Args:
            team: Filter by team (compute, datapipeline, etc.)
            project: Filter by project (jobs, wx, g4, etc.)
            severity: Filter by severity (critical, warning, info)
            limit: Maximum results

        Returns:
            List of matching alert definitions
        """
        query = select(GrafanaAlertDefinition).where(
            GrafanaAlertDefinition.deleted_at.is_(None)
        )

        if team:
            query = query.where(GrafanaAlertDefinition.team == team)

        if project:
            query = query.where(GrafanaAlertDefinition.project == project)

        if severity:
            query = query.where(GrafanaAlertDefinition.severity == severity)

        # Order by alert name
        query = query.order_by(GrafanaAlertDefinition.alert_name).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def scan_alert_repo(self) -> Dict[str, int]:
        """Scan alert repository directories to index team/project structure.

        NOTE: Full Terraform parsing is deferred to future phase.
        For Phase 1, we just index the directory structure to establish
        team/project ownership for alerts discovered via Slack.

        Scans ~/code/build-deploy/planet-grafana-cloud-users/modules/
        for alert directories (e.g., compute-team-jobs-alerts) and records
        their existence for metadata inference.

        Returns:
            Stats dict with total_scanned, new_alerts, updated_alerts, errors

        Examples:
            >>> stats = await service.scan_alert_repo()
            >>> print(f"Scanned {stats['total_scanned']} alert directories")
        """
        if not self.MODULES_PATH.exists():
            logger.error(f"Alert repo not found: {self.MODULES_PATH}")
            return {
                "total_scanned": 0,
                "new_alerts": 0,
                "updated_alerts": 0,
                "errors": [{"file": str(self.MODULES_PATH), "error": "Directory not found"}]
            }

        stats = {
            "total_scanned": 0,
            "new_alerts": 0,
            "updated_alerts": 0,
            "errors": [],
            "note": "Terraform parsing deferred - directories indexed for metadata"
        }

        logger.info(f"Starting alert repo scan from {self.MODULES_PATH}")

        # Scan alert directories
        for alert_dir in self.MODULES_PATH.iterdir():
            if not alert_dir.is_dir():
                continue

            # Parse team/project from directory name
            team, project = self._parse_team_project(alert_dir)
            if not team:
                continue

            logger.debug(f"Found alert directory: {alert_dir.name} (team={team}, project={project})")
            stats["total_scanned"] += 1

            # NOTE: Full Terraform parsing would happen here in future phase
            # For now, we just record the directory structure

        logger.info(
            f"Alert repo scan complete: {stats['total_scanned']} directories found. "
            f"Full Terraform parsing deferred to future phase."
        )

        return stats
