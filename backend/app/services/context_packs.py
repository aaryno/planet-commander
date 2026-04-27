"""Context pack builder for agent spawning.

Assembles rich context preambles based on what the user was looking at
when they launched an agent — project config, JIRA ticket details,
MR diffs, Slack threads, deployment state.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


async def build_project_context(project_key: str, db: AsyncSession) -> str:
    """Build a project context pack from the Project entity."""
    from app.models.project import Project

    result = await db.execute(select(Project).where(Project.key == project_key))
    project = result.scalar_one_or_none()
    if not project:
        return ""

    lines = [
        f"[Project Context: {project.name}]",
        f"Key: {project.key}",
    ]

    if project.description:
        lines.append(f"Description: {project.description}")

    if project.repositories:
        repo_list = ", ".join(r.get("path", "") for r in project.repositories)
        lines.append(f"Repositories: {repo_list}")

    if project.jira_project_keys:
        lines.append(f"JIRA projects: {', '.join(project.jira_project_keys)}")

    if project.slack_channels:
        channels = ", ".join(c.get("name", "") for c in project.slack_channels)
        lines.append(f"Slack channels: {channels}")

    if project.grafana_dashboards:
        for d in project.grafana_dashboards[:3]:
            lines.append(f"Dashboard: {d.get('name', '')} — {d.get('url', '')}")

    if project.deployment_config:
        dc = project.deployment_config
        lines.append(f"Deployment: {dc.get('type', 'unknown')} on {dc.get('cluster', 'unknown')}")
        if dc.get("namespaces"):
            lines.append(f"Namespaces: {', '.join(dc['namespaces'])}")

    if project.links:
        doc_links = [l for l in project.links if l.get("category") in ("docs", "runbook", "context")]
        for link in doc_links[:3]:
            lines.append(f"Doc: {link.get('label', '')} — {link.get('url', '')}")

    return "\n".join(lines) + "\n"


async def build_jira_context(jira_key: str, db: AsyncSession) -> str:
    """Build a JIRA ticket context pack with full details if available."""
    from app.models.jira_issue import JiraIssue

    result = await db.execute(
        select(JiraIssue).where(JiraIssue.external_key == jira_key)
    )
    issue = result.scalar_one_or_none()

    lines = [f"[JIRA Ticket: {jira_key}]"]
    lines.append(f"URL: {settings.jira_base_url}/browse/{jira_key}")

    if issue:
        if issue.summary:
            lines.append(f"Summary: {issue.summary}")
        if issue.status:
            lines.append(f"Status: {issue.status}")
        if issue.assignee:
            lines.append(f"Assignee: {issue.assignee}")
        if issue.issue_type:
            lines.append(f"Type: {issue.issue_type}")
        if issue.priority:
            lines.append(f"Priority: {issue.priority}")
        if issue.labels:
            lines.append(f"Labels: {', '.join(issue.labels)}")
        if issue.description:
            desc = issue.description[:500]
            if len(issue.description) > 500:
                desc += "..."
            lines.append(f"Description:\n{desc}")
    else:
        lines.append("(Ticket details not cached — agent can fetch via JIRA API)")

    return "\n".join(lines) + "\n"


async def build_mr_context(project: str, mr_iid: int, db: AsyncSession) -> str:
    """Build an MR context pack with title, branch, and status."""
    from app.models.gitlab_merge_request import GitLabMergeRequest

    result = await db.execute(
        select(GitLabMergeRequest).where(
            GitLabMergeRequest.repository == project,
            GitLabMergeRequest.external_mr_id == mr_iid,
        )
    )
    mr = result.scalar_one_or_none()

    if not mr:
        return f"[MR Context: !{mr_iid} in {project} — details not cached]\n"

    lines = [
        f"[MR Context: !{mr_iid} in {project}]",
        f"Title: {mr.title}",
        f"Author: {mr.author}",
        f"Branch: {mr.source_branch} → {mr.target_branch}",
        f"State: {mr.state}",
        f"URL: {mr.web_url}",
    ]

    if mr.jira_keys:
        lines.append(f"Linked JIRA: {', '.join(mr.jira_keys)}")

    if mr.description:
        desc = mr.description[:300]
        if len(mr.description) > 300:
            desc += "..."
        lines.append(f"Description:\n{desc}")

    return "\n".join(lines) + "\n"


def build_slack_thread_context(channel: str, thread_ts: str | None = None, messages: list[dict] | None = None) -> str:
    """Build a Slack thread/message context pack."""
    lines = [f"[Slack Context: #{channel}]"]

    if thread_ts:
        lines.append(f"Thread: {thread_ts}")

    if messages:
        lines.append(f"Messages ({len(messages)}):")
        for msg in messages[:10]:
            author = msg.get("author", msg.get("user", "unknown"))
            text = msg.get("text", msg.get("content", ""))[:200]
            lines.append(f"  {author}: {text}")
        if len(messages) > 10:
            lines.append(f"  ... and {len(messages) - 10} more messages")

    return "\n".join(lines) + "\n"


async def build_context_preamble(
    *,
    project_key: str | None = None,
    jira_key: str | None = None,
    mr_project: str | None = None,
    mr_iid: int | None = None,
    slack_channel: str | None = None,
    slack_thread_ts: str | None = None,
    slack_messages: list[dict] | None = None,
    source: str | None = None,
    db: AsyncSession,
) -> str:
    """Build a full context preamble from all available sources.

    Called at agent spawn time. Assembles context packs in order:
    1. Project context (always, if project_key set)
    2. JIRA ticket context (if jira_key set)
    3. MR context (if mr_project + mr_iid set)
    4. Slack context (if slack_channel set)
    """
    parts = []

    if project_key:
        pack = await build_project_context(project_key, db)
        if pack:
            parts.append(pack)

    if jira_key:
        pack = await build_jira_context(jira_key, db)
        if pack:
            parts.append(pack)

    if mr_project and mr_iid:
        pack = await build_mr_context(mr_project, mr_iid, db)
        if pack:
            parts.append(pack)

    if slack_channel:
        pack = build_slack_thread_context(slack_channel, slack_thread_ts, slack_messages)
        if pack:
            parts.append(pack)

    if not parts:
        return ""

    return "\n".join(parts) + "\n"
