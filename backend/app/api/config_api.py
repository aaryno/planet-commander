"""Public configuration API — exposes instance config for the frontend."""

import logging

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

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


@router.get("/features")
async def get_features():
    """Return optional-integration feature flags for the frontend.

    The frontend uses these to hide UI elements (sidebar entries, pages,
    etc.) for integrations that aren't enabled on this instance. Default
    everything to safe (off) values so a vanilla install doesn't show
    broken nav links.
    """
    return {
        "pcg_integration": settings.enable_pcg_integration,
    }


@router.get("/validate-repo")
async def validate_repo(path: str):
    """Check if a GitLab repo exists and is accessible.

    Returns repo metadata on success, or an error message.
    """
    from app.services.gitlab_api_client import get_gitlab_client

    if not path or "/" not in path:
        return {"valid": False, "error": "Invalid path format. Expected: group/repo"}

    client = get_gitlab_client()
    encoded = path.replace("/", "%2F")

    try:
        result = await client.get(f"/projects/{encoded}")
        if result is None:
            return {"valid": False, "error": f"Repository not found: {path}"}

        return {
            "valid": True,
            "path": result.get("path_with_namespace", path),
            "name": result.get("name", ""),
            "description": result.get("description", ""),
            "default_branch": result.get("default_branch", "main"),
            "web_url": result.get("web_url", ""),
        }
    except Exception as e:
        logger.warning("Failed to validate repo %s: %s", path, e)
        return {"valid": False, "error": str(e)}
