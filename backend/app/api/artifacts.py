"""Artifact API endpoints for Commander enrichment."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.artifact_service import ArtifactService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


# Pydantic response models
class ArtifactResponse(BaseModel):
    """Response model for artifact data."""

    id: str
    file_path: str
    filename: str
    file_size: Optional[int]
    project: Optional[str]
    artifact_type: Optional[str]
    created_at: datetime
    title: Optional[str]
    description: Optional[str]
    content_preview: str  # First 200 chars
    jira_keys: List[str]
    keywords: List[str]
    entities: dict
    file_modified_at: Optional[datetime]
    indexed_at: datetime
    age_days: int
    is_recent: bool
    has_jira_keys: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, artifact):
        """Create response from ORM model."""
        return cls(
            id=str(artifact.id),
            file_path=artifact.file_path,
            filename=artifact.filename,
            file_size=artifact.file_size,
            project=artifact.project,
            artifact_type=artifact.artifact_type,
            created_at=artifact.created_at,
            title=artifact.title,
            description=artifact.description,
            content_preview=artifact.content_preview,
            jira_keys=artifact.jira_keys or [],
            keywords=artifact.keywords or [],
            entities=artifact.entities or {},
            file_modified_at=artifact.file_modified_at,
            indexed_at=artifact.indexed_at,
            age_days=artifact.age_days,
            is_recent=artifact.is_recent,
            has_jira_keys=artifact.has_jira_keys,
        )


class ArtifactScanResponse(BaseModel):
    """Response model for artifact scan operation."""

    total_scanned: int
    new_artifacts: int
    updated_artifacts: int
    error_count: int
    errors: List[dict]


@router.get("", response_model=List[ArtifactResponse])
async def list_artifacts(
    project: Optional[str] = Query(None, description="Filter by project (wx, g4, jobs, etc.)"),
    artifact_type: Optional[str] = Query(None, description="Filter by type (investigation, plan, etc.)"),
    keywords: Optional[str] = Query(None, description="Filter by keywords (comma-separated)"),
    limit: int = Query(50, le=200, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[ArtifactResponse]:
    """List artifacts with optional filters.

    Args:
        project: Filter by project name
        artifact_type: Filter by artifact type
        keywords: Comma-separated keywords
        limit: Maximum results (default 50, max 200)
        db: Database session

    Returns:
        List of artifacts matching filters
    """
    service = ArtifactService(db)

    # Parse keywords
    keyword_list = None
    if keywords and isinstance(keywords, str):
        keyword_list = [k.strip() for k in keywords.split(",")]

    # Search with filters
    results = await service.search_artifacts(
        keywords=keyword_list,
        project=project,
        limit=limit,
    )

    # Filter by artifact_type if provided (client-side for now)
    if artifact_type:
        results = [a for a in results if a.artifact_type == artifact_type]

    return [ArtifactResponse.from_orm(a) for a in results]


@router.get("/search", response_model=List[ArtifactResponse])
async def search_artifacts(
    jira_key: Optional[str] = Query(None, description="Filter by JIRA key (e.g., COMPUTE-1234)"),
    keywords: Optional[str] = Query(None, description="Filter by keywords (comma-separated)"),
    project: Optional[str] = Query(None, description="Filter by project (wx, g4, jobs, etc.)"),
    date_from: Optional[str] = Query(None, description="Filter by created date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by created date to (YYYY-MM-DD)"),
    limit: int = Query(20, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[ArtifactResponse]:
    """Search artifacts by various criteria.

    Args:
        jira_key: JIRA ticket key
        keywords: Comma-separated keywords
        project: Project name
        date_from: Created date from (YYYY-MM-DD)
        date_to: Created date to (YYYY-MM-DD)
        limit: Maximum results (default 20, max 100)
        db: Database session

    Returns:
        List of matching artifacts
    """
    service = ArtifactService(db)

    # Parse keywords
    keyword_list = None
    if keywords and isinstance(keywords, str):
        keyword_list = [k.strip() for k in keywords.split(",")]

    # Search
    results = await service.search_artifacts(
        jira_key=jira_key,
        keywords=keyword_list,
        project=project,
        limit=limit,
    )

    # TODO: Add date filtering (would need to enhance service method)
    # For now, filter client-side
    if date_from or date_to:
        from datetime import datetime as dt
        filtered = []
        for artifact in results:
            artifact_date = artifact.created_at.date()
            if date_from:
                from_date = dt.strptime(date_from, "%Y-%m-%d").date()
                if artifact_date < from_date:
                    continue
            if date_to:
                to_date = dt.strptime(date_to, "%Y-%m-%d").date()
                if artifact_date > to_date:
                    continue
            filtered.append(artifact)
        results = filtered

    return [ArtifactResponse.from_orm(a) for a in results]


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Get single artifact by ID.

    Args:
        artifact_id: Artifact UUID
        db: Database session

    Returns:
        Artifact details

    Raises:
        HTTPException: 404 if artifact not found
    """
    service = ArtifactService(db)

    try:
        artifact_uuid = UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact ID format")

    artifact = await service.get_artifact_by_id(artifact_uuid)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return ArtifactResponse.from_orm(artifact)


@router.get("/similar/{artifact_id}", response_model=List[ArtifactResponse])
async def find_similar_artifacts(
    artifact_id: str,
    limit: int = Query(5, le=20, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> List[ArtifactResponse]:
    """Find similar artifacts based on keywords and JIRA keys.

    Phase 1: Keyword + JIRA key overlap
    Phase 2: Embedding similarity (future)

    Args:
        artifact_id: Artifact UUID to find similar to
        limit: Maximum results (default 5, max 20)
        db: Database session

    Returns:
        List of similar artifacts

    Raises:
        HTTPException: 404 if artifact not found
    """
    service = ArtifactService(db)

    try:
        artifact_uuid = UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact ID format")

    # Check artifact exists
    artifact = await service.get_artifact_by_id(artifact_uuid)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Find similar
    results = await service.find_similar_artifacts(artifact_uuid, limit=limit)

    return [ArtifactResponse.from_orm(a) for a in results]


@router.post("/{artifact_id}/refresh", response_model=ArtifactResponse)
async def refresh_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArtifactResponse:
    """Force re-index of specific artifact.

    Re-reads the file from disk and updates database record.

    Args:
        artifact_id: Artifact UUID
        db: Database session

    Returns:
        Updated artifact

    Raises:
        HTTPException: 404 if artifact not found
    """
    service = ArtifactService(db)

    try:
        artifact_uuid = UUID(artifact_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid artifact ID format")

    # Get existing artifact
    artifact = await service.get_artifact_by_id(artifact_uuid)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Re-index by scanning the file
    from pathlib import Path

    file_path = Path(artifact.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found on disk")

    # Force re-index by updating mtime tracking
    result = await service._index_artifact(file_path, artifact.project)
    logger.info(f"Refreshed artifact {artifact_id}: {result}")

    # Fetch updated artifact
    artifact = await service.get_artifact_by_id(artifact_uuid)

    return ArtifactResponse.from_orm(artifact)


@router.get("/context/{context_id}", response_model=List[ArtifactResponse])
async def get_context_artifacts(
    context_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[ArtifactResponse]:
    """Get all artifacts linked to a work context.

    This will query entity_links to find artifacts connected to the context.

    Args:
        context_id: Work context UUID
        db: Database session

    Returns:
        List of linked artifacts
    """
    # TODO: Implement after Day 6 (auto-linking)
    # For now, return empty list
    logger.info(f"Context artifact query for {context_id} (not yet implemented)")
    return []


@router.post("/scan", response_model=ArtifactScanResponse)
async def scan_artifacts(
    db: AsyncSession = Depends(get_db),
) -> ArtifactScanResponse:
    """Trigger artifact filesystem scan.

    Scans ~/claude/projects/*/artifacts/ directories and indexes new/updated files.

    Args:
        db: Database session

    Returns:
        Scan statistics
    """
    service = ArtifactService(db)

    logger.info("Manual artifact scan triggered via API")
    stats = await service.scan_artifacts()

    return ArtifactScanResponse(
        total_scanned=stats["total_scanned"],
        new_artifacts=stats["new_artifacts"],
        updated_artifacts=stats["updated_artifacts"],
        error_count=len(stats["errors"]),
        errors=stats["errors"][:10],  # Return first 10 errors
    )
