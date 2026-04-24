"""Service for indexing Google Drive documents."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.google_drive_document import GoogleDriveDocument

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for indexing Google Drive documents."""

    GDRIVE_BASE = Path.home() / "Library" / "CloudStorage"
    COMPUTE_TEAM_PATH = "GoogleDrive-aaryn@planet.com/Shared drives/Compute Team"

    # Document kind patterns
    POSTMORTEM_PATTERNS = ["postmortem", "post-mortem", "prodissue-", "incident"]
    RFD_PATTERNS = ["rfd:", "rfc:", "adr:"]
    MEETING_NOTES_PATTERNS = ["meeting notes", "sprint planning", "retrospective", "standup"]
    ON_CALL_PATTERNS = ["on-call", "oncall", "on call"]

    # JIRA key pattern
    JIRA_KEY_PATTERN = re.compile(r"\b(?:COMPUTE|PRODISSUE|WX|JOBS|G4|TEMPORAL|ESO)-\d+\b", re.IGNORECASE)

    # Tech keywords
    TECH_KEYWORDS = {
        "kubernetes", "k8s", "postgres", "redis", "api", "database",
        "incident", "outage", "bug", "failure", "timeout", "oom",
        "deployment", "migration", "rollback", "scaling"
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_google_drive(self) -> Dict:
        """Scan Google Drive shared drives for .gdoc files.

        Returns:
            Dict with scan statistics
        """
        logger.info("Scanning Google Drive shared drives")

        stats = {
            "total_scanned": 0,
            "new_docs": 0,
            "updated_docs": 0,
            "unchanged_docs": 0,
            "errors": [],
        }

        compute_team_path = self.GDRIVE_BASE / self.COMPUTE_TEAM_PATH

        if not compute_team_path.exists():
            error_msg = f"Compute Team shared drive not found: {compute_team_path}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            return stats

        # Find all .gdoc files
        for gdoc_file in compute_team_path.rglob("*.gdoc"):
            stats["total_scanned"] += 1

            try:
                result = await self.update_document(gdoc_file)

                if result == "new":
                    stats["new_docs"] += 1
                elif result == "updated":
                    stats["updated_docs"] += 1
                elif result == "unchanged":
                    stats["unchanged_docs"] += 1

                logger.debug(f"Processed {gdoc_file.name}: {result}")

            except Exception as e:
                # Rollback on error to keep session clean
                await self.db.rollback()
                error_msg = f"Error processing {gdoc_file}: {e}"
                logger.error(error_msg, exc_info=True)
                stats["errors"].append(error_msg)

        return stats

    def parse_gdoc_file(self, file_path: Path) -> Dict:
        """Parse .gdoc JSON file.

        Args:
            file_path: Path to .gdoc file

        Returns:
            {
                "external_doc_id": "1a2b3c4d5e6f7g8h9i0j",
                "url": "https://docs.google.com/document/d/...",
                "doc_type": "document",
                "owner": "aaryn@planet.com"
            }
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Extract doc ID from URL or doc_id field
            doc_id = data.get("doc_id")
            url = data.get("url", "")

            # Determine doc type from URL
            doc_type = "document"  # default
            if "spreadsheets" in url:
                doc_type = "spreadsheet"
            elif "presentation" in url:
                doc_type = "presentation"

            # Get owner email
            owner = data.get("email")

            return {
                "external_doc_id": doc_id,
                "url": url,
                "doc_type": doc_type,
                "owner": owner
            }

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            raise

    def infer_document_metadata(self, file_path: Path, gdoc_data: Dict) -> Dict:
        """Infer metadata from file path and name.

        Args:
            file_path: Path to .gdoc file
            gdoc_data: Parsed .gdoc JSON data

        Returns:
            {
                "title": "PRODISSUE-574 Postmortem - 2024-02-28 Jobs elevated failure rate",
                "shared_drive": "Compute Team",
                "folder_path": "Postmortems",
                "document_kind": "postmortem",
                "project": "jobs",
                "jira_keys": ["PRODISSUE-574"],
                "keywords": ["jobs", "failure", "incident"]
            }
        """
        # Extract from path
        parts = file_path.parts
        try:
            shared_drive_idx = parts.index("Shared drives")
            shared_drive = parts[shared_drive_idx + 1]  # "Compute Team"
            # Folder path relative to shared drive
            folder_path = "/".join(parts[shared_drive_idx + 2:-1])  # "Postmortems/Completed"
        except (ValueError, IndexError):
            shared_drive = None
            folder_path = None

        # Extract from filename
        filename = file_path.stem  # Remove .gdoc extension
        filename_lower = filename.lower()

        # Determine document kind
        document_kind = None
        if any(p in filename_lower for p in self.POSTMORTEM_PATTERNS):
            document_kind = "postmortem"
        elif any(p in filename_lower for p in self.RFD_PATTERNS):
            # Check if it's RFD or RFC
            if "rfd:" in filename_lower:
                document_kind = "rfd"
            else:
                document_kind = "rfc"
        elif any(p in filename_lower for p in self.MEETING_NOTES_PATTERNS):
            document_kind = "meeting-notes"
        elif any(p in filename_lower for p in self.ON_CALL_PATTERNS):
            document_kind = "on-call-log"

        # Also check folder path for kind
        if folder_path and document_kind is None:
            folder_lower = folder_path.lower()
            if "postmortem" in folder_lower:
                document_kind = "postmortem"
            elif "rfc" in folder_lower or "rfd" in folder_lower or "design doc" in folder_lower:
                document_kind = "rfd"
            elif "meeting" in folder_lower:
                document_kind = "meeting-notes"
            elif "on-call" in folder_lower or "oncall" in folder_lower:
                document_kind = "on-call-log"

        # Extract JIRA keys
        jira_keys = list(set(self.JIRA_KEY_PATTERN.findall(filename)))

        # Infer project from folder path or filename
        project = None
        combined_text = f"{folder_path or ''} {filename}".lower()

        if "workexchange" in combined_text or " wx " in combined_text or "wx-" in combined_text or "/wx/" in combined_text:
            project = "wx"
        elif "jobs" in combined_text:
            project = "jobs"
        elif " g4 " in combined_text or "g4-" in combined_text or "/g4/" in combined_text:
            project = "g4"
        elif "temporal" in combined_text:
            project = "temporal"
        elif "eso" in combined_text:
            project = "eso"
        elif "fusion" in combined_text or "tardis" in combined_text:
            project = "fusion"

        # Extract keywords from filename
        keywords = []
        words = re.findall(r'\b\w+\b', filename_lower)
        for word in words:
            if word in self.TECH_KEYWORDS:
                keywords.append(word)

        return {
            "title": filename,
            "filename": file_path.name,
            "shared_drive": shared_drive,
            "folder_path": folder_path,
            "document_kind": document_kind,
            "project": project,
            "jira_keys": jira_keys,
            "keywords": keywords
        }

    async def update_document(self, file_path: Path) -> str:
        """Update or create document from file.

        Args:
            file_path: Path to .gdoc file

        Returns:
            "new", "updated", or "unchanged"
        """
        # Parse .gdoc file
        gdoc_data = self.parse_gdoc_file(file_path)

        # Infer metadata from path and filename
        metadata = self.infer_document_metadata(file_path, gdoc_data)

        # Get file modification time
        file_stat = file_path.stat()
        last_modified_at = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)

        # Check if document already exists
        result = await self.db.execute(
            select(GoogleDriveDocument).where(
                GoogleDriveDocument.external_doc_id == gdoc_data["external_doc_id"]
            )
        )
        existing_doc = result.scalar_one_or_none()

        # If modification time unchanged, skip update
        if existing_doc and existing_doc.last_modified_at:
            if abs((existing_doc.last_modified_at - last_modified_at).total_seconds()) < 1:
                return "unchanged"

        if existing_doc:
            # Update existing doc
            existing_doc.doc_type = gdoc_data["doc_type"]
            existing_doc.url = gdoc_data["url"]
            existing_doc.title = metadata["title"]
            existing_doc.file_path = str(file_path)
            existing_doc.filename = metadata["filename"]
            existing_doc.shared_drive = metadata["shared_drive"]
            existing_doc.folder_path = metadata["folder_path"]
            existing_doc.project = metadata["project"]
            existing_doc.document_kind = metadata["document_kind"]
            existing_doc.last_modified_at = last_modified_at
            existing_doc.owner = gdoc_data["owner"]
            existing_doc.jira_keys = metadata["jira_keys"] or None
            existing_doc.keywords = metadata["keywords"] or None
            existing_doc.last_indexed_at = datetime.now(timezone.utc)

            await self.db.commit()
            return "updated"

        else:
            # Create new doc
            new_doc = GoogleDriveDocument(
                external_doc_id=gdoc_data["external_doc_id"],
                doc_type=gdoc_data["doc_type"],
                url=gdoc_data["url"],
                title=metadata["title"],
                file_path=str(file_path),
                filename=metadata["filename"],
                shared_drive=metadata["shared_drive"],
                folder_path=metadata["folder_path"],
                project=metadata["project"],
                document_kind=metadata["document_kind"],
                last_modified_at=last_modified_at,
                owner=gdoc_data["owner"],
                jira_keys=metadata["jira_keys"] or None,
                keywords=metadata["keywords"] or None,
                last_indexed_at=datetime.now(timezone.utc)
            )
            self.db.add(new_doc)
            await self.db.commit()
            return "new"

    async def search_documents(
        self,
        query: str,
        shared_drive: Optional[str] = None,
        document_kind: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20
    ) -> List[GoogleDriveDocument]:
        """Search documents by keywords/content.

        Args:
            query: Search query string
            shared_drive: Filter by shared drive
            document_kind: Filter by document kind
            project: Filter by project
            limit: Maximum results

        Returns:
            List of matching GoogleDriveDocument instances
        """
        # Build base query
        stmt = select(GoogleDriveDocument)

        # Add filters
        conditions = []

        if shared_drive:
            conditions.append(GoogleDriveDocument.shared_drive == shared_drive)

        if document_kind:
            conditions.append(GoogleDriveDocument.document_kind == document_kind)

        if project:
            conditions.append(GoogleDriveDocument.project == project)

        # Search in title, keywords, JIRA keys
        if query:
            query_lower = query.lower()
            conditions.append(
                or_(
                    GoogleDriveDocument.title.ilike(f"%{query}%"),
                    GoogleDriveDocument.keywords.contains([query_lower]),
                    GoogleDriveDocument.jira_keys.contains([query.upper()])
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.order_by(GoogleDriveDocument.last_modified_at.desc())
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_document(self, external_doc_id: str) -> Optional[GoogleDriveDocument]:
        """Get document by external_doc_id.

        Args:
            external_doc_id: Google Doc ID

        Returns:
            GoogleDriveDocument instance or None
        """
        result = await self.db.execute(
            select(GoogleDriveDocument).where(
                GoogleDriveDocument.external_doc_id == external_doc_id
            )
        )
        return result.scalar_one_or_none()

    async def get_documents_by_jira(self, jira_key: str) -> List[GoogleDriveDocument]:
        """Get documents mentioning JIRA key.

        Args:
            jira_key: JIRA key (e.g., "PRODISSUE-574")

        Returns:
            List of GoogleDriveDocument instances
        """
        result = await self.db.execute(
            select(GoogleDriveDocument).where(
                GoogleDriveDocument.jira_keys.contains([jira_key.upper()])
            ).order_by(GoogleDriveDocument.last_modified_at.desc())
        )
        return list(result.scalars().all())

    async def list_postmortems(
        self,
        project: Optional[str] = None,
        limit: int = 50
    ) -> List[GoogleDriveDocument]:
        """List all postmortems.

        Args:
            project: Filter by project
            limit: Maximum results

        Returns:
            List of postmortem GoogleDriveDocument instances
        """
        stmt = select(GoogleDriveDocument).where(
            GoogleDriveDocument.document_kind == "postmortem"
        )

        if project:
            stmt = stmt.where(GoogleDriveDocument.project == project)

        stmt = stmt.order_by(GoogleDriveDocument.last_modified_at.desc())
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
