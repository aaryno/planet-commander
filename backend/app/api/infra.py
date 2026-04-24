"""Infrastructure metrics API — preemption, scale, capacity."""

import logging
import os
import subprocess
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/infra", tags=["infrastructure"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_grafana_token():
    token = os.environ.get("GRAFANA_API_TOKEN")
    if token:
        return token
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "grafana-api-token", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    try:
        with open(Path.home() / ".config" / "grafana-token") as f:
            return f.read().strip()
    except Exception:
        return None


def _get_gcloud_token():
    try:
        r = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        return None


def _prom_query(promql: str, token: str) -> list:
    try:
        r = subprocess.run(
            [
                "curl", "-s", "-G", "--max-time", "10",
                "-H", f"Authorization: Bearer {token}",
                "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
                "--data-urlencode", f"query={promql}",
                "--data-urlencode", f"time={int(time.time())}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        return data.get("data", {}).get("result", []) if data.get("status") == "success" else []
    except Exception:
        return []


def _gcp_monitoring_query(project: str, metric_type: str, hours: int, gcloud_token: str) -> list:
    """Query GCP Cloud Monitoring for a metric."""
    from datetime import timedelta
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    url = (
        f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries"
        f"?filter=metric.type%3D%22{metric_type.replace('/', '%2F')}%22"
        f"&interval.startTime={start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&interval.endTime={end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"&aggregation.alignmentPeriod=3600s"
        f"&aggregation.perSeriesAligner=ALIGN_SUM"
        f"&aggregation.crossSeriesReducer=REDUCE_SUM"
        f"&aggregation.groupByFields=metric.label.zone"
    )

    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-H", f"Authorization: Bearer {gcloud_token}", url],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        return data.get("timeSeries", [])
    except Exception as e:
        logger.warning(f"GCP Monitoring query failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PreemptionData(BaseModel):
    zone: str
    hourly_counts: list[dict]  # [{time, count}]
    current_rate_hr: float


class G4ClusterScale(BaseModel):
    cluster: str
    pool_size: float
    success_rate_hr: float
    failure_rate_hr: float


class K8sClusterScale(BaseModel):
    cluster: str
    nodes: int
    pods: int | None = None


class QueueMetrics(BaseModel):
    total_queued: float
    top_programs: list[dict]  # [{program, queued}]


class InfraResponse(BaseModel):
    timestamp: str
    preemption: dict  # {zones: [PreemptionData], total_hr: float}
    g4_scale: list[G4ClusterScale]
    g4_total_pool: float
    k8s_clusters: list[K8sClusterScale]
    k8s_total_nodes: int
    jobs_queue: QueueMetrics
    pipeline_throughput_hr: float


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/overview")
async def get_infra_overview(hours: int = Query(default=6, le=24, ge=1)):
    """Get infrastructure overview: preemption, scale, capacity."""
    grafana_token = _get_grafana_token()
    gcloud_token = _get_gcloud_token()

    # --- Preemption (GCP Monitoring) ---
    preemption_zones = []
    preemption_total = 0.0
    if gcloud_token:
        ts_data = _gcp_monitoring_query(
            "planet-workers-prod",
            "logging.googleapis.com/user/compute.instances.preempted",
            hours,
            gcloud_token,
        )
        for ts in ts_data:
            zone = ts.get("metric", {}).get("labels", {}).get("zone", "unknown")
            points = []
            for pt in reversed(ts.get("points", [])):
                val = int(pt["value"].get("int64Value", 0))
                points.append({
                    "time": pt["interval"]["endTime"],
                    "count": val,
                })
            current = points[-1]["count"] if points else 0
            preemption_zones.append(PreemptionData(
                zone=zone,
                hourly_counts=points,
                current_rate_hr=current,
            ))
            preemption_total += current

    # --- G4 Scale (Prometheus) ---
    g4_clusters = []
    g4_total = 0.0
    if grafana_token:
        pool_results = _prom_query(
            'sum by (g4_cluster) (g4_pool_pool_running_size)', grafana_token
        )
        success_results = _prom_query(
            'sum by (g4_cluster) (g4_executor_task_instance_total_rate2m{result="success"}) * 3600',
            grafana_token,
        )
        failure_results = _prom_query(
            'sum by (g4_cluster) (g4_executor_task_instance_total_rate2m{result="failure"}) * 3600',
            grafana_token,
        )

        pools = {r["metric"]["g4_cluster"]: float(r["value"][1]) for r in pool_results}
        successes = {r["metric"]["g4_cluster"]: float(r["value"][1]) for r in success_results}
        failures = {r["metric"]["g4_cluster"]: float(r["value"][1]) for r in failure_results}

        for cluster, pool in sorted(pools.items(), key=lambda x: -x[1]):
            g4_clusters.append(G4ClusterScale(
                cluster=cluster,
                pool_size=pool,
                success_rate_hr=round(successes.get(cluster, 0), 1),
                failure_rate_hr=round(failures.get(cluster, 0), 1),
            ))
            g4_total += pool

    # --- K8s Clusters (Prometheus) ---
    k8s_clusters = []
    k8s_total_nodes = 0
    if grafana_token:
        node_results = _prom_query(
            'count by (kubernetes_cluster) (kube_node_info)', grafana_token
        )
        pod_results = _prom_query(
            'count by (kubernetes_cluster) (kube_pod_info)', grafana_token
        )
        pods_by_cluster = {r["metric"]["kubernetes_cluster"]: int(float(r["value"][1])) for r in pod_results}

        for r in sorted(node_results, key=lambda x: -float(x["value"][1])):
            cluster = r["metric"]["kubernetes_cluster"]
            nodes = int(float(r["value"][1]))
            k8s_clusters.append(K8sClusterScale(
                cluster=cluster,
                nodes=nodes,
                pods=pods_by_cluster.get(cluster),
            ))
            k8s_total_nodes += nodes

    # --- Jobs Queue (Prometheus) ---
    jobs_total = 0.0
    top_programs = []
    if grafana_token:
        total_result = _prom_query(
            'sum(jobs_jobs{namespace="live",status="queued"})', grafana_token
        )
        if total_result:
            jobs_total = float(total_result[0]["value"][1])

        program_results = _prom_query(
            'topk(10, sum by (program) (jobs_jobs{namespace="live",status="queued"}))',
            grafana_token,
        )
        for r in program_results:
            v = float(r["value"][1])
            if v > 0:
                top_programs.append({
                    "program": r["metric"]["program"],
                    "queued": round(v),
                })

    # --- Pipeline throughput ---
    throughput = 0.0
    if grafana_token:
        tp_result = _prom_query(
            'sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{namespace="live", status="complete"}[5m])) * 3600',
            grafana_token,
        )
        if tp_result:
            throughput = round(float(tp_result[0]["value"][1]), 1)

    return InfraResponse(
        timestamp=datetime.now(timezone.utc).isoformat(),
        preemption={
            "zones": [z.model_dump() for z in preemption_zones],
            "total_hr": preemption_total,
        },
        g4_scale=g4_clusters,
        g4_total_pool=g4_total,
        k8s_clusters=k8s_clusters,
        k8s_total_nodes=k8s_total_nodes,
        jobs_queue=QueueMetrics(total_queued=jobs_total, top_programs=top_programs),
        pipeline_throughput_hr=throughput,
    )
