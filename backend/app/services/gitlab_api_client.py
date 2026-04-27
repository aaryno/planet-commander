"""GitLab REST API client using httpx.

Reads the personal access token from the glab CLI config file and
provides async methods for GitLab API endpoints.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)

_GLAB_CONFIG_PATH = Path.home() / ".config" / "glab-cli" / "config.yml"

_api_token: Optional[str] = None


def _load_token() -> str:
    """Load GitLab API token from glab CLI config.

    Reads the token from ~/.config/glab-cli/config.yml, using the
    hostname from settings.gitlab_base_url to find the right host entry.
    """
    global _api_token
    if _api_token is not None:
        return _api_token

    if not _GLAB_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"glab CLI config not found at {_GLAB_CONFIG_PATH}. "
            "Run 'glab auth login' to configure."
        )

    with open(_GLAB_CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    hosts = config.get("hosts", {})
    gitlab_host = urlparse(settings.gitlab_base_url).hostname or ""
    host_config = hosts.get(gitlab_host, {})
    token = host_config.get("token")

    if not token:
        raise ValueError(
            f"GitLab token not found in {_GLAB_CONFIG_PATH} "
            f"under hosts > {gitlab_host} > token"
        )

    _api_token = token
    logger.info("Loaded GitLab API token from glab config")
    return _api_token


class GitLabAPIClient:
    """Async HTTP client for GitLab REST API.

    Uses httpx for async HTTP requests with the personal access token
    from the glab CLI configuration.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        base_url = base_url or settings.gitlab_api_url
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client."""
        if self._client is None or self._client.is_closed:
            token = _load_token()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "PRIVATE-TOKEN": token,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def encode_project_path(project_path: str) -> str:
        """URL-encode a GitLab project path for API use.

        Args:
            project_path: Project path like "wx/wx" or "product/g4-wk/g4"

        Returns:
            URL-encoded path like "wx%2Fwx" or "product%2Fg4-wk%2Fg4"
        """
        return project_path.replace("/", "%2F")

    async def get(self, path: str, params: Optional[dict] = None) -> Optional[dict | list]:
        """Make a GET request to the GitLab API.

        Args:
            path: API path (e.g., "/projects/wx%2Fwx/merge_requests/123")
            params: Optional query parameters

        Returns:
            Parsed JSON response, or None on error
        """
        client = await self._get_client()
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "GitLab API error: %s %s -> %d: %s",
                "GET", path, e.response.status_code,
                e.response.text[:200] if e.response.text else "no body"
            )
            return None
        except httpx.TimeoutException:
            logger.error("GitLab API timeout: GET %s", path)
            return None
        except Exception as e:
            logger.error("GitLab API unexpected error: GET %s -> %s", path, e)
            return None

    async def get_mr_changes(
        self,
        project_path: str,
        mr_iid: int,
        access_raw_diffs: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Fetch MR changes (diff statistics) from GitLab API.

        Calls GET /projects/:id/merge_requests/:iid/changes which returns
        the MR details plus a `changes` array with per-file diff info.

        Note: For MRs with very large diffs (>1000 files), GitLab may
        return overflow: true and truncate the changes list.

        Args:
            project_path: Project path (e.g., "wx/wx")
            mr_iid: MR internal ID
            access_raw_diffs: If True, request raw diffs (larger response)

        Returns:
            API response dict with 'changes' key, or None on error
        """
        encoded_path = self.encode_project_path(project_path)
        path = f"/projects/{encoded_path}/merge_requests/{mr_iid}/changes"
        params = {}
        if access_raw_diffs:
            params["access_raw_diffs"] = "true"

        return await self.get(path, params=params if params else None)

    async def get_mr_detail(
        self,
        project_path: str,
        mr_iid: int,
    ) -> Optional[dict[str, Any]]:
        """Fetch MR detail from GitLab API.

        Calls GET /projects/:id/merge_requests/:iid which returns
        basic MR metadata including changes_count.

        Args:
            project_path: Project path (e.g., "wx/wx")
            mr_iid: MR internal ID

        Returns:
            API response dict, or None on error
        """
        encoded_path = self.encode_project_path(project_path)
        path = f"/projects/{encoded_path}/merge_requests/{mr_iid}"
        return await self.get(path)


# Module-level singleton for shared use
_default_client: Optional[GitLabAPIClient] = None


def get_gitlab_client() -> GitLabAPIClient:
    """Get the module-level GitLab API client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = GitLabAPIClient()
    return _default_client
