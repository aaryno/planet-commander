"""Google Drive documents API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.google_drive_document import GoogleDriveDocument
from app.services.google_drive_service import GoogleDriveService

router = APIRouter(prefix="/google-drive", tags=["google-drive"])


# Pydantic response models
class GoogleDriveDocumentResponse(BaseModel):
    """Google Drive document response."""

    id: str
    external_doc_id: str
    doc_type: str
    url: str
    title: str
    file_path: str
    filename: Optional[str]
    shared_drive: Optional[str]
    folder_path: Optional[str]
    project: Optional[str]
    document_kind: Optional[str]
    last_modified_at: Optional[str]
    owner: Optional[str]
    jira_keys: Optional[List[str]]
    keywords: Optional[List[str]]
    last_indexed_at: str
    created_at: str
    updated_at: str
    # Computed properties
    is_stale: bool
    is_postmortem: bool
    is_rfd: bool
    has_jira_keys: bool
    age_days: int

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, doc: GoogleDriveDocument) -> "GoogleDriveDocumentResponse":
        """Convert SQLAlchemy model to Pydantic response."""
        return cls(
            id=str(doc.id),
            external_doc_id=doc.external_doc_id,
            doc_type=doc.doc_type,
            url=doc.url,
            title=doc.title,
            file_path=doc.file_path,
            filename=doc.filename,
            shared_drive=doc.shared_drive,
            folder_path=doc.folder_path,
            project=doc.project,
            document_kind=doc.document_kind,
            last_modified_at=doc.last_modified_at.isoformat() if doc.last_modified_at else None,
            owner=doc.owner,
            jira_keys=doc.jira_keys,
            keywords=doc.keywords,
            last_indexed_at=doc.last_indexed_at.isoformat(),
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
            # Computed properties
            is_stale=doc.is_stale,
            is_postmortem=doc.is_postmortem,
            is_rfd=doc.is_rfd,
            has_jira_keys=doc.has_jira_keys,
            age_days=doc.age_days,
        )


class GoogleDriveDocumentListResponse(BaseModel):
    """List of Google Drive documents."""

    documents: List[GoogleDriveDocumentResponse]
    total: int


class ScanStatsResponse(BaseModel):
    """Google Drive scan statistics."""

    total_scanned: int
    new_docs: int
    updated_docs: int
    unchanged_docs: int
    errors: List[str]


@router.get("/documents", response_model=GoogleDriveDocumentListResponse)
async def list_documents(
    shared_drive: Optional[str] = None,
    document_kind: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List Google Drive documents.

    Args:
        shared_drive: Filter by shared drive name
        document_kind: Filter by document kind (postmortem, rfd, meeting-notes, etc.)
        project: Filter by project (wx, jobs, g4, temporal, etc.)
        limit: Maximum number of documents to return (default: 50)

    Returns:
        List of Google Drive documents with metadata
    """
    service = GoogleDriveService(db)

    # Use search_documents with empty query to get filtered list
    documents = await service.search_documents(
        query="",
        shared_drive=shared_drive,
        document_kind=document_kind,
        project=project,
        limit=limit,
    )

    return GoogleDriveDocumentListResponse(
        documents=[GoogleDriveDocumentResponse.from_model(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/search", response_model=GoogleDriveDocumentListResponse)
async def search_documents(
    q: str,
    shared_drive: Optional[str] = None,
    document_kind: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Search Google Drive documents.

    Searches in title, keywords, and JIRA keys.

    Args:
        q: Search query string
        shared_drive: Filter by shared drive name
        document_kind: Filter by document kind
        project: Filter by project
        limit: Maximum number of results (default: 20)

    Returns:
        List of matching documents
    """
    service = GoogleDriveService(db)
    documents = await service.search_documents(
        query=q,
        shared_drive=shared_drive,
        document_kind=document_kind,
        project=project,
        limit=limit,
    )

    return GoogleDriveDocumentListResponse(
        documents=[GoogleDriveDocumentResponse.from_model(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/jira/{jira_key}", response_model=GoogleDriveDocumentListResponse)
async def get_documents_by_jira(
    jira_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get documents mentioning a JIRA key.

    Args:
        jira_key: JIRA key (e.g., PRODISSUE-574, COMPUTE-1234)

    Returns:
        List of documents mentioning the JIRA key
    """
    service = GoogleDriveService(db)
    documents = await service.get_documents_by_jira(jira_key.upper())

    return GoogleDriveDocumentListResponse(
        documents=[GoogleDriveDocumentResponse.from_model(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/postmortems", response_model=GoogleDriveDocumentListResponse)
async def list_postmortems(
    project: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all postmortems.

    Args:
        project: Filter by project (wx, jobs, g4, temporal, etc.)
        limit: Maximum number of postmortems (default: 50)

    Returns:
        List of postmortem documents
    """
    service = GoogleDriveService(db)
    documents = await service.list_postmortems(project=project, limit=limit)

    return GoogleDriveDocumentListResponse(
        documents=[GoogleDriveDocumentResponse.from_model(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/documents/{external_doc_id}", response_model=GoogleDriveDocumentResponse)
async def get_document(
    external_doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document by external doc ID.

    Args:
        external_doc_id: Google Doc ID

    Returns:
        Google Drive document details

    Raises:
        404: Document not found
    """
    service = GoogleDriveService(db)
    document = await service.get_document(external_doc_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return GoogleDriveDocumentResponse.from_model(document)


@router.post("/scan", response_model=ScanStatsResponse)
async def scan_google_drive(
    db: AsyncSession = Depends(get_db),
):
    """Scan Google Drive for new/updated documents.

    This endpoint triggers a full scan of the Google Drive for Desktop mount,
    parsing all .gdoc files and updating the database.

    Returns:
        Scan statistics (total scanned, new, updated, unchanged, errors)
    """
    service = GoogleDriveService(db)
    stats = await service.scan_google_drive()

    return ScanStatsResponse(**stats)
