"""
CTA (Call-to-Action) state machine for Planet Commander audit system.

Pure function: readiness snapshot -> single best action with color semantics.
Ported from agent-commander's cta-state.mjs deriveCtaState().

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 4.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

STYLE_GREEN = "primary-green"
STYLE_BLUE = "primary-blue"
STYLE_AMBER = "primary-amber"
STYLE_DEFAULT = "primary-default"


# ---------------------------------------------------------------------------
# CTAState dataclass
# ---------------------------------------------------------------------------


@dataclass
class CTAState:
    """Represents a single call-to-action derived from audit state.

    Attributes:
        label: Button text displayed to the user.
        action: Machine-readable action identifier (e.g. "analyze", "fix-it").
        subtext: Short explanation shown below the button.
        style: Color style key for the UI.  One of:
            "primary-green", "primary-blue", "primary-amber", "primary-default".
        secondary_actions: List of alternative actions, each a dict with
            ``label`` (display text) and ``action`` (machine action id).
    """

    label: str
    action: str
    subtext: str
    style: str
    secondary_actions: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Finding codes that require human input
# ---------------------------------------------------------------------------

_HUMAN_REQUIRED_CODES: frozenset[str] = frozenset({
    "NO_TEST_PLAN",
    "MISSING_ACCEPTANCE_CRITERIA",
    "NO_SURFACE_IDENTIFIED",
    "INSUFFICIENT_DESCRIPTION",
    "LOW_SCORE_OBJECTIVE_CLARITY",
    "LOW_SCORE_ACCEPTANCE_CRITERIA",
    "LOW_SCORE_TARGET_SURFACE",
    "LOW_SCORE_VALIDATION_PATH",
    "LOW_SCORE_SCOPE_BOUNDARIES",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_human_required(finding: dict) -> bool:
    """Determine if a finding requires human input.

    A finding is human-required when it is NOT auto-fixable AND either:
      - it is blocking, or
      - its code is in the known human-required set, or
      - its code starts with ``LOW_SCORE``.

    Args:
        finding: A finding dict (or dict-like) with keys ``auto_fixable``,
            ``blocking``, and ``code``.

    Returns:
        True if a human must resolve this finding.
    """
    if finding.get("auto_fixable"):
        return False
    if finding.get("blocking"):
        return True

    code = finding.get("code", "")
    if code in _HUMAN_REQUIRED_CODES or code.startswith("LOW_SCORE"):
        return True

    return False


def derive_cta_state(
    readiness: str | None,
    findings: list[dict],
    auto_fixable_count: int = 0,
    blocking_count: int = 0,
) -> CTAState:
    """Derive the single best CTA from a readiness snapshot.

    This is a **pure function** -- same inputs always produce the same output.
    No I/O, no database calls.

    Priority order:
      1. No snapshot (readiness is None) -> style=blue, action="analyze"
      2. Ready (readiness == "ready")    -> style=green, action="ready"
      3. Auto-fixable findings exist     -> style=blue, action="fix-it"
      4. Human-required findings exist   -> style=amber, action="guide-me"
      5. Fallback                        -> style=default, action="re-analyze"

    Secondary actions are always available once a snapshot exists.

    Args:
        readiness: Current readiness level string, or None if no snapshot.
            Known values: "ready", "needs-work", "exploratory-only", "blocked".
        findings: List of finding dicts. Each must have at least ``code``,
            ``auto_fixable``, and ``blocking`` keys.
        auto_fixable_count: Number of auto-fixable findings (from AuditRun).
        blocking_count: Number of blocking findings (from AuditRun).

    Returns:
        A CTAState representing the single best action.
    """
    # Diagnostics -- always available when a snapshot exists
    diagnostics: list[dict[str, str]] = [
        {"label": "Re-analyze", "action": "re-analyze"},
        {"label": "View Previous", "action": "view-previous"},
    ]

    # ----- Priority 1: No snapshot -----
    if readiness is None:
        return CTAState(
            label="Analyze Readiness",
            action="analyze",
            subtext="Score readiness dimensions, run audits",
            style=STYLE_BLUE,
            secondary_actions=[],
        )

    # Count human-required findings
    human_findings = [f for f in findings if is_human_required(f)]
    human_count = len(human_findings)

    # ----- Priority 2: All clear -----
    is_ready = readiness == "ready"
    if is_ready:
        return CTAState(
            label="Ready for Work",
            action="ready",
            subtext="All readiness checks pass",
            style=STYLE_GREEN,
            secondary_actions=list(diagnostics),
        )

    # ----- Priority 3: Auto-fixable findings -----
    if auto_fixable_count > 0:
        secondary = list(diagnostics)
        if human_count > 0:
            secondary.append(
                {"label": f"Guide Me ({human_count})", "action": "guide-me"}
            )
        return CTAState(
            label="Fix Issues",
            action="fix-it",
            subtext=f"{auto_fixable_count} auto-fixable, {human_count} need input",
            style=STYLE_BLUE,
            secondary_actions=secondary,
        )

    # ----- Priority 4: Human-required findings -----
    if human_count > 0:
        plural = "s" if human_count != 1 else ""
        return CTAState(
            label=f"Answer {human_count} Question{plural}",
            action="guide-me",
            subtext=f"{human_count} finding{plural} need your input",
            style=STYLE_AMBER,
            secondary_actions=list(diagnostics),
        )

    # ----- Priority 5: Fallback -----
    return CTAState(
        label="Re-analyze",
        action="re-analyze",
        subtext="Check readiness again",
        style=STYLE_DEFAULT,
        secondary_actions=list(diagnostics),
    )
