"""Project documentation API endpoints."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.project_doc_service import ProjectDocService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/project-docs", tags=["project-docs"])


# Pydantic response models
class ProjectDocResponse(BaseModel):
    """Response model for project documentation."""

    id: str
    project_name: str
    file_path: str
    team: Optional[str]
    primary_contact: Optional[str]
    repositories: List[str]
    slack_channels: List[str]
    word_count: int
    is_stale: bool
    last_updated_days_ago: int
    file_modified_at: Optional[datetime]
    last_synced_at: datetime
    keywords: List[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, doc):
        """Create response from ORM model."""
        return cls(
            id=str(doc.id),
            project_name=doc.project_name,
            file_path=doc.file_path,
            team=doc.team,
            primary_contact=doc.primary_contact,
            repositories=doc.repositories or [],
            slack_channels=doc.slack_channels or [],
            word_count=doc.word_count,
            is_stale=doc.is_stale,
            last_updated_days_ago=doc.last_updated_days_ago,
            file_modified_at=doc.file_modified_at,
            last_synced_at=doc.last_synced_at,
            keywords=doc.keywords or [],
        )


class SectionResponse(BaseModel):
    """Response model for project documentation section."""

    id: str
    section_name: str
    heading_level: int
    content: str
    order_index: int

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, section):
        """Create response from ORM model."""
        return cls(
            id=str(section.id),
            section_name=section.section_name,
            heading_level=section.heading_level,
            content=section.content,
            order_index=section.order_index,
        )


class ScanResponse(BaseModel):
    """Response model for scan operation."""

    total_scanned: int
    new_docs: int
    updated_docs: int
    unchanged_docs: int
    error_count: int
    note: Optional[str] = None


@router.get("", response_model=List[ProjectDocResponse])
async def list_project_docs(
    team: Optional[str] = Query(None, description="Filter by team (compute, datapipeline, etc.)"),
    stale_only: bool = Query(False, description="Show only stale docs (>30 days)"),
    limit: int = Query(50, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectDocResponse]:
    """List all project documentation.

    Args:
        team: Filter by team name
        stale_only: Show only stale documentation
        limit: Maximum results (default 50, max 100)
        db: Database session

    Returns:
        List of project documentation matching filters
    """
    service = ProjectDocService(db)

    # Get all docs
    results = await service.search_project_docs(
        query="",
        team=team,
        limit=limit
    )

    # Filter stale if requested
    if stale_only:
        results = [doc for doc in results if doc.is_stale]

    return [ProjectDocResponse.from_orm(doc) for doc in results]


@router.get("/search", response_model=List[ProjectDocResponse])
async def search_project_docs(
    query: str = Query(..., description="Search query (keywords, content)"),
    project: Optional[str] = Query(None, description="Filter by project"),
    team: Optional[str] = Query(None, description="Filter by team"),
    limit: int = Query(20, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectDocResponse]:
    """Search project documentation.

    Args:
        query: Search query string
        project: Filter by project name
        team: Filter by team
        limit: Maximum results (default 20, max 100)
        db: Database session

    Returns:
        List of matching project documentation
    """
    service = ProjectDocService(db)

    results = await service.search_project_docs(
        query=query,
        project=project,
        team=team,
        limit=limit
    )

    return [ProjectDocResponse.from_orm(doc) for doc in results]


@router.get("/{project_name}", response_model=ProjectDocResponse)
async def get_project_doc(
    project_name: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectDocResponse:
    """Get project documentation by name.

    Args:
        project_name: Project name (e.g., "wx", "g4", "jobs")
        db: Database session

    Returns:
        Project documentation details

    Raises:
        HTTPException: 404 if project not found
    """
    service = ProjectDocService(db)

    doc = await service.get_project_doc(project_name)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    return ProjectDocResponse.from_orm(doc)


@router.get("/{project_name}/sections", response_model=List[SectionResponse])
async def get_project_sections(
    project_name: str,
    db: AsyncSession = Depends(get_db),
) -> List[SectionResponse]:
    """Get all sections for a project.

    Args:
        project_name: Project name (e.g., "wx", "g4", "jobs")
        db: Database session

    Returns:
        List of documentation sections ordered by appearance

    Raises:
        HTTPException: 404 if project not found
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.project_doc import ProjectDoc

    # Get project doc with sections eagerly loaded
    result = await db.execute(
        select(ProjectDoc)
        .where(ProjectDoc.project_name == project_name)
        .options(selectinload(ProjectDoc.doc_sections))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    # Sort sections by order
    sections = sorted(doc.doc_sections, key=lambda s: s.order_index)

    return [SectionResponse.from_orm(section) for section in sections]


@router.post("/scan", response_model=ScanResponse)
async def scan_project_docs(
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """Trigger project documentation scan.

    Scans ~/claude/projects/ for *-notes/*-claude.md files
    and updates database with latest content.

    Args:
        db: Database session

    Returns:
        Scan statistics
    """
    service = ProjectDocService(db)

    logger.info("Manual project docs scan triggered via API")
    stats = await service.scan_project_docs()

    return ScanResponse(
        total_scanned=stats["total_scanned"],
        new_docs=stats["new_docs"],
        updated_docs=stats["updated_docs"],
        unchanged_docs=stats["unchanged_docs"],
        error_count=len(stats["errors"]),
        note="Scan complete" if not stats["errors"] else f"{len(stats['errors'])} errors occurred"
    )
