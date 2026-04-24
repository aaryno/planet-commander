"""
Readiness dimensions scoring for JIRA tickets.

Adapted from agent-commander's readiness-dimensions.mjs for JIRA ticket format.
Scores 8 dimensions (0/1/2 each) using regex pattern matching against the
ticket's description, acceptance_criteria, and labels fields.

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 2.
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Dimension names (ordered)
# ---------------------------------------------------------------------------
DIMENSION_NAMES = [
    "objective_clarity",
    "target_surface",
    "acceptance_criteria",
    "dependencies",
    "validation_path",
    "scope_boundaries",
    "missing_decisions",
    "execution_safety",
]

# Maximum score per dimension
MAX_PER_DIMENSION = 2

# ---------------------------------------------------------------------------
# Guidance text for low-scoring dimensions (used by findings)
# ---------------------------------------------------------------------------
DIMENSION_GUIDANCE: dict[str, dict[str, str]] = {
    "objective_clarity": {
        "title": "Objective clarity is low",
        "description": (
            "The ticket does not clearly state its goal, objective, or expected outcome. "
            "Add a short summary explaining *what* this ticket delivers and *why* it matters."
        ),
    },
    "target_surface": {
        "title": "Target surface is unclear",
        "description": (
            "The ticket does not identify which files, modules, endpoints, or components "
            "will be touched. List the affected services, file paths, or infrastructure "
            "resources so reviewers can assess blast radius."
        ),
    },
    "acceptance_criteria": {
        "title": "Acceptance criteria are missing or weak",
        "description": (
            "The ticket lacks testable acceptance criteria. Add bullet-pointed criteria "
            "starting with 'should', 'must', or 'verify' so that completion is unambiguous."
        ),
    },
    "dependencies": {
        "title": "Dependencies are not documented",
        "description": (
            "The ticket references dependencies or prerequisites but does not provide "
            "enough detail. List upstream tickets, services, or approvals that must be "
            "in place before work can begin."
        ),
    },
    "validation_path": {
        "title": "Validation path is missing",
        "description": (
            "There is no test plan or verification strategy described. Specify how the "
            "change will be validated -- unit tests, integration tests, manual verification, "
            "or staging deployment checks."
        ),
    },
    "scope_boundaries": {
        "title": "Scope boundaries are not defined",
        "description": (
            "The ticket does not distinguish what is in scope from what is out of scope. "
            "Add explicit 'in scope' and 'out of scope' sections to prevent scope creep."
        ),
    },
    "missing_decisions": {
        "title": "Open questions or TBDs remain",
        "description": (
            "The ticket contains unresolved questions, TBD markers, or open decisions. "
            "Resolve these before starting implementation to avoid mid-flight pivots."
        ),
    },
    "execution_safety": {
        "title": "Execution safety is low",
        "description": (
            "The ticket lacks sufficient structure and context for safe execution. "
            "Ensure the objective is clear, acceptance criteria are defined, and the "
            "description is detailed enough for an implementer to work confidently."
        ),
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_dimensions(
    description: str,
    acceptance_criteria: str | None = None,
    labels: dict[str, Any] | None = None,
) -> dict[str, int]:
    """
    Score 8 readiness dimensions for a JIRA ticket.

    Returns a dict mapping dimension name -> 0 | 1 | 2.

    Adapted from agent-commander readiness-dimensions.mjs with JIRA-specific
    patterns (no ## headers, separate acceptance_criteria field, JSONB labels).

    Args:
        description: The JIRA ticket description (main body text).
        acceptance_criteria: Separate JIRA AC field (may be None).
        labels: JSONB labels dict from JiraIssue model (may be None).

    Returns:
        Dict of 8 dimension names to integer scores (0, 1, or 2).
    """
    scores: dict[str, int] = {}

    # Combine description + AC for full body analysis
    full_body = (description or "") + "\n" + (acceptance_criteria or "")

    # 1. objective_clarity ------------------------------------------------
    has_goal = bool(re.search(
        r"(goal|objective|purpose|summary|overview)[:.\s]",
        full_body, re.I,
    ))
    has_outcome = bool(re.search(
        r"(outcome|deliver|result|should\s+(be|do|have|produce|create|enable))",
        full_body, re.I,
    ))
    body_length = len(full_body)

    if has_goal and has_outcome and body_length > 300:
        scores["objective_clarity"] = 2
    elif has_goal or (has_outcome and body_length > 150):
        scores["objective_clarity"] = 1
    else:
        scores["objective_clarity"] = 0

    # 2. target_surface -- adapted for Go/Python/Terraform ----------------
    has_scope = bool(re.search(
        r"(scope|target|surface|component|deliverable|affected)",
        full_body, re.I,
    ))
    mentions_files = bool(re.search(
        r"\.(go|py|tf|yaml|yml|proto|sql|hcl|json)\b",
        full_body,
    ))
    mentions_modules = bool(re.search(
        r"(api|route|endpoint|handler|controller|service|model|schema|"
        r"migration|crd|operator|deployment|module|resource)",
        full_body, re.I,
    ))

    if has_scope and (mentions_files or mentions_modules):
        scores["target_surface"] = 2
    elif has_scope or mentions_files or mentions_modules:
        scores["target_surface"] = 1
    else:
        scores["target_surface"] = 0

    # 3. acceptance_criteria -- JIRA has a dedicated field -----------------
    has_ac_field = bool(
        acceptance_criteria and len(acceptance_criteria.strip()) > 20
    )
    has_ac_inline = bool(re.search(
        r"(acceptance|criteria|definition.of.done|done.when)",
        full_body, re.I,
    ))
    has_testable = bool(re.search(
        r"(should|must|verify|confirm|expect|assert|check|ensure)",
        full_body, re.I,
    ))
    has_bullets = (
        len(re.findall(r"^\s*[-*]\s+.{10,}", acceptance_criteria or "", re.M))
        >= 2
    )

    if has_ac_field and has_bullets:
        scores["acceptance_criteria"] = 2
    elif has_ac_field or has_ac_inline or has_testable:
        scores["acceptance_criteria"] = 1
    else:
        scores["acceptance_criteria"] = 0

    # 4. dependencies -----------------------------------------------------
    has_deps = bool(re.search(
        r"(depend|prerequisite|requires|blocked.by|upstream)",
        full_body, re.I,
    ))
    has_deps_detail = has_deps and len(
        re.findall(r"[-*]\s+.{10,}", full_body)
    ) > 0

    if has_deps and has_deps_detail:
        scores["dependencies"] = 2
    elif has_deps:
        scores["dependencies"] = 1
    else:
        scores["dependencies"] = 0

    # 5. validation_path --------------------------------------------------
    has_validation = bool(re.search(
        r"(validation|test|verification|test.plan|how.to.verify)",
        full_body, re.I,
    ))
    mentions_tests = bool(re.search(
        r"(test|spec|assert|verify|check|manual.test|automated|e2e|integration)",
        full_body, re.I,
    ))

    if has_validation:
        scores["validation_path"] = 2
    elif mentions_tests:
        scores["validation_path"] = 1
    else:
        scores["validation_path"] = 0

    # 6. scope_boundaries -------------------------------------------------
    has_in_scope = bool(re.search(
        r"(in.scope|scope\b|included|what.this.covers)",
        full_body, re.I,
    ))
    has_out_scope = bool(re.search(
        r"(out.of.scope|non.goal|not.in.scope|excluded|what.this.does.not)",
        full_body, re.I,
    ))

    if has_in_scope and has_out_scope:
        scores["scope_boundaries"] = 2
    elif has_in_scope or has_out_scope:
        scores["scope_boundaries"] = 1
    else:
        scores["scope_boundaries"] = 0

    # 7. missing_decisions ------------------------------------------------
    has_open_questions = bool(re.search(
        r"(open.question|decision|tbd|unresolved|to.be.determined)",
        full_body, re.I,
    ))
    question_count = len(re.findall(r"\?\s*$", full_body, re.M))
    has_tbd = bool(re.search(r"\bTBD\b|\bTBC\b|\bTBR\b", full_body))

    if has_tbd or has_open_questions:
        # Unresolved questions/TBDs penalize this dimension
        scores["missing_decisions"] = 0
    elif question_count > 3:
        scores["missing_decisions"] = 0
    elif question_count > 1:
        scores["missing_decisions"] = 1
    else:
        scores["missing_decisions"] = 2

    # 8. execution_safety (depends on objective_clarity and acceptance_criteria)
    has_context = len(full_body) > 400
    has_structure = (
        len(re.findall(r"[-*]\s+", full_body)) >= 3
        or len(re.findall(r"\n\n", full_body)) >= 3
    )
    no_major_gaps = (
        scores["objective_clarity"] >= 1
        and scores["acceptance_criteria"] >= 1
    )

    if has_context and has_structure and no_major_gaps:
        scores["execution_safety"] = 2
    elif has_context and (has_structure or no_major_gaps):
        scores["execution_safety"] = 1
    else:
        scores["execution_safety"] = 0

    return scores


def compute_readiness_verdict(scores: dict[str, int]) -> str:
    """
    Map aggregate dimension scores to an AuditVerdict string.

    Verdict thresholds:
      - "approved"          : total >= 75% of max AND no dimension at 0
      - "changes_required"  : objective_clarity >= 1 (workable but needs improvement)
      - "blocked"           : objective_clarity == 0 (cannot safely begin work)

    Args:
        scores: Dict of dimension name -> 0|1|2 from score_dimensions().

    Returns:
        One of: "approved", "changes_required", "blocked"
    """
    if not scores:
        return "blocked"

    max_score = len(scores) * MAX_PER_DIMENSION
    total = sum(scores.values())
    has_zero = any(v == 0 for v in scores.values())

    # High readiness: 75%+ and no zeros
    if total >= max_score * 0.75 and not has_zero:
        return "approved"

    # Workable but needs improvement
    if scores.get("objective_clarity", 0) >= 1:
        return "changes_required"

    # Cannot safely begin work
    return "blocked"


def build_readiness_findings(
    scores: dict[str, int],
    jira_key: str,
) -> list[dict[str, Any]]:
    """
    Generate structured finding dicts for low-scoring dimensions.

    Each finding follows the AuditFinding shape so it can be persisted
    directly to the audit_findings table.

    Findings are created for dimensions scoring 0 (error) or 1 (warning).
    Dimensions scoring 2 produce no findings.

    Args:
        scores: Dict of dimension name -> 0|1|2 from score_dimensions().
        jira_key: The JIRA issue key (e.g. "COMPUTE-2059") for entity linkage.

    Returns:
        List of finding dicts ready for AuditFinding creation.
    """
    findings: list[dict[str, Any]] = []

    for dimension, score in scores.items():
        if score >= 2:
            continue

        guidance = DIMENSION_GUIDANCE.get(dimension, {})
        dim_upper = dimension.upper()
        code = f"LOW_SCORE_{dim_upper}"

        severity = "error" if score == 0 else "warning"
        blocking = score == 0 and dimension in (
            "objective_clarity",
            "acceptance_criteria",
        )

        finding = {
            "code": code,
            "category": "readiness",
            "severity": severity,
            "confidence": "high",
            "title": guidance.get("title", f"{dimension} scored {score}/2"),
            "description": guidance.get(
                "description",
                f"Dimension '{dimension}' scored {score}/2. Review and improve.",
            ),
            "blocking": blocking,
            "auto_fixable": False,
            "actions": [
                {
                    "type": "suggest-update",
                    "label": "Improve",
                    "description": guidance.get("description", ""),
                }
            ],
            "status": "open",
            "related_entity_type": "jira_issue",
            "related_entity_id": jira_key,
        }
        findings.append(finding)

    return findings


def compute_readiness_confidence(scores: dict[str, int]) -> float:
    """
    Compute a 0.0-1.0 confidence value for the readiness verdict.

    Confidence is based on the proportion of max possible score achieved.
    Higher scores = higher confidence in the verdict.

    Args:
        scores: Dict of dimension name -> 0|1|2 from score_dimensions().

    Returns:
        Float between 0.0 and 1.0.
    """
    if not scores:
        return 0.0
    max_score = len(scores) * MAX_PER_DIMENSION
    total = sum(scores.values())
    return round(total / max_score, 2) if max_score > 0 else 0.0
