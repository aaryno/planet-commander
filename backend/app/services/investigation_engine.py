"""Investigation engine for agent-assisted resolution of audit findings.

Defines investigatable finding codes and provides prompt templates for
deeper analysis using Claude Sonnet. Investigations produce structured
JSON with `analysis` + `draft` fields — drafts are markdown text ready
to paste into JIRA ticket fields.

Budget: max 15 turns per investigation, $0.50 cost cap.
Model: Claude Sonnet (investigations need deeper reasoning than coaching).
"""

import json
import logging
import time
from typing import Any

import anthropic

from app.services.coach_prompts import _get_api_key, _extract_tool_result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model & budget configuration
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-20250514"

# Timeout for API calls (seconds) — longer than coaching prompts
API_TIMEOUT = 60.0

# Budget caps
MAX_TURNS = 15
MAX_COST_USD = 0.50

# Sonnet pricing (as of 2025)
SONNET_INPUT_COST_PER_MTOK = 3.00    # $3.00 per million input tokens
SONNET_OUTPUT_COST_PER_MTOK = 15.00  # $15.00 per million output tokens


# ---------------------------------------------------------------------------
# Investigatable finding definitions
# ---------------------------------------------------------------------------

INVESTIGATABLE_FINDINGS: dict[str, dict[str, Any]] = {
    "LOW_SCORE_OBJECTIVE_CLARITY": {
        "description": "Issue lacks clear goal or objective statement",
        "investigation": "Read issue scope and related context, draft a Goal section",
        "output_fields": ["outcomes", "draft"],
        "prompt_template": (
            "You are investigating a JIRA issue that scored low on Objective Clarity.\n\n"
            "The issue lacks a clear goal or objective statement — it's unclear what\n"
            "success looks like when this work is complete.\n\n"
            "ISSUE KEY: {jira_key}\n"
            "ISSUE TITLE: {title}\n"
            "ISSUE DESCRIPTION:\n{description}\n\n"
            "REPO CONTEXT (if available):\n{repo_info}\n\n"
            "Your task:\n"
            "1. Analyze the issue description and extract the implied intent\n"
            "2. Identify measurable outcomes that would signal completion\n"
            "3. Draft a **Goal** section in markdown, suitable for prepending to the issue body\n\n"
            "The draft must be specific enough that any engineer could read it and know\n"
            "when the work is done. Avoid vague goals like 'improve performance' — instead\n"
            "say 'reduce p99 latency from 2s to 500ms for /api/tasks endpoint'.\n\n"
            "Use the provide_investigation_result tool to respond."
        ),
    },
    "LOW_SCORE_TARGET_SURFACE": {
        "description": "Issue doesn't specify affected files or modules",
        "investigation": "Analyze repo structure, identify affected files and modules",
        "output_fields": ["target_files", "modules", "draft"],
        "prompt_template": (
            "You are investigating a JIRA issue that scored low on Target Surface.\n\n"
            "The issue doesn't specify which files, modules, or services will be\n"
            "modified. This makes it hard to assess scope, risk, and reviewers.\n\n"
            "ISSUE KEY: {jira_key}\n"
            "ISSUE TITLE: {title}\n"
            "ISSUE DESCRIPTION:\n{description}\n\n"
            "REPO CONTEXT (if available):\n{repo_info}\n\n"
            "Your task:\n"
            "1. From the issue description, infer what changes are needed\n"
            "2. Identify the likely affected files and modules (be specific: paths, packages)\n"
            "3. Note any cross-service or cross-repo dependencies\n"
            "4. Draft a **Target Surface** section in markdown listing:\n"
            "   - Files to modify (with paths)\n"
            "   - Modules/packages affected\n"
            "   - Services impacted\n\n"
            "If the repo context is available, use it to ground your analysis in actual\n"
            "file paths rather than guesses.\n\n"
            "Use the provide_investigation_result tool to respond."
        ),
    },
    "LOW_SCORE_VALIDATION_PATH": {
        "description": "No test plan or verification strategy specified",
        "investigation": "Find test patterns in repo, draft a test plan",
        "output_fields": ["test_patterns", "draft"],
        "prompt_template": (
            "You are investigating a JIRA issue that scored low on Validation Path.\n\n"
            "The issue has no test plan or verification strategy — it's unclear how to\n"
            "confirm the work is correct after implementation.\n\n"
            "ISSUE KEY: {jira_key}\n"
            "ISSUE TITLE: {title}\n"
            "ISSUE DESCRIPTION:\n{description}\n\n"
            "REPO CONTEXT (if available):\n{repo_info}\n\n"
            "Your task:\n"
            "1. Identify what kind of testing is appropriate for this change\n"
            "   (unit tests, integration tests, manual QA, load testing, etc.)\n"
            "2. If repo context is available, identify existing test patterns and conventions\n"
            "3. Draft a **Test Plan** section in markdown with:\n"
            "   - Test categories needed (unit, integration, e2e, manual)\n"
            "   - Specific test cases to write (describe inputs, expected outputs)\n"
            "   - Verification steps for manual testing\n"
            "   - Rollback verification (how to confirm rollback works if needed)\n\n"
            "Be specific — name the test file to create, the function to test, and the\n"
            "assertions to make. Generic 'write unit tests' is not helpful.\n\n"
            "Use the provide_investigation_result tool to respond."
        ),
    },
    "LOW_SCORE_SCOPE_BOUNDARIES": {
        "description": "Scope boundaries not defined (what's in/out)",
        "investigation": "Analyze issue scope, draft in-scope and out-of-scope sections",
        "output_fields": ["scope_analysis", "draft"],
        "prompt_template": (
            "You are investigating a JIRA issue that scored low on Scope Boundaries.\n\n"
            "The issue doesn't clearly define what is in-scope and what is out-of-scope.\n"
            "This risks scope creep, over-engineering, or missed expectations.\n\n"
            "ISSUE KEY: {jira_key}\n"
            "ISSUE TITLE: {title}\n"
            "ISSUE DESCRIPTION:\n{description}\n\n"
            "REPO CONTEXT (if available):\n{repo_info}\n\n"
            "Your task:\n"
            "1. Analyze the issue description to identify the core deliverable\n"
            "2. Identify likely scope-creep risks (related work that could be pulled in)\n"
            "3. Identify things that might seem in-scope but should be deferred\n"
            "4. Draft a **Scope** section in markdown with:\n"
            "   - **In Scope**: Bulleted list of what this ticket covers\n"
            "   - **Out of Scope**: Bulleted list of what this ticket does NOT cover\n"
            "   - **Future Work**: Items to create follow-up tickets for\n\n"
            "Be opinionated about scope — err on the side of keeping the ticket small\n"
            "and deferring related work to follow-up tickets.\n\n"
            "Use the provide_investigation_result tool to respond."
        ),
    },
    "MISSING_BLAST_RADIUS": {
        "description": "Impact of changes not analyzed",
        "investigation": "Trace callers and consumers of modified functions",
        "output_fields": ["affected_paths", "draft"],
        "prompt_template": (
            "You are investigating a JIRA issue where the blast radius is not analyzed.\n\n"
            "The issue describes changes but hasn't mapped out what other systems,\n"
            "services, or consumers will be affected by those changes.\n\n"
            "ISSUE KEY: {jira_key}\n"
            "ISSUE TITLE: {title}\n"
            "ISSUE DESCRIPTION:\n{description}\n\n"
            "REPO CONTEXT (if available):\n{repo_info}\n\n"
            "Your task:\n"
            "1. Identify the functions, APIs, or interfaces being modified\n"
            "2. Trace upstream callers and downstream consumers\n"
            "3. Identify cross-service impacts (other repos, services, pipelines)\n"
            "4. Assess risk level for each affected path\n"
            "5. Draft a **Blast Radius** section in markdown with:\n"
            "   - **Direct Changes**: What this ticket modifies\n"
            "   - **Upstream Impact**: Callers that depend on modified interfaces\n"
            "   - **Downstream Impact**: Consumers of modified outputs\n"
            "   - **Cross-Service**: Other services/repos affected\n"
            "   - **Risk Assessment**: High/Medium/Low with justification\n\n"
            "Use the provide_investigation_result tool to respond."
        ),
    },
}


# ---------------------------------------------------------------------------
# Tool definition for structured output
# ---------------------------------------------------------------------------

INVESTIGATION_TOOL = {
    "name": "provide_investigation_result",
    "description": "Provide the structured result of an investigation into an audit finding.",
    "input_schema": {
        "type": "object",
        "properties": {
            "analysis": {
                "type": "string",
                "description": (
                    "Detailed analysis of the finding — what was discovered, "
                    "key observations, and reasoning behind the draft."
                ),
            },
            "draft": {
                "type": "string",
                "description": (
                    "Markdown text ready to paste into JIRA ticket fields. "
                    "Should be a complete section (## heading + content) that "
                    "can be appended to the issue description."
                ),
            },
            "metadata": {
                "type": "object",
                "description": (
                    "Additional structured data from the investigation. "
                    "Keys depend on finding code — e.g. target_files, modules, "
                    "test_patterns, affected_paths, outcomes, scope_analysis."
                ),
            },
        },
        "required": ["analysis", "draft", "metadata"],
    },
}


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def _estimate_cost(usage: Any) -> dict:
    """Calculate estimated cost from API usage data (Sonnet pricing)."""
    input_tokens = getattr(usage, "input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    input_cost = (input_tokens / 1_000_000) * SONNET_INPUT_COST_PER_MTOK
    output_cost = (output_tokens / 1_000_000) * SONNET_OUTPUT_COST_PER_MTOK
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(input_cost + output_cost, 6),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_investigatable(finding_code: str) -> bool:
    """Check whether a finding code has an investigation defined.

    Args:
        finding_code: The finding code to check (e.g. "LOW_SCORE_OBJECTIVE_CLARITY")

    Returns:
        True if the finding code can be investigated by the engine.
    """
    return finding_code in INVESTIGATABLE_FINDINGS


def get_investigation_spec(finding_code: str) -> dict | None:
    """Get the investigation specification for a finding code.

    Args:
        finding_code: The finding code to look up.

    Returns:
        Dict with description, investigation, output_fields, and prompt_template,
        or None if the finding code is not investigatable.
    """
    spec = INVESTIGATABLE_FINDINGS.get(finding_code)
    if spec is None:
        return None
    # Return a copy so callers can't mutate the registry
    return {
        "code": finding_code,
        "description": spec["description"],
        "investigation": spec["investigation"],
        "output_fields": list(spec["output_fields"]),
    }


async def investigate_finding(finding_code: str, context: dict) -> dict:
    """Run an investigation for a specific finding code.

    Uses Claude Sonnet to analyze the finding in context and produce
    a structured result with analysis and JIRA-ready draft text.

    Args:
        finding_code: The finding code to investigate.
        context: Dict with keys:
            - jira_key: JIRA issue key (e.g. "COMPUTE-1234")
            - title: Issue title
            - description: Issue body text
            - repo_info: Optional repo structure / context string

    Returns:
        Dict with keys: analysis, draft, metadata, cost_usd, model, turns_used

    Raises:
        ValueError: If finding_code is not investigatable or API key is unavailable.
        RuntimeError: If budget cap ($0.50) is exceeded.
    """
    if finding_code not in INVESTIGATABLE_FINDINGS:
        raise ValueError(
            f"Finding code '{finding_code}' is not investigatable. "
            f"Valid codes: {sorted(INVESTIGATABLE_FINDINGS.keys())}"
        )

    spec = INVESTIGATABLE_FINDINGS[finding_code]

    # Build the prompt from template
    prompt_vars = {
        "jira_key": context.get("jira_key", "(unknown)"),
        "title": context.get("title", "(untitled)"),
        "description": context.get("description", "(no description)"),
        "repo_info": context.get("repo_info", "(no repo context available)"),
    }
    user_message = spec["prompt_template"].format(**prompt_vars)

    # Get API client
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Anthropic API key not available. "
            "Set ANTHROPIC_API_KEY environment variable or add 'anthropic-api-key' to macOS Keychain."
        )
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=API_TIMEOUT)

    system_prompt = (
        "You are an investigation agent for Planet's audit system. "
        "Your job is to deeply analyze audit findings and produce actionable "
        "drafts that can be pasted directly into JIRA tickets.\n\n"
        "Rules:\n"
        "- Be specific and concrete — name files, functions, endpoints\n"
        "- Draft sections must be valid markdown with proper headings\n"
        "- Prefer action over discussion\n"
        "- Keep drafts concise but complete\n"
        "- Include concrete examples where possible\n"
        "- The metadata field should contain structured data matching the "
        f"expected output fields: {spec['output_fields']}"
    )

    # Single-turn investigation (prompt is self-contained)
    start_time = time.monotonic()
    total_cost_usd = 0.0
    turns_used = 0

    messages = [{"role": "user", "content": user_message}]

    # Agentic loop: allow up to MAX_TURNS in case the model needs
    # to refine its answer (unlikely for single-shot, but safe)
    final_result: dict = {}

    for turn in range(MAX_TURNS):
        turns_used += 1

        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=[INVESTIGATION_TOOL],
            tool_choice={"type": "tool", "name": "provide_investigation_result"},
            messages=messages,
        )

        # Track cost
        usage = _estimate_cost(response.usage)
        total_cost_usd += usage["estimated_cost_usd"]

        # Budget check
        if total_cost_usd > MAX_COST_USD:
            logger.warning(
                "Investigation budget exceeded: $%.4f > $%.2f after %d turns for %s",
                total_cost_usd, MAX_COST_USD, turns_used, finding_code,
            )
            raise RuntimeError(
                f"Investigation budget exceeded: ${total_cost_usd:.4f} > ${MAX_COST_USD:.2f}. "
                f"Stopped after {turns_used} turns."
            )

        # Extract result
        final_result = _extract_tool_result(response, "provide_investigation_result")

        # If we got a valid result with both analysis and draft, we're done
        if final_result.get("analysis") and final_result.get("draft"):
            break

        # If the model didn't produce a valid result, we could retry,
        # but with tool_choice forced, this shouldn't happen. Break anyway.
        logger.warning(
            "Investigation turn %d for %s produced incomplete result, stopping",
            turns_used, finding_code,
        )
        break

    elapsed = time.monotonic() - start_time

    logger.info(
        "investigate_finding completed in %.2fs | turns=%d | cost=$%.4f | code=%s",
        elapsed, turns_used, total_cost_usd, finding_code,
    )

    return {
        "analysis": final_result.get("analysis", ""),
        "draft": final_result.get("draft", ""),
        "metadata": final_result.get("metadata", {}),
        "cost_usd": round(total_cost_usd, 6),
        "model": MODEL,
        "turns_used": turns_used,
    }
