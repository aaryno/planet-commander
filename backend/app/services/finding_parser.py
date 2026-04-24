"""Finding parser for review persona prose output.

Converts prose markdown from the 5 review persona agents into structured
AuditFinding dicts. Uses regex-based deterministic extraction first,
with a fallback to Claude Haiku for edge cases.

Spec reference: dashboard/AUDIT-SYSTEM-SPEC.md section 1.4
Issue: aaryn/claude#11
"""
import re
from typing import Any

from app.models.audit_finding import FindingCategory, FindingSeverity

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches verdict/risk/assessment/impact lines across all 5 personas:
#   code-quality:  **Verdict**: APPROVE / NEEDS WORK / DISCUSS
#   security:      **Risk Level**: CLEAR / LOW RISK / MEDIUM RISK / HIGH RISK / CRITICAL
#   architecture:  **Assessment**: SOUND / CONCERNS / NEEDS REDESIGN
#   performance:   **Impact**: CLEAR / WATCH / NEEDS FIX
#   adversarial:   **Risk Profile**: LOW / MODERATE / HIGH / DO NOT MERGE
VERDICT_PATTERN = re.compile(
    r"\*\*(?:Verdict|Risk\s*Level|Assessment|Impact|Risk\s*Profile)\*\*\s*:\s*(.+)",
    re.IGNORECASE,
)

# Matches individual finding headers across all personas:
#   security:    #### [CRITICAL] — Title
#   code-quality: uses section headers + bullet items (handled separately)
#   architecture: uses section headers + bullet items (handled separately)
#   performance:  uses section headers + bullet items (handled separately)
#   adversarial: #### [SHOWSTOPPER] — Title
#
# The heading may use ### or ####, brackets or not, and --- or — as separator.
FINDING_PATTERN = re.compile(
    r"^#{3,4}\s*\[?"
    r"(CRITICAL|HIGH|MEDIUM|LOW|BLOCKER|SUGGESTION|NIT|CONCERN|"
    r"SHOWSTOPPER|HIGH\s*RISK|RISK|NOTED|WARNING|OPTIMIZATION)"
    r"\]?\s*[-–—]+\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches file location lines within a finding block:
#   **Location**: path/to/file.py:42
#   **Location**: path/to/file.py
LOCATION_PATTERN = re.compile(
    r"\*\*Location\*\*\s*:\s*(.+)",
    re.IGNORECASE,
)

# Matches section headers that group findings by category:
#   ### Blockers
#   ### Suggestions
#   ### Nits
#   ### Findings
#   ### Warnings
#   ### Concerns
#   ### Optimizations
#   ### Failure Modes Found
SECTION_PATTERN = re.compile(
    r"^#{2,3}\s*(Blockers?|Suggestions?|Nits?|Findings?|Warnings?|Concerns?"
    r"|Optimizations?|Failure\s+Modes?\s+Found)$",
    re.IGNORECASE | re.MULTILINE,
)

# Sections that should NOT produce findings (informational sections in review output)
NON_FINDING_SECTIONS = re.compile(
    r"^#{2,3}\s*(What'?s\s+Done\s+Well|Design\s+Decisions?|Attack\s+Surface\s+Changes?"
    r"|Not\s+In\s+Scope|Affected\s+Contracts?|Hot\s+Path\s+Assessment"
    r"|Rollback\s+Assessment|Pre-?merge\s+Checklist|Monitoring\s+Recommendations?)$",
    re.IGNORECASE | re.MULTILINE,
)

# Matches bullet-item findings used by code-quality, architecture, performance:
#   - [description] — [file:line or diff URL]
#   - description — file:line
#   - description (no location)
# The location part is only captured if there is a file-like pattern after the separator.
BULLET_FINDING_PATTERN = re.compile(
    r"^[-*]\s+(.+?)(?:\s+[-–—]+\s+(\S+\.\S+.*))?$",
    re.MULTILINE,
)

# Extracts file:line from a location string:
#   path/to/file.py:42  →  ("path/to/file.py", 42)
#   path/to/file.py     →  ("path/to/file.py", None)
FILE_LINE_PATTERN = re.compile(
    r"([^\s:]+\.[a-zA-Z0-9]+)(?::(\d+))?",
)

# ---------------------------------------------------------------------------
# Severity mapping (prose label → FindingSeverity + blocking flag)
# ---------------------------------------------------------------------------

SEVERITY_MAP: dict[str, tuple[FindingSeverity, bool]] = {
    # Critical/Blocker → error, blocking
    "critical": (FindingSeverity.ERROR, True),
    "blocker": (FindingSeverity.ERROR, True),
    "showstopper": (FindingSeverity.ERROR, True),
    # High/Concern → warning, blocking
    "high": (FindingSeverity.WARNING, True),
    "high risk": (FindingSeverity.WARNING, True),
    "concern": (FindingSeverity.WARNING, True),
    "warning": (FindingSeverity.WARNING, True),
    # Medium/Suggestion → warning, non-blocking
    "medium": (FindingSeverity.WARNING, False),
    "suggestion": (FindingSeverity.WARNING, False),
    "optimization": (FindingSeverity.WARNING, False),
    "risk": (FindingSeverity.WARNING, False),
    # Low/Nit → info, non-blocking
    "low": (FindingSeverity.INFO, False),
    "nit": (FindingSeverity.INFO, False),
    "noted": (FindingSeverity.INFO, False),
}

# Section header → default severity label (for bullet-item findings under sections)
SECTION_SEVERITY_MAP: dict[str, str] = {
    "blockers": "blocker",
    "blocker": "blocker",
    "findings": "medium",
    "suggestions": "suggestion",
    "suggestion": "suggestion",
    "nits": "nit",
    "nit": "nit",
    "warnings": "warning",
    "warning": "warning",
    "concerns": "concern",
    "concern": "concern",
    "optimizations": "optimization",
    "optimization": "optimization",
    "failure modes found": "high risk",
}

# ---------------------------------------------------------------------------
# Category mapping (persona name → FindingCategory)
# ---------------------------------------------------------------------------

PERSONA_CATEGORY_MAP: dict[str, FindingCategory] = {
    "security-reviewer": FindingCategory.SECURITY,
    "security": FindingCategory.SECURITY,
    "architecture-reviewer": FindingCategory.ARCHITECTURE,
    "architecture": FindingCategory.ARCHITECTURE,
    "performance-reviewer": FindingCategory.PERFORMANCE,
    "performance": FindingCategory.PERFORMANCE,
    "adversarial-reviewer": FindingCategory.ADVERSARIAL,
    "adversarial": FindingCategory.ADVERSARIAL,
    "code-quality-reviewer": FindingCategory.CODE_QUALITY,
    "code-quality": FindingCategory.CODE_QUALITY,
    "code_quality": FindingCategory.CODE_QUALITY,
}

# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------


def _generate_finding_code(category: FindingCategory, title: str) -> str:
    """Generate a finding code from category + title.

    Example: FindingCategory.SECURITY + "SQL Injection in Auth Handler"
             → "SECURITY_SQL_INJECTION_IN_AUTH_HANDLER"

    Codes are upper-cased, non-alphanumeric replaced with underscores,
    and truncated to 100 chars to fit the DB column.
    """
    category_prefix = category.name  # e.g. "SECURITY", "CODE_QUALITY"
    # Normalize title: strip, upper, replace non-alphanum with underscore
    normalized = re.sub(r"[^A-Z0-9]+", "_", title.strip().upper())
    # Remove leading/trailing underscores
    normalized = normalized.strip("_")
    code = f"{category_prefix}_{normalized}"
    return code[:100]


# ---------------------------------------------------------------------------
# Location parsing
# ---------------------------------------------------------------------------


def _parse_location(location_str: str) -> tuple[str | None, int | None]:
    """Parse a location string into (file_path, line_number).

    Handles:
      - path/to/file.py:42
      - path/to/file.py
      - diff URL (returns the path from the URL if possible)
    """
    if not location_str:
        return None, None

    location_str = location_str.strip().strip("`")
    m = FILE_LINE_PATTERN.search(location_str)
    if m:
        file_path = m.group(1)
        line_num = int(m.group(2)) if m.group(2) else None
        return file_path, line_num
    return None, None


# ---------------------------------------------------------------------------
# Block-based finding extraction (security, adversarial)
# ---------------------------------------------------------------------------


def _extract_block_text(prose: str, start: int, next_heading_pos: int | None) -> str:
    """Extract the text block between a finding heading and the next heading."""
    end = next_heading_pos if next_heading_pos is not None else len(prose)
    return prose[start:end].strip()


def _extract_field(block: str, field_name: str) -> str | None:
    """Extract a named field from a finding block.

    Matches: **FieldName**: value text
    Returns the value text, or None if not found.
    """
    pattern = re.compile(
        rf"\*\*{re.escape(field_name)}\*\*\s*:\s*(.+?)(?=\n\*\*[A-Z]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(block)
    if m:
        return m.group(1).strip()
    return None


def _parse_heading_findings(
    prose: str,
    category: FindingCategory,
) -> list[dict[str, Any]]:
    """Parse findings that use #### [SEVERITY] -- Title heading format.

    Used by security-reviewer and adversarial-reviewer.
    """
    findings: list[dict[str, Any]] = []
    matches = list(FINDING_PATTERN.finditer(prose))

    for i, m in enumerate(matches):
        severity_label = m.group(1).strip().lower()
        title = m.group(2).strip()

        # Determine block boundaries
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(prose)
        block_text = prose[block_start:block_end].strip()

        # Parse severity + blocking
        severity, blocking = SEVERITY_MAP.get(
            severity_label, (FindingSeverity.WARNING, False)
        )

        # Parse location
        location_str = _extract_field(block_text, "Location")
        source_file, source_line = _parse_location(location_str or "")

        # Build description from block fields
        description_parts: list[str] = []
        for field_name in ("Attack", "Impact", "Scenario", "Blast radius",
                           "Detection", "Recovery", "Fix"):
            val = _extract_field(block_text, field_name)
            if val:
                description_parts.append(f"**{field_name}**: {val}")

        # If no structured fields found, use the raw block text as description
        if not description_parts:
            description = block_text
        else:
            description = "\n".join(description_parts)

        # Build actions from Fix/Recovery field
        actions: list[dict[str, str]] | None = None
        fix_text = _extract_field(block_text, "Fix") or _extract_field(block_text, "Recovery")
        if fix_text:
            actions = [{"type": "suggest-update", "label": "Fix", "description": fix_text}]

        code = _generate_finding_code(category, title)

        findings.append({
            "code": code,
            "category": category.value,
            "severity": severity.value,
            "confidence": "high",
            "title": title,
            "description": description,
            "blocking": blocking,
            "auto_fixable": False,
            "actions": actions,
            "source_file": source_file,
            "source_line": source_line,
        })

    return findings


# ---------------------------------------------------------------------------
# Section-based finding extraction (code-quality, architecture, performance)
# ---------------------------------------------------------------------------


def _parse_section_findings(
    prose: str,
    category: FindingCategory,
) -> list[dict[str, Any]]:
    """Parse findings from section-grouped bullet items.

    Used by code-quality-reviewer, architecture-reviewer, performance-reviewer.
    These use section headers like ### Blockers, ### Suggestions, ### Nits
    with bullet items underneath.
    """
    findings: list[dict[str, Any]] = []

    # Find all section headers (both finding and non-finding) to determine boundaries
    all_sections = list(re.finditer(
        r"^#{2,3}\s+.+$", prose, re.MULTILINE
    ))
    sections = list(SECTION_PATTERN.finditer(prose))

    for i, section_match in enumerate(sections):
        section_name = section_match.group(1).strip().lower()

        # Skip sections that don't map to severity
        if section_name not in SECTION_SEVERITY_MAP:
            continue

        severity_label = SECTION_SEVERITY_MAP[section_name]
        severity, blocking = SEVERITY_MAP.get(
            severity_label, (FindingSeverity.WARNING, False)
        )

        # Get section content (until next ## or ### header of any kind, or end)
        section_start = section_match.end()
        section_end = len(prose)
        for s in all_sections:
            if s.start() > section_match.start() and s.start() != section_match.start():
                section_end = s.start()
                break
        section_text = prose[section_start:section_end]

        # Check for sub-headings within the section (#### [SEVERITY] -- Title)
        sub_headings = list(FINDING_PATTERN.finditer(section_text))
        if sub_headings:
            # This section has structured sub-headings; parse them
            for j, sh in enumerate(sub_headings):
                sub_severity_label = sh.group(1).strip().lower()
                sub_title = sh.group(2).strip()
                sub_severity, sub_blocking = SEVERITY_MAP.get(
                    sub_severity_label, (severity, blocking)
                )

                block_start = sh.end()
                block_end = (
                    sub_headings[j + 1].start()
                    if j + 1 < len(sub_headings)
                    else len(section_text)
                )
                block_text = section_text[block_start:block_end].strip()

                location_str = _extract_field(block_text, "Location")
                source_file, source_line = _parse_location(location_str or "")

                fix_text = _extract_field(block_text, "Fix")
                actions = None
                if fix_text:
                    actions = [{"type": "suggest-update", "label": "Fix", "description": fix_text}]

                code = _generate_finding_code(category, sub_title)
                findings.append({
                    "code": code,
                    "category": category.value,
                    "severity": sub_severity.value,
                    "confidence": "high",
                    "title": sub_title,
                    "description": block_text if block_text else sub_title,
                    "blocking": sub_blocking,
                    "auto_fixable": False,
                    "actions": actions,
                    "source_file": source_file,
                    "source_line": source_line,
                })
            continue

        # Parse bullet-item findings
        for bullet_match in BULLET_FINDING_PATTERN.finditer(section_text):
            description_text = bullet_match.group(1).strip()
            location_text = bullet_match.group(2)

            # Skip items that look like counts (e.g. "3 nits (expand on request)")
            if re.match(r"^\d+\s+(nit|suggestion|optimization|available)", description_text, re.I):
                continue

            # Skip items that are clearly not findings (generic praise, etc.)
            if not description_text or len(description_text) < 5:
                continue

            # Skip checklist items (e.g. "[ ] Verify migration")
            if re.match(r"^\[[ x]\]\s+", description_text, re.I):
                continue

            source_file, source_line = _parse_location(location_text or "")
            title = description_text[:200]  # Truncate long descriptions for title

            code = _generate_finding_code(category, title)
            findings.append({
                "code": code,
                "category": category.value,
                "severity": severity.value,
                "confidence": "high",
                "title": title,
                "description": description_text,
                "blocking": blocking,
                "auto_fixable": False,
                "actions": None,
                "source_file": source_file,
                "source_line": source_line,
            })

    return findings


# ---------------------------------------------------------------------------
# Verdict extraction
# ---------------------------------------------------------------------------


def _extract_verdict(prose: str) -> str | None:
    """Extract the verdict/risk level/assessment from the prose output."""
    m = VERDICT_PATTERN.search(prose)
    if m:
        return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_review_output(prose: str, persona: str) -> list[dict[str, Any]]:
    """Parse review persona prose output into structured finding dicts.

    Args:
        prose: Raw markdown output from a review persona agent.
        persona: Persona name (e.g. "security-reviewer", "code-quality-reviewer").

    Returns:
        List of finding dicts, each with keys:
            code, category, severity, confidence, title, description,
            blocking, auto_fixable, actions, source_file, source_line

    The dicts are ready to be used to create AuditFinding model instances.
    """
    if not prose or not prose.strip():
        return []

    # Resolve category from persona name
    category = PERSONA_CATEGORY_MAP.get(persona)
    if category is None:
        # Try stripping common suffixes
        base = persona.replace("-reviewer", "").replace("_reviewer", "")
        category = PERSONA_CATEGORY_MAP.get(base, FindingCategory.CODE_QUALITY)

    findings: list[dict[str, Any]] = []

    # Strategy 1: Try heading-based extraction (security, adversarial)
    heading_findings = _parse_heading_findings(prose, category)

    # Strategy 2: Try section-based extraction (code-quality, architecture, performance)
    section_findings = _parse_section_findings(prose, category)

    # Merge: heading findings take priority, then section findings.
    # De-duplicate by code to avoid counting the same finding twice
    # (e.g. if a finding appears under both a section AND a heading).
    seen_codes: set[str] = set()
    for f in heading_findings:
        if f["code"] not in seen_codes:
            findings.append(f)
            seen_codes.add(f["code"])

    for f in section_findings:
        if f["code"] not in seen_codes:
            findings.append(f)
            seen_codes.add(f["code"])

    return findings


def extract_verdict(prose: str) -> str | None:
    """Extract the verdict line from review prose.

    Returns the raw verdict text (e.g. "APPROVE", "NEEDS WORK",
    "HIGH RISK", "SOUND"), or None if no verdict line found.
    """
    return _extract_verdict(prose)
