"""Context resolution service for Planet Commander Phase 1.

Resolves work contexts from any entity (JIRA issue, chat, branch, worktree).
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Agent,
    AuditFinding,
    AuditRun,
    EntityLink,
    GitBranch,
    GitLabMergeRequest,
    GrafanaAlertDefinition,
    InvestigationArtifact,
    JiraIssue,
    PagerDutyIncident,
    WorkContext,
    Worktree,
    OriginType,
    ContextStatus,
    HealthStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ResolvedContext:
    """Data transfer object for resolved context data."""

    context: WorkContext | None = None
    jira_issues: list[JiraIssue] = field(default_factory=list)
    chats: list[Agent] = field(default_factory=list)
    branches: list[GitBranch] = field(default_factory=list)
    worktrees: list[Worktree] = field(default_factory=list)
    pagerduty_incidents: list[PagerDutyIncident] = field(default_factory=list)
    grafana_alerts: list[GrafanaAlertDefinition] = field(default_factory=list)
    artifacts: list[InvestigationArtifact] = field(default_factory=list)
    merge_requests: list[GitLabMergeRequest] = field(default_factory=list)
    audit_runs: list[AuditRun] = field(default_factory=list)
    audit_findings: list[AuditFinding] = field(default_factory=list)
    links: list[EntityLink] = field(default_factory=list)
    suggested_links: list[EntityLink] = field(default_factory=list)
    missing_links: list[dict[str, Any]] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)
    v2_docs: dict[str, Any] | None = None  # v2 documentation metadata


class ContextResolverService:
    """Resolve work contexts from entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_from_jira_key(self, jira_key: str) -> ResolvedContext:
        """Resolve context from JIRA issue key (e.g., COMPUTE-2059).

        Args:
            jira_key: JIRA issue key

        Returns:
            ResolvedContext with linked entities
        """
        # 1. Find JiraIssue
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        jira_issue = result.scalar_one_or_none()

        if not jira_issue:
            logger.warning(f"JIRA issue {jira_key} not found in cache")
            return ResolvedContext(missing_links=[{"type": "jira_issue", "key": jira_key}])

        # 2. Find or create WorkContext
        if jira_issue.context_id:
            result = await self.db.execute(
                select(WorkContext).where(WorkContext.id == jira_issue.context_id)
            )
            context = result.scalar_one_or_none()
        else:
            context = await self._get_or_create_context(
                origin_type=OriginType.JIRA,
                origin_id=str(jira_issue.id),
                title=f"{jira_key}: {jira_issue.title}",
                primary_jira_issue_id=jira_issue.id,
            )
            jira_issue.context_id = context.id
            await self.db.commit()

        # 3. Resolve all linked entities
        resolved = await self._resolve_context_graph(context.id)
        resolved.context = context
        resolved.jira_issues = [jira_issue]

        # 4. Compute health
        resolved.health = self._compute_health(resolved)

        # 5. Load v2 docs (stub for Week 3 UI integration)
        resolved.v2_docs = self._load_v2_docs_stub(resolved)

        return resolved

    async def resolve_from_chat_id(self, chat_id: uuid.UUID) -> ResolvedContext:
        """Resolve context from chat/agent ID.

        Args:
            chat_id: Agent/chat UUID

        Returns:
            ResolvedContext with linked entities
        """
        # 1. Find Agent (Chat)
        result = await self.db.execute(select(Agent).where(Agent.id == chat_id))
        chat = result.scalar_one_or_none()

        if not chat:
            logger.warning(f"Chat {chat_id} not found")
            return ResolvedContext(missing_links=[{"type": "chat", "id": str(chat_id)}])

        # 2. Find or create WorkContext
        if chat.context_id:
            result = await self.db.execute(
                select(WorkContext).where(WorkContext.id == chat.context_id)
            )
            context = result.scalar_one_or_none()
        else:
            # Check if linked to JIRA issue
            if chat.jira_key:
                result = await self.db.execute(
                    select(JiraIssue).where(JiraIssue.external_key == chat.jira_key)
                )
                jira_issue = result.scalar_one_or_none()
                if jira_issue and jira_issue.context_id:
                    # Use existing context from JIRA issue
                    context_result = await self.db.execute(
                        select(WorkContext).where(WorkContext.id == jira_issue.context_id)
                    )
                    context = context_result.scalar_one_or_none()
                    chat.context_id = context.id
                    await self.db.commit()
                else:
                    # Create new context
                    context = await self._get_or_create_context(
                        origin_type=OriginType.CHAT,
                        origin_id=str(chat.id),
                        title=chat.title or f"Chat {chat.id}",
                        primary_chat_id=chat.id,
                    )
                    chat.context_id = context.id
                    await self.db.commit()
            else:
                # No JIRA key, create chat-origin context
                context = await self._get_or_create_context(
                    origin_type=OriginType.CHAT,
                    origin_id=str(chat.id),
                    title=chat.title or f"Chat {chat.id}",
                    primary_chat_id=chat.id,
                )
                chat.context_id = context.id
                await self.db.commit()

        # 3. Resolve all linked entities
        resolved = await self._resolve_context_graph(context.id)
        resolved.context = context
        resolved.chats = [chat]

        # 4. Compute health
        resolved.health = self._compute_health(resolved)

        # 5. Load v2 docs (stub for Week 3 UI integration)
        resolved.v2_docs = self._load_v2_docs_stub(resolved)

        return resolved

    async def resolve_from_branch_id(self, branch_id: uuid.UUID) -> ResolvedContext:
        """Resolve context from git branch ID.

        Args:
            branch_id: GitBranch UUID

        Returns:
            ResolvedContext with linked entities
        """
        # 1. Find GitBranch
        result = await self.db.execute(select(GitBranch).where(GitBranch.id == branch_id))
        branch = result.scalar_one_or_none()

        if not branch:
            logger.warning(f"Branch {branch_id} not found")
            return ResolvedContext(missing_links=[{"type": "branch", "id": str(branch_id)}])

        # 2. Find or create WorkContext
        if branch.context_id:
            result = await self.db.execute(
                select(WorkContext).where(WorkContext.id == branch.context_id)
            )
            context = result.scalar_one_or_none()
        else:
            context = await self._get_or_create_context(
                origin_type=OriginType.BRANCH,
                origin_id=str(branch.id),
                title=f"{branch.repo}/{branch.branch_name}",
            )
            branch.context_id = context.id
            await self.db.commit()

        # 3. Resolve all linked entities
        resolved = await self._resolve_context_graph(context.id)
        resolved.context = context
        resolved.branches = [branch]

        # 4. Compute health
        resolved.health = self._compute_health(resolved)

        # 5. Load v2 docs (stub for Week 3 UI integration)
        resolved.v2_docs = self._load_v2_docs_stub(resolved)

        return resolved

    async def resolve_from_worktree_id(self, worktree_id: uuid.UUID) -> ResolvedContext:
        """Resolve context from worktree ID.

        Args:
            worktree_id: Worktree UUID

        Returns:
            ResolvedContext with linked entities
        """
        # 1. Find Worktree
        result = await self.db.execute(
            select(Worktree)
            .options(selectinload(Worktree.branch))
            .where(Worktree.id == worktree_id)
        )
        worktree = result.scalar_one_or_none()

        if not worktree:
            logger.warning(f"Worktree {worktree_id} not found")
            return ResolvedContext(missing_links=[{"type": "worktree", "id": str(worktree_id)}])

        # 2. Find context via branch
        branch = worktree.branch
        if branch.context_id:
            result = await self.db.execute(
                select(WorkContext).where(WorkContext.id == branch.context_id)
            )
            context = result.scalar_one_or_none()
        else:
            context = await self._get_or_create_context(
                origin_type=OriginType.WORKTREE,
                origin_id=str(worktree.id),
                title=f"{worktree.repo}/{branch.branch_name}",
            )
            branch.context_id = context.id
            await self.db.commit()

        # 3. Resolve all linked entities
        resolved = await self._resolve_context_graph(context.id)
        resolved.context = context
        resolved.branches = [branch]
        resolved.worktrees = [worktree]

        # 4. Compute health
        resolved.health = self._compute_health(resolved)

        # 5. Load v2 docs (stub for Week 3 UI integration)
        resolved.v2_docs = self._load_v2_docs_stub(resolved)

        return resolved

    async def resolve_from_context_id(self, context_id: uuid.UUID) -> ResolvedContext:
        """Resolve context by ID.

        Args:
            context_id: WorkContext UUID

        Returns:
            ResolvedContext with linked entities
        """
        result = await self.db.execute(select(WorkContext).where(WorkContext.id == context_id))
        context = result.scalar_one_or_none()

        if not context:
            logger.warning(f"Context {context_id} not found")
            return ResolvedContext()

        resolved = await self._resolve_context_graph(context.id)
        resolved.context = context
        resolved.health = self._compute_health(resolved)

        return resolved

    async def _get_or_create_context(
        self,
        origin_type: OriginType,
        origin_id: str,
        title: str,
        primary_jira_issue_id: uuid.UUID | None = None,
        primary_chat_id: uuid.UUID | None = None,
    ) -> WorkContext:
        """Get or create a work context.

        Args:
            origin_type: Type of origin entity
            origin_id: ID of origin entity
            title: Context title
            primary_jira_issue_id: Optional primary JIRA issue
            primary_chat_id: Optional primary chat

        Returns:
            WorkContext instance
        """
        # Generate slug from title
        slug = self._generate_slug(title)

        # Check if context already exists by slug
        result = await self.db.execute(select(WorkContext).where(WorkContext.slug == slug))
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Create new context
        context = WorkContext(
            title=title,
            slug=slug,
            origin_type=origin_type,
            primary_jira_issue_id=primary_jira_issue_id,
            primary_chat_id=primary_chat_id,
            status=ContextStatus.ACTIVE,
            health_status=HealthStatus.UNKNOWN,
        )

        self.db.add(context)
        await self.db.flush()  # Get ID without committing

        return context

    async def _resolve_context_graph(self, context_id: uuid.UUID) -> ResolvedContext:
        """Build full context graph from context ID.

        Args:
            context_id: WorkContext UUID

        Returns:
            ResolvedContext with all linked entities
        """
        resolved = ResolvedContext()

        # Get all entities with this context_id
        # JIRA issues
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.context_id == context_id)
        )
        resolved.jira_issues = list(result.scalars().all())

        # Chats (Agents)
        result = await self.db.execute(select(Agent).where(Agent.context_id == context_id))
        resolved.chats = list(result.scalars().all())

        # Branches
        result = await self.db.execute(
            select(GitBranch).where(GitBranch.context_id == context_id)
        )
        resolved.branches = list(result.scalars().all())

        # Worktrees (via branches)
        if resolved.branches:
            branch_ids = [b.id for b in resolved.branches]
            result = await self.db.execute(
                select(Worktree)
                .options(selectinload(Worktree.branch))
                .where(Worktree.branch_id.in_(branch_ids))
            )
            resolved.worktrees = list(result.scalars().all())

        # Entity links (Phase 1: just load, don't traverse yet)
        # In Phase 5 we'll add more sophisticated graph traversal
        result = await self.db.execute(
            select(EntityLink).where(
                (EntityLink.from_type == "context")
                & (EntityLink.from_id == str(context_id))
            )
        )
        resolved.links = list(result.scalars().all())

        # PagerDuty incidents (linked via EntityLink)
        # Find all links to PagerDuty incidents from entities in this context
        entity_types = []
        entity_ids = []

        if resolved.jira_issues:
            entity_types.extend(["jira_issue"] * len(resolved.jira_issues))
            entity_ids.extend([str(issue.id) for issue in resolved.jira_issues])

        if resolved.chats:
            entity_types.extend(["agent"] * len(resolved.chats))
            entity_ids.extend([str(chat.id) for chat in resolved.chats])

        if entity_ids:
            # Find links to PagerDuty incidents
            pd_links_result = await self.db.execute(
                select(EntityLink).where(
                    EntityLink.from_id.in_(entity_ids)
                    & (EntityLink.to_type == "pagerduty_incident")
                )
            )
            pd_links = pd_links_result.scalars().all()

            # Extract incident IDs and fetch incidents (IDs are strings, not UUIDs)
            incident_ids = []
            for link in pd_links:
                try:
                    incident_ids.append(uuid.UUID(link.to_id))
                except ValueError:
                    logger.debug(f"Skipping non-UUID PD incident ID: {link.to_id}")
                    continue

            if incident_ids:
                incidents_result = await self.db.execute(
                    select(PagerDutyIncident).where(PagerDutyIncident.id.in_(incident_ids))
                )
                resolved.pagerduty_incidents = list(incidents_result.scalars().all())

            # Grafana alerts (linked via EntityLink)
            # Find all links from Grafana alerts to entities in this context
            grafana_links_result = await self.db.execute(
                select(EntityLink).where(
                    EntityLink.to_id.in_(entity_ids)
                    & (EntityLink.from_type == "grafana_alert")
                )
            )
            grafana_links = grafana_links_result.scalars().all()

            # Extract alert IDs and fetch alerts
            alert_ids = []
            for link in grafana_links:
                try:
                    alert_ids.append(uuid.UUID(link.from_id))
                except ValueError:
                    continue

            if alert_ids:
                alerts_result = await self.db.execute(
                    select(GrafanaAlertDefinition).where(GrafanaAlertDefinition.id.in_(alert_ids))
                )
                resolved.grafana_alerts = list(alerts_result.scalars().all())

            # Artifacts (linked via EntityLink)
            # Find all links to artifacts from entities in this context
            artifact_links_result = await self.db.execute(
                select(EntityLink).where(
                    EntityLink.from_id.in_(entity_ids) & (EntityLink.to_type == "artifact")
                )
            )
            artifact_links = artifact_links_result.scalars().all()

            # Extract artifact IDs and fetch artifacts
            artifact_ids = []
            for link in artifact_links:
                try:
                    artifact_ids.append(uuid.UUID(link.to_id))
                except ValueError:
                    continue

            if artifact_ids:
                artifacts_result = await self.db.execute(
                    select(InvestigationArtifact).where(
                        InvestigationArtifact.id.in_(artifact_ids)
                    )
                )
                resolved.artifacts = list(artifacts_result.scalars().all())

            # GitLab merge requests (linked via EntityLink)
            # Find all links to merge requests from entities in this context
            mr_links_result = await self.db.execute(
                select(EntityLink).where(
                    EntityLink.from_id.in_(entity_ids)
                    & (EntityLink.to_type == "gitlab_merge_request")
                )
            )
            mr_links = mr_links_result.scalars().all()

            # Extract MR IDs and fetch MR records
            mr_ids = []
            for link in mr_links:
                try:
                    mr_ids.append(uuid.UUID(link.to_id))
                except ValueError:
                    continue

            if mr_ids:
                mrs_result = await self.db.execute(
                    select(GitLabMergeRequest).where(GitLabMergeRequest.id.in_(mr_ids))
                )
                resolved.merge_requests = list(mrs_result.scalars().all())

            # Audit runs (linked via EntityLink, Pattern A: entity -> audit_run)
            # Link direction: from_id is entity (JIRA, etc.), to_id is audit_run
            audit_links_result = await self.db.execute(
                select(EntityLink).where(
                    EntityLink.from_id.in_(entity_ids)
                    & (EntityLink.link_type == "audited_by")
                )
            )
            audit_links = audit_links_result.scalars().all()

            audit_run_ids = []
            for link in audit_links:
                try:
                    audit_run_ids.append(uuid.UUID(link.to_id))
                except ValueError:
                    continue

            if audit_run_ids:
                audit_runs_result = await self.db.execute(
                    select(AuditRun).where(AuditRun.id.in_(audit_run_ids))
                )
                resolved.audit_runs = list(audit_runs_result.scalars().all())

                # Fetch findings for those audit runs
                findings_result = await self.db.execute(
                    select(AuditFinding).where(
                        AuditFinding.audit_run_id.in_(audit_run_ids)
                    )
                )
                resolved.audit_findings = list(findings_result.scalars().all())

        return resolved

    def _compute_health(self, resolved: ResolvedContext) -> dict[str, Any]:
        """Compute basic health indicators.

        Args:
            resolved: ResolvedContext with entities

        Returns:
            Health indicator dict
        """
        has_ticket = len(resolved.jira_issues) > 0
        has_branch = len(resolved.branches) > 0
        has_active_worktree = any(w.is_active for w in resolved.worktrees)
        has_chat = len(resolved.chats) > 0

        # Simple health logic for Phase 1
        if has_ticket and has_branch and has_active_worktree:
            overall = "green"
        elif has_ticket:
            overall = "yellow"
        else:
            overall = "red"

        return {
            "has_ticket": has_ticket,
            "has_branch": has_branch,
            "has_active_worktree": has_active_worktree,
            "has_chat": has_chat,
            "overall": overall,
        }

    def _load_v2_docs_stub(self, resolved: ResolvedContext) -> dict[str, Any] | None:
        """Load v2 documentation metadata using actual v2_loader.

        Integrates with ECC v2_loader to determine which docs would auto-load
        for this context based on project/tool detection.

        Args:
            resolved: ResolvedContext with entities

        Returns:
            v2 docs metadata dict or None
        """
        try:
            # Import v2_loader from ECC hooks
            import sys
            import os
            hooks_path = os.path.expanduser("~/.claude/hooks")
            if hooks_path not in sys.path:
                sys.path.insert(0, hooks_path)

            from v2_loader import auto_load_v2_docs

            # Build a synthetic prompt to trigger v2 loading
            # Include context info that would appear in real prompts
            prompt_parts = []

            # Add JIRA key if present
            if resolved.jira_issues:
                prompt_parts.append(resolved.jira_issues[0].external_key)

            # Add project if known
            if resolved.jira_issues:
                jira_key = resolved.jira_issues[0].external_key
                if "-" in jira_key:
                    project = jira_key.split("-")[0]
                    prompt_parts.append(project)
            elif resolved.chats and resolved.chats[0].project:
                prompt_parts.append(resolved.chats[0].project)

            # Add common context words
            prompt_parts.extend(["debug", "task", "kubectl"])

            # Create synthetic prompt
            prompt = " ".join(prompt_parts)

            # Call v2_loader
            v2_result = auto_load_v2_docs(prompt)

            if not v2_result:
                return None

            # Convert v2_loader result to API format
            layers = []
            for idx, layer in enumerate(v2_result.get("layers", [])):
                # Determine layer number (0 = INDEX, 1 = project, 2 = tool)
                file_name = layer["file"]
                if file_name == "INDEX.md":
                    layer_num = 0
                elif "INDEX.md" in file_name:
                    layer_num = 1
                else:
                    layer_num = 2

                layers.append({
                    "name": file_name,
                    "tokens": layer["tokens"],
                    "layer": layer_num,
                })

            total_tokens = v2_result.get("total_tokens", 0)

            return {
                "layers": layers,
                "total_tokens": total_tokens,
                "budget_limit": 15000,
                "budget_exceeded": total_tokens > 15000,
            }

        except Exception as e:
            # If v2_loader fails, fall back to simple response
            logger.warning(f"v2_loader failed: {e}, falling back to stub")

            return {
                "layers": [
                    {"name": "INDEX.md", "tokens": 2081, "layer": 0},
                ],
                "total_tokens": 2081,
                "budget_limit": 15000,
                "budget_exceeded": False,
            }

    def _generate_slug(self, title: str) -> str:
        """Generate URL-safe slug from title.

        Args:
            title: Context title

        Returns:
            URL-safe slug
        """
        import re

        # Lowercase and replace non-alphanumeric with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Truncate to 200 chars (max slug length)
        return slug[:200]
