"""WX Deployment Service - Query real deployment status from Kubernetes."""
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from app.config import settings

logger = logging.getLogger(__name__)


class WXDeploymentService:
    """Service to query WX deployment status from Kubernetes clusters."""

    # Map environment names to kubectl contexts and namespaces
    # ArgoCD app names follow: argocd/tnt-wx-wx-{argo_component}-{cluster}
    ENVIRONMENTS = {
        "dev-01": {
            "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
            "namespace": "wx-staging",
            "deployment": "wx-dev-01-api",
            "argocd_app": "argocd/tnt-wx-wx-wx-dev-01-stg-wxctl-01",
            "tier": "staging",
        },
        "loadtest-01": {
            "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
            "namespace": "wx-staging",
            "deployment": "wx-loadtest-01-api",
            "argocd_app": "argocd/tnt-wx-wx-wx-loadtest-01-stg-wxctl-01",
            "tier": "staging",
        },
        "staging": {
            "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
            "namespace": "wx-staging",
            "deployment": "wx-staging-api",
            "argocd_app": "argocd/tnt-wx-wx-wx-staging-stg-wxctl-01",
            "tier": "staging",
        },
        "prod-us": {
            "context": "gke_wx-k8s-prod_us-central1_prd-wxctl-01",
            "namespace": "wx-prod",
            "deployment": "wx-prod-api",
            "argocd_app": "argocd/tnt-wx-wx-wx-prod-prd-wxctl-01",
            "tier": "prod",
        },
    }

    def _parse_image_tag(self, image: str) -> Optional[Dict[str, str]]:
        """Parse WX image tag to extract version, commit SHA, and timestamp.

        Format: us.gcr.io/planet-gcr/wx/wx-api:v0.8.2-33-gf8db14b29494-20260316195704
        Returns: {
            "version": "v0.8.2-33",
            "commit_sha": "f8db14b29494",
            "commit_short": "f8db14b2",
            "timestamp": "20260316195704",
            "deployed_at": "2026-03-16T19:57:04"
        }
        """
        # Pattern: :v{semver}-{commits}-g{sha}-{timestamp}
        pattern = r":v([\d.]+-\d+)-g([0-9a-f]+)-(\d{14})"
        match = re.search(pattern, image)

        if not match:
            return None

        version, commit_sha, timestamp = match.groups()

        # Parse timestamp: YYYYMMDDHHMMSS -> ISO format
        try:
            dt = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
            deployed_at = dt.isoformat()
        except ValueError:
            deployed_at = None

        return {
            "version": f"v{version}",
            "commit_sha": commit_sha,
            "commit_short": commit_sha[:8],
            "timestamp": timestamp,
            "deployed_at": deployed_at,
        }

    def _query_deployment(
        self, context: str, namespace: str, deployment: str
    ) -> Optional[str]:
        """Query kubectl for deployment image.

        Returns the container image string or None if query fails.
        """
        cmd = [
            "kubectl",
            "--context", context,
            "get", "deployment", deployment,
            "-n", namespace,
            "-o", "jsonpath={.spec.template.spec.containers[0].image}",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

        return None

    def _build_urls(
        self, env_name: str, commit_sha: str, argocd_app: str
    ) -> Dict[str, str]:
        """Build GitLab and ArgoCD URLs for an environment."""
        return {
            "commit_url": f"{settings.gitlab_base_url}/wx/wx/-/commit/{commit_sha}",
            "argocd_url": f"https://argocd.prod.planet-labs.com/applications/{argocd_app}?view=tree",
            "tigercli_url": f"https://tigercli.prod.planet-labs.com/deploy/wx/{env_name}",
        }

    def get_deployment_status(self, env_name: str) -> Optional[Dict[str, Any]]:
        """Get deployment status for a single environment.

        Args:
            env_name: Environment name (e.g., "staging", "dev-01", "prod-us")

        Returns:
            Deployment info dict or None if environment not found or query failed
        """
        env_config = self.ENVIRONMENTS.get(env_name)
        if not env_config:
            return None

        # Query kubectl for deployment image
        image = self._query_deployment(
            env_config["context"],
            env_config["namespace"],
            env_config["deployment"],
        )

        if not image:
            return None

        # Parse image tag
        parsed = self._parse_image_tag(image)
        if not parsed:
            return None

        # Build URLs
        urls = self._build_urls(
            env_name,
            parsed["commit_sha"],
            env_config["argocd_app"],
        )

        return {
            "name": env_name,
            "build_id": parsed["commit_short"],
            "deployed_at": parsed["deployed_at"],
            "status": "healthy",  # TODO: Query ArgoCD or k8s for health status
            "tier": env_config["tier"],
            **urls,
        }

    def get_all_deployments(self) -> List[Dict[str, Any]]:
        """Get deployment status for all WX environments.

        Returns:
            List of deployment info dicts, ordered by tier (prod first, then staging).
            Environments that fail to query are skipped (no partial/error entries).
        """
        deployments = []

        # Query all environments
        for env_name in self.ENVIRONMENTS.keys():
            try:
                deployment = self.get_deployment_status(env_name)
                if deployment:
                    deployments.append(deployment)
            except Exception:
                # Skip environments that fail to query
                # This allows partial success if some clusters are unreachable
                continue

        # Sort: PROD first, then staging (within each tier, sort by name)
        def sort_key(env: Dict[str, Any]) -> tuple:
            tier = env.get("tier", "staging")
            tier_priority = 0 if tier == "prod" else 1
            return (tier_priority, env["name"])

        deployments.sort(key=sort_key)
        return deployments


async def commits_since_deploy(deployed_sha: str) -> dict:
    """Count commits on main since a deployed SHA.

    Args:
        deployed_sha: The commit SHA currently deployed.

    Returns:
        Dict with count of commits and the SHA queried.
    """
    wx_repo = Path.home() / "code" / "wx" / "wx"
    try:
        result = subprocess.run(
            ["git", "-C", str(wx_repo), "log", "--oneline", f"{deployed_sha}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                "git log failed for sha %s: %s", deployed_sha, result.stderr[:200]
            )
            return {"count": 0, "sha": deployed_sha, "error": "git log failed"}

        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        return {"count": len(lines), "sha": deployed_sha}

    except subprocess.TimeoutExpired:
        logger.warning("git log timed out for sha %s", deployed_sha)
        return {"count": 0, "sha": deployed_sha, "error": "timeout"}
    except Exception as e:
        logger.error("commits_since_deploy failed: %s", e)
        return {"count": 0, "sha": deployed_sha, "error": str(e)}
