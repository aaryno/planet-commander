"""Skill suggestion service - analyzes work contexts and suggests relevant skills."""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    WorkContext,
    SkillRegistry,
    SuggestedSkill,
    JiraIssue,
    Agent,
    EntityLink,
    SlackThread,
)

logger = logging.getLogger(__name__)


class SkillSuggestionService:
    """Analyze work contexts and suggest relevant skills."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def suggest_skills_for_context(
        self,
        context_id: UUID,
        min_confidence: float = 0.3
    ) -> List[Dict]:
        """Analyze context and suggest skills.

        Args:
            context_id: Work context UUID
            min_confidence: Minimum confidence score (0.0-1.0)

        Returns:
            List of suggestions with skill, confidence, and reasons
        """
        # Get work context with relationships
        result = await self.db.execute(
            select(WorkContext)
            .where(WorkContext.id == context_id)
            .options(
                selectinload(WorkContext.primary_jira_issue),
                selectinload(WorkContext.primary_chat),
            )
        )
        context = result.scalar_one_or_none()

        if not context:
            logger.warning(f"Work context not found: {context_id}")
            return []

        # Extract signals from context
        signals = await self.extract_context_signals(context)

        # Match against skill registry
        matches = await self.match_skills(signals)

        # Score and rank
        ranked = self.rank_skills(matches, min_confidence)

        # Store suggestions
        await self.store_suggestions(context_id, ranked)

        return ranked

    async def extract_context_signals(self, context: WorkContext) -> Dict:
        """Extract matching signals from work context.

        Args:
            context: WorkContext object

        Returns:
            Dictionary with signals:
            {
                "labels": ["wx", "incident"],
                "keywords": ["task failure", "lease expiration"],
                "systems": ["kubectl", "Grafana"],
                "entity_types": ["jira_issue", "slack_thread"],
                "severity": "SEV2",
                "is_incident": True
            }
        """
        signals = {
            "labels": [],
            "keywords": [],
            "systems": [],
            "entity_types": [],
            "severity": None,
            "is_incident": False
        }

        # From JIRA issue
        if context.primary_jira_issue:
            jira = context.primary_jira_issue

            # Extract labels
            if jira.labels:
                signals["labels"].extend(jira.labels)

            # Extract keywords from description
            if jira.description:
                signals["keywords"].extend(
                    self.extract_keywords(jira.description)
                )

            # Check for incident labels
            if "incident" in (jira.labels or []):
                signals["is_incident"] = True

            # Extract severity from summary or labels
            if jira.summary:
                severity = self.extract_severity(jira.summary)
                if severity:
                    signals["severity"] = severity

        # From agent chat
        if context.primary_chat:
            agent = context.primary_chat

            # Extract keywords from chat messages (if available)
            # Note: Agent model may not have messages field yet
            # This is a placeholder for future implementation
            pass

        # From linked entities
        result = await self.db.execute(
            select(EntityLink)
            .where(EntityLink.from_id == str(context.id))
        )
        links = result.scalars().all()

        for link in links:
            signals["entity_types"].append(link.to_type)

            # If linked to Slack thread, check for incident flags
            if link.to_type == "slack_thread":
                thread_result = await self.db.execute(
                    select(SlackThread).where(SlackThread.id == UUID(link.to_id))
                )
                thread = thread_result.scalar_one_or_none()
                if thread and thread.is_incident:
                    signals["is_incident"] = True
                    if thread.severity:
                        signals["severity"] = thread.severity

        # Deduplicate lists
        signals["labels"] = list(set(signals["labels"]))
        signals["keywords"] = list(set(signals["keywords"]))
        signals["systems"] = list(set(signals["systems"]))
        signals["entity_types"] = list(set(signals["entity_types"]))

        return signals

    def extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text.

        Args:
            text: Input text

        Returns:
            List of keywords
        """
        if not text:
            return []

        keywords = []
        text_lower = text.lower()

        # Pattern matching for common issue keywords
        patterns = {
            "task failure": ["task fail", "task failed", "task failure"],
            "lease expiration": ["lease expir", "lease expired"],
            "oom": ["oom", "out of memory", "memory limit"],
            "crashloop": ["crashloop", "crash loop", "crashing"],
            "timeout": ["timeout", "timed out"],
            "stuck": ["stuck", "hanging", "not progressing"],
            "slow": ["slow", "latency", "performance"],
            "unavailable": ["unavailable", "down", "not responding"],
            "alert firing": ["firing", "alert", "critical"],
            "deployment": ["deploy", "deployment", "release"],
            "config change": ["config", "configuration"],
        }

        for keyword, patterns_list in patterns.items():
            if any(pattern in text_lower for pattern in patterns_list):
                keywords.append(keyword)

        return keywords

    def extract_severity(self, text: str) -> Optional[str]:
        """Extract severity from text.

        Args:
            text: Input text

        Returns:
            Severity string like "SEV1" or None
        """
        pattern = r"\b(SEV\s*[1-4]|P[1-4]|severity\s*[1-4])\b"
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            # Normalize to SEV1-4 format
            severity = match.group(1).upper().replace(" ", "")
            if severity.startswith("P"):
                severity = "SEV" + severity[1]
            elif severity.startswith("SEVERITY"):
                severity = "SEV" + severity[-1]
            return severity

        return None

    async def match_skills(self, signals: Dict) -> List[Dict]:
        """Match signals against skill registry.

        Args:
            signals: Extracted signals from context

        Returns:
            List of skill matches with scores and reasons
        """
        # Query all skills
        result = await self.db.execute(select(SkillRegistry))
        skills = result.scalars().all()

        matches = []
        for skill in skills:
            score, reasons = self.calculate_match_score(skill, signals)
            if score > 0:
                matches.append({
                    "skill": skill,
                    "score": score,
                    "reasons": reasons
                })

        return matches

    def calculate_match_score(
        self,
        skill: SkillRegistry,
        signals: Dict
    ) -> Tuple[float, List[Dict]]:
        """Calculate match score between skill and signals.

        Scoring weights:
        - Label matching: 0.4 (0.2 per label match, max 0.4)
        - Keyword matching: 0.4 (0.15 per keyword match, max 0.4)
        - System matching: 0.2 (0.1 per system match, max 0.2)
        - Incident boost: 0.2 (if both skill and context are incident-related)

        Args:
            skill: SkillRegistry object
            signals: Context signals

        Returns:
            Tuple of (score, reasons)
        """
        score = 0.0
        reasons = []

        # Label matching (weight: 0.4)
        if skill.trigger_labels and signals["labels"]:
            label_matches = set(signals["labels"]) & set(skill.trigger_label_list)
            if label_matches:
                label_score = len(label_matches) * 0.2  # 0.2 per label match
                score += min(label_score, 0.4)
                reasons.append({
                    "type": "label_match",
                    "values": list(label_matches),
                    "weight": min(label_score, 0.4)
                })

        # Keyword matching (weight: 0.4)
        if skill.trigger_keywords and signals["keywords"]:
            keyword_matches = []
            for skill_kw in skill.trigger_keyword_list:
                # Check if skill keyword appears in any signal keyword
                if any(
                    skill_kw.lower() in signal_kw.lower()
                    for signal_kw in signals["keywords"]
                ):
                    keyword_matches.append(skill_kw)

            if keyword_matches:
                keyword_score = len(keyword_matches) * 0.15  # 0.15 per keyword match
                score += min(keyword_score, 0.4)
                reasons.append({
                    "type": "keyword_match",
                    "values": keyword_matches,
                    "weight": min(keyword_score, 0.4)
                })

        # System matching (weight: 0.2)
        if skill.trigger_systems and signals["systems"]:
            system_matches = set(signals["systems"]) & set(skill.trigger_system_list)
            if system_matches:
                system_score = len(system_matches) * 0.1  # 0.1 per system match
                score += min(system_score, 0.2)
                reasons.append({
                    "type": "system_match",
                    "values": list(system_matches),
                    "weight": min(system_score, 0.2)
                })

        # Incident boost (if skill is incident-related and context is incident)
        if signals["is_incident"]:
            incident_keywords = ["incident", "response", "triage", "alert"]
            if any(kw in skill.skill_name.lower() for kw in incident_keywords):
                score += 0.2
                reasons.append({
                    "type": "incident_boost",
                    "weight": 0.2
                })

        return score, reasons

    def rank_skills(self, matches: List[Dict], min_confidence: float) -> List[Dict]:
        """Rank and filter skill matches by confidence threshold.

        Args:
            matches: List of skill matches with scores
            min_confidence: Minimum confidence threshold

        Returns:
            Ranked list of top 5 suggestions
        """
        # Filter by min confidence
        filtered = [m for m in matches if m["score"] >= min_confidence]

        # Sort by score descending
        ranked = sorted(filtered, key=lambda m: m["score"], reverse=True)

        # Limit to top 5
        return ranked[:5]

    async def store_suggestions(
        self,
        context_id: UUID,
        suggestions: List[Dict]
    ) -> None:
        """Store skill suggestions in database.

        Args:
            context_id: Work context UUID
            suggestions: List of ranked suggestions
        """
        for suggestion in suggestions:
            skill = suggestion["skill"]

            # Check if suggestion already exists
            result = await self.db.execute(
                select(SuggestedSkill).where(
                    SuggestedSkill.work_context_id == context_id,
                    SuggestedSkill.skill_id == skill.id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing suggestion
                existing.confidence_score = suggestion["score"]
                existing.match_reasons = suggestion["reasons"]
                existing.suggested_at = datetime.utcnow()
            else:
                # Create new suggestion
                suggested_skill = SuggestedSkill(
                    work_context_id=context_id,
                    skill_id=skill.id,
                    skill_name=skill.skill_name,
                    confidence_score=suggestion["score"],
                    match_reasons=suggestion["reasons"]
                )
                self.db.add(suggested_skill)

        await self.db.commit()

    async def record_user_action(
        self,
        context_id: UUID,
        skill_id: UUID,
        action: str,
        feedback: Optional[str] = None
    ) -> None:
        """Record user action on suggested skill.

        Args:
            context_id: Work context UUID
            skill_id: Skill UUID
            action: Action taken ("accepted", "dismissed", "deferred")
            feedback: Optional user feedback
        """
        result = await self.db.execute(
            select(SuggestedSkill).where(
                SuggestedSkill.work_context_id == context_id,
                SuggestedSkill.skill_id == skill_id
            )
        )
        suggestion = result.scalar_one_or_none()

        if not suggestion:
            logger.warning(
                f"Suggested skill not found: context={context_id}, skill={skill_id}"
            )
            return

        suggestion.user_action = action
        suggestion.user_feedback = feedback
        suggestion.actioned_at = datetime.utcnow()

        # Increment skill invocation count if accepted
        if action == "accepted":
            skill_result = await self.db.execute(
                select(SkillRegistry).where(SkillRegistry.id == skill_id)
            )
            skill = skill_result.scalar_one_or_none()
            if skill:
                skill.invocation_count += 1
                skill.last_invoked_at = datetime.utcnow()

        await self.db.commit()

    async def get_suggestions_for_context(
        self,
        context_id: UUID
    ) -> List[SuggestedSkill]:
        """Get all suggestions for a work context.

        Args:
            context_id: Work context UUID

        Returns:
            List of SuggestedSkill objects
        """
        result = await self.db.execute(
            select(SuggestedSkill)
            .where(SuggestedSkill.work_context_id == context_id)
            .order_by(SuggestedSkill.confidence_score.desc())
        )
        return result.scalars().all()
