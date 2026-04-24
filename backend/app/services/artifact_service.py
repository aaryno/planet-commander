"""Artifact indexing service for Commander enrichment."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation_artifact import InvestigationArtifact

logger = logging.getLogger(__name__)


class ArtifactService:
    """Service for indexing and searching investigation artifacts."""

    # Filename pattern: YYYYMMDD-[HHMM]-{description}.md
    # Time component is optional for backward compatibility
    # Examples:
    # - 20260211-1455-proximity-insights-mvp-complete.md (with time)
    # - 20260105-k8s-operator-findings.md (without time)
    # - 20260130-1200-chad-g4-cost-onboarding.md (with time)
    FILENAME_PATTERN = re.compile(r"^(\d{8})(?:-(\d{4}))?-(.+)\.md$")

    # JIRA key pattern
    JIRA_KEY_PATTERN = re.compile(r"\b(?:COMPUTE|WX|JOBS|TEMPORAL|G4|PRODISSUE)-\d+\b")

    # Artifact type patterns (inferred from description)
    TYPE_PATTERNS = {
        "investigation": r"investigat|incident|debug|stuck|failure|diagnos",
        "plan": r"plan|implementation|roadmap|strategy|design",
        "handoff": r"handoff|transition",
        "analysis": r"analysis|audit|findings|review|assessment",
        "complete": r"complete|done|finished|mvp",
        "summary": r"summary|report|overview|recap",
    }

    # Common systems/platforms (for entity extraction)
    SYSTEMS = [
        "WX",
        "WorkExchange",
        "G4",
        "Jobs",
        "Temporal",
        "DataCollect",
        "TARDIS",
        "Hobbes",
        "ESO",
        "PagerDuty",
        "Grafana",
        "Kubernetes",
        "k8s",
        "PostgreSQL",
        "Redis",
        "Spanner",
        "BigQuery",
    ]

    # Alert name pattern (lowercase-with-dashes)
    ALERT_PATTERN = re.compile(r"\b([a-z0-9]+-){2,}[a-z0-9]+\b")

    def __init__(self, db: AsyncSession):
        """Initialize artifact service.

        Args:
            db: SQLAlchemy async database session
        """
        self.db = db

    def parse_filename(self, filename: str) -> Optional[Dict]:
        """Extract metadata from artifact filename.

        Args:
            filename: Artifact filename (e.g., "20260211-1455-description.md")

        Returns:
            Dict with created_at, description, artifact_type or None if invalid

        Examples:
            >>> service = ArtifactService(db)
            >>> service.parse_filename("20260211-1455-wx-task-investigation.md")
            {
                "created_at": datetime(2026, 2, 11, 14, 55, tzinfo=timezone.utc),
                "description": "wx-task-investigation",
                "artifact_type": "investigation"
            }
        """
        match = self.FILENAME_PATTERN.match(filename)
        if not match:
            return None

        date_str, time_str, description = match.groups()

        try:
            # Parse YYYYMMDD to date
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            # Parse HHMM if present, otherwise default to midnight
            if time_str:
                hour = int(time_str[0:2])
                minute = int(time_str[2:4])
            else:
                hour = 0
                minute = 0

            created_at = datetime(
                year, month, day, hour, minute, tzinfo=timezone.utc
            )
        except ValueError as e:
            logger.warning(f"Failed to parse datetime from {filename}: {e}")
            return None

        # Infer artifact type from description
        artifact_type = self.infer_artifact_type(description)

        return {
            "created_at": created_at,
            "description": description,
            "artifact_type": artifact_type,
        }

    def infer_artifact_type(self, description: str) -> Optional[str]:
        """Infer artifact type from description.

        Args:
            description: Artifact description from filename

        Returns:
            Artifact type or None if no match

        Examples:
            >>> service.infer_artifact_type("wx-task-investigation")
            "investigation"
            >>> service.infer_artifact_type("phase1-implementation-plan")
            "plan"
        """
        description_lower = description.lower()

        for artifact_type, pattern in self.TYPE_PATTERNS.items():
            if re.search(pattern, description_lower):
                return artifact_type

        return None

    async def parse_content(self, file_path: str) -> Dict:
        """Extract metadata from markdown content.

        Args:
            file_path: Absolute path to artifact file

        Returns:
            Dict with title, content, jira_keys, keywords, entities

        Examples:
            >>> await service.parse_content("/path/to/artifact.md")
            {
                "title": "WX Task Investigation",
                "content": "# WX Task Investigation\\n\\n...",
                "jira_keys": ["COMPUTE-1234", "WX-567"],
                "keywords": ["task", "lease", "investigation"],
                "entities": {
                    "systems": ["WX", "Redis"],
                    "alerts": ["wx-task-lease-expiration"]
                }
            }
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {
                "title": None,
                "content": None,
                "jira_keys": [],
                "keywords": [],
                "entities": {},
            }

        # Extract title (first markdown heading)
        title = self._extract_title(content)

        # Extract JIRA keys
        jira_keys = self._extract_jira_keys(content)

        # Extract keywords (from content)
        keywords = self.extract_keywords(content)

        # Extract entities (systems, alerts)
        entities = self.extract_entities(content)

        return {
            "title": title,
            "content": content,
            "jira_keys": jira_keys,
            "keywords": keywords,
            "entities": entities,
        }

    def _extract_title(self, content: str) -> Optional[str]:
        """Extract first markdown heading as title.

        Args:
            content: Markdown content

        Returns:
            Title string or None
        """
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                # Remove leading # and whitespace
                title = line.lstrip("#").strip()
                return title

        return None

    def _extract_jira_keys(self, content: str) -> List[str]:
        """Extract JIRA ticket keys from content.

        Args:
            content: Text content

        Returns:
            List of unique JIRA keys
        """
        matches = self.JIRA_KEY_PATTERN.findall(content)
        # Deduplicate and sort
        return sorted(list(set(matches)))

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text.

        Simple approach: lowercase words, filter common words, take most frequent.

        Args:
            text: Text content

        Returns:
            List of keywords (up to 10)
        """
        # Common English words to filter out
        STOPWORDS = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "can",
            "may",
            "might",
        }

        # Extract words (alphanumeric + hyphens)
        words = re.findall(r"\b[a-z0-9]+-?[a-z0-9]+\b", text.lower())

        # Filter stopwords and short words
        words = [w for w in words if w not in STOPWORDS and len(w) > 3]

        # Count word frequency
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top 10 keywords
        return [word for word, count in sorted_words[:10]]

    def extract_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract entities from content.

        Args:
            content: Text content

        Returns:
            Dict with "systems" and "alerts" lists

        Examples:
            >>> service.extract_entities("WX task failed in Redis")
            {"systems": ["WX", "Redis"], "alerts": []}
        """
        entities = {"systems": [], "alerts": []}

        # Extract systems
        for system in self.SYSTEMS:
            # Case-insensitive word boundary search
            pattern = re.compile(rf"\b{re.escape(system)}\b", re.IGNORECASE)
            if pattern.search(content):
                entities["systems"].append(system)

        # Deduplicate systems
        entities["systems"] = sorted(list(set(entities["systems"])))

        # Extract alert names (lowercase-with-dashes pattern)
        alert_matches = [m.group(0) for m in self.ALERT_PATTERN.finditer(content)]
        # Filter: must have at least one platform keyword
        platform_keywords = ["wx", "g4", "jobs", "temporal", "compute"]
        alerts = [
            match
            for match in alert_matches
            if any(kw in match.lower() for kw in platform_keywords)
        ]
        entities["alerts"] = sorted(list(set(alerts)))

        return entities

    async def get_artifact_by_id(self, artifact_id: UUID) -> Optional[InvestigationArtifact]:
        """Get artifact by ID.

        Args:
            artifact_id: Artifact UUID

        Returns:
            InvestigationArtifact or None
        """
        result = await self.db.execute(
            select(InvestigationArtifact).where(InvestigationArtifact.id == artifact_id)
        )
        return result.scalar_one_or_none()

    async def get_artifact_by_path(self, file_path: str) -> Optional[InvestigationArtifact]:
        """Get artifact by file path.

        Args:
            file_path: Absolute file path

        Returns:
            InvestigationArtifact or None
        """
        result = await self.db.execute(
            select(InvestigationArtifact).where(
                InvestigationArtifact.file_path == file_path
            )
        )
        return result.scalar_one_or_none()

    async def search_artifacts(
        self,
        jira_key: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> List[InvestigationArtifact]:
        """Search artifacts by criteria.

        Args:
            jira_key: Filter by JIRA key (e.g., "COMPUTE-1234")
            keywords: Filter by keywords
            project: Filter by project (wx, g4, jobs, etc.)
            limit: Maximum results

        Returns:
            List of matching artifacts
        """
        query = select(InvestigationArtifact).where(
            InvestigationArtifact.deleted_at.is_(None)
        )

        if jira_key:
            # JSONB contains query
            query = query.where(
                InvestigationArtifact.jira_keys.contains([jira_key])
            )

        if keywords and len(keywords) > 0:
            # Check if any keyword in keywords JSONB array
            for keyword in keywords:
                query = query.where(
                    InvestigationArtifact.keywords.contains([keyword])
                )

        if project:
            query = query.where(InvestigationArtifact.project == project)

        # Order by created_at descending
        query = query.order_by(InvestigationArtifact.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_similar_artifacts(
        self, artifact_id: UUID, limit: int = 5
    ) -> List[InvestigationArtifact]:
        """Find similar artifacts based on keywords and JIRA keys.

        Phase 1: Keyword + JIRA key overlap
        Phase 2: Embedding similarity (future)

        Args:
            artifact_id: Artifact to find similar to
            limit: Maximum results

        Returns:
            List of similar artifacts
        """
        # Get source artifact
        artifact = await self.get_artifact_by_id(artifact_id)
        if not artifact:
            return []

        # Find artifacts with overlapping keywords or JIRA keys
        query = select(InvestigationArtifact).where(
            InvestigationArtifact.id != artifact_id,
            InvestigationArtifact.deleted_at.is_(None),
        )

        # Filter by project (similar project = more relevant)
        if artifact.project:
            query = query.where(InvestigationArtifact.project == artifact.project)

        # TODO: Rank by keyword/JIRA key overlap
        # For now, just return recent from same project
        query = query.order_by(InvestigationArtifact.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def scan_artifacts(
        self, base_path: str = "~/claude/projects"
    ) -> Dict[str, int]:
        """Scan all artifact directories and index to database.

        Args:
            base_path: Base path to projects directory

        Returns:
            Dict with stats: total_scanned, new_artifacts, updated_artifacts, errors

        Examples:
            >>> stats = await service.scan_artifacts()
            >>> print(f"Scanned {stats['total_scanned']} artifacts")
        """
        base_path_obj = Path(base_path).expanduser()
        stats = {
            "total_scanned": 0,
            "new_artifacts": 0,
            "updated_artifacts": 0,
            "errors": [],
        }

        logger.info(f"Starting artifact scan from {base_path_obj}")

        # Scan each project directory
        for project_dir in base_path_obj.glob("*-notes"):
            project = project_dir.name.replace("-notes", "")
            artifacts_dir = project_dir / "artifacts"

            if not artifacts_dir.exists():
                logger.debug(f"No artifacts directory for {project}")
                continue

            logger.info(f"Scanning {project} artifacts: {artifacts_dir}")

            # Scan all .md files
            for file_path in artifacts_dir.glob("*.md"):
                # Skip INDEX.md, README.md, etc.
                if file_path.name.upper() in ["INDEX.MD", "README.MD"]:
                    continue

                try:
                    result = await self._index_artifact(file_path, project)
                    stats["total_scanned"] += 1

                    if result == "new":
                        stats["new_artifacts"] += 1
                    elif result == "updated":
                        stats["updated_artifacts"] += 1

                except Exception as e:
                    logger.error(f"Error indexing {file_path}: {e}")
                    stats["errors"].append({"file": str(file_path), "error": str(e)})

        logger.info(
            f"Artifact scan complete: {stats['total_scanned']} scanned, "
            f"{stats['new_artifacts']} new, {stats['updated_artifacts']} updated, "
            f"{len(stats['errors'])} errors"
        )

        return stats

    async def _index_artifact(
        self, file_path: Path, project: str
    ) -> str:
        """Index a single artifact file.

        Args:
            file_path: Path to artifact file
            project: Project name (wx, g4, jobs, etc.)

        Returns:
            "new", "updated", or "skipped"
        """
        # Check if already indexed
        existing = await self.get_artifact_by_path(str(file_path))

        # Check if file modified since last index
        file_mtime = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=timezone.utc
        )

        if existing and existing.file_modified_at:
            # Compare mtimes
            if existing.file_modified_at >= file_mtime:
                # Already indexed and up-to-date
                logger.debug(f"Skipping up-to-date artifact: {file_path.name}")
                return "skipped"

        # Parse filename metadata
        filename_meta = self.parse_filename(file_path.name)
        if not filename_meta:
            logger.warning(f"Invalid filename format: {file_path.name}")
            raise ValueError(f"Invalid filename format: {file_path.name}")

        # Parse content
        content_meta = await self.parse_content(str(file_path))

        # Get file size
        file_size = file_path.stat().st_size

        if existing:
            # Update existing artifact
            existing.filename = file_path.name
            existing.file_size = file_size
            existing.project = project
            existing.artifact_type = filename_meta["artifact_type"]
            existing.created_at = filename_meta["created_at"]
            existing.description = filename_meta["description"]
            existing.title = content_meta["title"]
            existing.content = content_meta["content"]
            existing.jira_keys = content_meta["jira_keys"]
            existing.keywords = content_meta["keywords"]
            existing.entities = content_meta["entities"]
            existing.file_modified_at = file_mtime
            existing.indexed_at = datetime.now(timezone.utc)

            await self.db.commit()
            logger.info(f"Updated artifact: {file_path.name}")
            return "updated"
        else:
            # Create new artifact
            artifact = InvestigationArtifact(
                file_path=str(file_path),
                filename=file_path.name,
                file_size=file_size,
                project=project,
                artifact_type=filename_meta["artifact_type"],
                created_at=filename_meta["created_at"],
                description=filename_meta["description"],
                title=content_meta["title"],
                content=content_meta["content"],
                jira_keys=content_meta["jira_keys"],
                keywords=content_meta["keywords"],
                entities=content_meta["entities"],
                file_modified_at=file_mtime,
            )

            self.db.add(artifact)
            await self.db.commit()
            logger.info(f"Indexed new artifact: {file_path.name}")
            return "new"
