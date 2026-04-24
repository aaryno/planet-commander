# Audit System Integration Spec: Agent-Commander Patterns in Planet Commander

**Date**: 2026-04-10
**Author**: Aaryn Olsson + Claude
**Status**: Spec Complete — Implementation Tracked via [GitLab Issues](https://hello.planet.com/code/aaryn/claude/-/issues)
**Source**: agent-commander (`~/workspaces/agent-commander/`) audit system patterns
**Target**: Planet Commander (`~/claude/dashboard/`)

## Preamble: Source Code References

This spec is grounded in direct examination of both codebases:

- **Planet Commander** models: `/Users/aaryn/claude/dashboard/backend/app/models/` (19 SQLAlchemy models, EntityLink with 28 LinkType values)
- **Agent-Commander** audit system: `/Users/aaryn/workspaces/agent-commander/src/` (dispatcher.mjs, cta-state.mjs, coach-session.mjs, audits/readiness-dimensions.mjs, audits/change-risk-score.mjs)
- **Review Personas**: `/Users/aaryn/.claude/agents/` (5 agent .md files producing prose markdown)
- **Existing integration pattern**: CLAUDE.md's 5-step entity integration (context_resolver.py, contexts.py API, api.ts types, ContextPanel.tsx, completion artifact)

---

## 1. Finding Object Model

### 1.1 SQLAlchemy Model: `AuditFinding`

File: `backend/app/models/audit_finding.py`

```python
class FindingSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class FindingCategory(str, enum.Enum):
    CODE_QUALITY = "code-quality"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    ADVERSARIAL = "adversarial"
    READINESS = "readiness"
    CHANGE_RISK = "change-risk"
    STALENESS = "staleness"
    SYSTEM = "system"
    CONTEXT = "context"
    # Gap coverage auditors (added 2026-04-14)
    DEAD_CODE = "dead-code"
    DUPLICATION = "duplication"
    ACCURACY = "accuracy"
    SCOPE = "scope"
    OPERATOR_UX = "operator-ux"
    OBSERVABILITY = "observability"
    DOCUMENTATION = "documentation"

class FindingStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    AUTO_FIXED = "auto_fixed"

class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[uuid.UUID]         # PK, gen_random_uuid()
    audit_run_id: Mapped[uuid.UUID]  # FK to audit_runs.id
    
    # Finding identity (mirrors agent-commander finding shape)
    code: Mapped[str]             # String(100), e.g. "CHANGE_RISK_SCORE", "LOW_SCORE_OBJECTIVE_CLARITY"
    category: Mapped[FindingCategory]  # SAEnum
    severity: Mapped[FindingSeverity]  # SAEnum
    confidence: Mapped[str]       # String(20), "high" | "medium" | "low"
    
    # Content
    title: Mapped[str]            # String(500)
    description: Mapped[str]      # Text
    
    # Actionability
    blocking: Mapped[bool]        # Boolean, default=False
    auto_fixable: Mapped[bool]    # Boolean, default=False
    actions: Mapped[dict | None]  # JSONB, list of {type, label, description}
    
    # Status tracking
    status: Mapped[FindingStatus] # SAEnum, default=OPEN
    resolution: Mapped[str | None]  # Text, human/auto resolution text
    resolved_at: Mapped[datetime | None]  # DateTime(tz=True)
    resolved_by: Mapped[str | None]  # String(100), "auto" | "human" | agent name
    
    # Linkage
    related_entity_type: Mapped[str | None]  # String(50), "jira_issue" | "gitlab_merge_request" | etc.
    related_entity_id: Mapped[str | None]    # String(200)
    
    # Source metadata
    source_file: Mapped[str | None]     # String(500), file path where finding occurs
    source_line: Mapped[int | None]     # Integer
    
    created_at: Mapped[datetime]  # DateTime(tz=True), server_default=func.now()
    updated_at: Mapped[datetime]  # DateTime(tz=True), onupdate=func.now()
```

**Indexes:**
- `idx_finding_audit_run` on `audit_run_id`
- `idx_finding_code` on `code`
- `idx_finding_category` on `category`
- `idx_finding_severity` on `severity`
- `idx_finding_status` on `status`
- `idx_finding_entity` on `(related_entity_type, related_entity_id)`

### 1.2 SQLAlchemy Model: `AuditRun`

File: `backend/app/models/audit_run.py`

```python
class AuditVerdict(str, enum.Enum):
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"
    BLOCKED = "blocked"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"

class AuditSource(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    AGENT_REVIEW = "agent_review"
    HYBRID = "hybrid"

class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[uuid.UUID]         # PK
    
    # What was audited
    audit_family: Mapped[str]     # String(100), e.g. "readiness-dimensions", "change-risk-score", "code-quality"
    audit_tier: Mapped[int]       # Integer, 1=fast/deterministic, 2=LLM-assisted, 3=deep
    source: Mapped[AuditSource]   # SAEnum
    
    # Target entity
    target_type: Mapped[str]      # String(50), "jira_issue" | "gitlab_merge_request" | "work_context"
    target_id: Mapped[str]        # String(200)
    
    # Verdict
    verdict: Mapped[AuditVerdict] # SAEnum
    confidence: Mapped[float]     # Float, 0.0-1.0
    
    # Aggregate metrics
    finding_count: Mapped[int]    # Integer, default=0
    blocking_count: Mapped[int]   # Integer, default=0
    auto_fixable_count: Mapped[int]  # Integer, default=0
    error_count: Mapped[int]      # Integer, default=0
    warning_count: Mapped[int]    # Integer, default=0
    
    # Dimension scores (for readiness audits)
    dimension_scores: Mapped[dict | None]  # JSONB, e.g. {"objective_clarity": 2, ...}
    
    # Risk score (for change-risk audits)
    risk_score: Mapped[float | None]  # Float, 0.0-1.0
    risk_level: Mapped[str | None]    # String(20), "low" | "medium" | "high"
    risk_factors: Mapped[dict | None] # JSONB, list of {id, score, detail}
    
    # Execution metadata
    duration_ms: Mapped[int]      # Integer
    model_used: Mapped[str | None]  # String(100), Claude model if LLM audit
    cost_usd: Mapped[float]       # Float, default=0.0
    
    # Raw output (for debugging)
    raw_output: Mapped[str | None]  # Text, original prose or JSON
    
    created_at: Mapped[datetime]  # DateTime(tz=True), server_default=func.now()
```

**Indexes:**
- `idx_audit_run_family` on `audit_family`
- `idx_audit_run_target` on `(target_type, target_id)`
- `idx_audit_run_verdict` on `verdict`
- `idx_audit_run_created` on `created_at`

### 1.3 Pydantic Schemas

File: `backend/app/api/audits.py` (request/response models)

```python
class FindingResponse(BaseModel):
    id: str
    code: str
    category: str
    severity: str
    confidence: str
    title: str
    description: str
    blocking: bool
    auto_fixable: bool
    actions: list[dict] | None
    status: str
    resolution: str | None
    source_file: str | None
    source_line: int | None
    related_entity_type: str | None
    related_entity_id: str | None

class AuditRunResponse(BaseModel):
    id: str
    audit_family: str
    audit_tier: int
    source: str
    target_type: str
    target_id: str
    verdict: str
    confidence: float
    finding_count: int
    blocking_count: int
    auto_fixable_count: int
    dimension_scores: dict | None
    risk_score: float | None
    risk_level: str | None
    risk_factors: list[dict] | None
    duration_ms: int
    findings: list[FindingResponse]
    created_at: str

class RunAuditRequest(BaseModel):
    target_type: str  # "jira_issue" | "gitlab_merge_request"
    target_id: str    # JIRA key or MR UUID
    audit_families: list[str] | None = None  # None = run all applicable
    include_agent: bool = False  # Include LLM-based review persona audits
```

### 1.4 Prose-to-Structured Conversion

The 5 review persona agents currently output prose markdown. Conversion happens in a new service:

File: `backend/app/services/finding_parser.py`

**Strategy:** Each review persona agent is invoked via the existing review skills (review-security, review-architecture, etc.). A post-processing step parses the prose output using regex + LLM-assisted extraction.

Deterministic extraction patterns (try first, avoiding LLM cost):

```python
VERDICT_PATTERN = re.compile(r'\*\*(?:Verdict|Risk Level|Assessment)\*\*:\s*(.+)', re.IGNORECASE)
FINDING_PATTERN = re.compile(
    r'####?\s*\[(CRITICAL|HIGH|MEDIUM|LOW|BLOCKER|SUGGESTION|NIT|CONCERN)\]\s*[---]*\s*(.+)',
    re.IGNORECASE
)
LOCATION_PATTERN = re.compile(r'\*\*Location\*\*:\s*(.+)', re.IGNORECASE)
```

For each detected finding block, the parser emits a `FindingCreateRequest`:
- `code`: Generated from category + title hash, e.g. `SECURITY_SQL_INJECTION_AUTH_HANDLER`
- `severity`: Mapped from persona classification (CRITICAL/BLOCKER -> error, HIGH/CONCERN -> warning, MEDIUM/SUGGESTION -> warning, LOW/NIT -> info)
- `blocking`: True for CRITICAL, HIGH, BLOCKER
- `auto_fixable`: False for all review persona findings (they are advisory)
- `category`: From persona name (security-reviewer -> "security")
- `actions`: `[{"type": "suggest-update", "label": "Fix", "description": "<remediation text>"}]`

**Fallback:** If regex extraction finds fewer than expected findings (based on the count mentioned in the summary), invoke Claude Haiku with a structured extraction prompt to parse the remaining prose. Cost: ~$0.01 per extraction.

### 1.5 EntityLink Integration

New LinkType values to add to the enum:

```python
# In entity_link.py LinkType enum:
AUDITED_BY = "audited_by"          # Entity -> AuditRun
HAS_FINDING = "has_finding"        # AuditRun -> AuditFinding  (redundant with FK but enables graph traversal)
FINDING_FOR = "finding_for"        # AuditFinding -> Entity (reverse)
```

Entity type strings for the link system: `"audit_run"`, `"audit_finding"`

---

## 2. Readiness Dimensions (Adapted for JIRA)

### 2.1 Adaptation from GitHub to JIRA

Agent-commander's `scoreDimensions()` uses GitHub issue markdown conventions (`## Goal`, `## Acceptance Criteria`, etc.). COMPUTE JIRA tickets use a different format:

**JIRA format differences:**
- Description field (not "body") is the main content
- Acceptance criteria is a separate JIRA field (`acceptance_criteria` column on `JiraIssue`)
- Labels are a JSONB column, not GitHub label strings
- No `##` markdown headers in most JIRA tickets; uses plain text or bullet lists
- Fix versions instead of milestones

### 2.2 Scoring Service

File: `backend/app/services/readiness_scorer.py`

```python
def score_dimensions(description: str, acceptance_criteria: str | None, labels: dict | None) -> dict[str, int]:
    """
    Score 8 readiness dimensions for a JIRA ticket.
    Returns dict mapping dimension name -> 0|1|2.
    
    Adapted from agent-commander readiness-dimensions.mjs with JIRA-specific patterns.
    """
    scores = {}
    # Combine description + AC for full body analysis
    full_body = (description or "") + "\n" + (acceptance_criteria or "")
    
    # 1. objective_clarity
    has_goal = bool(re.search(r'(goal|objective|purpose|summary|overview)[:.\s]', full_body, re.I))
    has_outcome = bool(re.search(r'(outcome|deliver|result|should\s+(be|do|have|produce|create|enable))', full_body, re.I))
    body_length = len(full_body)
    if has_goal and has_outcome and body_length > 300:
        scores["objective_clarity"] = 2
    elif has_goal or (has_outcome and body_length > 150):
        scores["objective_clarity"] = 1
    else:
        scores["objective_clarity"] = 0
    
    # 2. target_surface — adapted for Go/Python/Terraform
    has_scope = bool(re.search(r'(scope|target|surface|component|deliverable|affected)', full_body, re.I))
    mentions_files = bool(re.search(r'\.(go|py|tf|yaml|yml|proto|sql|hcl|json)\b', full_body))
    mentions_modules = bool(re.search(
        r'(api|route|endpoint|handler|controller|service|model|schema|migration|crd|operator|deployment|module|resource)',
        full_body, re.I
    ))
    if has_scope and (mentions_files or mentions_modules):
        scores["target_surface"] = 2
    elif has_scope or mentions_files or mentions_modules:
        scores["target_surface"] = 1
    else:
        scores["target_surface"] = 0
    
    # 3. dependencies
    has_deps = bool(re.search(r'(depend|prerequisite|requires|blocked.by|upstream)', full_body, re.I))
    has_deps_detail = has_deps and len(re.findall(r'[-*]\s+.{10,}', full_body)) > 0
    if has_deps and has_deps_detail:
        scores["dependencies"] = 2
    elif has_deps:
        scores["dependencies"] = 1
    else:
        scores["dependencies"] = 0
    
    # 4. acceptance_criteria — JIRA has a dedicated field
    has_ac_field = bool(acceptance_criteria and len(acceptance_criteria.strip()) > 20)
    has_ac_inline = bool(re.search(r'(acceptance|criteria|definition.of.done|done.when)', full_body, re.I))
    has_testable = bool(re.search(r'(should|must|verify|confirm|expect|assert|check|ensure)', full_body, re.I))
    has_bullets = len(re.findall(r'^\s*[-*]\s+.{10,}', acceptance_criteria or "", re.M)) >= 2
    if has_ac_field and has_bullets:
        scores["acceptance_criteria"] = 2
    elif has_ac_field or has_ac_inline or has_testable:
        scores["acceptance_criteria"] = 1
    else:
        scores["acceptance_criteria"] = 0
    
    # 5. validation_path
    has_validation = bool(re.search(r'(validation|test|verification|test.plan|how.to.verify)', full_body, re.I))
    mentions_tests = bool(re.search(r'(test|spec|assert|verify|check|manual.test|automated|e2e|integration)', full_body, re.I))
    if has_validation:
        scores["validation_path"] = 2
    elif mentions_tests:
        scores["validation_path"] = 1
    else:
        scores["validation_path"] = 0
    
    # 6. scope_boundaries
    has_in_scope = bool(re.search(r'(in.scope|scope\b|included|what.this.covers)', full_body, re.I))
    has_out_scope = bool(re.search(r'(out.of.scope|non.goal|not.in.scope|excluded|what.this.does.not)', full_body, re.I))
    if has_in_scope and has_out_scope:
        scores["scope_boundaries"] = 2
    elif has_in_scope or has_out_scope:
        scores["scope_boundaries"] = 1
    else:
        scores["scope_boundaries"] = 0
    
    # 7. missing_decisions
    has_open_questions = bool(re.search(r'(open.question|decision|tbd|unresolved|to.be.determined)', full_body, re.I))
    question_count = len(re.findall(r'\?\s*$', full_body, re.M))
    has_tbd = bool(re.search(r'\bTBD\b|\bTBC\b|\bTBR\b', full_body))
    if has_tbd or has_open_questions:
        scores["missing_decisions"] = 0
    elif question_count > 3:
        scores["missing_decisions"] = 0
    elif question_count > 1:
        scores["missing_decisions"] = 1
    else:
        scores["missing_decisions"] = 2
    
    # 8. execution_safety (depends on 1 and 4)
    has_context = len(full_body) > 400
    has_structure = len(re.findall(r'[-*]\s+', full_body)) >= 3 or len(re.findall(r'\n\n', full_body)) >= 3
    no_major_gaps = scores["objective_clarity"] >= 1 and scores["acceptance_criteria"] >= 1
    if has_context and has_structure and no_major_gaps:
        scores["execution_safety"] = 2
    elif has_context and (has_structure or no_major_gaps):
        scores["execution_safety"] = 1
    else:
        scores["execution_safety"] = 0
    
    return scores
```

### 2.3 Integration with JiraIssue Model

The `JiraIssue` model already has `last_context_audit_id` and `last_acceptance_audit_id` columns (marked "FK to audits (Phase 3)" in comments). These columns map to `AuditRun.id` directly. No schema change needed on `jira_issues`; just start populating those fields.

Additionally, the readiness verdict is stored on the `AuditRun` row itself (verdict, dimension_scores). The latest readiness state for a JIRA issue is always the most recent `AuditRun` where `target_type = 'jira_issue'` and `audit_family = 'readiness-dimensions'`.

---

## 3. Change Risk Score (Adapted for GitLab MRs)

### 3.1 Planet-Specific Risk Patterns

File: `backend/app/services/change_risk_scorer.py`

```python
HIGH_RISK_PATTERNS = [
    # WX OpenAPI
    {"pattern": r"openapi|swagger|api.*spec", "category": "api-contract", "weight": 0.12},
    # G4 CRDs
    {"pattern": r"crd|custom.resource|operator|controller-gen", "category": "crd-change", "weight": 0.15},
    # Terraform IAM
    {"pattern": r"\.tf$|terraform|iam|policy|role|permission", "category": "iam-terraform", "weight": 0.15},
    # Database migrations
    {"pattern": r"migration|alembic|schema.*change|alter\s+table", "category": "migration", "weight": 0.12},
    # Secrets/config
    {"pattern": r"\.env|secret|credential|token|vault", "category": "secrets", "weight": 0.15},
    # Auth/RBAC
    {"pattern": r"auth|rbac|role|permission|middleware", "category": "auth", "weight": 0.12},
    # Deployment
    {"pattern": r"deploy|helmfile|kustomize|argocd|pipeline|ci", "category": "deployment", "weight": 0.08},
    # Proto/gRPC
    {"pattern": r"\.proto$|grpc|protobuf", "category": "grpc-contract", "weight": 0.10},
    # Shared libraries
    {"pattern": r"pkg/|lib/|common/|shared/|internal/", "category": "shared-module", "weight": 0.08},
    # Database
    {"pattern": r"db\.|database|pool|connection|repository", "category": "database", "weight": 0.10},
]

SHARED_MODULE_PATTERNS = [
    r"^pkg/",
    r"^internal/",
    r"^lib/",
    r"^common/",
    r"^shared/",
    r"^cmd/",  # Go main packages
]
```

### 3.2 Input from GitLabMergeRequest Model

The existing `GitLabMergeRequest` model has: `external_mr_id`, `repository`, `source_branch`, `target_branch`, `state`, `jira_keys`, `author`. But it does NOT have diff stats (additions, deletions, changed files).

**Required enrichment:** The `gitlab_mr_sync.py` job must be extended to fetch diff stats from the GitLab API (`GET /projects/:id/merge_requests/:iid/changes`) and store them:

New columns on `GitLabMergeRequest`:
```python
additions: Mapped[int | None]       # Integer
deletions: Mapped[int | None]       # Integer
changed_file_count: Mapped[int | None]  # Integer
changed_files: Mapped[list | None]  # JSONB, list of file paths
```

### 3.3 Risk Computation Function

```python
def compute_change_risk(
    mr: GitLabMergeRequest,
    changed_files: list[str] | None = None,
    additions: int = 0,
    deletions: int = 0,
) -> dict:
    """
    Compute change risk score for a GitLab MR.
    Returns: {score: float, level: str, factors: list[dict]}
    Pure function, no I/O.
    """
    files = changed_files or []
    factors = []
    
    # Factor 1: File count
    file_count = len(files)
    if file_count > 20:
        factors.append({"id": "large-changeset", "score": 0.15, "detail": f"{file_count} files changed"})
    elif file_count > 10:
        factors.append({"id": "medium-changeset", "score": 0.08, "detail": f"{file_count} files changed"})
    
    # Factor 2: Churn
    total_churn = additions + deletions
    if total_churn > 1000:
        factors.append({"id": "high-churn", "score": 0.12, "detail": f"{total_churn} lines changed"})
    elif total_churn > 500:
        factors.append({"id": "medium-churn", "score": 0.06, "detail": f"{total_churn} lines changed"})
    
    # Factor 3: Risk patterns
    matched_categories = set()
    for f in files:
        for rp in HIGH_RISK_PATTERNS:
            if re.search(rp["pattern"], f, re.I) and rp["category"] not in matched_categories:
                matched_categories.add(rp["category"])
                factors.append({"id": f"risk-{rp['category']}", "score": rp["weight"], "detail": f"Touches {rp['category']}: {f}"})
    
    # Factor 4: Shared modules
    shared = [f for f in files if any(re.match(p, f) for p in SHARED_MODULE_PATTERNS)]
    if shared:
        score = min(0.15, len(shared) * 0.05)
        factors.append({"id": "shared-module-blast", "score": score, "detail": f"{len(shared)} shared module(s)"})
    
    # Factor 5: No test files
    test_files = [f for f in files if re.search(r'_test\.go$|test_.*\.py$|\.test\.(ts|js)$|spec\.(ts|js)$', f)]
    source_files = [f for f in files if re.search(r'\.(go|py|ts|js)$', f) and f not in test_files]
    if source_files and not test_files:
        factors.append({"id": "no-test-changes", "score": 0.10, "detail": f"{len(source_files)} source files, no tests"})
    
    total_score = min(1.0, sum(f["score"] for f in factors))
    
    if total_score >= 0.6:
        level = "high"
    elif total_score >= 0.3:
        level = "medium"
    else:
        level = "low"
    
    return {"score": total_score, "level": level, "factors": factors}
```

---

## 4. CTA State Machine

### 4.1 Python Implementation

File: `backend/app/services/cta_engine.py`

```python
from dataclasses import dataclass

@dataclass
class CTAState:
    label: str
    action: str
    subtext: str
    style: str      # "primary-green" | "primary-blue" | "primary-amber" | "primary-default"
    secondary_actions: list[dict]  # [{label, action}]

def is_human_required(finding: dict) -> bool:
    """Determine if a finding requires human input."""
    if finding.get("auto_fixable"):
        return False
    if finding.get("blocking"):
        return True
    human_codes = {
        "NO_TEST_PLAN", "MISSING_ACCEPTANCE_CRITERIA", "NO_SURFACE_IDENTIFIED",
        "INSUFFICIENT_DESCRIPTION", "LOW_SCORE_OBJECTIVE_CLARITY",
        "LOW_SCORE_ACCEPTANCE_CRITERIA", "LOW_SCORE_TARGET_SURFACE",
        "LOW_SCORE_VALIDATION_PATH", "LOW_SCORE_SCOPE_BOUNDARIES",
    }
    code = finding.get("code", "")
    if code in human_codes or code.startswith("LOW_SCORE"):
        return True
    return False

def derive_cta_state(
    readiness: str | None,
    findings: list[dict],
    auto_fixable_count: int = 0,
    blocking_count: int = 0,
) -> CTAState:
    """
    Pure function: readiness snapshot -> single best CTA.
    Mirrors agent-commander cta-state.mjs deriveCtaState().
    """
    diagnostics = [
        {"label": "Re-analyze", "action": "re-analyze"},
        {"label": "View Previous", "action": "view-previous"},
    ]
    
    if readiness is None:
        return CTAState(
            label="Analyze Readiness",
            action="analyze",
            subtext="Score readiness dimensions, run audits",
            style="primary-blue",
            secondary_actions=[],
        )
    
    human_findings = [f for f in findings if is_human_required(f)]
    human_count = len(human_findings)
    is_ready = readiness == "ready"
    
    if is_ready:
        return CTAState(
            label="Ready for Work",
            action="ready",
            subtext="All readiness checks pass",
            style="primary-green",
            secondary_actions=diagnostics,
        )
    
    if auto_fixable_count > 0:
        secondary = list(diagnostics)
        if human_count > 0:
            secondary.append({"label": f"Guide Me ({human_count})", "action": "guide-me"})
        return CTAState(
            label="Fix Issues",
            action="fix-it",
            subtext=f"{auto_fixable_count} auto-fixable, {human_count} need input",
            style="primary-blue",
            secondary_actions=secondary,
        )
    
    if human_count > 0:
        return CTAState(
            label=f"Answer {human_count} Question{'s' if human_count != 1 else ''}",
            action="guide-me",
            subtext=f"{human_count} finding{'s' if human_count != 1 else ''} need your input",
            style="primary-amber",
            secondary_actions=diagnostics,
        )
    
    return CTAState(
        label="Re-analyze",
        action="re-analyze",
        subtext="Check readiness again",
        style="primary-default",
        secondary_actions=diagnostics,
    )
```

### 4.2 CTA in ContextPanel UI

The CTA renders in the ContextHeader component, directly above the tabs. Color mapping:

| style | Tailwind classes |
|-------|-----------------|
| `primary-green` | `bg-emerald-500/20 text-emerald-400 border-emerald-500/30` |
| `primary-blue` | `bg-blue-500/20 text-blue-400 border-blue-500/30` |
| `primary-amber` | `bg-amber-500/20 text-amber-400 border-amber-500/30` |
| `primary-default` | `bg-zinc-700/50 text-zinc-300 border-zinc-600` |

The CTA bar is a new component: `frontend/src/components/audit/CTABar.tsx`

```tsx
interface CTABarProps {
  cta: CTAState;
  onAction: (action: string) => void;
}
```

---

## 5. Coach Sessions

### 5.1 SQLAlchemy Model

File: `backend/app/models/coach_session.py`

```python
class CoachItemStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    BLOCKED = "blocked"

class CoachSession(Base):
    __tablename__ = "coach_sessions"

    id: Mapped[uuid.UUID]              # PK
    
    # What this session is for
    target_type: Mapped[str]           # String(50), "jira_issue"
    target_id: Mapped[str]             # String(200), JIRA key
    
    # Session state
    readiness: Mapped[str]             # String(50), current readiness level
    active_item_id: Mapped[str | None] # String(100), current item being worked
    completed_count: Mapped[int]       # Integer, default=0
    total_count: Mapped[int]           # Integer
    
    # Items stored as JSONB array (same structure as agent-commander)
    items: Mapped[list]                # JSONB, list of HumanAuditItem objects
    
    # Audit run reference
    audit_run_id: Mapped[uuid.UUID | None]  # FK to audit_runs.id
    
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**Indexes:**
- `uq_coach_session_target` unique on `(target_type, target_id)` (one session per target)
- `idx_coach_session_readiness` on `readiness`

### 5.2 API Endpoints

File: `backend/app/api/coach.py`

```python
router = APIRouter(prefix="/coach", tags=["coach"])

# POST /api/coach/sessions
# Create or get coach session for a target
# Body: {target_type, target_id, audit_run_id?}
# Returns: CoachSessionResponse

# GET /api/coach/sessions/{session_id}
# Get session state
# Returns: CoachSessionResponse with items

# POST /api/coach/sessions/{session_id}/items/{item_id}/transition
# Transition item to new status
# Body: {status, resolution?, notes?}
# Returns: {item, next_item, all_done}

# POST /api/coach/sessions/{session_id}/items/{item_id}/respond
# Submit human response to an item (triggers evaluation via Claude API)
# Body: {response: str}
# Returns: {complete, follow_up, summary, suggested_resolution}

# POST /api/coach/sessions/{session_id}/items/{item_id}/explain
# Get explanation for an item (triggers explanation via Claude API)
# Returns: {explanation, recommended_approach, exact_edit, question}

# DELETE /api/coach/sessions/{session_id}
# Delete session

# POST /api/coach/sessions/{session_id}/reconcile
# Reconcile with fresh findings after re-analysis
# Body: {audit_run_id}
# Returns: CoachSessionResponse
```

### 5.3 Frontend Component

File: `frontend/src/components/audit/CoachPanel.tsx`

This is a guided walkthrough component that renders inside a Sheet (slide-over panel) or a dedicated tab. It shows:

1. Progress bar: `{completed}/{total}` items
2. Current item card with:
   - Title and description
   - "Why human required" explanation
   - Recommended question
   - Text input for response
   - "Resolve" / "Defer" / "Skip" buttons
3. Item list sidebar showing all items with status indicators
4. Ability to jump between items

### 5.4 Claude API Integration

The coach session uses Claude API for two operations, both handled server-side:

1. **Explanation prompt** (`buildExplanationPrompt` equivalent): Called when user opens an item. Uses Claude Haiku for cost efficiency. Returns structured JSON.

2. **Evaluation prompt** (`buildEvaluationPrompt` equivalent): Called when user submits a response. Evaluates completeness. Uses Claude Haiku.

Both use the existing `anthropic` Python SDK. The prompts are direct translations from `coach-session.mjs` `buildExplanationPrompt()` and `buildEvaluationPrompt()`.

---

## 6. Audit Dispatcher

### 6.1 Registry Pattern

File: `backend/app/services/audit_dispatcher.py`

```python
from typing import Protocol, Any

class AuditRequest:
    """Input to an audit runner."""
    audit_family: str
    target_type: str
    target_id: str
    # Context data varies by audit type
    jira_issue: JiraIssue | None = None
    merge_request: GitLabMergeRequest | None = None
    work_context: WorkContext | None = None
    # Additional context
    description: str | None = None
    acceptance_criteria: str | None = None
    labels: dict | None = None
    changed_files: list[str] | None = None

class AuditRunner(Protocol):
    """Protocol for audit runners."""
    async def run(self, request: AuditRequest) -> AuditRun: ...
    
    @property
    def audit_family(self) -> str: ...
    
    @property
    def required_context(self) -> str: ...  # "jira_issue" | "gitlab_merge_request" | "any"

# Registry
_audit_registry: dict[str, AuditRunner] = {}

def register_audit(family: str, runner: AuditRunner) -> None:
    _audit_registry[family] = runner

def get_registered_audits() -> list[str]:
    return list(_audit_registry.keys())

async def run_audit(
    db: AsyncSession,
    target_type: str,
    target_id: str,
    families: list[str] | None = None,
) -> list[AuditRun]:
    """Run selected audits against a target. Returns list of AuditRun results."""
    ...

async def assess_readiness(
    db: AsyncSession,
    jira_key: str,
) -> dict:
    """Full readiness assessment for a JIRA issue. Returns merged verdict."""
    ...
```

### 6.2 Built-in Audit Runners

| Runner | Family | Tier | Source | Required Context |
|--------|--------|------|--------|-----------------|
| `ReadinessAuditRunner` | `readiness-dimensions` | 1 | deterministic | jira_issue |
| `ChangeRiskAuditRunner` | `change-risk-score` | 2 | deterministic | gitlab_merge_request |
| `CodeQualityAuditRunner` | `code-quality` | 3 | agent_review | gitlab_merge_request |
| `SecurityAuditRunner` | `security` | 3 | agent_review | gitlab_merge_request |
| `ArchitectureAuditRunner` | `architecture` | 3 | agent_review | gitlab_merge_request |
| `PerformanceAuditRunner` | `performance` | 3 | agent_review | gitlab_merge_request |
| `AdversarialAuditRunner` | `adversarial` | 3 | agent_review | gitlab_merge_request |
| `ObservabilityAuditRunner` | `observability` | 3 | agent_review | gitlab_merge_request |
| `DeadCodeAuditRunner` | `dead-code` | 3 | agent_review | gitlab_merge_request |
| `ScopeAuditRunner` | `scope` | 3 | agent_review | gitlab_merge_request |
| `OperatorUXAuditRunner` | `operator-ux` | 3 | agent_review | gitlab_merge_request |
| `DuplicationAuditRunner` | `duplication` | 3 | agent_review | gitlab_merge_request |
| `AccuracyAuditRunner` | `accuracy` | 3 | agent_review | gitlab_merge_request |
| `DocumentationAuditRunner` | `documentation` | 3 | agent_review | gitlab_merge_request |

### 6.3 Review Persona Mapping

Each of the 11 agents maps to an audit runner:

| Agent File | Audit Family | Severity Mapping |
|------------|--------------|-----------------|
| `code-quality-reviewer.md` | `code-quality` | BLOCKER->error, SUGGESTION->warning, NIT->info |
| `security-reviewer.md` | `security` | CRITICAL->error, HIGH->error, MEDIUM->warning, LOW->info |
| `architecture-reviewer.md` | `architecture` | BLOCKER->error, CONCERN->warning, SUGGESTION->info |
| `performance-reviewer.md` | `performance` | CRITICAL->error, HIGH->warning, MEDIUM->info, LOW->info |
| `adversarial-reviewer.md` | `adversarial` | BLOCKER->error, RISK->warning, CONSIDERATION->info |
| `observability-reviewer.md` | `observability` | BLIND->error, GAP->warning, NOISY->info |
| `dead-code-reviewer.md` | `dead-code` | REMOVE->warning, INVESTIGATE->info, NOTE->info |
| `scope-reviewer.md` | `scope` | SPLIT->error, DEFER->warning, TRACK->info |
| `operator-ux-reviewer.md` | `operator-ux` | CONFUSING->error, FRICTION->warning, POLISH->info |
| `duplication-reviewer.md` | `duplication` | REDUNDANT->warning, OPPORTUNITY->info, ACCEPTABLE->info |
| `accuracy-reviewer.md` | `accuracy` | WRONG->error, STALE->warning, MISLEADING->info |
| `documentation-reviewer.md` | `documentation` | MISSING->error, STRUCTURE->warning, POLISH->info |

The agent review runners invoke the review skills (review-security, review-code-quality, etc.) then parse the prose output into structured findings using `FindingParser`.

### 6.4 Merged Verdict Computation

```python
def compute_merged_verdict(audit_runs: list[AuditRun]) -> dict:
    """Merge findings from multiple audit runs into a single verdict."""
    all_findings = []
    all_dimension_scores = {}
    
    for run in audit_runs:
        all_findings.extend(run.findings)
        if run.dimension_scores:
            all_dimension_scores.update(run.dimension_scores)
    
    blocking_count = sum(1 for f in all_findings if f.blocking)
    auto_fixable_count = sum(1 for f in all_findings if f.auto_fixable)
    
    # Readiness computation
    if blocking_count > 0:
        readiness = "blocked"
    elif all_dimension_scores:
        max_score = len(all_dimension_scores) * 2
        total = sum(all_dimension_scores.values())
        if total >= max_score * 0.75 and blocking_count == 0:
            readiness = "ready"
        elif all_dimension_scores.get("objective_clarity", 0) >= 1:
            readiness = "needs-work"
        else:
            readiness = "exploratory-only"
    else:
        readiness = "needs-work"
    
    return {
        "readiness": readiness,
        "findings": all_findings,
        "dimension_scores": all_dimension_scores,
        "blocking_count": blocking_count,
        "auto_fixable_count": auto_fixable_count,
        "finding_count": len(all_findings),
    }
```

---

## 7. Database Migrations

### 7.1 Migration: Create audit_runs table

File: `backend/alembic/versions/20260409_0100_create_audit_runs.py`

```python
def upgrade():
    # Create audit verdict enum
    op.execute("CREATE TYPE auditverdict AS ENUM ('approved', 'changes_required', 'blocked', 'unverified', 'unknown')")
    op.execute("CREATE TYPE auditsource AS ENUM ('deterministic', 'agent_review', 'hybrid')")
    
    op.create_table(
        'audit_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('audit_family', sa.String(100), nullable=False),
        sa.Column('audit_tier', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source', postgresql.ENUM('deterministic', 'agent_review', 'hybrid', name='auditsource', create_type=False), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(200), nullable=False),
        sa.Column('verdict', postgresql.ENUM('approved', 'changes_required', 'blocked', 'unverified', 'unknown', name='auditverdict', create_type=False), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('finding_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocking_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_fixable_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dimension_scores', postgresql.JSONB(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('risk_factors', postgresql.JSONB(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('raw_output', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_audit_run_family', 'audit_runs', ['audit_family'])
    op.create_index('idx_audit_run_target', 'audit_runs', ['target_type', 'target_id'])
    op.create_index('idx_audit_run_verdict', 'audit_runs', ['verdict'])
    op.create_index('idx_audit_run_created', 'audit_runs', ['created_at'])
```

### 7.2 Migration: Create audit_findings table

File: `backend/alembic/versions/20260409_0105_create_audit_findings.py`

```python
def upgrade():
    op.execute("CREATE TYPE findingseverity AS ENUM ('error', 'warning', 'info')")
    op.execute("CREATE TYPE findingcategory AS ENUM ('code-quality', 'security', 'architecture', 'performance', 'adversarial', 'readiness', 'change-risk', 'staleness', 'system', 'context')")
    op.execute("CREATE TYPE findingstatus AS ENUM ('open', 'resolved', 'deferred', 'rejected', 'auto_fixed')")
    
    op.create_table(
        'audit_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('audit_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('category', postgresql.ENUM(name='findingcategory', create_type=False), nullable=False),
        sa.Column('severity', postgresql.ENUM(name='findingseverity', create_type=False), nullable=False),
        sa.Column('confidence', sa.String(20), nullable=False, server_default="'high'"),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('blocking', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_fixable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('actions', postgresql.JSONB(), nullable=True),
        sa.Column('status', postgresql.ENUM(name='findingstatus', create_type=False), nullable=False, server_default="'open'"),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(100), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.String(200), nullable=True),
        sa.Column('source_file', sa.String(500), nullable=True),
        sa.Column('source_line', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_finding_audit_run', 'audit_findings', ['audit_run_id'])
    op.create_index('idx_finding_code', 'audit_findings', ['code'])
    op.create_index('idx_finding_category', 'audit_findings', ['category'])
    op.create_index('idx_finding_severity', 'audit_findings', ['severity'])
    op.create_index('idx_finding_status', 'audit_findings', ['status'])
    op.create_index('idx_finding_entity', 'audit_findings', ['related_entity_type', 'related_entity_id'])
    
    # Add new LinkType values
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'audited_by'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'has_finding'")
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'finding_for'")
```

### 7.3 Migration: Create coach_sessions table

File: `backend/alembic/versions/20260409_0110_create_coach_sessions.py`

```python
def upgrade():
    op.create_table(
        'coach_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(200), nullable=False),
        sa.Column('readiness', sa.String(50), nullable=False),
        sa.Column('active_item_id', sa.String(100), nullable=True),
        sa.Column('completed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_count', sa.Integer(), nullable=False),
        sa.Column('items', postgresql.JSONB(), nullable=False),
        sa.Column('audit_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('target_type', 'target_id', name='uq_coach_session_target'),
    )
    op.create_index('idx_coach_session_readiness', 'coach_sessions', ['readiness'])
```

### 7.4 Migration: Add diff stats to GitLab MRs

File: `backend/alembic/versions/20260409_0115_add_mr_diff_stats.py`

```python
def upgrade():
    op.add_column('gitlab_merge_requests', sa.Column('additions', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('deletions', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('changed_file_count', sa.Integer(), nullable=True))
    op.add_column('gitlab_merge_requests', sa.Column('changed_files', postgresql.JSONB(), nullable=True))
```

---

## 8. API Endpoints

### 8.1 Audit API

File: `backend/app/api/audits.py`

```python
router = APIRouter(prefix="/audits", tags=["audits"])

# POST /api/audits/run
# Run audits against a target
# Body: RunAuditRequest {target_type, target_id, audit_families?, include_agent?}
# Returns: {audit_runs: list[AuditRunResponse], merged_verdict: MergedVerdictResponse}

# GET /api/audits/runs
# List audit runs with filters
# Query: target_type?, target_id?, audit_family?, limit=20, offset=0
# Returns: {runs: list[AuditRunResponse], total: int}

# GET /api/audits/runs/{run_id}
# Get single audit run with findings
# Returns: AuditRunResponse

# GET /api/audits/findings
# List findings with filters
# Query: target_type?, target_id?, category?, severity?, status?, blocking?, limit=50
# Returns: {findings: list[FindingResponse], total: int}

# PATCH /api/audits/findings/{finding_id}
# Update finding status
# Body: {status, resolution?}
# Returns: FindingResponse

# GET /api/audits/readiness/{jira_key}
# Get current readiness state for JIRA issue
# Returns: ReadinessResponse {readiness, dimension_scores, findings, cta, latest_run_id}

# GET /api/audits/risk/{mr_id}
# Get change risk for a merge request
# Returns: ChangeRiskResponse {score, level, factors, findings}

# GET /api/audits/cta/{target_type}/{target_id}
# Get current CTA state for a target
# Returns: CTAStateResponse {label, action, subtext, style, secondary_actions}
```

### 8.2 Coach API

(See section 5.2 above for coach endpoints)

### 8.3 Integration with Existing Context API

The `ContextResponse` model gains new fields:

```python
class ContextResponse(BaseModel):
    # ... existing fields ...
    audit_runs: list[AuditRunSummaryResponse] = Field(default_factory=list)
    findings_summary: FindingsSummaryResponse | None = None
    readiness: ReadinessSnapshotResponse | None = None
    cta: CTAStateResponse | None = None
```

This follows the 5-step integration pattern: update `ResolvedContext` dataclass, update `context_resolver.py`, update `contexts.py` API, update `api.ts` types, update `ContextPanel.tsx`.

---

## 9. Frontend Components

### 9.1 New Components

| Component | File | Purpose |
|-----------|------|---------|
| `CTABar` | `components/audit/CTABar.tsx` | Primary CTA button + secondary action dropdown |
| `ReadinessRadar` | `components/audit/ReadinessRadar.tsx` | 8-dimension radar chart (or spider chart) |
| `FindingCard` | `components/audit/FindingCard.tsx` | Single finding display with severity badge |
| `FindingsList` | `components/audit/FindingsList.tsx` | Filterable list of findings |
| `AuditRunCard` | `components/audit/AuditRunCard.tsx` | Summary of an audit run |
| `ChangeRiskGauge` | `components/audit/ChangeRiskGauge.tsx` | Visual 0-100% risk meter |
| `CoachPanel` | `components/audit/CoachPanel.tsx` | Guided walkthrough for human items |
| `CoachItemCard` | `components/audit/CoachItemCard.tsx` | Single coach item with Q&A |
| `DimensionScoreBar` | `components/audit/DimensionScoreBar.tsx` | Single dimension 0/1/2 bar |

### 9.2 ContextPanel Integration

Add a new "Audit" tab to the ContextPanel (following the existing tab pattern):

```tsx
<TabsTrigger value="audit" className="flex-1">
  <Shield className="w-3 h-3 mr-1" />
  Audit ({context.findings_summary?.total || 0})
</TabsTrigger>
```

The audit tab content:

1. **CTA Bar** at the top (always visible)
2. **Readiness Radar** showing dimension scores
3. **Findings List** grouped by category, sorted by severity
4. **Change Risk Gauge** (if MR is linked)

### 9.3 Review Page Integration

The existing `/review` page (`frontend/src/app/review/page.tsx`) uses `MRAgentPane` for review agent interaction. The audit system adds a findings overlay:

- After a review persona completes, structured findings appear in a `FindingsList` panel alongside the diff view
- The `MRCenterPane` gains a "Findings" sub-tab showing findings pinned to file locations

### 9.4 Color Semantics

| Element | Severity | Tailwind |
|---------|----------|----------|
| Finding badge | error | `bg-red-500/20 text-red-400` |
| Finding badge | warning | `bg-amber-500/20 text-amber-400` |
| Finding badge | info | `bg-blue-500/20 text-blue-400` |
| Risk gauge | high (>60%) | `bg-red-500` |
| Risk gauge | medium (30-60%) | `bg-amber-500` |
| Risk gauge | low (<30%) | `bg-emerald-500` |
| Dimension bar | 0 | `bg-red-500/40` |
| Dimension bar | 1 | `bg-amber-500/40` |
| Dimension bar | 2 | `bg-emerald-500/40` |

---

## 10. Integration with Review Personas

### 10.1 Agent-to-Runner Mapping

Each review persona skill invocation becomes an `AuditRunner` implementation:

File: `backend/app/services/audit_runners/review_persona_runner.py`

```python
class ReviewPersonaRunner:
    """Base class for review persona audit runners.
    
    Invokes a Claude Code agent with a review persona prompt,
    captures the prose output, parses it into structured findings.
    """
    
    def __init__(self, persona_name: str, audit_family: str):
        self.persona_name = persona_name
        self.audit_family = audit_family
        self.parser = FindingParser(persona_name)
    
    async def run(self, request: AuditRequest) -> AuditRun:
        # 1. Build prompt (diff + persona instructions)
        # 2. Invoke Claude API with persona system prompt
        # 3. Parse prose output into findings
        # 4. Create AuditRun + AuditFinding records
        ...
```

### 10.2 Output Format Conversion

The prose markdown output from each persona follows a documented format (see agent .md files). The `FindingParser` extracts:

1. **Verdict line**: `**Verdict**: APPROVE / NEEDS WORK / DISCUSS` -> `AuditVerdict`
2. **Finding blocks**: Headed by `### Blockers`, `### Suggestions`, `### Nits`, `### Findings` -> individual `AuditFinding` rows
3. **Individual findings**: `#### [SEVERITY] - Title` followed by `**Location**:`, `**Attack**:`, `**Impact**:`, `**Fix**:` -> populated finding fields

### 10.3 Skill Updates

The existing review skills (`review-security`, `review-code-quality`, etc.) do not need modification. They are invoked by the audit runners, which capture their output. However, a new skill should be created:

File: `~/.claude/skills/run-audit.md` -- a skill that runs the full audit pipeline (readiness + risk + optional review personas) and displays structured results.

---

## 11. Implementation Phases

### Phase 1: Foundation (3-4 days)
**Dependencies:** None
**Deliverables:**
- Database migrations for `audit_runs`, `audit_findings`, `coach_sessions`
- SQLAlchemy models: `AuditRun`, `AuditFinding`, `CoachSession`
- Pydantic response schemas
- Model registration in `__init__.py`
- Migration for MR diff stats columns

**GitLab Issues:**
1. **"Add audit_runs and audit_findings database tables"** -- Create Alembic migrations, SQLAlchemy models, register in `__init__.py`. Include indexes and new LinkType enum values. Add diff stats columns to `gitlab_merge_requests`.
2. **"Add coach_sessions database table"** -- Create migration, model, unique constraint on target.

### Phase 2: Readiness Dimensions + CTA (3-4 days)
**Dependencies:** Phase 1
**Deliverables:**
- `readiness_scorer.py` service with `score_dimensions()` adapted for JIRA
- `cta_engine.py` with `derive_cta_state()` pure function
- `ReadinessAuditRunner` class
- API endpoint: `GET /api/audits/readiness/{jira_key}`
- API endpoint: `GET /api/audits/cta/{target_type}/{target_id}`
- Frontend: `DimensionScoreBar`, `ReadinessRadar`, `CTABar` components
- Integration into ContextPanel (audit tab)

**GitLab Issues:**
3. **"Implement readiness dimensions scoring for JIRA tickets"** -- Port `scoreDimensions()` to Python, adapt regex patterns for JIRA markdown format, wire into AuditRun model.
4. **"Implement CTA state machine"** -- Port `deriveCtaState()` to Python, add API endpoints, create CTABar frontend component with color semantics.
5. **"Add readiness radar and dimension bar components"** -- Create frontend components for visualizing 8-dimension scores, integrate into ContextPanel audit tab.

### Phase 3: Change Risk Score (2-3 days)
**Dependencies:** Phase 1, MR diff stats
**Deliverables:**
- `change_risk_scorer.py` service with Planet-specific risk patterns
- `ChangeRiskAuditRunner` class
- Extended `gitlab_mr_sync.py` to fetch diff stats
- API endpoint: `GET /api/audits/risk/{mr_id}`
- Frontend: `ChangeRiskGauge` component
- Integration into ContextPanel for contexts with linked MRs

**GitLab Issues:**
6. **"Enrich GitLab MR sync with diff statistics"** -- Extend `gitlab_mr_sync.py` to fetch additions/deletions/changed_files from GitLab API, populate new columns.
7. **"Implement change risk scorer with Planet-specific patterns"** -- Create `ChangeRiskAuditRunner`, define WX/G4/Terraform risk patterns, compute composite 0-1 score.
8. **"Add change risk gauge component"** -- Create `ChangeRiskGauge` frontend component, integrate into ContextPanel and MR detail views.

### Phase 4: Audit Dispatcher + Finding Model (3-4 days)
**Dependencies:** Phase 1, Phase 2, Phase 3
**Deliverables:**
- `audit_dispatcher.py` with registry pattern
- `finding_parser.py` for prose-to-structured conversion
- Full `POST /api/audits/run` endpoint
- `FindingCard`, `FindingsList` components
- Audit tab in ContextPanel with findings list
- EntityLink integration (audited_by, has_finding links)
- Context resolver integration (5-step pattern)

**GitLab Issues:**
9. **"Implement audit dispatcher with registry pattern"** -- Create dispatcher service, audit runner protocol, context validation, merged verdict computation.
10. **"Create finding parser for review persona prose output"** -- Build regex + fallback LLM extraction pipeline, severity mapping per persona.
11. **"Add findings list UI components"** -- Create FindingCard, FindingsList with filtering by category/severity/status.
12. **"Integrate audits into context resolution (5-step pattern)"** -- Follow Planet Commander's entity integration pattern: update ResolvedContext, context_resolver.py, contexts.py API, api.ts types, ContextPanel.tsx.

### Phase 5: Review Persona Integration (3-4 days)
**Dependencies:** Phase 4
**Deliverables:**
- `ReviewPersonaRunner` base class
- 5 specific runners (code-quality, security, architecture, performance, adversarial)
- Claude API integration for running review personas server-side
- Full audit pipeline: readiness + risk + personas
- `run-audit` skill

**GitLab Issues:**
13. **"Create review persona audit runners"** -- Implement ReviewPersonaRunner base class, 5 concrete runners mapping to existing persona agents, Claude API invocation.
14. **"Build full audit pipeline combining all runners"** -- Wire readiness + risk + persona runners into single `assess_readiness()` call, produce merged verdict.
15. **"Create run-audit skill for CLI invocation"** -- New skill that runs full audit pipeline and displays structured results in terminal.

### Phase 6: Coach Sessions + Investigation (4-5 days)
**Dependencies:** Phase 4
**Deliverables:**
- Coach session API endpoints (create, transition, respond, explain, reconcile)
- Claude API integration for explanation/evaluation prompts
- `CoachPanel`, `CoachItemCard` frontend components
- Sheet/modal integration for guided walkthrough
- Investigation engine stubs (finding-specific repo research prompts)

**GitLab Issues:**
16. **"Implement coach session API"** -- CRUD endpoints, item state machine transitions, session reconciliation after re-analysis.
17. **"Add Claude API integration for coach prompts"** -- Implement explanation and evaluation prompt generators, integrate Anthropic Python SDK.
18. **"Build coach panel frontend component"** -- Create guided walkthrough UI with progress tracking, item navigation, response input, follow-up handling.
19. **"Add investigation engine stubs"** -- Define investigatable finding codes for Planet codebase (nullability, blast radius, verification surface), create prompt templates.

### Total Estimated Effort

| Phase | Days | Cumulative |
|-------|------|-----------|
| Phase 1: Foundation | 3-4 | 3-4 |
| Phase 2: Readiness + CTA | 3-4 | 6-8 |
| Phase 3: Change Risk | 2-3 | 8-11 |
| Phase 4: Dispatcher + Findings | 3-4 | 11-15 |
| Phase 5: Review Personas | 3-4 | 14-19 |
| Phase 6: Coach + Investigation | 4-5 | 18-24 |

**Total: 18-24 working days (4-5 weeks)**

Phases 2 and 3 can run in parallel. Phases 5 and 6 can run in parallel. With parallelization: 14-18 working days (3-4 weeks).

---

### Critical Files for Implementation
- `/Users/aaryn/claude/dashboard/backend/app/models/entity_link.py` -- Must extend LinkType enum with audit link types
- `/Users/aaryn/claude/dashboard/backend/app/services/context_resolver.py` -- Must add audit entity resolution (5-step pattern Step 1)
- `/Users/aaryn/claude/dashboard/backend/app/api/contexts.py` -- Must add audit fields to ContextResponse (5-step pattern Step 2)
- `/Users/aaryn/workspaces/agent-commander/src/audits/readiness-dimensions.mjs` -- Source of truth for dimension scoring logic to port
- `/Users/aaryn/workspaces/agent-commander/src/cta-state.mjs` -- Source of truth for CTA state machine to port