from datetime import datetime
from fastapi import APIRouter
from app.services.wx_deployment_service import WXDeploymentService, commits_since_deploy

router = APIRouter()


@router.get("/deployments")
async def wx_deployments():
    """Get current WX deployment status across all environments.

    Shows:
    - Current build ID (commit SHA) for each environment
    - Links to ArgoCD, commit, and tigercli deploy
    - Deployment timestamp
    - Health status (from Kubernetes deployment status)

    Queries live data from Kubernetes clusters via kubectl.
    """
    service = WXDeploymentService()
    environments = service.get_all_deployments()

    return {
        "environments": environments,
        "last_updated": datetime.now().isoformat(),
    }


@router.get("/deployments/commits-since/{sha}")
async def get_commits_since(sha: str):
    """Count commits on main since a deployed SHA."""
    return await commits_since_deploy(sha)
