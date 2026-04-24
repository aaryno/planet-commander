"""Claude API integration for coach session explanation and evaluation prompts.

Provides two async functions that call the Claude API to:
1. Explain a coach item (what needs attention, suggested approach)
2. Evaluate a user's response (completeness assessment)

Uses claude-haiku-4-5-20251001 for cost efficiency. API key is loaded from
the ANTHROPIC_API_KEY environment variable or macOS Keychain.
"""

import json
import logging
import os
import subprocess
import time
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# Model selection: Haiku for cost efficiency on coaching prompts
MODEL = "claude-haiku-4-5-20251001"

# Timeout for API calls (seconds)
API_TIMEOUT = 30.0

# Approximate cost per token (Haiku pricing as of 2025)
HAIKU_INPUT_COST_PER_MTOK = 0.80   # $0.80 per million input tokens
HAIKU_OUTPUT_COST_PER_MTOK = 4.00  # $4.00 per million output tokens


def _get_api_key() -> str | None:
    """Load Anthropic API key. Tries: env var -> macOS Keychain.

    Returns None if no key is available (graceful degradation).
    """
    # 1. Environment variable (standard for Anthropic SDK)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. macOS Keychain (Planet convention)
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "anthropic-api-key", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def _get_client() -> anthropic.AsyncAnthropic:
    """Create an async Anthropic client with the available API key.

    Raises ValueError if no API key is available.
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Anthropic API key not available. "
            "Set ANTHROPIC_API_KEY environment variable or add 'anthropic-api-key' to macOS Keychain: "
            "security add-generic-password -s 'anthropic-api-key' -a 'aaryn' -w 'sk-ant-...'"
        )
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=API_TIMEOUT)


def _estimate_cost(usage: Any) -> dict:
    """Calculate estimated cost from API usage data."""
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    input_cost = (input_tokens / 1_000_000) * HAIKU_INPUT_COST_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * HAIKU_OUTPUT_COST_PER_MTOK
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(input_cost + output_cost, 6),
    }


# ---------------------------------------------------------------------------
# Tool definitions for structured output
# ---------------------------------------------------------------------------

EXPLANATION_TOOL = {
    "name": "provide_explanation",
    "description": "Provide a structured explanation of a coach audit item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "2-3 sentence explanation of what this audit item checks and why it matters for readiness.",
            },
            "recommended_approach": {
                "type": "string",
                "description": "One decisive recommendation for how to resolve this finding. Be specific -- name the section to add, the text to write, or the decision to make.",
            },
            "exact_edit": {
                "type": ["string", "null"],
                "description": "The exact markdown text that should be added to or changed in the issue body to resolve this finding. Copy-pasteable content, not instructions. Null if the finding requires a human decision that cannot be pre-drafted.",
            },
            "question": {
                "type": "string",
                "description": "The question to ask the user after presenting the recommendation.",
            },
        },
        "required": ["explanation", "recommended_approach", "question"],
    },
}

EVALUATION_TOOL = {
    "name": "provide_evaluation",
    "description": "Evaluate whether a user's response adequately addresses an audit item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "complete": {
                "type": "boolean",
                "description": "True if the user gave enough information to resolve this audit item, or explicitly deferred.",
            },
            "follow_up": {
                "type": ["string", "null"],
                "description": "A follow-up question if incomplete, or null if complete.",
            },
            "summary": {
                "type": "string",
                "description": "1-2 sentence summary of what the user decided.",
            },
            "suggested_resolution": {
                "type": "string",
                "description": "Text that could be added to the issue body to address this finding. Actual content, not instructions.",
            },
        },
        "required": ["complete", "summary", "suggested_resolution"],
    },
}


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

EXPLANATION_SYSTEM_PROMPT = """\
You are a readiness coach for software engineering work items. Your role is to \
help humans understand audit findings and take action to resolve them.

You will be given an audit item (a finding from an automated readiness check) \
and context about the issue it belongs to. Your job is to:

1. Explain what the audit item checks and why it matters
2. Provide one decisive recommendation (not a list of options)
3. Draft exact text to add to the issue if possible
4. Ask a focused question to guide the human's response

Be concise, practical, and opinionated. Prefer action over discussion.\
"""

EVALUATION_SYSTEM_PROMPT = """\
You are evaluating a user's response to an audit question for a software work item.

Rules:
- "complete" = true if the user gave enough information to resolve this audit item
- "complete" = true if the user explicitly defers ("skip", "later", "don't know", "N/A")
- If the user defers, summarize the deferral
- follow_up should be null if complete=true
- suggested_resolution should be the actual text to add, not instructions
- Keep summary concise (1-2 sentences)\
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def explain_item(
    item: dict,
    issue_context: dict | None = None,
) -> dict:
    """Generate an explanation and recommended approach for a coach item.

    Args:
        item: Coach item dict with keys: title, description, code, category, severity, blocking
        issue_context: Optional dict with keys: jira_key, title, description

    Returns:
        dict with keys: explanation, recommended_approach, exact_edit, question, usage
    """
    issue_context = issue_context or {}
    issue_title = issue_context.get("title", "(untitled)")
    issue_body = issue_context.get("description", "")

    user_message = f"""AUDIT ITEM: {item.get("title", "")}
FINDING CODE: {item.get("code", "")}
CATEGORY: {item.get("category", "general")}
SEVERITY: {item.get("severity", "unknown")}
BLOCKING: {item.get("blocking", False)}
DESCRIPTION: {item.get("description", "")}

ISSUE: {issue_context.get("jira_key", "")} - {issue_title}

RELEVANT ISSUE CONTEXT (truncated):
{(issue_body or "")[:3000]}

Use the provide_explanation tool to respond."""

    start_time = time.monotonic()
    client = _get_client()

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=EXPLANATION_SYSTEM_PROMPT,
        tools=[EXPLANATION_TOOL],
        tool_choice={"type": "tool", "name": "provide_explanation"},
        messages=[{"role": "user", "content": user_message}],
    )

    elapsed = time.monotonic() - start_time
    usage = _estimate_cost(response.usage)

    # Extract tool use result
    result = _extract_tool_result(response, "provide_explanation")

    logger.info(
        "explain_item completed in %.2fs | tokens=%d | cost=$%.6f | item=%s",
        elapsed,
        usage["total_tokens"],
        usage["estimated_cost_usd"],
        item.get("code", "unknown"),
    )

    return {
        "explanation": result.get("explanation", ""),
        "recommended_approach": result.get("recommended_approach", ""),
        "exact_edit": result.get("exact_edit"),
        "question": result.get("question", ""),
        "usage": usage,
    }


async def evaluate_response(
    item: dict,
    user_response: str,
    issue_context: dict | None = None,
) -> dict:
    """Evaluate whether a user's response adequately addresses a coach item.

    Args:
        item: Coach item dict with keys: title, description, code, category, severity, blocking
        user_response: The user's text response to the coaching question
        issue_context: Optional dict with keys: jira_key, title, description

    Returns:
        dict with keys: complete, follow_up, summary, suggested_resolution, usage
    """
    issue_context = issue_context or {}
    issue_title = issue_context.get("title", "(untitled)")

    # Build conversation history if available
    conversation_text = ""
    conversation = item.get("conversation", [])
    if conversation:
        conversation_text = f"\nPREVIOUS CONVERSATION:\n" + "\n".join(conversation) + "\n"

    user_message = f"""AUDIT ITEM: {item.get("title", "")}
FINDING CODE: {item.get("code", "")}
DESCRIPTION: {item.get("description", "")}
BLOCKING: {item.get("blocking", False)}

ISSUE: {issue_context.get("jira_key", "")} - {issue_title}

QUESTION ASKED: {item.get("recommended_question", item.get("description", ""))}

USER'S RESPONSE: {user_response}
{conversation_text}
Use the provide_evaluation tool to respond."""

    start_time = time.monotonic()
    client = _get_client()

    response = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=EVALUATION_SYSTEM_PROMPT,
        tools=[EVALUATION_TOOL],
        tool_choice={"type": "tool", "name": "provide_evaluation"},
        messages=[{"role": "user", "content": user_message}],
    )

    elapsed = time.monotonic() - start_time
    usage = _estimate_cost(response.usage)

    # Extract tool use result
    result = _extract_tool_result(response, "provide_evaluation")

    logger.info(
        "evaluate_response completed in %.2fs | tokens=%d | cost=$%.6f | item=%s | complete=%s",
        elapsed,
        usage["total_tokens"],
        usage["estimated_cost_usd"],
        item.get("code", "unknown"),
        result.get("complete", "?"),
    )

    return {
        "complete": result.get("complete", False),
        "follow_up": result.get("follow_up"),
        "summary": result.get("summary", ""),
        "suggested_resolution": result.get("suggested_resolution", ""),
        "usage": usage,
    }


def _extract_tool_result(response: Any, tool_name: str) -> dict:
    """Extract the tool use input from a Claude API response.

    Falls back to parsing text content if no tool use block is found.
    """
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input if isinstance(block.input, dict) else {}

    # Fallback: try to parse text content as JSON
    for block in response.content:
        if block.type == "text":
            try:
                # Try to find JSON in the text
                text = block.text.strip()
                fence_match = None
                if "```" in text:
                    import re
                    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
                if fence_match:
                    text = fence_match.group(1).strip()
                return json.loads(text)
            except (json.JSONDecodeError, ValueError):
                pass

    logger.warning("No tool use result found for %s, returning empty dict", tool_name)
    return {}
