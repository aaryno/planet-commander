"""Public configuration API — exposes instance config for the frontend."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/urls")
async def get_urls():
    """Return base URLs for the frontend to use in links."""
    return {
        "gitlab": settings.gitlab_base_url,
        "jira": settings.jira_base_url,
        "grafana": settings.grafana_base_url,
        "slack": settings.slack_base_url,
    }


@router.get("/user")
async def get_user():
    """Return current user identity for 'me' filters."""
    return {
        "display_name": settings.user_display_name,
    }
