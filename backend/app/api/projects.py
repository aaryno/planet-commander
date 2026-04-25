"""Project configuration API — CRUD for project entities."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    color: str = "#6366F1"
    icon: str | None = None
    jira_project_keys: list[str] = Field(default_factory=list)
    jira_default_filters: dict[str, Any] = Field(default_factory=dict)
    repositories: list[dict[str, Any]] = Field(default_factory=list)
    grafana_dashboards: list[dict[str, Any]] = Field(default_factory=list)
    pagerduty_service_ids: list[str] = Field(default_factory=list)
    slack_channels: list[dict[str, Any]] = Field(default_factory=list)
    deployment_config: dict[str, Any] | None = None
    links: list[dict[str, Any]] = Field(default_factory=list)
    sort_order: int = 0


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    jira_project_keys: list[str] | None = None
    jira_default_filters: dict[str, Any] | None = None
    repositories: list[dict[str, Any]] | None = None
    grafana_dashboards: list[dict[str, Any]] | None = None
    pagerduty_service_ids: list[str] | None = None
    slack_channels: list[dict[str, Any]] | None = None
    deployment_config: dict[str, Any] | None = None
    links: list[dict[str, Any]] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str | None
    color: str
    icon: str | None
    jira_project_keys: list[str]
    jira_default_filters: dict[str, Any]
    repositories: list[dict[str, Any]]
    grafana_dashboards: list[dict[str, Any]]
    pagerduty_service_ids: list[str]
    slack_channels: list[dict[str, Any]]
    deployment_config: dict[str, Any] | None
    links: list[dict[str, Any]]
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str


def _to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=str(p.id),
        key=p.key,
        name=p.name,
        description=p.description,
        color=p.color,
        icon=p.icon,
        jira_project_keys=p.jira_project_keys or [],
        jira_default_filters=p.jira_default_filters or {},
        repositories=p.repositories or [],
        grafana_dashboards=p.grafana_dashboards or [],
        pagerduty_service_ids=p.pagerduty_service_ids or [],
        slack_channels=p.slack_channels or [],
        deployment_config=p.deployment_config,
        links=p.links or [],
        sort_order=p.sort_order,
        is_active=p.is_active,
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(Project).order_by(Project.sort_order, Project.key)
    if not include_inactive:
        query = query.where(Project.is_active == True)
    result = await db.execute(query)
    return [_to_response(p) for p in result.scalars().all()]


@router.get("/{key}", response_model=ProjectResponse)
async def get_project(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.key == key))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, f"Project '{key}' not found")
    return _to_response(project)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(req: ProjectCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Project).where(Project.key == req.key))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Project '{req.key}' already exists")

    project = Project(
        key=req.key,
        name=req.name,
        description=req.description,
        color=req.color,
        icon=req.icon,
        jira_project_keys=req.jira_project_keys,
        jira_default_filters=req.jira_default_filters,
        repositories=req.repositories,
        grafana_dashboards=req.grafana_dashboards,
        pagerduty_service_ids=req.pagerduty_service_ids,
        slack_channels=req.slack_channels,
        deployment_config=req.deployment_config,
        links=req.links,
        sort_order=req.sort_order,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    logger.info(f"Created project: {req.key}")
    return _to_response(project)


@router.put("/{key}", response_model=ProjectResponse)
async def update_project(
    key: str, req: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).where(Project.key == key))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, f"Project '{key}' not found")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    logger.info(f"Updated project: {key}")
    return _to_response(project)


@router.delete("/{key}", response_model=ProjectResponse)
async def delete_project(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.key == key))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, f"Project '{key}' not found")

    project.is_active = False
    await db.commit()
    await db.refresh(project)
    logger.info(f"Soft-deleted project: {key}")
    return _to_response(project)


@router.get("/{key}/links")
async def get_project_links(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.key == key))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, f"Project '{key}' not found")

    categorized: dict[str, list] = {}
    for link in (project.links or []):
        cat = link.get("category", "other")
        categorized.setdefault(cat, []).append(link)

    return {"project": key, "links": categorized}
