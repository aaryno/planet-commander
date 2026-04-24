"""Skill indexing service - parses and indexes skills from ~/.claude/skills/"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SkillRegistry

logger = logging.getLogger(__name__)


class SkillIndexingService:
    """Parse and index skills from ~/.claude/skills/ directory."""

    SKILL_DIR = Path.home() / ".claude" / "skills"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def index_all_skills(self) -> Dict:
        """Scan and index all skills from directory.

        Returns:
            Dictionary with indexing statistics:
            {
                "indexed": int,    # New skills added
                "updated": int,    # Existing skills updated
                "removed": int,    # Obsolete skills removed
                "errors": [str]    # Error messages
            }
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting skill indexing from {self.SKILL_DIR}")

        stats = {
            "indexed": 0,
            "updated": 0,
            "removed": 0,
            "errors": []
        }

        if not self.SKILL_DIR.exists():
            error_msg = f"Skill directory not found: {self.SKILL_DIR}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        # Track all skill names found in filesystem
        found_skills = set()

        # Scan directory for skills
        for skill_dir in self.SKILL_DIR.iterdir():
            if not skill_dir.is_dir():
                continue

            # Skip special directories
            if skill_dir.name.startswith(".") or skill_dir.name.startswith("_"):
                continue

            found_skills.add(skill_dir.name)

            try:
                # Parse skill
                skill_data = self.parse_skill(skill_dir)

                if not skill_data:
                    logger.debug(f"Skipping {skill_dir.name} - no SKILL.md file")
                    continue

                # Check if skill exists in database
                result = await self.db.execute(
                    select(SkillRegistry).where(
                        SkillRegistry.skill_name == skill_data["skill_name"]
                    )
                )
                existing_skill = result.scalar_one_or_none()

                if existing_skill:
                    # Update existing skill
                    for key, value in skill_data.items():
                        if key != "skill_name":  # Don't update the name
                            setattr(existing_skill, key, value)
                    existing_skill.last_updated_at = datetime.utcnow()
                    stats["updated"] += 1
                    logger.debug(f"Updated skill: {skill_data['skill_name']}")
                else:
                    # Insert new skill
                    skill = SkillRegistry(**skill_data)
                    self.db.add(skill)
                    stats["indexed"] += 1
                    logger.debug(f"Indexed new skill: {skill_data['skill_name']}")

            except Exception as e:
                error_msg = f"Failed to index skill {skill_dir.name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                stats["errors"].append(error_msg)

        # Remove skills that no longer exist in filesystem
        result = await self.db.execute(select(SkillRegistry))
        all_skills = result.scalars().all()

        for skill in all_skills:
            if skill.skill_name not in found_skills:
                await self.db.delete(skill)
                stats["removed"] += 1
                logger.debug(f"Removed obsolete skill: {skill.skill_name}")

        # Commit all changes
        await self.db.commit()

        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Skill indexing complete: {stats['indexed']} new, "
            f"{stats['updated']} updated, {stats['removed']} removed "
            f"in {duration:.1f}s"
        )

        return stats

    def parse_skill(self, skill_dir: Path) -> Optional[Dict]:
        """Parse SKILL.md file to extract metadata and trigger conditions.

        Args:
            skill_dir: Path to skill directory

        Returns:
            Dictionary with skill data or None if no SKILL.md found
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text()

        # Extract YAML frontmatter
        frontmatter = self.extract_frontmatter(content)

        # Extract trigger conditions
        triggers = self.extract_triggers(content, frontmatter)

        # Infer metadata from skill name and content
        skill_name = skill_dir.name
        category = self.infer_category(skill_name)
        labels = self.infer_labels(skill_name, content)
        systems = self.infer_systems(content)

        return {
            "skill_name": skill_name,
            "skill_path": str(skill_dir),
            "title": frontmatter.get("name", skill_name),
            "description": frontmatter.get("description", ""),
            "trigger_keywords": triggers.get("keywords", []),
            "trigger_labels": labels,
            "trigger_systems": systems,
            "trigger_patterns": triggers.get("patterns", []),
            "category": category,
            "complexity": self.infer_complexity(content),
            "estimated_duration": self.infer_duration(content),
        }

    def extract_frontmatter(self, content: str) -> Dict:
        """Extract YAML frontmatter from skill file.

        Args:
            content: Full file content

        Returns:
            Parsed frontmatter as dictionary
        """
        # Match YAML frontmatter (between --- delimiters)
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}

        try:
            frontmatter = yaml.safe_load(match.group(1))
            return frontmatter if frontmatter else {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter: {e}")
            return {}

    def extract_triggers(self, content: str, frontmatter: Dict) -> Dict:
        """Extract trigger conditions from frontmatter and content.

        Args:
            content: Full file content
            frontmatter: Parsed frontmatter

        Returns:
            Dictionary with keywords and patterns
        """
        keywords = []

        # Get triggers from frontmatter
        if "triggers" in frontmatter and isinstance(frontmatter["triggers"], list):
            keywords = frontmatter["triggers"]

        # Extract from "When to Use" section if no frontmatter triggers
        if not keywords:
            when_section = self.extract_section(content, "When to Use")
            if when_section:
                # Simple heuristic: bullet points in this section
                bullet_pattern = r"^[-*]\s+(.+)$"
                for line in when_section.split("\n"):
                    match = re.match(bullet_pattern, line.strip())
                    if match:
                        keywords.append(match.group(1).lower())

        return {
            "keywords": keywords[:20],  # Limit to 20 keywords
            "patterns": []  # TODO: Support regex patterns if needed
        }

    def extract_section(self, content: str, heading: str) -> Optional[str]:
        """Extract content from a specific markdown section.

        Args:
            content: Full file content
            heading: Section heading to extract

        Returns:
            Section content or None if not found
        """
        pattern = rf"^#+\s+{re.escape(heading)}\s*\n(.*?)(?=^#+\s|\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if match:
            return match.group(1).strip()

        return None

    def infer_category(self, skill_name: str) -> str:
        """Infer skill category from name.

        Args:
            skill_name: Skill directory name

        Returns:
            Category string
        """
        # Category patterns
        patterns = {
            "investigation": ["debug", "investigate", "investigation", "triage"],
            "onboarding": ["onboard"],
            "analysis": ["analysis", "cost-analysis"],
            "workflow": ["worktree", "mr-review"],
            "automation": ["generator"],
            "response": ["incident-response", "alert-triage"],
            "documentation": ["project-docs"],
            "utility": ["color", "slack-catchup"],
        }

        for category, keywords in patterns.items():
            if any(kw in skill_name.lower() for kw in keywords):
                return category

        return "general"

    def infer_labels(self, skill_name: str, content: str) -> List[str]:
        """Infer JIRA/project labels from skill name and content.

        Args:
            skill_name: Skill directory name
            content: Full file content

        Returns:
            List of label strings
        """
        labels = []

        # Project labels from skill name
        project_patterns = {
            "wx": ["wx", "workexchange", "work-exchange"],
            "jobs": ["jobs"],
            "g4": ["g4"],
            "temporal": ["temporal"],
            "incident": ["incident", "prodissue"],
        }

        for label, keywords in project_patterns.items():
            if any(kw in skill_name.lower() for kw in keywords):
                labels.append(label)

        # Check content for project mentions
        content_lower = content.lower()
        if "workexchange" in content_lower or "work exchange" in content_lower:
            if "wx" not in labels:
                labels.append("wx")

        if "jobs platform" in content_lower or "jobs-" in content_lower:
            if "jobs" not in labels:
                labels.append("jobs")

        return labels

    def infer_systems(self, content: str) -> List[str]:
        """Infer referenced systems from content.

        Args:
            content: Full file content

        Returns:
            List of system names
        """
        systems = []

        # System patterns to detect
        system_keywords = {
            "kubectl": ["kubectl", "kubernetes", "k8s"],
            "wxctl": ["wxctl"],
            "Grafana": ["grafana", "prometheus"],
            "Loki": ["loki"],
            "BigQuery": ["bigquery", "bq query"],
            "JIRA": ["jira", "ticket"],
            "Slack": ["slack"],
            "GitLab": ["gitlab", "glab"],
            "PagerDuty": ["pagerduty"],
        }

        content_lower = content.lower()

        for system, keywords in system_keywords.items():
            if any(kw in content_lower for kw in keywords):
                systems.append(system)

        return systems

    def infer_complexity(self, content: str) -> str:
        """Infer skill complexity from content length and structure.

        Args:
            content: Full file content

        Returns:
            Complexity string: "low", "medium", "high"
        """
        line_count = len(content.split("\n"))

        if line_count < 200:
            return "low"
        elif line_count < 500:
            return "medium"
        else:
            return "high"

    def infer_duration(self, content: str) -> str:
        """Infer estimated duration from content.

        Args:
            content: Full file content

        Returns:
            Duration string like "5-10 minutes"
        """
        line_count = len(content.split("\n"))

        # Heuristic based on content length
        if line_count < 200:
            return "5-10 minutes"
        elif line_count < 500:
            return "15-30 minutes"
        else:
            return "30-60 minutes"

    async def get_all_skills(self, category: Optional[str] = None) -> List[SkillRegistry]:
        """Get all registered skills, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of SkillRegistry objects
        """
        query = select(SkillRegistry).order_by(SkillRegistry.skill_name)

        if category:
            query = query.where(SkillRegistry.category == category)

        result = await self.db.execute(query)
        return result.scalars().all()
