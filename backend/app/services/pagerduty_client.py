"""PagerDuty REST API client."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Token path (same as configured in docker-compose.yml)
_TOKEN_PATH = Path.home() / ".config" / "pagerduty-token"

# Lazy-loaded token
_api_token: Optional[str] = None


def _load_token() -> str:
    """Load PagerDuty API token from file.

    Returns:
        API token string

    Raises:
        FileNotFoundError: If token file doesn't exist
    """
    global _api_token
    if _api_token is not None:
        return _api_token

    if not _TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"PagerDuty token not found at {_TOKEN_PATH}. "
            "Expected user API token in ~/.config/pagerduty-token"
        )

    with open(_TOKEN_PATH) as f:
        token = f.read().strip()

    if not token:
        raise ValueError(f"PagerDuty token file is empty: {_TOKEN_PATH}")

    _api_token = token
    logger.info("Loaded PagerDuty API token")
    return _api_token


def _headers() -> Dict[str, str]:
    """Get headers for PagerDuty API requests.

    Returns:
        Dict of HTTP headers including auth
    """
    token = _load_token()
    return {
        "Authorization": f"Token token={token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }


async def get_incident_by_number(incident_number: int) -> Optional[Dict]:
    """Fetch incident by incident number.

    Args:
        incident_number: PagerDuty incident number (e.g., 1120590)

    Returns:
        Incident data dict or None if not found
    """
    url = f"https://api.pagerduty.com/incidents/{incident_number}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_headers(), timeout=10.0)

            if response.status_code == 404:
                logger.warning(f"Incident not found: {incident_number}")
                return None

            response.raise_for_status()
            data = response.json()
            return data.get("incident")

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error fetching incident {incident_number}: "
            f"{e.response.status_code} {e.response.text}"
        )
        return None
    except Exception as e:
        logger.error(f"Error fetching incident {incident_number}: {e}")
        return None


async def search_incidents(
    query: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    limit: int = 25,
) -> List[Dict]:
    """Search for incidents.

    Args:
        query: Search query string
        statuses: List of statuses to filter (triggered, acknowledged, resolved)
        limit: Maximum number of results

    Returns:
        List of incident dicts
    """
    url = "https://api.pagerduty.com/incidents"
    params = {
        "limit": limit,
        "sort_by": "created_at:desc",
    }

    if statuses:
        params["statuses[]"] = statuses

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=_headers(), params=params, timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("incidents", [])

    except Exception as e:
        logger.error(f"Error searching incidents: {e}")
        return []


async def get_incident_by_id(incident_id: str) -> Optional[Dict]:
    """Fetch incident by internal PagerDuty ID.

    Args:
        incident_id: PagerDuty incident ID (e.g., "Q1UNIR7Y5WK5E3")

    Returns:
        Incident data dict or None if not found
    """
    # PagerDuty API uses incident ID in the URL for direct lookups
    url = f"https://api.pagerduty.com/incidents/{incident_id}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_headers(), timeout=10.0)

            if response.status_code == 404:
                logger.warning(f"Incident not found: {incident_id}")
                return None

            response.raise_for_status()
            data = response.json()
            return data.get("incident")

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error fetching incident {incident_id}: "
            f"{e.response.status_code} {e.response.text}"
        )
        return None
    except Exception as e:
        logger.error(f"Error fetching incident {incident_id}: {e}")
        return None


async def get_oncall_for_escalation_policy(policy_id: str) -> List[Dict]:
    """Get current on-call users for an escalation policy.

    Args:
        policy_id: Escalation policy ID (e.g., "PIGJRDR" for Compute Team)

    Returns:
        List of on-call user dicts
    """
    url = "https://api.pagerduty.com/oncalls"
    params = {
        "escalation_policy_ids[]": [policy_id],
        "earliest": "true",  # Only get current on-call
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=_headers(), params=params, timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("oncalls", [])

    except Exception as e:
        logger.error(f"Error fetching on-call for policy {policy_id}: {e}")
        return []
