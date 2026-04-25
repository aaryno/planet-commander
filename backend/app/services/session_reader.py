"""Reads Claude Code session data from ~/.claude/projects/."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SessionEntry:
    session_id: str
    full_path: str
    first_prompt: str
    message_count: int
    created: str
    modified: str
    git_branch: str
    project_path: str
    project_dir_name: str  # e.g. -Users-aaryn-workspaces-wx-1
    is_sidechain: bool = False


@dataclass
class ParsedMessage:
    role: str  # "user" or "assistant"
    timestamp: str
    content: str | None = None  # user message text
    summary: str | None = None  # assistant text blocks joined
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_count: int = 0
    has_thinking: bool = False
    thinking: str | None = None  # only populated when expand=True
    model: str | None = None
    artifacts: list[dict] = field(default_factory=list)  # files created/edited: {path, type, tool}


def discover_sessions() -> list[SessionEntry]:
    """Scan all sessions-index.json files AND unindexed JSONL files."""
    sessions = []
    indexed_ids: set[str] = set()
    projects_dir = settings.claude_projects_dir

    if not projects_dir.exists():
        logger.warning("Claude projects dir not found: %s", projects_dir)
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Phase 1: Read indexed sessions from sessions-index.json
        index_file = project_dir / "sessions-index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                entries = data.get("entries", [])
                for entry in entries:
                    sid = entry["sessionId"]
                    indexed_ids.add(sid)
                    sessions.append(SessionEntry(
                        session_id=sid,
                        full_path=entry.get("fullPath", ""),
                        first_prompt=entry.get("firstPrompt", ""),
                        message_count=entry.get("messageCount", 0),
                        created=entry.get("created", ""),
                        modified=entry.get("modified", ""),
                        git_branch=entry.get("gitBranch", ""),
                        project_path=entry.get("projectPath", ""),
                        project_dir_name=project_dir.name,
                        is_sidechain=entry.get("isSidechain", False),
                    ))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to parse %s: %s", index_file, e)

        # Phase 2: Discover unindexed JSONL files
        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            if session_id in indexed_ids:
                continue

            entry = _parse_unindexed_session(jsonl_file, project_dir.name)
            if entry:
                sessions.append(entry)

    return sessions


def _parse_unindexed_session(jsonl_path: Path, project_dir_name: str) -> SessionEntry | None:
    """Extract basic metadata from an unindexed JSONL session file."""
    session_id = jsonl_path.stem
    first_prompt = ""
    first_timestamp = ""
    last_timestamp = ""
    git_branch = ""
    project_path = ""
    message_count = 0

    try:
        with jsonl_path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                record_type = record.get("type")

                if record_type in ("user", "assistant"):
                    message_count += 1
                    ts = record.get("timestamp", "")
                    if ts:
                        if not first_timestamp:
                            first_timestamp = ts
                        last_timestamp = ts

                    if record_type == "user" and not first_prompt:
                        msg = record.get("message", {})
                        content = msg.get("content", [])
                        text = _extract_user_text(content)
                        if text.strip():
                            first_prompt = text[:500]

                    # Grab git branch and project path from first record that has them
                    if not git_branch:
                        git_branch = record.get("gitBranch", "")
                    if not project_path:
                        project_path = record.get("cwd", "")

    except OSError as e:
        logger.error("Failed to read %s: %s", jsonl_path, e)
        return None

    if message_count == 0:
        return None

    return SessionEntry(
        session_id=session_id,
        full_path=str(jsonl_path),
        first_prompt=first_prompt,
        message_count=message_count,
        created=first_timestamp,
        modified=last_timestamp,
        git_branch=git_branch,
        project_path=project_path,
        project_dir_name=project_dir_name,
    )


def map_project(project_dir_name: str) -> str:
    """Map a Claude project directory name to a project key."""
    return settings.project_path_map.get(project_dir_name, "general")


def _resolve_session_path(session: SessionEntry) -> Path | None:
    """Resolve the JSONL file path for a session.

    The fullPath in sessions-index.json references the host path,
    but we may be running in a container where ~/.claude is mounted
    at a different location.
    """
    if not session.session_id:
        return None

    # Try using the project dir + session id directly
    if session.project_dir_name:
        jsonl_path = settings.claude_projects_dir / session.project_dir_name / f"{session.session_id}.jsonl"
        if jsonl_path.exists() and jsonl_path.is_file():
            return jsonl_path

    # Fall back to the stored fullPath (works when running on host)
    if session.full_path:
        stored = Path(session.full_path)
        if stored.exists() and stored.is_file():
            return stored

    # Search all project dirs for this session (dashboard-spawned agents
    # may not have project_dir_name set)
    for project_dir in settings.claude_projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session.session_id}.jsonl"
        if candidate.exists() and candidate.is_file():
            return candidate

    return None


def extract_files_changed(session: SessionEntry) -> dict[str, str]:
    """Extract files created/edited from a session JSONL. Lightweight scan."""
    jsonl_path = _resolve_session_path(session)
    if not jsonl_path:
        return {}

    import json
    files: dict[str, str] = {}
    try:
        with open(jsonl_path, "r", errors="replace") as f:
            for line in f:
                if '"Write"' not in line and '"Edit"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") != "assistant":
                        continue
                    for block in obj.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use" and block.get("name") in ("Write", "Edit"):
                            fp = block.get("input", {}).get("file_path")
                            if fp:
                                files[fp] = "created" if block["name"] == "Write" else "edited"
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return files


def extract_mr_references(session: SessionEntry) -> list[dict]:
    """Extract MR references mentioned in a session. Lightweight scan."""
    jsonl_path = _resolve_session_path(session)
    if not jsonl_path:
        return []

    import json, re
    mrs: dict[str, dict] = {}
    mr_pattern = re.compile(r'(?:https://hello\.planet\.com/code/([\w/-]+)/-/merge_requests/(\d+))|(?:!(\d+))')

    try:
        with open(jsonl_path, "r", errors="replace") as f:
            for line in f:
                if "merge_request" not in line and "!(" not in line and "!" not in line:
                    continue
                # Look for GitLab MR URLs
                for match in mr_pattern.finditer(line):
                    repo, mr_num_url, mr_num_bang = match.groups()
                    if repo and mr_num_url:
                        key = f"{repo}!{mr_num_url}"
                        mrs[key] = {
                            "repo": repo,
                            "iid": int(mr_num_url),
                            "url": f"https://hello.planet.com/code/{repo}/-/merge_requests/{mr_num_url}",
                        }
    except Exception:
        pass
    return list(mrs.values())


def get_session_stats(session: SessionEntry) -> dict:
    """Sum token usage and count prompts from a JSONL session file.

    Returns {"total_input_tokens", "total_output_tokens", "total_tokens", "num_prompts"}.
    """
    jsonl_path = _resolve_session_path(session)
    if jsonl_path is None:
        return {"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0, "num_prompts": 0}

    total_input = 0
    total_output = 0
    num_prompts = 0

    try:
        for line in jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            record_type = record.get("type")

            if record_type == "assistant":
                usage = record.get("message", {}).get("usage", {})
                total_input += usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                total_output += usage.get("output_tokens", 0)

            elif record_type == "user":
                content = record.get("message", {}).get("content", [])
                if not _is_tool_result(content):
                    num_prompts += 1
    except OSError as e:
        logger.error("Failed to read stats for %s: %s", session.session_id, e)

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "num_prompts": num_prompts,
    }


def parse_chat_history(session: SessionEntry, expand: bool = False) -> list[ParsedMessage]:
    """Parse a JSONL session file into structured chat messages."""
    jsonl_path = _resolve_session_path(session)
    if jsonl_path is None:
        logger.warning("Session file not found for %s", session.session_id)
        return []

    messages: list[ParsedMessage] = []
    pending_assistant: ParsedMessage | None = None

    for line in jsonl_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        record_type = record.get("type")

        if record_type == "user":
            msg = record.get("message", {})
            content_blocks = msg.get("content", [])

            # Skip tool_result messages (automatic tool responses, not user input)
            if _is_tool_result(content_blocks):
                continue

            # Flush pending assistant
            if pending_assistant:
                messages.append(pending_assistant)
                pending_assistant = None

            text = _extract_user_text(content_blocks)
            timestamp = record.get("timestamp", "")

            # Skip empty user messages
            if not text.strip():
                continue

            messages.append(ParsedMessage(
                role="user",
                timestamp=timestamp,
                content=text,
            ))

        elif record_type == "assistant":
            msg = record.get("message", {})
            content_blocks = msg.get("content", [])
            timestamp = record.get("timestamp", "")
            model = msg.get("model")

            text_parts = []
            tool_calls = []
            has_thinking = False
            thinking_text = None

            artifacts = []

            for block in content_blocks:
                block_type = block.get("type")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "tool_use":
                    name = block.get("name", "unknown")
                    inp = block.get("input", {})
                    tool_calls.append({
                        "name": name,
                        "input_preview": _truncate_tool_input(inp),
                    })
                    # Track artifact-producing tools (Write, Edit, NotebookEdit)
                    if name in ("Write", "Edit", "NotebookEdit") and isinstance(inp, dict):
                        file_path = inp.get("file_path", "")
                        if file_path:
                            artifacts.append({
                                "path": file_path,
                                "type": "write" if name == "Write" else "edit",
                                "tool": name,
                            })
                elif block_type == "thinking":
                    has_thinking = True
                    if expand:
                        thinking_text = block.get("thinking", "")

            # Deduplicate artifacts by path (keep last occurrence)
            seen_paths: set[str] = set()
            deduped_artifacts: list[dict] = []
            for a in reversed(artifacts):
                if a["path"] not in seen_paths:
                    seen_paths.add(a["path"])
                    deduped_artifacts.append(a)
            deduped_artifacts.reverse()

            summary = "\n".join(text_parts) if text_parts else None

            # Merge consecutive assistant messages into one turn
            if pending_assistant:
                if summary:
                    existing = pending_assistant.summary or ""
                    pending_assistant.summary = (existing + "\n" + summary).strip() if existing else summary
                pending_assistant.tool_calls.extend(tool_calls)
                pending_assistant.tool_call_count += len(tool_calls)
                # Extend artifacts, dedup by path (keep latest)
                existing_paths = {a["path"] for a in pending_assistant.artifacts}
                for a in deduped_artifacts:
                    if a["path"] not in existing_paths:
                        pending_assistant.artifacts.append(a)
                        existing_paths.add(a["path"])
                if has_thinking:
                    pending_assistant.has_thinking = True
                    if expand and thinking_text:
                        existing_thinking = pending_assistant.thinking or ""
                        pending_assistant.thinking = (existing_thinking + "\n" + thinking_text).strip() if existing_thinking else thinking_text
            else:
                pending_assistant = ParsedMessage(
                    role="assistant",
                    timestamp=timestamp,
                    summary=summary,
                    tool_calls=tool_calls if expand else [],
                    tool_call_count=len(tool_calls),
                    has_thinking=has_thinking,
                    thinking=thinking_text,
                    model=model,
                    artifacts=deduped_artifacts,
                )

        # Skip queue-operation, file-history-snapshot

    # Flush final pending assistant
    if pending_assistant:
        messages.append(pending_assistant)

    return messages


def _is_tool_result(content_blocks) -> bool:
    """Check if content blocks are tool_result (automatic, not user-typed)."""
    if isinstance(content_blocks, list):
        return any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content_blocks
        )
    return False


def _extract_user_text(content_blocks) -> str:
    """Extract text from user message content (string or content blocks)."""
    if isinstance(content_blocks, str):
        return content_blocks
    parts = []
    for block in content_blocks:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def _truncate_tool_input(input_data: dict | str, max_len: int = 200) -> str:
    """Truncate tool input to a preview string."""
    if isinstance(input_data, str):
        text = input_data
    else:
        # For common tools, show the most useful field
        if "command" in input_data:
            text = input_data["command"]
        elif "file_path" in input_data:
            text = input_data["file_path"]
        elif "pattern" in input_data:
            text = input_data["pattern"]
        elif "query" in input_data:
            text = input_data["query"]
        elif "prompt" in input_data:
            text = str(input_data["prompt"])[:100]
        else:
            text = json.dumps(input_data, default=str)

    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
