"""Service for parsing and indexing project documentation."""

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_doc import ProjectDoc
from app.models.project_doc_section import ProjectDocSection

logger = logging.getLogger(__name__)


class ProjectDocService:
    """Service for parsing and indexing project documentation."""

    PROJECTS_DIR = Path.home() / "claude" / "projects"

    # Common tech keywords to extract
    TECH_KEYWORDS = {
        "kubernetes", "k8s", "docker", "postgres", "redis", "fastapi",
        "python", "golang", "typescript", "react", "nextjs",
        "grafana", "loki", "prometheus", "pagerduty",
        "gitlab", "jira", "slack", "temporal",
        "api", "database", "deployment", "monitoring", "logging"
    }

    # Project name mappings
    PROJECT_NAMES = ["wx", "g4", "jobs", "temporal", "prodissue", "eso"]

    # Slack channel to project mapping
    SLACK_CHANNEL_MAP = {
        "#wx-dev": "wx",
        "#wx-users": "wx",
        "#g4-users": "g4",
        "#jobs-users": "jobs",
        "#temporalio-cloud": "temporal",
        "#compute-platform": "compute",  # Multi-project
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_project_docs(self) -> Dict:
        """Scan ~/claude/projects/ for *-notes/*-claude.md files.

        Returns:
            Dict with scan statistics
        """
        logger.info(f"Scanning project docs in {self.PROJECTS_DIR}")

        stats = {
            "total_scanned": 0,
            "new_docs": 0,
            "updated_docs": 0,
            "unchanged_docs": 0,
            "errors": [],
        }

        if not self.PROJECTS_DIR.exists():
            error_msg = f"Projects directory not found: {self.PROJECTS_DIR}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        # Find all *-claude.md files in *-notes/ directories
        pattern = "*-notes/*-claude.md"
        for doc_path in self.PROJECTS_DIR.glob(pattern):
            stats["total_scanned"] += 1

            try:
                # Extract project name from path
                # e.g., wx-notes/wx-claude.md -> wx
                notes_dir = doc_path.parent.name  # wx-notes
                project_name = notes_dir.replace("-notes", "")  # wx

                # Read file content
                content = doc_path.read_text(encoding="utf-8")

                # Update or create project doc
                result = await self.update_project_doc(project_name, doc_path, content)

                if result == "new":
                    stats["new_docs"] += 1
                elif result == "updated":
                    stats["updated_docs"] += 1
                elif result == "unchanged":
                    stats["unchanged_docs"] += 1

                logger.info(f"Processed {project_name}: {result}")

            except Exception as e:
                # Rollback on error to keep session clean
                await self.db.rollback()
                error_msg = f"Error processing {doc_path}: {e}"
                logger.error(error_msg, exc_info=True)
                stats["errors"].append(error_msg)

        return stats

    def parse_markdown(self, content: str) -> Dict:
        """Parse markdown content into sections, keywords, and links.

        Returns:
            {
                "sections": [{"name": "Architecture", "level": 2, "content": "..."}],
                "keywords": ["wx", "kubernetes", "fastapi"],
                "links": {"repos": [...], "dashboards": [...], "urls": [...]}
            }
        """
        sections = []
        keywords = set()
        links = {"repos": [], "dashboards": [], "urls": []}

        # Split content by headings
        # Match: ## Architecture, ### Deployment, etc.
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

        matches = list(heading_pattern.finditer(content))

        for i, match in enumerate(matches):
            heading_level = len(match.group(1))  # Number of # symbols
            section_name = match.group(2).strip()

            # Get content until next heading
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start_pos:end_pos].strip()

            sections.append({
                "name": section_name,
                "level": heading_level,
                "content": section_content,
                "order": i
            })

            # Extract keywords from section name
            section_words = re.findall(r"\b[a-z]{3,}\b", section_name.lower())
            keywords.update(word for word in section_words if word in self.TECH_KEYWORDS)

        # Extract keywords from entire content
        content_words = re.findall(r"\b[a-z]{3,}\b", content.lower())
        keywords.update(word for word in content_words if word in self.TECH_KEYWORDS)

        # Extract repository references (e.g., wx/wx, product/g4-wk/g4)
        repo_pattern = re.compile(r"(?:^|\s|`)([\w-]+/[\w-]+(?:/[\w-]+)?)")
        repo_matches = repo_pattern.findall(content)
        links["repos"] = list(set(repo_matches))

        # Extract Grafana dashboard URLs
        dashboard_pattern = re.compile(r"https://planet\.grafana\.net/d/([\w-]+)/")
        dashboard_matches = dashboard_pattern.findall(content)
        links["dashboards"] = list(set(dashboard_matches))

        # Extract general URLs
        url_pattern = re.compile(r"https?://[^\s)\]]+")
        url_matches = url_pattern.findall(content)
        links["urls"] = list(set(url_matches))

        return {
            "sections": sections,
            "keywords": sorted(list(keywords)),
            "links": links
        }

    def compute_content_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def update_project_doc(
        self,
        project_name: str,
        file_path: Path,
        content: Optional[str] = None
    ) -> str:
        """Update or create project doc from file.

        Uses content hash to detect changes (skip unchanged files).

        Returns:
            "new", "updated", or "unchanged"
        """
        # Read content if not provided
        if content is None:
            content = file_path.read_text(encoding="utf-8")

        # Compute content hash
        content_hash = self.compute_content_hash(content)

        # Get file modification time
        file_modified_at = datetime.fromtimestamp(
            file_path.stat().st_mtime,
            tz=timezone.utc
        )

        # Check if doc already exists
        result = await self.db.execute(
            select(ProjectDoc).where(ProjectDoc.project_name == project_name)
        )
        existing_doc = result.scalar_one_or_none()

        # If content unchanged, skip update
        if existing_doc and existing_doc.content_hash == content_hash:
            return "unchanged"

        # Parse markdown
        parsed = self.parse_markdown(content)

        # Infer team from project name
        team = "compute" if project_name in self.PROJECT_NAMES else None

        # Infer Slack channels from project name
        slack_channels = []
        for channel, proj in self.SLACK_CHANNEL_MAP.items():
            if proj == project_name:
                slack_channels.append(channel)

        if existing_doc:
            # Delete old sections first (cascade will handle this, but we'll be explicit)
            from sqlalchemy import delete
            await self.db.execute(
                delete(ProjectDocSection).where(
                    ProjectDocSection.project_doc_id == existing_doc.id
                )
            )
            await self.db.flush()

            # Update existing doc
            existing_doc.file_path = str(file_path)
            existing_doc.content = content
            existing_doc.content_hash = content_hash
            existing_doc.sections = {"sections": parsed["sections"]}
            existing_doc.keywords = parsed["keywords"]
            existing_doc.links = parsed["links"]
            existing_doc.team = team
            existing_doc.repositories = parsed["links"]["repos"]
            existing_doc.slack_channels = slack_channels or None
            existing_doc.file_modified_at = file_modified_at
            existing_doc.last_synced_at = datetime.now(timezone.utc)

            # Create new sections
            for section_data in parsed["sections"]:
                section = ProjectDocSection(
                    project_doc_id=existing_doc.id,
                    section_name=section_data["name"],
                    heading_level=section_data["level"],
                    order_index=section_data["order"],
                    content=section_data["content"],
                    content_hash=self.compute_content_hash(section_data["content"])
                )
                self.db.add(section)

            await self.db.commit()
            return "updated"

        else:
            # Create new doc
            new_doc = ProjectDoc(
                project_name=project_name,
                file_path=str(file_path),
                content=content,
                content_hash=content_hash,
                sections={"sections": parsed["sections"]},
                keywords=parsed["keywords"],
                links=parsed["links"],
                team=team,
                repositories=parsed["links"]["repos"] or None,
                slack_channels=slack_channels or None,
                file_modified_at=file_modified_at,
                last_synced_at=datetime.now(timezone.utc)
            )
            self.db.add(new_doc)
            await self.db.flush()  # Get ID for sections

            # Create sections
            for section_data in parsed["sections"]:
                section = ProjectDocSection(
                    project_doc_id=new_doc.id,
                    section_name=section_data["name"],
                    heading_level=section_data["level"],
                    order_index=section_data["order"],
                    content=section_data["content"],
                    content_hash=self.compute_content_hash(section_data["content"])
                )
                self.db.add(section)

            await self.db.commit()
            return "new"

    async def search_project_docs(
        self,
        query: str,
        project: Optional[str] = None,
        team: Optional[str] = None,
        limit: int = 20
    ) -> List[ProjectDoc]:
        """Search project docs by keywords/content.

        Args:
            query: Search query string
            project: Filter by project name
            team: Filter by team
            limit: Maximum results

        Returns:
            List of matching ProjectDoc instances
        """
        # Build base query
        stmt = select(ProjectDoc)

        # Add filters
        conditions = []

        if project:
            conditions.append(ProjectDoc.project_name == project)

        if team:
            conditions.append(ProjectDoc.team == team)

        # Search in content, keywords, project name
        if query:
            query_lower = query.lower()
            conditions.append(
                or_(
                    ProjectDoc.content.ilike(f"%{query}%"),
                    ProjectDoc.project_name.ilike(f"%{query}%"),
                    ProjectDoc.keywords.contains([query_lower])
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_project_doc(self, project_name: str) -> Optional[ProjectDoc]:
        """Get project doc by name.

        Args:
            project_name: Project name (e.g., "wx", "g4")

        Returns:
            ProjectDoc instance or None
        """
        result = await self.db.execute(
            select(ProjectDoc).where(ProjectDoc.project_name == project_name)
        )
        return result.scalar_one_or_none()

    async def infer_project_from_context(
        self,
        jira_labels: Optional[List[str]] = None,
        slack_channel: Optional[str] = None,
        working_dir: Optional[str] = None
    ) -> Optional[str]:
        """Infer project name from context clues.

        Examples:
        - JIRA label "wx" → "wx"
        - Slack channel "#wx-dev" → "wx"
        - Working dir "~/code/wx/wx-1/" → "wx"

        Args:
            jira_labels: JIRA issue labels
            slack_channel: Slack channel name
            working_dir: Working directory path

        Returns:
            Project name or None
        """
        # Check JIRA labels
        if jira_labels:
            for label in jira_labels:
                label_lower = label.lower()
                if label_lower in self.PROJECT_NAMES:
                    return label_lower

        # Check Slack channel
        if slack_channel:
            if slack_channel in self.SLACK_CHANNEL_MAP:
                return self.SLACK_CHANNEL_MAP[slack_channel]

        # Check working directory
        if working_dir:
            path_lower = working_dir.lower()
            for project in self.PROJECT_NAMES:
                # Match patterns like ~/code/wx/, ~/workspaces/g4/, etc.
                if f"/{project}/" in path_lower or f"/{project}-" in path_lower:
                    return project

        return None
