"""GitLab Merge Requests API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.gitlab_merge_request import GitLabMergeRequest
from app.services.gitlab_mr_service import GitLabMRService

router = APIRouter(prefix="/gitlab/mrs", tags=["gitlab-mrs"])


# Pydantic response models
class GitLabMRResponse(BaseModel):
    """GitLab merge request response."""

    id: str
    external_mr_id: int
    repository: str
    title: str
    description: Optional[str]
    url: str
    source_branch: str
    target_branch: str
    author: str
    reviewers: Optional[dict]
    approval_status: Optional[str]
    ci_status: Optional[str]
    state: str
    jira_keys: Optional[List[str]]
    created_at: str
    updated_at: str
    merged_at: Optional[str]
    closed_at: Optional[str]
    last_synced_at: str
    # Computed properties
    is_approved: bool
    is_ci_passing: bool
    is_merged: bool
    is_open: bool
    is_stale: bool
    age_days: int
    has_jira_keys: bool
    short_repository: str
    project_name: str

    class Config:
        from_attributes = True

    @classmethod
    def from_model(cls, mr: GitLabMergeRequest) -> "GitLabMRResponse":
        """Convert SQLAlchemy model to Pydantic response."""
        return cls(
            id=str(mr.id),
            external_mr_id=mr.external_mr_id,
            repository=mr.repository,
            title=mr.title,
            description=mr.description,
            url=mr.url,
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            author=mr.author,
            reviewers=mr.reviewers,
            approval_status=mr.approval_status,
            ci_status=mr.ci_status,
            state=mr.state,
            jira_keys=mr.jira_keys,
            created_at=mr.created_at.isoformat(),
            updated_at=mr.updated_at.isoformat(),
            merged_at=mr.merged_at.isoformat() if mr.merged_at else None,
            closed_at=mr.closed_at.isoformat() if mr.closed_at else None,
            last_synced_at=mr.last_synced_at.isoformat(),
            # Computed properties
            is_approved=mr.is_approved,
            is_ci_passing=mr.is_ci_passing,
            is_merged=mr.is_merged,
            is_open=mr.is_open,
            is_stale=mr.is_stale,
            age_days=mr.age_days,
            has_jira_keys=mr.has_jira_keys,
            short_repository=mr.short_repository,
            project_name=mr.project_name,
        )


class GitLabMRListResponse(BaseModel):
    """List of GitLab merge requests."""

    mrs: List[GitLabMRResponse]
    total: int


class GitLabMRScanStatsResponse(BaseModel):
    """GitLab MR scan statistics."""

    repository: str
    state: str
    total_scanned: int
    new_mrs: int
    updated_mrs: int
    unchanged_mrs: int
    errors: List[str]


@router.get("", response_model=GitLabMRListResponse)
async def list_mrs(
    repository: Optional[str] = None,
    state: Optional[str] = None,
    author: Optional[str] = None,
    jira_key: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List GitLab merge requests.

    Args:
        repository: Filter by repository (e.g., "wx/wx", "product/g4-wk/g4")
        state: Filter by state ("opened", "merged", "closed")
        author: Filter by author username
        jira_key: Filter by JIRA key
        limit: Maximum number of MRs to return (max: 200, default: 50)

    Returns:
        List of merge requests with metadata
    """
    service = GitLabMRService(db)

    mrs = await service.search_mrs(
        repository=repository,
        state=state,
        author=author,
        jira_key=jira_key,
        limit=limit,
    )

    return GitLabMRListResponse(
        mrs=[GitLabMRResponse.from_model(mr) for mr in mrs],
        total=len(mrs),
    )


@router.get("/search", response_model=GitLabMRListResponse)
async def search_mrs(
    q: str,
    repository: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search GitLab merge requests.

    Searches in title and description.

    Args:
        q: Search query string
        repository: Filter by repository
        state: Filter by state
        limit: Maximum number of results (max: 200, default: 50)

    Returns:
        List of matching merge requests
    """
    service = GitLabMRService(db)
    mrs = await service.search_mrs(
        query=q,
        repository=repository,
        state=state,
        limit=limit,
    )

    return GitLabMRListResponse(
        mrs=[GitLabMRResponse.from_model(mr) for mr in mrs],
        total=len(mrs),
    )


@router.get("/jira/{jira_key}", response_model=GitLabMRListResponse)
async def get_mrs_by_jira(
    jira_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get merge requests mentioning a JIRA key.

    Args:
        jira_key: JIRA key (e.g., "COMPUTE-1234")

    Returns:
        List of merge requests mentioning the JIRA key
    """
    service = GitLabMRService(db)
    mrs = await service.get_mrs_by_jira(jira_key.upper())

    return GitLabMRListResponse(
        mrs=[GitLabMRResponse.from_model(mr) for mr in mrs],
        total=len(mrs),
    )


@router.get("/branch/{branch_name:path}", response_model=GitLabMRListResponse)
async def get_mrs_by_branch(
    branch_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Get merge requests by source branch name.

    Args:
        branch_name: Branch name (e.g., "ao/COMPUTE-1234-new-feature")

    Returns:
        List of merge requests with this source branch
    """
    service = GitLabMRService(db)
    mrs = await service.get_mrs_by_branch(branch_name)

    return GitLabMRListResponse(
        mrs=[GitLabMRResponse.from_model(mr) for mr in mrs],
        total=len(mrs),
    )


@router.get("/{repository:path}/{mr_number}", response_model=GitLabMRResponse)
async def get_mr(
    repository: str,
    mr_number: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single merge request by repository and MR number.

    Args:
        repository: Repository path (e.g., "wx/wx")
        mr_number: MR number (iid)

    Returns:
        Merge request details

    Raises:
        404: MR not found
    """
    service = GitLabMRService(db)
    mr = await service.get_mr_by_number(repository, mr_number)

    if not mr:
        raise HTTPException(status_code=404, detail="Merge request not found")

    return GitLabMRResponse.from_model(mr)


@router.post("/scan", response_model=List[GitLabMRScanStatsResponse])
async def scan_mrs(
    repositories: Optional[List[str]] = None,
    state: str = "opened",
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Scan GitLab repositories for merge requests.

    This endpoint triggers a manual scan of one or more repositories.

    Args:
        repositories: List of repositories to scan (default: all tracked repos)
        state: MR state to scan ("opened", "merged", "closed", "all")
        limit: Maximum MRs per repository

    Returns:
        Scan statistics for each repository
    """
    service = GitLabMRService(db)

    # Use default repositories if none specified
    if not repositories:
        repositories = service.DEFAULT_REPOSITORIES

    results = []
    for repo in repositories:
        stats = await service.scan_repository_mrs(repo, state=state, limit=limit)
        results.append(GitLabMRScanStatsResponse(**stats))

    return results
