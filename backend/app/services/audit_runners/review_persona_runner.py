"""Review persona audit runners that invoke Claude API with agent system prompts.

Each runner loads a review persona definition from ~/.claude/agents/{persona}.md,
builds a user prompt from MR diff data, calls the Claude API, and parses the
prose response into structured AuditFinding dicts via finding_parser.

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 10
Issue: aaryn/claude#14
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import anthropic

from app.services.audit_dispatcher import AuditRequest, AuditRunResult, register_audit
from app.services.finding_parser import extract_verdict, parse_review_output

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Agent definitions directory
AGENTS_DIR = Path.home() / ".claude" / "agents"

# API timeout for review calls (reviews can be lengthy)
API_TIMEOUT = 120.0

# Cost per million tokens by model family
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (input_cost_per_mtok, output_cost_per_mtok)
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-6": (15.0, 75.0),
}

# Verdict mapping: raw prose verdict text -> AuditVerdict value
# Covers all 5 persona verdict formats
VERDICT_MAP: dict[str, str] = {
    # code-quality: Verdict
    "approve": "approved",
    "needs work": "changes_required",
    "discuss": "changes_required",
    # security: Risk Level
    "clear": "approved",
    "low risk": "approved",
    "medium risk": "changes_required",
    "high risk": "changes_required",
    "critical": "blocked",
    # architecture: Assessment
    "sound": "approved",
    "concerns": "changes_required",
    "needs redesign": "blocked",
    # performance: Impact
    "watch": "changes_required",
    "needs fix": "changes_required",
    # adversarial: Risk Profile
    "low": "approved",
    "moderate": "changes_required",
    "high": "changes_required",
    "do not merge": "blocked",
}

# Default confidence by persona (Opus models get higher confidence)
PERSONA_CONFIDENCE: dict[str, float] = {
    "code-quality": 0.80,
    "security": 0.90,
    "architecture": 0.85,
    "performance": 0.80,
    "adversarial": 0.90,
}


# ---------------------------------------------------------------------------
# API key loading (shared with coach_prompts.py pattern)
# ---------------------------------------------------------------------------


def _get_api_key() -> str | None:
    """Load Anthropic API key. Tries: env var -> macOS Keychain."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

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
    """Create an async Anthropic client."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "Anthropic API key not available. "
            "Set ANTHROPIC_API_KEY env var or add 'anthropic-api-key' to macOS Keychain."
        )
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=API_TIMEOUT)


# ---------------------------------------------------------------------------
# System prompt loading
# ---------------------------------------------------------------------------


def _load_system_prompt(persona_name: str) -> str:
    """Load a persona system prompt from ~/.claude/agents/{persona_name}.md.

    Strips the YAML front matter (between --- markers) and returns the
    markdown body as the system prompt.

    Args:
        persona_name: Agent file name without extension (e.g. "code-quality-reviewer").

    Returns:
        The system prompt text.

    Raises:
        FileNotFoundError: If the agent definition file doesn't exist.
    """
    agent_file = AGENTS_DIR / f"{persona_name}.md"
    if not agent_file.exists():
        raise FileNotFoundError(
            f"Agent definition not found: {agent_file}"
        )

    content = agent_file.read_text(encoding="utf-8")

    # Strip YAML front matter (between --- markers)
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            # parts[0] = empty, parts[1] = YAML front matter, parts[2] = body
            return parts[2].strip()

    return content.strip()


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Estimate USD cost from token counts and model.

    Returns:
        Estimated cost in USD, rounded to 6 decimal places.
    """
    costs = MODEL_COSTS.get(model, (3.0, 15.0))  # default to Sonnet pricing
    input_cost = (input_tokens / 1_000_000) * costs[0]
    output_cost = (output_tokens / 1_000_000) * costs[1]
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# User prompt template
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """\
## Merge Request Review

**Repository**: {repository}
**Title**: {title}
**Author**: {author}
**Target Branch**: {target_branch}

### Description
{description}

### Changed Files ({changed_file_count} files, +{additions}/-{deletions})
{file_list}

### Diff Summary
{diff_or_file_details}

Please review this merge request according to your review guidelines."""


def _build_user_prompt(request: AuditRequest) -> str:
    """Build the user prompt from MR data in the AuditRequest.

    Extracts merge request metadata and changed file information to
    populate the review prompt template.
    """
    mr = request.merge_request or {}

    # Build file list
    changed_files = mr.get("changed_files", []) or request.changed_files or []
    if changed_files:
        file_list = "\n".join(f"- `{f}`" for f in changed_files)
    else:
        file_list = "(no file list available)"

    # Try to get actual diff content from review orchestrator
    from app.services.review_orchestrator import get_diff_override
    injected_diff = get_diff_override(mr.get("id", ""))

    if injected_diff:
        max_diff_chars = 80_000
        if len(injected_diff) > max_diff_chars:
            diff_or_file_details = injected_diff[:max_diff_chars] + "\n\n... (diff truncated)"
        else:
            diff_or_file_details = injected_diff
    elif changed_files:
        # Fallback: group by directory for a summary view
        dirs: dict[str, list[str]] = {}
        for f in changed_files:
            parts = f.rsplit("/", 1)
            d = parts[0] if len(parts) > 1 else "."
            dirs.setdefault(d, []).append(parts[-1] if len(parts) > 1 else f)

        diff_lines: list[str] = []
        for d, files in sorted(dirs.items()):
            diff_lines.append(f"**{d}/**: {', '.join(files)}")
        diff_or_file_details = "\n".join(diff_lines)
    else:
        diff_or_file_details = "(no diff data available)"

    return USER_PROMPT_TEMPLATE.format(
        repository=mr.get("repository", "(unknown)"),
        title=mr.get("title", "(untitled)"),
        author=mr.get("author", "(unknown)"),
        target_branch=mr.get("target_branch", "main"),
        description=mr.get("description", "(no description)") or "(no description)",
        changed_file_count=mr.get("changed_file_count", len(changed_files)),
        additions=mr.get("additions", 0),
        deletions=mr.get("deletions", 0),
        file_list=file_list,
        diff_or_file_details=diff_or_file_details,
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class ReviewPersonaRunner:
    """Base class for review persona audit runners.

    Implements the AuditRunner protocol. Loads a persona system prompt from
    the agent definition file, calls the Claude API with MR data, and parses
    the prose output into structured findings.

    Subclasses set class attributes: audit_family, persona_name, model.
    """

    audit_family: str = ""
    required_context: list[str] = ["gitlab_merge_request"]
    persona_name: str = ""
    model: str = "claude-sonnet-4-6"

    def __init__(self) -> None:
        """Initialize the runner and load the system prompt."""
        if not self.persona_name:
            raise ValueError(
                f"{self.__class__.__name__} must set persona_name"
            )
        self._system_prompt = _load_system_prompt(self.persona_name)
        logger.info(
            "Loaded system prompt for %s (%d chars)",
            self.persona_name,
            len(self._system_prompt),
        )

    @property
    def system_prompt(self) -> str:
        """The loaded system prompt text."""
        return self._system_prompt

    async def run(self, request: AuditRequest) -> AuditRunResult:
        """Execute the review persona against MR data.

        Steps:
          1. Build user prompt from MR diff data.
          2. Call Claude API with system_prompt + user prompt.
          3. Parse prose output via finding_parser.parse_review_output().
          4. Extract verdict via finding_parser.extract_verdict().
          5. Map verdict text to AuditVerdict enum value.
          6. Return AuditRunResult with findings, verdict, cost tracking.

        Returns:
            AuditRunResult with structured findings and metadata.
        """
        assert request.merge_request is not None, (
            f"{self.__class__.__name__} requires gitlab_merge_request context"
        )

        # 1. Build user prompt
        user_prompt = _build_user_prompt(request)

        # 2. Call Claude API
        t0 = time.monotonic()
        try:
            client = _get_client()
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self._system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ),
                timeout=API_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                "%s timed out after %.0fs", self.audit_family, API_TIMEOUT
            )
            return AuditRunResult(
                verdict="unverified",
                confidence=0.0,
                findings=[],
                model_used=self.model,
                raw_output=f"Timeout after {API_TIMEOUT}s",
            )
        except Exception as exc:
            logger.exception("%s API call failed: %s", self.audit_family, exc)
            return AuditRunResult(
                verdict="unverified",
                confidence=0.0,
                findings=[],
                model_used=self.model,
                raw_output=f"API error: {exc}",
            )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Extract raw prose from response
        raw_output = ""
        for block in response.content:
            if block.type == "text":
                raw_output += block.text

        # Track token usage
        input_tokens = getattr(response.usage, "input_tokens", 0)
        output_tokens = getattr(response.usage, "output_tokens", 0)
        cost_usd = _estimate_cost(self.model, input_tokens, output_tokens)

        logger.info(
            "%s completed in %dms | tokens: %d in, %d out | cost: $%.6f",
            self.audit_family,
            elapsed_ms,
            input_tokens,
            output_tokens,
            cost_usd,
        )

        # 3. Parse findings from prose
        findings = parse_review_output(raw_output, self.persona_name)

        # 4. Extract verdict text
        verdict_text = extract_verdict(raw_output)

        # 5. Map verdict to AuditVerdict value
        verdict = "unverified"
        if verdict_text:
            normalized = verdict_text.strip().lower()
            verdict = VERDICT_MAP.get(normalized, "unverified")
            logger.debug(
                "%s verdict: %r -> %s", self.audit_family, verdict_text, verdict
            )

        # 6. Return result
        confidence = PERSONA_CONFIDENCE.get(self.audit_family, 0.80)

        return AuditRunResult(
            verdict=verdict,
            confidence=confidence,
            findings=findings,
            duration_ms=elapsed_ms,
            model_used=self.model,
            cost_usd=cost_usd,
            raw_output=raw_output,
        )


# ---------------------------------------------------------------------------
# Concrete runners
# ---------------------------------------------------------------------------


class CodeQualityRunner(ReviewPersonaRunner):
    """Code quality review persona (Sonnet)."""

    audit_family = "code-quality"
    persona_name = "code-quality-reviewer"
    model = "claude-sonnet-4-6"


class SecurityRunner(ReviewPersonaRunner):
    """Security review persona (Opus)."""

    audit_family = "security"
    persona_name = "security-reviewer"
    model = "claude-opus-4-6"


class ArchitectureRunner(ReviewPersonaRunner):
    """Architecture review persona (Opus)."""

    audit_family = "architecture"
    persona_name = "architecture-reviewer"
    model = "claude-opus-4-6"


class PerformanceRunner(ReviewPersonaRunner):
    """Performance review persona (Sonnet)."""

    audit_family = "performance"
    persona_name = "performance-reviewer"
    model = "claude-sonnet-4-6"


class AdversarialRunner(ReviewPersonaRunner):
    """Adversarial review persona (Opus)."""

    audit_family = "adversarial"
    persona_name = "adversarial-reviewer"
    model = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------


def _register_persona_runners() -> None:
    """Register all review persona runners at module import time.

    Gracefully handles missing agent definition files by logging a
    warning instead of raising, so the app can start even if some
    persona files are absent.
    """
    runner_classes = [
        CodeQualityRunner,
        SecurityRunner,
        ArchitectureRunner,
        PerformanceRunner,
        AdversarialRunner,
    ]

    for cls in runner_classes:
        try:
            runner = cls()
            register_audit(runner)
        except FileNotFoundError as exc:
            logger.warning(
                "Skipping %s registration: %s", cls.__name__, exc
            )
        except Exception as exc:
            logger.warning(
                "Failed to register %s: %s", cls.__name__, exc
            )


_register_persona_runners()
