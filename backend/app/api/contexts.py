"""Context resolution API endpoints for Planet Commander Phase 1.

Provides endpoints for resolving work contexts from any entity type.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.context_resolver import ContextResolverService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contexts", tags=["contexts"])


# Response Models


class JiraIssueResponse(BaseModel):
    """JIRA issue in context response."""

    id: str
    external_key: str
    title: str
    status: str
    priority: str | None
    assignee: str | None
    url: str


class ChatResponse(BaseModel):
    """Chat/agent in context response."""

    id: str
    title: str | None
    status: str
    project: str | None
    jira_key: str | None
    message_count: int
    last_active_at: str | None


class BranchResponse(BaseModel):
    """Git branch in context response."""

    id: str
    repo: str
    branch_name: str
    status: str
    ahead_count: int | None
    behind_count: int | None
    has_open_pr: bool
    linked_ticket_key_guess: str | None


class WorktreeResponse(BaseModel):
    """Worktree in context response."""

    id: str
    path: str
    repo: str
    status: str
    is_active: bool
    has_uncommitted_changes: bool
    has_untracked_files: bool
    is_rebasing: bool


class PagerDutyIncidentResponse(BaseModel):
    """PagerDuty incident in context response."""

    id: str
    external_incident_id: str
    incident_number: int | None
    title: str
    status: str
    urgency: str | None
    triggered_at: str
    resolved_at: str | None
    html_url: str | None
    is_active: bool
    is_high_urgency: bool


class GrafanaAlertResponse(BaseModel):
    """Grafana alert definition in context response."""

    id: str
    alert_name: str
    team: str | None
    project: str | None
    severity: str | None
    runbook_url: str | None
    summary: str | None
    is_active: bool
    is_critical: bool
    has_runbook: bool


class ArtifactResponse(BaseModel):
    """Investigation artifact in context response."""

    id: str
    filename: str
    file_path: str
    title: str | None
    project: str | None
    artifact_type: str | None
    created_at: str
    content_preview: str | None
    jira_keys: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    age_days: int
    is_recent: bool


class MergeRequestResponse(BaseModel):
    """GitLab merge request in context response."""

    id: str
    external_mr_id: int
    repository: str
    title: str
    url: str
    source_branch: str
    target_branch: str
    author: str
    state: str
    approval_status: str | None
    ci_status: str | None
    jira_keys: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    merged_at: str | None
    is_approved: bool
    is_ci_passing: bool
    is_merged: bool
    is_open: bool
    age_days: int
    project_name: str


class AuditRunSummaryResponse(BaseModel):
    """Audit run summary in context response."""

    id: str
    family: str
    verdict: str
    finding_count: int
    blocking_count: int
    risk_score: float | None
    dimension_scores: dict | None
    created_at: str


class FindingsSummaryResponse(BaseModel):
    """Aggregate summary of audit findings in context response."""

    total: int
    errors: int
    warnings: int
    info: int
    blocking: int
    auto_fixable: int


class EntityLinkResponse(BaseModel):
    """Entity link in context response."""

    id: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    link_type: str
    source_type: str
    status: str
    confidence_score: float | None
    link_metadata: dict | None


class V2DocLayer(BaseModel):
    """v2 documentation layer metadata."""

    name: str
    tokens: int
    layer: int  # 0 = INDEX.md, 1 = project index, 2 = tool quick-ref


class V2DocsMetadata(BaseModel):
    """v2 documentation loading metadata."""

    layers: list[V2DocLayer] = Field(default_factory=list)
    total_tokens: int = 0
    budget_limit: int = 15000
    budget_exceeded: bool = False


class HealthResponse(BaseModel):
    """Context health indicators."""

    has_ticket: bool
    has_branch: bool
    has_active_worktree: bool
    has_chat: bool
    overall: str


class ContextResponse(BaseModel):
    """Full context with all linked entities."""

    id: str
    title: str
    slug: str
    origin_type: str
    status: str
    health_status: str
    summary_text: str | None
    owner: str | None
    jira_issues: list[JiraIssueResponse] = Field(default_factory=list)
    chats: list[ChatResponse] = Field(default_factory=list)
    branches: list[BranchResponse] = Field(default_factory=list)
    worktrees: list[WorktreeResponse] = Field(default_factory=list)
    pagerduty_incidents: list[PagerDutyIncidentResponse] = Field(default_factory=list)
    grafana_alerts: list[GrafanaAlertResponse] = Field(default_factory=list)
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
    merge_requests: list[MergeRequestResponse] = Field(default_factory=list)
    audit_runs: list[AuditRunSummaryResponse] = Field(default_factory=list)
    findings_summary: FindingsSummaryResponse | None = None
    links: list[EntityLinkResponse] = Field(default_factory=list)
    v2_docs: V2DocsMetadata | None = None
    health: HealthResponse


# Endpoints


@router.post("/enrich/{entity_type}/{entity_id}")
async def enrich_from_entity(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db)
) -> ContextResponse:
    """
    Enrich context starting from an entity reference.

    Supported entity types:
    - "jira": JIRA ticket (e.g., COMPUTE-1234)
    - "pagerduty": PagerDuty incident (e.g., Q1ABC2DEF3GHI)
    - "slack": Slack thread (e.g., C123/p456)
    - "artifact": Investigation artifact (e.g., 20260320-1500-summary.md)
    - "chat": Agent/chat session (UUID)
    - "branch": Git branch (UUID)
    - "worktree": Worktree (UUID)

    Returns enriched work context with all linked entities.
    """
    resolver = ContextResolverService(db)

    try:
        # Route to appropriate resolver based on entity type
        if entity_type == "jira":
            resolved = await resolver.resolve_from_jira_key(entity_id)
        elif entity_type == "pagerduty":
            # PagerDuty incident ID - need to look up in database first
            raise HTTPException(
                status_code=501,
                detail="PagerDuty enrichment not yet implemented - requires incident lookup"
            )
        elif entity_type == "slack":
            # Slack thread reference - need to parse and look up
            raise HTTPException(
                status_code=501,
                detail="Slack enrichment not yet implemented - requires thread lookup"
            )
        elif entity_type == "artifact":
            # Artifact filename - need to look up in database
            raise HTTPException(
                status_code=501,
                detail="Artifact enrichment not yet implemented - requires artifact lookup"
            )
        elif entity_type == "chat":
            # Chat/agent UUID
            try:
                chat_uuid = uuid.UUID(entity_id)
                resolved = await resolver.resolve_from_chat_id(chat_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid chat UUID format")
        elif entity_type == "branch":
            # Branch UUID
            try:
                branch_uuid = uuid.UUID(entity_id)
                resolved = await resolver.resolve_from_branch_id(branch_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid branch UUID format")
        elif entity_type == "worktree":
            # Worktree UUID
            try:
                worktree_uuid = uuid.UUID(entity_id)
                resolved = await resolver.resolve_from_worktree_id(worktree_uuid)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid worktree UUID format")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported entity type: {entity_type}. "
                       f"Supported types: jira, pagerduty, slack, artifact, chat, branch, worktree"
            )

        if not resolved.context:
            raise HTTPException(
                status_code=404,
                detail=f"Entity {entity_type}/{entity_id} not found or failed to create context"
            )

        # Commit to persist any auto-created contexts or links
        await db.commit()

        return _build_context_response(resolved)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enrich {entity_type}/{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{context_id}", response_model=ContextResponse)
async def get_context(context_id: str, db: AsyncSession = Depends(get_db)):
    """Get work context by ID.

    Args:
        context_id: WorkContext UUID

    Returns:
        Full context with all linked entities
    """
    try:
        context_uuid = uuid.UUID(context_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid context ID format")

    resolver = ContextResolverService(db)

    try:
        resolved = await resolver.resolve_from_context_id(context_uuid)

        if not resolved.context:
            raise HTTPException(status_code=404, detail="Context not found")

        return _build_context_response(resolved)

    except Exception as e:
        logger.error(f"Failed to resolve context {context_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jira/{jira_key}", response_model=ContextResponse)
async def get_context_by_jira_key(jira_key: str, db: AsyncSession = Depends(get_db)):
    """Resolve context from JIRA issue key.

    Args:
        jira_key: JIRA issue key (e.g., COMPUTE-2059)

    Returns:
        Full context with all linked entities
    """
    resolver = ContextResolverService(db)

    try:
        resolved = await resolver.resolve_from_jira_key(jira_key)

        if not resolved.context:
            raise HTTPException(
                status_code=404, detail=f"JIRA issue {jira_key} not found in cache"
            )

        # Commit to persist auto-created context
        await db.commit()

        return _build_context_response(resolved)

    except Exception as e:
        logger.error(f"Failed to resolve context for JIRA {jira_key}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chat/{chat_id}", response_model=ContextResponse)
async def get_context_by_chat_id(chat_id: str, db: AsyncSession = Depends(get_db)):
    """Resolve context from chat/agent ID.

    Args:
        chat_id: Agent/chat UUID

    Returns:
        Full context with all linked entities
    """
    try:
        chat_uuid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    resolver = ContextResolverService(db)

    try:
        resolved = await resolver.resolve_from_chat_id(chat_uuid)

        if not resolved.context:
            raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found")

        # Commit to persist auto-created context
        await db.commit()

        return _build_context_response(resolved)

    except Exception as e:
        import traceback
        logger.error(f"Failed to resolve context for chat {chat_id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/branch/{branch_id}", response_model=ContextResponse)
async def get_context_by_branch_id(branch_id: str, db: AsyncSession = Depends(get_db)):
    """Resolve context from git branch ID.

    Args:
        branch_id: GitBranch UUID

    Returns:
        Full context with all linked entities
    """
    try:
        branch_uuid = uuid.UUID(branch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid branch ID format")

    resolver = ContextResolverService(db)

    try:
        resolved = await resolver.resolve_from_branch_id(branch_uuid)

        if not resolved.context:
            raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")

        # Commit to persist auto-created context
        await db.commit()

        return _build_context_response(resolved)

    except Exception as e:
        logger.error(f"Failed to resolve context for branch {branch_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/worktree/{worktree_id}", response_model=ContextResponse)
async def get_context_by_worktree_id(worktree_id: str, db: AsyncSession = Depends(get_db)):
    """Resolve context from worktree ID.

    Args:
        worktree_id: Worktree UUID

    Returns:
        Full context with all linked entities
    """
    try:
        worktree_uuid = uuid.UUID(worktree_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid worktree ID format")

    resolver = ContextResolverService(db)

    try:
        resolved = await resolver.resolve_from_worktree_id(worktree_uuid)

        if not resolved.context:
            raise HTTPException(status_code=404, detail=f"Worktree {worktree_id} not found")

        # Commit to persist auto-created context
        await db.commit()

        return _build_context_response(resolved)

    except Exception as e:
        logger.error(f"Failed to resolve context for worktree {worktree_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper Functions


def _build_context_response(resolved: Any) -> ContextResponse:
    """Build ContextResponse from ResolvedContext.

    Args:
        resolved: ResolvedContext instance

    Returns:
        ContextResponse for API
    """
    context = resolved.context

    return ContextResponse(
        id=str(context.id),
        title=context.title,
        slug=context.slug,
        origin_type=context.origin_type.value,
        status=context.status.value,
        health_status=context.health_status.value,
        summary_text=context.summary_text,
        owner=context.owner,
        jira_issues=[
            JiraIssueResponse(
                id=str(issue.id),
                external_key=issue.external_key,
                title=issue.title,
                status=issue.status,
                priority=issue.priority,
                assignee=issue.assignee,
                url=issue.url,
            )
            for issue in resolved.jira_issues
        ],
        chats=[
            ChatResponse(
                id=str(chat.id),
                title=chat.title,
                status=chat.status,
                project=chat.project,
                jira_key=chat.jira_key,
                message_count=chat.message_count,
                last_active_at=chat.last_active_at.isoformat() if chat.last_active_at else None,
            )
            for chat in resolved.chats
        ],
        branches=[
            BranchResponse(
                id=str(branch.id),
                repo=branch.repo,
                branch_name=branch.branch_name,
                status=branch.status.value,
                ahead_count=branch.ahead_count,
                behind_count=branch.behind_count,
                has_open_pr=branch.has_open_pr,
                linked_ticket_key_guess=branch.linked_ticket_key_guess,
            )
            for branch in resolved.branches
        ],
        worktrees=[
            WorktreeResponse(
                id=str(wt.id),
                path=wt.path,
                repo=wt.repo,
                status=wt.status.value,
                is_active=wt.is_active,
                has_uncommitted_changes=wt.has_uncommitted_changes,
                has_untracked_files=wt.has_untracked_files,
                is_rebasing=wt.is_rebasing,
            )
            for wt in resolved.worktrees
        ],
        pagerduty_incidents=[
            PagerDutyIncidentResponse(
                id=str(incident.id),
                external_incident_id=incident.external_incident_id,
                incident_number=incident.incident_number,
                title=incident.title,
                status=incident.status,
                urgency=incident.urgency,
                triggered_at=incident.triggered_at.isoformat(),
                resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
                html_url=incident.html_url,
                is_active=incident.is_active,
                is_high_urgency=incident.is_high_urgency,
            )
            for incident in resolved.pagerduty_incidents
        ],
        grafana_alerts=[
            GrafanaAlertResponse(
                id=str(alert.id),
                alert_name=alert.alert_name,
                team=alert.team,
                project=alert.project,
                severity=alert.severity,
                runbook_url=alert.runbook_url,
                summary=alert.summary,
                is_active=alert.is_active,
                is_critical=alert.is_critical,
                has_runbook=alert.has_runbook,
            )
            for alert in resolved.grafana_alerts
        ],
        artifacts=[
            ArtifactResponse(
                id=str(artifact.id),
                filename=artifact.filename,
                file_path=artifact.file_path,
                title=artifact.title,
                project=artifact.project,
                artifact_type=artifact.artifact_type,
                created_at=artifact.created_at.isoformat(),
                content_preview=artifact.content_preview,
                jira_keys=artifact.jira_keys or [],
                keywords=artifact.keywords or [],
                age_days=artifact.age_days,
                is_recent=artifact.is_recent,
            )
            for artifact in resolved.artifacts
        ],
        merge_requests=[
            MergeRequestResponse(
                id=str(mr.id),
                external_mr_id=mr.external_mr_id,
                repository=mr.repository,
                title=mr.title,
                url=mr.url,
                source_branch=mr.source_branch,
                target_branch=mr.target_branch,
                author=mr.author,
                state=mr.state,
                approval_status=mr.approval_status,
                ci_status=mr.ci_status,
                jira_keys=mr.jira_keys or [],
                created_at=mr.created_at.isoformat(),
                updated_at=mr.updated_at.isoformat(),
                merged_at=mr.merged_at.isoformat() if mr.merged_at else None,
                is_approved=mr.is_approved,
                is_ci_passing=mr.is_ci_passing,
                is_merged=mr.is_merged,
                is_open=mr.is_open,
                age_days=mr.age_days,
                project_name=mr.project_name,
            )
            for mr in resolved.merge_requests
        ],
        audit_runs=[
            AuditRunSummaryResponse(
                id=str(run.id),
                family=run.audit_family,
                verdict=run.verdict,
                finding_count=run.finding_count,
                blocking_count=run.blocking_count,
                risk_score=run.risk_score,
                dimension_scores=run.dimension_scores,
                created_at=run.created_at.isoformat(),
            )
            for run in resolved.audit_runs
        ],
        findings_summary=(
            FindingsSummaryResponse(
                total=len(resolved.audit_findings),
                errors=sum(1 for f in resolved.audit_findings if f.severity == "error"),
                warnings=sum(1 for f in resolved.audit_findings if f.severity == "warning"),
                info=sum(1 for f in resolved.audit_findings if f.severity == "info"),
                blocking=sum(1 for f in resolved.audit_findings if f.blocking),
                auto_fixable=sum(1 for f in resolved.audit_findings if f.auto_fixable),
            )
            if resolved.audit_findings
            else None
        ),
        links=[
            EntityLinkResponse(
                id=str(link.id),
                from_type=link.from_type,
                from_id=link.from_id,
                to_type=link.to_type,
                to_id=link.to_id,
                link_type=link.link_type.value,
                source_type=link.source_type.value,
                status=link.status.value,
                confidence_score=link.confidence_score,
                link_metadata=link.link_metadata,
            )
            for link in resolved.links
        ],
        v2_docs=(
            V2DocsMetadata(
                layers=[
                    V2DocLayer(
                        name=layer["name"],
                        tokens=layer["tokens"],
                        layer=layer["layer"],
                    )
                    for layer in (resolved.v2_docs.get("layers", []) if resolved.v2_docs else [])
                ],
                total_tokens=resolved.v2_docs.get("total_tokens", 0) if resolved.v2_docs else 0,
                budget_limit=resolved.v2_docs.get("budget_limit", 15000) if resolved.v2_docs else 15000,
                budget_exceeded=resolved.v2_docs.get("budget_exceeded", False) if resolved.v2_docs else False,
            )
            if resolved.v2_docs
            else None
        ),
        health=HealthResponse(
            has_ticket=resolved.health["has_ticket"],
            has_branch=resolved.health["has_branch"],
            has_active_worktree=resolved.health["has_active_worktree"],
            has_chat=resolved.health["has_chat"],
            overall=resolved.health["overall"],
        ),
    )
