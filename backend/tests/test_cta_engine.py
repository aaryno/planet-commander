"""Tests for the CTA state machine (cta_engine.py).

Validates the five priority states and the is_human_required helper.
Pure function tests -- no database or I/O needed.
"""
import pytest

from app.services.cta_engine import (
    CTAState,
    STYLE_AMBER,
    STYLE_BLUE,
    STYLE_DEFAULT,
    STYLE_GREEN,
    derive_cta_state,
    is_human_required,
)


# ---------------------------------------------------------------------------
# is_human_required tests
# ---------------------------------------------------------------------------


class TestIsHumanRequired:
    def test_auto_fixable_not_human_required(self):
        finding = {"code": "WHATEVER", "auto_fixable": True, "blocking": False}
        assert is_human_required(finding) is False

    def test_auto_fixable_trumps_blocking(self):
        finding = {"code": "WHATEVER", "auto_fixable": True, "blocking": True}
        assert is_human_required(finding) is False

    def test_blocking_is_human_required(self):
        finding = {"code": "WHATEVER", "auto_fixable": False, "blocking": True}
        assert is_human_required(finding) is True

    def test_known_human_code(self):
        finding = {
            "code": "LOW_SCORE_OBJECTIVE_CLARITY",
            "auto_fixable": False,
            "blocking": False,
        }
        assert is_human_required(finding) is True

    def test_low_score_prefix_match(self):
        finding = {
            "code": "LOW_SCORE_SOME_NEW_DIMENSION",
            "auto_fixable": False,
            "blocking": False,
        }
        assert is_human_required(finding) is True

    def test_non_human_finding(self):
        finding = {
            "code": "STYLE_VIOLATION",
            "auto_fixable": False,
            "blocking": False,
        }
        assert is_human_required(finding) is False

    def test_missing_keys_default_false(self):
        """Missing keys should not cause errors."""
        finding = {}
        assert is_human_required(finding) is False


# ---------------------------------------------------------------------------
# derive_cta_state tests -- priority order
# ---------------------------------------------------------------------------


class TestDeriveCTAState:
    # Priority 1: No snapshot
    def test_no_snapshot(self):
        cta = derive_cta_state(readiness=None, findings=[])
        assert cta.style == STYLE_BLUE
        assert cta.action == "analyze"
        assert cta.label == "Analyze Readiness"
        assert cta.secondary_actions == []

    # Priority 2: All clear
    def test_ready(self):
        cta = derive_cta_state(readiness="ready", findings=[])
        assert cta.style == STYLE_GREEN
        assert cta.action == "ready"
        assert cta.label == "Ready for Work"
        assert len(cta.secondary_actions) == 2  # diagnostics

    # Priority 3: Auto-fixable findings
    def test_auto_fixable_findings(self):
        findings = [
            {"code": "FIX_ME", "auto_fixable": True, "blocking": False},
        ]
        cta = derive_cta_state(
            readiness="needs-work",
            findings=findings,
            auto_fixable_count=1,
        )
        assert cta.style == STYLE_BLUE
        assert cta.action == "fix-it"
        assert "1 auto-fixable" in cta.subtext

    def test_auto_fixable_with_human_findings(self):
        findings = [
            {"code": "FIX_ME", "auto_fixable": True, "blocking": False},
            {"code": "LOW_SCORE_OBJECTIVE_CLARITY", "auto_fixable": False, "blocking": False},
        ]
        cta = derive_cta_state(
            readiness="needs-work",
            findings=findings,
            auto_fixable_count=1,
        )
        assert cta.style == STYLE_BLUE
        assert cta.action == "fix-it"
        # Should have diagnostics + "Guide Me" secondary
        guide_actions = [a for a in cta.secondary_actions if a["action"] == "guide-me"]
        assert len(guide_actions) == 1
        assert "1" in guide_actions[0]["label"]  # "Guide Me (1)"

    # Priority 4: Human-required findings
    def test_human_required_findings(self):
        findings = [
            {"code": "LOW_SCORE_OBJECTIVE_CLARITY", "auto_fixable": False, "blocking": False},
            {"code": "MISSING_ACCEPTANCE_CRITERIA", "auto_fixable": False, "blocking": False},
        ]
        cta = derive_cta_state(
            readiness="needs-work",
            findings=findings,
            auto_fixable_count=0,
        )
        assert cta.style == STYLE_AMBER
        assert cta.action == "guide-me"
        assert "2 Question" in cta.label
        assert "2 finding" in cta.subtext

    def test_single_human_finding_no_plural(self):
        findings = [
            {"code": "LOW_SCORE_OBJECTIVE_CLARITY", "auto_fixable": False, "blocking": False},
        ]
        cta = derive_cta_state(
            readiness="needs-work",
            findings=findings,
            auto_fixable_count=0,
        )
        assert cta.label == "Answer 1 Question"  # no "s"
        assert "1 finding need" in cta.subtext  # no "s"

    # Priority 5: Fallback
    def test_fallback(self):
        cta = derive_cta_state(
            readiness="needs-work",
            findings=[],
            auto_fixable_count=0,
        )
        assert cta.style == STYLE_DEFAULT
        assert cta.action == "re-analyze"
        assert cta.label == "Re-analyze"

    # Edge cases
    def test_blocked_readiness_with_blocking_findings(self):
        findings = [
            {"code": "CRITICAL_BUG", "auto_fixable": False, "blocking": True},
        ]
        cta = derive_cta_state(
            readiness="blocked",
            findings=findings,
            auto_fixable_count=0,
            blocking_count=1,
        )
        # Blocking finding is human-required, so priority 4
        assert cta.style == STYLE_AMBER
        assert cta.action == "guide-me"

    def test_exploratory_only_no_findings(self):
        cta = derive_cta_state(
            readiness="exploratory-only",
            findings=[],
            auto_fixable_count=0,
        )
        assert cta.style == STYLE_DEFAULT
        assert cta.action == "re-analyze"

    def test_secondary_actions_always_present_with_snapshot(self):
        """Every state with a snapshot should have secondary actions."""
        for readiness in ["ready", "needs-work", "blocked", "exploratory-only"]:
            cta = derive_cta_state(readiness=readiness, findings=[])
            assert len(cta.secondary_actions) >= 2, (
                f"Expected secondary_actions for readiness={readiness}"
            )

    def test_cta_state_is_dataclass(self):
        cta = derive_cta_state(readiness=None, findings=[])
        assert isinstance(cta, CTAState)
        assert hasattr(cta, "label")
        assert hasattr(cta, "action")
        assert hasattr(cta, "subtext")
        assert hasattr(cta, "style")
        assert hasattr(cta, "secondary_actions")

    def test_pure_function_determinism(self):
        """Same inputs should always produce same output."""
        findings = [
            {"code": "LOW_SCORE_OBJECTIVE_CLARITY", "auto_fixable": False, "blocking": False},
        ]
        cta1 = derive_cta_state(readiness="needs-work", findings=findings)
        cta2 = derive_cta_state(readiness="needs-work", findings=findings)
        assert cta1.label == cta2.label
        assert cta1.action == cta2.action
        assert cta1.style == cta2.style
        assert cta1.subtext == cta2.subtext
        assert cta1.secondary_actions == cta2.secondary_actions
