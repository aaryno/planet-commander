"""
Change risk scoring for GitLab merge requests.

Adapted from agent-commander's change-risk-score.mjs for Planet's codebase
(Go, Python, Terraform, Kubernetes, gRPC).

Computes a 0.0-1.0 risk score based on:
  - File-level risk pattern matching (Planet-specific categories)
  - Change size (additions + deletions)
  - Test gap detection (source files without matching test files)
  - Shared module blast radius

Pure function: no I/O, no database access.

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 3.
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Planet-specific high-risk file patterns
# ---------------------------------------------------------------------------

HIGH_RISK_PATTERNS: list[dict[str, Any]] = [
    # WX OpenAPI / Swagger spec changes
    {
        "pattern": r"openapi|swagger|api.*spec",
        "category": "api-contract",
        "weight": 0.12,
        "label": "API contract change",
    },
    # G4 CRD definitions
    {
        "pattern": r"\.crd\.yaml|crd.*\.go|crd.*\.py",
        "category": "crd-definition",
        "weight": 0.15,
        "label": "CRD definition change",
    },
    # Terraform IAM policies
    {
        "pattern": r"\.tf$.*iam|iam.*\.tf$",
        "category": "iam-terraform",
        "weight": 0.15,
        "label": "Terraform IAM change",
    },
    # Database migrations
    {
        "pattern": r"migration|migrate|alembic",
        "category": "database-migration",
        "weight": 0.12,
        "label": "Database migration",
    },
    # Secrets / credentials exposure
    {
        "pattern": r"secret|credential|token|apikey",
        "category": "secrets-exposure",
        "weight": 0.15,
        "label": "Secrets or credential file change",
    },
    # Auth / RBAC boundaries
    {
        "pattern": r"auth|authentication|authorization|rbac",
        "category": "auth-boundary",
        "weight": 0.12,
        "label": "Auth boundary change",
    },
    # Deployment config
    {
        "pattern": r"deploy|helm|kustomize|argocd",
        "category": "deployment-config",
        "weight": 0.08,
        "label": "Deployment configuration change",
    },
    # Proto / gRPC contracts
    {
        "pattern": r"\.proto$|grpc|protobuf",
        "category": "api-protocol",
        "weight": 0.10,
        "label": "gRPC / protobuf contract change",
    },
    # Shared modules (pkg/, internal/, lib/, common/, shared/, cmd/)
    {
        "pattern": r"pkg/|internal/|lib/|common/|shared/|cmd/",
        "category": "shared-module",
        "weight": 0.08,
        "label": "Shared module change",
    },
    # Database schema / model changes
    {
        "pattern": r"schema|model.*\.py|\.sql$",
        "category": "database-schema",
        "weight": 0.10,
        "label": "Database schema or model change",
    },
]

# Compiled regex patterns for each risk category (compiled once at import time)
_COMPILED_PATTERNS: list[tuple[re.Pattern, dict[str, Any]]] = [
    (re.compile(rp["pattern"], re.IGNORECASE), rp)
    for rp in HIGH_RISK_PATTERNS
]

# Test file patterns (Go, Python, TypeScript/JS)
_TEST_FILE_RE = re.compile(
    r"_test\.go$|test_.*\.py$|.*_test\.py$|\.test\.(ts|js)$|\.spec\.(ts|js)$"
)

# Source file patterns
_SOURCE_FILE_RE = re.compile(r"\.(go|py|ts|js)$")


# ---------------------------------------------------------------------------
# Size penalty thresholds
# ---------------------------------------------------------------------------

SIZE_THRESHOLDS: list[dict[str, Any]] = [
    {"min_lines": 1000, "score": 0.10, "label": "very-large-diff"},
    {"min_lines": 500, "score": 0.05, "label": "large-diff"},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_change_risk(
    changed_files: list[str] | None = None,
    additions: int = 0,
    deletions: int = 0,
) -> dict[str, Any]:
    """
    Compute change risk score for a set of changed files and diff stats.

    Pure function -- no I/O, no database access.

    Args:
        changed_files: List of file paths changed in the MR.
        additions: Number of lines added.
        deletions: Number of lines deleted.

    Returns:
        Dict with keys:
          - score (float): 0.0-1.0, capped at 1.0
          - level (str): "low" | "medium" | "high"
          - factors (list[dict]): Each factor has {id, score, detail}
    """
    files = changed_files or []
    factors: list[dict[str, Any]] = []

    # -----------------------------------------------------------------------
    # Factor: Risk pattern matching
    # -----------------------------------------------------------------------
    matched_categories: set[str] = set()
    for filepath in files:
        for compiled, rp in _COMPILED_PATTERNS:
            category = rp["category"]
            if category in matched_categories:
                continue
            if compiled.search(filepath):
                matched_categories.add(category)
                factors.append({
                    "id": f"risk-{category}",
                    "score": rp["weight"],
                    "detail": f"Touches {rp['label']}: {filepath}",
                })

    # -----------------------------------------------------------------------
    # Factor: Size penalty for large diffs
    # -----------------------------------------------------------------------
    total_churn = additions + deletions
    for threshold in SIZE_THRESHOLDS:
        if total_churn > threshold["min_lines"]:
            factors.append({
                "id": threshold["label"],
                "score": threshold["score"],
                "detail": f"{total_churn} lines changed (>{threshold['min_lines']})",
            })
            break  # Only apply the highest matching threshold

    # -----------------------------------------------------------------------
    # Factor: Test gap detection
    # -----------------------------------------------------------------------
    test_files = [f for f in files if _TEST_FILE_RE.search(f)]
    source_files = [
        f for f in files
        if _SOURCE_FILE_RE.search(f) and not _TEST_FILE_RE.search(f)
    ]
    if source_files and not test_files:
        factors.append({
            "id": "no-test-changes",
            "score": 0.10,
            "detail": f"{len(source_files)} source file(s) changed, no test files",
        })

    # -----------------------------------------------------------------------
    # Compute total score (capped at 1.0)
    # -----------------------------------------------------------------------
    total_score = min(1.0, sum(f["score"] for f in factors))

    # -----------------------------------------------------------------------
    # Determine risk level
    # -----------------------------------------------------------------------
    if total_score >= 0.6:
        level = "high"
    elif total_score >= 0.3:
        level = "medium"
    else:
        level = "low"

    return {
        "score": round(total_score, 3),
        "level": level,
        "factors": factors,
    }


def build_risk_findings(
    risk_result: dict[str, Any],
    mr_identifier: str,
) -> list[dict[str, Any]]:
    """
    Generate structured finding dicts from a risk computation result.

    Produces one AuditFinding-shaped dict per risk factor, plus an overall
    risk summary finding. Suitable for direct persistence to audit_findings.

    Args:
        risk_result: Output of compute_change_risk().
        mr_identifier: MR identifier string for entity linkage.

    Returns:
        List of finding dicts ready for AuditFinding creation.
    """
    findings: list[dict[str, Any]] = []
    score = risk_result["score"]
    level = risk_result["level"]
    factors = risk_result["factors"]

    # Overall risk finding
    if level == "high":
        severity = "error"
    elif level == "medium":
        severity = "warning"
    else:
        severity = "info"

    findings.append({
        "code": "CHANGE_RISK_SCORE",
        "category": "change-risk",
        "severity": severity,
        "confidence": "high",
        "title": f"Change risk: {level} ({score:.2f})",
        "description": (
            f"Composite change risk score is {score:.2f} ({level}). "
            f"{len(factors)} risk factor(s) detected."
        ),
        "blocking": level == "high",
        "auto_fixable": False,
        "actions": None,
        "status": "open",
        "related_entity_type": "gitlab_merge_request",
        "related_entity_id": mr_identifier,
    })

    # Individual factor findings
    for factor in factors:
        factor_severity = "warning" if factor["score"] >= 0.10 else "info"
        findings.append({
            "code": f"RISK_FACTOR_{factor['id'].upper().replace('-', '_')}",
            "category": "change-risk",
            "severity": factor_severity,
            "confidence": "high",
            "title": factor["detail"],
            "description": (
                f"Risk factor '{factor['id']}' contributed {factor['score']:.2f} "
                f"to the composite score."
            ),
            "blocking": False,
            "auto_fixable": False,
            "actions": None,
            "status": "open",
            "related_entity_type": "gitlab_merge_request",
            "related_entity_id": mr_identifier,
        })

    return findings
