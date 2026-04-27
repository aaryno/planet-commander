"""JIRA service - search tickets via JIRA REST API.

Reads auth from ~/.jira/config (same format as ~/tools/jira/).
"""

import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path.home() / ".jira" / "config"

# Lazy-loaded config
_config: dict[str, str] | None = None


def _load_config() -> dict[str, str]:
    global _config
    if _config is not None:
        return _config

    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"JIRA config not found: {_CONFIG_PATH}")

    cfg: dict[str, str] = {}
    with open(_CONFIG_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                cfg[key.strip()] = value.strip()

    for req in ("JIRA_HOST", "JIRA_TOKEN", "JIRA_PROJECT"):
        if req not in cfg:
            raise ValueError(f"Missing {req} in {_CONFIG_PATH}")

    _config = cfg
    return _config


def _base_url() -> str:
    cfg = _load_config()
    return f"https://{cfg['JIRA_HOST']}/rest/api/2"


def _headers() -> dict[str, str]:
    cfg = _load_config()
    return {
        "Authorization": f"Bearer {cfg['JIRA_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _default_project() -> str:
    return _load_config()["JIRA_PROJECT"]


async def search_tickets(
    query: str,
    project: str | None = None,
    projects: list[str] | None = None,
    limit: int = 20,
    db: "AsyncSession | None" = None,
) -> list[dict[str, Any]]:
    """Search JIRA tickets by key or text.

    If query looks like a ticket key (e.g. COMPUTE-1234), fetches directly.
    Otherwise does a text search within the given projects.
    Accepts either `project` (single) or `projects` (list).
    When `db` is provided, uses project-configured JIRA keys from the database.
    """
    if not projects:
        if project:
            if db:
                from app.services.project_config import ProjectConfigService
                projects = await ProjectConfigService(db).get_jira_keys(project) or [project]
            else:
                projects = [project]
        elif db:
            from app.services.project_config import ProjectConfigService
            projects = await ProjectConfigService(db).get_all_jira_keys() or [_default_project()]
        else:
            projects = [_default_project()]

    # Build project filter clause
    if len(projects) == 1:
        project_clause = f"project = {projects[0]}"
    else:
        project_clause = f"project in ({', '.join(projects)})"

    # Build JQL
    q = query.strip()
    if not q:
        # Return recent in-progress tickets
        jql = (
            f"{project_clause} AND status in ('To Do', 'In Progress', 'In Review') "
            f"ORDER BY updated DESC"
        )
    elif any(q.upper().startswith(p.upper() + "-") for p in projects):
        # Direct key lookup
        jql = f"key = {q.upper()}"
    elif q.isdigit():
        # Just a number - treat as ticket ID in first project
        jql = f"key = {projects[0]}-{q}"
    else:
        # Text search - include labels since `text ~` doesn't search them
        escaped_q = q.replace('"', '\\"')
        jql = (
            f"{project_clause} AND "
            f"(text ~ \"{escaped_q}\" OR labels in (\"{escaped_q}\") OR summary ~ \"{escaped_q}\") "
            f"ORDER BY updated DESC"
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{_base_url()}/search",
                headers=_headers(),
                json={
                    "jql": jql,
                    "maxResults": limit,
                    "fields": [
                        "summary",
                        "description",
                        "status",
                        "assignee",
                        "priority",
                        "issuetype",
                        "fixVersions",
                        "labels",
                        "comment",
                        "customfield_10016",  # Story Points (standard Jira field)
                    ],
                    "expand": ["renderedFields"],
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # If we got results, fetch full comment history for each issue
            # The search endpoint only returns a subset of comments
            if data.get("issues"):
                for issue in data["issues"]:
                    issue_key = issue["key"]
                    try:
                        comment_resp = await client.get(
                            f"{_base_url()}/issue/{issue_key}/comment",
                            headers=_headers(),
                        )
                        comment_resp.raise_for_status()
                        comment_data = comment_resp.json()
                        # Replace the limited comments with full comment list
                        if "fields" in issue and comment_data.get("comments"):
                            issue["fields"]["comment"] = {
                                "comments": comment_data["comments"],
                                "total": comment_data.get("total", len(comment_data["comments"]))
                            }
                    except Exception as e:
                        logger.warning("Failed to fetch comments for %s: %s", issue_key, e)
    except httpx.HTTPStatusError as e:
        logger.error("JIRA search failed: %s %s", e.response.status_code, e.response.text[:200])
        return []
    except Exception as e:
        logger.error("JIRA search error: %s", e)
        return []

    results = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})

        # Extract description — pass wiki markup through for frontend rendering
        description = ""
        desc_obj = fields.get("description")
        if desc_obj:
            if isinstance(desc_obj, str):
                description = desc_obj  # Raw wiki markup — frontend handles rendering
            elif isinstance(desc_obj, dict):
                # ADF format - extract text from content nodes
                description = _extract_text_from_adf(desc_obj)

        # Extract comments
        comments = []
        comment_obj = fields.get("comment", {})
        if comment_obj and isinstance(comment_obj, dict):
            for comment in comment_obj.get("comments", []):
                author = comment.get("author", {})
                body = comment.get("body", "")

                # Extract text from ADF; pass wiki markup through for frontend
                if isinstance(body, dict):
                    body = _extract_text_from_adf(body)

                comments.append({
                    "id": comment.get("id", ""),
                    "author": author.get("displayName", "Unknown"),
                    "author_email": author.get("emailAddress", ""),
                    "avatar_url": (author.get("avatarUrls", {}) or {}).get("48x48", ""),
                    "body": body,
                    "created": comment.get("created", ""),
                    "updated": comment.get("updated", ""),
                })

        # Get story points (customfield_10016 is the standard Jira field)
        story_points = fields.get("customfield_10016")
        if story_points is not None:
            try:
                story_points = float(story_points)
            except (ValueError, TypeError):
                story_points = None

        results.append({
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "description": description,
            "status": (fields.get("status") or {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "fix_versions": [v["name"] for v in (fields.get("fixVersions") or [])],
            "labels": fields.get("labels", []),
            "comments": comments,
            "story_points": story_points,
        })

    return results


def _extract_text_from_adf(adf: dict) -> str:
    """Extract plain text from Atlassian Document Format."""
    if not isinstance(adf, dict):
        return ""

    parts = []

    def walk(node: dict | list):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            # Text nodes have a "text" key
            if "text" in node:
                parts.append(node["text"])
            # Recurse into content
            if "content" in node:
                walk(node["content"])

    walk(adf)
    return " ".join(parts)


def _convert_jira_markup_to_markdown(text: str) -> str:
    """Convert JIRA wiki markup to Markdown.

    Conservative conversions only — avoids mangling identifiers
    like wx-dev-02, wx_staging, service_account@project.iam.
    """
    import re

    if not text:
        return text

    # Headers: h1. -> #, h2. -> ##, etc.
    text = re.sub(r'^h1\.\s+(.+)$', r'# \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h2\.\s+(.+)$', r'## \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h3\.\s+(.+)$', r'### \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h4\.\s+(.+)$', r'#### \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h5\.\s+(.+)$', r'##### \1', text, flags=re.MULTILINE)
    text = re.sub(r'^h6\.\s+(.+)$', r'###### \1', text, flags=re.MULTILINE)

    # Code blocks: {code} ... {code} -> ``` ... ``` (do BEFORE brace/bold conversions)
    text = re.sub(r'\{code(?::[^}]*)?\}', '```', text)

    # Monospace/code: {{text}} -> `text` (do BEFORE brace conversions)
    text = re.sub(r'\{\{([^}]+)\}\}', r'`\1`', text)

    # Panels/boxes: remove JIRA-specific block markers
    text = re.sub(r'\{panel(?::[^}]*)?\}', '', text)
    text = re.sub(r'\{quote\}', '> ', text)
    text = re.sub(r'\{info(?::[^}]*)?\}', '', text)
    text = re.sub(r'\{note(?::[^}]*)?\}', '', text)
    text = re.sub(r'\{warning(?::[^}]*)?\}', '', text)
    text = re.sub(r'\{tip(?::[^}]*)?\}', '', text)
    text = re.sub(r'\{noformat\}', '```', text)
    text = re.sub(r'\{color[^}]*\}', '', text)

    # Bold: *text* -> **text** (only when * is at word boundary, not mid-word)
    text = re.sub(r'(?<!\w)\*([^*\n]+)\*(?!\w)', r'**\1**', text)

    # Italic: _text_ -> *text* (only when _ is at word boundary)
    text = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'*\1*', text)

    # Strikethrough: -text- -> ~~text~~ (only short inline, with word boundaries)
    # Must not match hyphens in identifiers like wx-dev-02 or table separators
    text = re.sub(r'(?<=\s)-([^\s-][^-\n]{0,40}[^\s-])-(?=[\s.,;:!?)]|$)', r'~~\1~~', text)

    # Lists: * item -> - item (already compatible)
    # Numbered lists: # item -> 1. item
    text = re.sub(r'^#\s+', '1. ', text, flags=re.MULTILINE)

    # Links: [text|url] -> [text](url)
    text = re.sub(r'\[([^|\]]+)\|([^\]]+)\]', r'[\1](\2)', text)
    # Simple links: [url] -> url
    text = re.sub(r'\[([^\]|]+)\]', r'\1', text)

    # Table header separator: || -> | (JIRA uses || for header cells)
    text = re.sub(r'\|\|', '|', text)

    return text


async def get_jira_summary(
    project: str | None = None,
    current_user_email: str | None = None,
    db: "AsyncSession | None" = None,
) -> dict[str, Any]:
    """Get JIRA summary with 'Me' and 'Team' sections.

    Returns tickets grouped by relationship and status.
    When `db` is provided, resolves JIRA project keys from the database.
    """
    from datetime import datetime, timedelta

    if not project:
        if db:
            from app.services.project_config import ProjectConfigService
            all_keys = await ProjectConfigService(db).get_all_jira_keys()
            project = all_keys[0] if all_keys else _default_project()
        else:
            project = _default_project()

    # Get current user from config if not provided
    if not current_user_email:
        cfg = _load_config()
        current_user_email = cfg.get("JIRA_USER_EMAIL") or cfg.get("JIRA_USERNAME", "")

    # Query for all active tickets in the project (including Backlog)
    # Prioritize active work by sorting by status category, then recency
    jql = (
        f"project = {project} AND "
        f"status not in ('Closed', 'Resolved', 'Rejected', 'Cancelled') AND "
        f"updated >= -365d "  # Last year
        f"ORDER BY updated DESC"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_base_url()}/search",
                headers=_headers(),
                json={
                    "jql": jql,
                    "maxResults": 500,
                    "fields": [
                        "summary",
                        "description",
                        "status",
                        "assignee",
                        "priority",
                        "issuetype",
                        "fixVersions",
                        "labels",
                        "watcher",
                        "created",
                        "updated",
                        "customfield_10016",  # Story Points
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error("Failed to fetch JIRA summary: %s", e)
        return {
            "me": {
                "assigned": [],
                "watching": [],
                "paired": [],
                "mr_reviewed": [],
                "slack_discussed": [],
            },
            "team": {
                "by_status": {
                    "backlog": [],
                    "selected": [],
                    "in_progress": [],
                    "in_review": [],
                    "ready_to_deploy": [],
                    "monitoring": [],
                    "done": [],
                },
                "stats": {
                    "backlog_count": 0,
                    "selected_count": 0,
                    "in_progress_count": 0,
                    "in_review_count": 0,
                    "ready_to_deploy_count": 0,
                    "monitoring_count": 0,
                    "done_count": 0,
                },
            },
            "project": project,
        }

    # Process tickets
    tickets = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        assignee_obj = fields.get("assignee") or {}

        # Calculate age
        created_str = fields.get("created", "")
        updated_str = fields.get("updated", "")
        age_days = 0
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                age_days = (datetime.now(created.tzinfo) - created).days
            except:
                pass

        # Determine relationships
        is_assigned = assignee_obj.get("emailAddress", "") == current_user_email
        # Note: Watching requires additional API call, skipping for MVP

        # Get story points
        story_points = fields.get("customfield_10016")
        if story_points is not None:
            try:
                story_points = float(story_points)
            except (ValueError, TypeError):
                story_points = None

        ticket = {
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "status": (fields.get("status") or {}).get("name", ""),
            "assignee": assignee_obj.get("displayName", "Unassigned"),
            "assignee_avatar_url": (assignee_obj.get("avatarUrls", {}) or {}).get("48x48", ""),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "fix_versions": [v["name"] for v in (fields.get("fixVersions") or [])],
            "labels": fields.get("labels", []),
            "story_points": story_points,
            "my_relationships": {
                "assigned": is_assigned,
                "watching": False,  # Would need watcher API call
                "paired": False,    # Would need to check paired field
                "mr_reviewed": False,  # Would need MR correlation
                "slack_discussed": False,  # Would need Slack correlation
            },
            "linked_mrs": [],  # Would need MR correlation
            "slack_mentions": [],  # Would need Slack correlation
            "age_days": age_days,
            "last_updated": updated_str,
        }
        tickets.append(ticket)

    # Group tickets by relationship (Me section)
    me_assigned = [t for t in tickets if t["my_relationships"]["assigned"] and t["status"] != "Done"]
    me_watching = [t for t in tickets if t["my_relationships"]["watching"] and not t["my_relationships"]["assigned"]]
    me_paired = [t for t in tickets if t["my_relationships"]["paired"]]
    me_mr_reviewed = [t for t in tickets if t["my_relationships"]["mr_reviewed"] and not t["my_relationships"]["assigned"]]
    me_slack_discussed = [t for t in tickets if t["my_relationships"]["slack_discussed"] and not any([
        t["my_relationships"]["assigned"],
        t["my_relationships"]["watching"],
        t["my_relationships"]["paired"],
        t["my_relationships"]["mr_reviewed"],
    ])]

    # Group tickets by status (Team section)
    team_backlog = [t for t in tickets if t["status"] in ("Backlog", "To Do")]
    team_selected = [t for t in tickets if t["status"] == "Selected for Development"]
    team_in_progress = [t for t in tickets if t["status"] == "In Progress"]
    team_in_review = [t for t in tickets if t["status"] in ("In Review", "Code Review")]
    team_ready_to_deploy = [t for t in tickets if t["status"] in ("Ready to Deploy", "Released to Staging")]
    team_monitoring = [t for t in tickets if t["status"] == "Monitoring"]
    team_done = [t for t in tickets if t["status"] == "Done"]

    return {
        "me": {
            "assigned": me_assigned,
            "watching": me_watching,
            "paired": me_paired,
            "mr_reviewed": me_mr_reviewed,
            "slack_discussed": me_slack_discussed,
        },
        "team": {
            "by_status": {
                "backlog": team_backlog,
                "selected": team_selected,
                "in_progress": team_in_progress,
                "in_review": team_in_review,
                "ready_to_deploy": team_ready_to_deploy,
                "monitoring": team_monitoring,
                "done": team_done,
            },
            "stats": {
                "backlog_count": len(team_backlog),
                "selected_count": len(team_selected),
                "in_progress_count": len(team_in_progress),
                "in_review_count": len(team_in_review),
                "ready_to_deploy_count": len(team_ready_to_deploy),
                "monitoring_count": len(team_monitoring),
                "done_count": len(team_done),
            },
        },
        "project": project,
    }
