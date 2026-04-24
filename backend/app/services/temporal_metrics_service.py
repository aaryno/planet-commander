"""Temporal Cloud metrics service.

Queries Grafana HTTP API for Temporal Cloud performance and usage metrics.
"""

import logging
from pathlib import Path
from time import time

import httpx

logger = logging.getLogger(__name__)

GRAFANA_BASE = "https://planet.grafana.net"
GRAFANA_TOKEN_PATH = Path.home() / ".config" / "grafana-token"

# Datasource UIDs from existing dashboard configs
TEMPORAL_CLOUD_DS = "temporalio-cloud-eap"
SDK_METRICS_DS_ID = 12  # grafanacloud-planet-prom


def _get_token() -> str | None:
    """Read Grafana bearer token."""
    try:
        return GRAFANA_TOKEN_PATH.read_text().strip()
    except OSError:
        logger.error("Cannot read Grafana token from %s", GRAFANA_TOKEN_PATH)
        return None


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


async def _query_prometheus(
    query: str, datasource_id: int = SDK_METRICS_DS_ID, timeout: float = 15.0
) -> dict | None:
    """Execute an instant PromQL query via Grafana proxy."""
    token = _get_token()
    if not token:
        return None

    url = f"{GRAFANA_BASE}/api/datasources/proxy/{datasource_id}/api/v1/query"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers=_headers(token),
                params={"query": query, "time": str(int(time()))},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Prometheus query failed: %s -> %s", query[:80], e)
        return None


def _extract_scalar(result: dict | None) -> float | None:
    """Extract a single scalar value from a Prometheus instant query result."""
    if not result:
        return None
    data = result.get("data", {})
    results = data.get("result", [])
    if not results:
        return None
    # For scalar results or single-vector results
    if data.get("resultType") == "scalar":
        return float(results[1]) if len(results) > 1 else None
    if data.get("resultType") == "vector" and results:
        value = results[0].get("value", [])
        return float(value[1]) if len(value) > 1 else None
    return None


def _extract_vector(result: dict | None) -> list[dict]:
    """Extract label+value pairs from a Prometheus vector result."""
    if not result:
        return []
    data = result.get("data", {})
    results = data.get("result", [])
    out = []
    for r in results:
        metric = r.get("metric", {})
        value = r.get("value", [])
        if len(value) > 1:
            out.append({
                "labels": metric,
                "value": float(value[1]),
            })
    return out


async def get_performance() -> dict:
    """Get Temporal Cloud performance metrics."""
    # Note: These queries go through Grafana's datasource proxy
    # The temporalio-cloud-eap datasource handles mTLS internally
    # We use the SDK metrics datasource (ID 12) for worker-emitted metrics

    # Try fetching SDK-level metrics (these go to grafanacloud-planet-prom)
    queries = {
        "activity_failures": (
            'sum(rate(temporal_activity_execution_failed[1h]))',
            SDK_METRICS_DS_ID,
        ),
        "workflow_completions": (
            'sum(rate(temporal_workflow_completed[1h]))',
            SDK_METRICS_DS_ID,
        ),
        "workflow_failures": (
            'sum(rate(temporal_workflow_failed[1h]))',
            SDK_METRICS_DS_ID,
        ),
    }

    results = {}
    for key, (query, ds_id) in queries.items():
        result = await _query_prometheus(query, ds_id)
        results[key] = _extract_scalar(result)

    # Activity failures by service for context
    activity_fail_by_svc = await _query_prometheus(
        'sum by (service)(rate(temporal_activity_execution_failed[1h]))',
        SDK_METRICS_DS_ID,
    )
    fail_services = []
    for item in _extract_vector(activity_fail_by_svc):
        svc = item["labels"].get("service", "unknown")
        per_hour = round(item["value"] * 3600)
        if per_hour > 0:
            fail_services.append({"service": svc, "failures_per_hour": per_hour})
    fail_services.sort(key=lambda x: x["failures_per_hour"], reverse=True)

    # Compute workflow success rate
    completions = results.get("workflow_completions") or 0
    failures = results.get("workflow_failures") or 0
    total = completions + failures
    success_rate = (completions / total * 100) if total > 0 else None

    return {
        "workflow_success_rate": round(success_rate, 1) if success_rate is not None else None,
        "workflow_completions_per_hour": round(completions * 3600, 1) if completions else None,
        "workflow_failures_per_hour": round(failures * 3600, 1) if failures else None,
        "activity_failures_per_hour": round((results.get("activity_failures") or 0) * 3600),
        "activity_failures_by_service": fail_services[:5],
        "status": "healthy" if (success_rate is None or success_rate > 95) else "degraded",
    }


async def get_usage(period: str = "30d") -> dict:
    """Get Temporal Cloud usage metrics."""
    # Query per-service activity metrics (available via SDK metrics)
    services_result = await _query_prometheus(
        f'sum by (service)(increase(temporal_activity_execution_latency_count[{period}]) or increase(temporal_activity_execution_latency_seconds_count[{period}]))',
        SDK_METRICS_DS_ID,
    )
    services = _extract_vector(services_result)

    by_service = []
    total_activities = 0
    for s in sorted(services, key=lambda x: x["value"], reverse=True):
        service_name = s["labels"].get("service", "unknown")
        count = s["value"]
        total_activities += count
        by_service.append({
            "service": service_name,
            "activity_count": round(count),
        })

    # Add percentage
    for s in by_service:
        s["percent"] = round(s["activity_count"] / total_activities * 100, 1) if total_activities > 0 else 0

    return {
        "total_activities": round(total_activities),
        "by_service": by_service[:10],  # Top 10
        "period": period,
    }
