"""Planet Heartbeat API — live pipeline health."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import json
import subprocess

from app.database import get_db

router = APIRouter(prefix="/api/heartbeat", tags=["heartbeat"])


class ProgramHealth(BaseModel):
    name: str
    complete_per_hour: float
    failed_per_hour: float
    total_per_hour: float
    success_rate: float


class ProductHealth(BaseModel):
    name: str
    complete_per_hour: float = 0
    failed_per_hour: float = 0
    total_per_hour: float = 0
    success_rate: float = 100
    program_count: int = 0


class HeartbeatSnapshot(BaseModel):
    timestamp: str
    platform_health: Optional[float] = None
    overall_success_rate: Optional[float] = None
    error_concentration: Optional[float] = None
    programs_failing: Optional[int] = None
    total_jobs_per_hour: Optional[float] = None
    total_failures_per_hour: Optional[float] = None
    ingest_per_hour: Optional[float] = None
    processing_per_hour: Optional[float] = None
    rectify_per_hour: Optional[float] = None
    anchor_ops_per_hour: Optional[float] = None
    alloy_rx_rate: Optional[float] = None
    queued_jobs: Optional[float] = None
    wx_api_rate: Optional[float] = None
    orders_rate: Optional[float] = None
    orders_queued: Optional[float] = None
    orders_running: Optional[float] = None
    orders_success_rate: Optional[float] = None
    orders_latency_p50: Optional[float] = None
    subs_rate: Optional[float] = None
    subs_queued: Optional[float] = None
    subs_success_rate: Optional[float] = None
    subs_latency_p50: Optional[float] = None
    publish_latency_ms: Optional[float] = None
    publish_rate: Optional[float] = None
    skysat_rate: Optional[float] = None
    pelican_tanager_rate: Optional[float] = None
    alert_level: str = "unknown"
    alert_reason: str = ""
    error_type: str = "unknown"
    top_failing_program: Optional[str] = None
    programs: list[ProgramHealth] = []
    products: list[ProductHealth] = []
    g4_clusters: dict[str, float] = {}
    k8s_nodes: dict[str, float] = {}
    k8s_pods: dict[str, float] = {}
    queue_by_program: dict[str, float] = {}
    queue_wait_by_program: dict[str, float] = {}
    g4_task_success: dict[str, float] = {}
    g4_task_failure: dict[str, float] = {}


class HeartbeatTrend(BaseModel):
    platform_health_trend: Optional[float] = None
    jobs_trend: Optional[float] = None
    ingest_trend: Optional[float] = None


class HeartbeatResponse(BaseModel):
    current: Optional[HeartbeatSnapshot] = None
    trend: Optional[HeartbeatTrend] = None
    history: list[dict] = []


def _row_to_snapshot(row) -> HeartbeatSnapshot:
    programs = []
    breakdown = row.program_breakdown or {}
    if isinstance(breakdown, str):
        breakdown = json.loads(breakdown)
    for name, data in sorted(breakdown.items(), key=lambda x: x[1].get("total_per_hour", 0), reverse=True):
        programs.append(ProgramHealth(
            name=name,
            complete_per_hour=data.get("complete_per_hour", 0),
            failed_per_hour=data.get("failed_per_hour", 0),
            total_per_hour=data.get("total_per_hour", 0),
            success_rate=data.get("success_rate", 0),
        ))

    product_list = []
    prod_data = getattr(row, "product_breakdown", None) or {}
    if isinstance(prod_data, str):
        prod_data = json.loads(prod_data)
    infra = prod_data.pop("_infrastructure", {}) if isinstance(prod_data, dict) else {}

    for name, data in sorted(prod_data.items(), key=lambda x: x[1].get("total_per_hour", 0) if isinstance(x[1], dict) else 0, reverse=True):
        if not isinstance(data, dict) or "total_per_hour" not in data:
            continue
        product_list.append(ProductHealth(
            name=name,
            complete_per_hour=data.get("complete_per_hour", 0),
            failed_per_hour=data.get("failed_per_hour", 0),
            total_per_hour=data.get("total_per_hour", 0),
            success_rate=data.get("success_rate", 100),
            program_count=data.get("program_count", 0),
        ))

    return HeartbeatSnapshot(
        timestamp=row.timestamp.isoformat() if hasattr(row.timestamp, "isoformat") else str(row.timestamp),
        platform_health=row.platform_health,
        overall_success_rate=row.overall_success_rate,
        error_concentration=row.error_concentration,
        programs_failing=int(row.programs_failing) if row.programs_failing else None,
        total_jobs_per_hour=row.total_jobs_per_hour,
        total_failures_per_hour=row.total_failures_per_hour,
        ingest_per_hour=row.ingest_per_hour,
        processing_per_hour=row.processing_per_hour,
        rectify_per_hour=row.rectify_per_hour,
        anchor_ops_per_hour=row.anchor_ops_per_hour,
        alloy_rx_rate=row.alloy_rx_rate,
        queued_jobs=getattr(row, "queued_jobs", None),
        wx_api_rate=getattr(row, "wx_api_rate", None),
        orders_rate=getattr(row, "orders_rate", None),
        orders_queued=getattr(row, "orders_queued", None),
        orders_running=getattr(row, "orders_running", None),
        orders_success_rate=getattr(row, "orders_success_rate", None),
        orders_latency_p50=getattr(row, "orders_latency_p50", None),
        subs_rate=getattr(row, "subs_rate", None),
        subs_queued=getattr(row, "subs_queued", None),
        subs_success_rate=getattr(row, "subs_success_rate", None),
        subs_latency_p50=getattr(row, "subs_latency_p50", None),
        publish_latency_ms=getattr(row, "publish_latency_ms", None),
        publish_rate=getattr(row, "publish_rate", None),
        skysat_rate=getattr(row, "skysat_rate", None),
        pelican_tanager_rate=getattr(row, "pelican_tanager_rate", None),
        alert_level=row.alert_level or "unknown",
        alert_reason=row.alert_reason or "",
        error_type=row.error_type or "unknown",
        top_failing_program=row.top_failing_program,
        programs=programs,
        products=product_list,
        g4_clusters=infra.get("g4_clusters", {}) if infra else {},
        k8s_nodes=infra.get("k8s_nodes", {}) if infra else {},
        k8s_pods=infra.get("k8s_pods", {}) if infra else {},
        queue_by_program=infra.get("queue_by_program", {}) if infra else {},
        queue_wait_by_program=infra.get("queue_wait_by_program", {}) if infra else {},
        g4_task_success=infra.get("g4_task_success", {}) if infra else {},
        g4_task_failure=infra.get("g4_task_failure", {}) if infra else {},
    )


VALID_LOOKBACKS = {"5m", "30m", "1h", "3h", "6h", "12h", "1d", "2d", "7d", "2w", "4w"}

# Noisy programs — same as heartbeat-collector.py
_NOISY_PROGRAMS = "rectify|rer|rectify-ss|rectify-runner.*|rectify-runner-pelican|rectify-runner-tanager"

# PromQL templates — {lb} is replaced with the lookback window
_LOOKBACK_QUERIES = {
    "platform_health": f"""
        (sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{{
            namespace="live", status="complete",
            program!~"{_NOISY_PROGRAMS}"
        }}[{{lb}}]))
        /
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{{
            namespace="live",
            program!~"{_NOISY_PROGRAMS}"
        }}[{{lb}}]))) * 100
    """,
    "overall_success_rate": """
        (sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", status="complete"
        }[{lb}]))
        /
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live"
        }[{lb}]))) * 100
    """,
    "error_concentration": """
        max(sum by (program) (rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", status="failed"
        }[{lb}])))
        /
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", status="failed"
        }[{lb}]))
    """,
    "programs_failing": """
        count(
            (sum by (program) (rate(planet_pipeline_jobs_api_objects_jobs_completed{
                namespace="live", status="failed"
            }[{lb}])))
            /
            (sum by (program) (rate(planet_pipeline_jobs_api_objects_jobs_completed{
                namespace="live"
            }[{lb}])))
            > 0.001
        )
    """,
    "total_jobs_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", status="complete"
        }[{lb}])) * 3600
    """,
    "total_failures_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", status="failed"
        }[{lb}])) * 3600
    """,
    "ingest_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program=~"ps_ingest|ps_ingest_back|skysat_process_anchor_npl|skysat_process_collect|pelican_process_collect|tanager_process_collect|tanager_ingest", status="complete"
        }[{lb}])) * 3600
    """,
    "processing_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program=~"product-processor.*", status="complete"
        }[{lb}])) * 3600
    """,
    "rectify_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program="rectify", status="complete"
        }[{lb}])) * 3600
    """,
    "anchor_ops_per_hour": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program=~"ps_all_anchor_operations|strip-stats|cloud-map|bundle-adjust|product-processor|product-processor-ppc.*", status="complete"
        }[{lb}])) * 3600
    """,
    "alloy_rx_rate": "sum(rate(alloy_resources_machine_rx_bytes_total[{lb}]))",
    "queued_jobs": 'sum(jobs_jobs{namespace="live",status="queued"})',
    "wx_api_rate": 'sum(rate(wx_api_requests_total{code=~"2.."}[{lb}])) * 3600',
    "orders_rate": 'sum(rate(ordersv2_updater_publish_to_finish_duration_secs_count[{lb}])) * 3600',
    "orders_queued": 'sum(ordersv2_director_live_view_queued_count)',
    "orders_running": 'sum(ordersv2_director_live_view_running_count)',
    "orders_success_rate": """
        (sum(rate(ordersv2_worker_order_products_success_count[{lb}]))
        /
        (sum(rate(ordersv2_worker_order_products_success_count[{lb}]))
         + sum(rate(ordersv2_worker_order_products_failed_count[{lb}])))) * 100
    """,
    "orders_latency_p50": """
        histogram_quantile(0.5,
            sum(rate(ordersv2_worker_order_create_to_uow_finish_duration_secs_bucket[{lb}])) by (le))
    """,
    "publish_latency_ms": "planet_pipeline_esindexers_index_latency_timing_median",
    "publish_rate": 'sum(rate(planet_pipeline_esindexers_index_latency_timing_count[{lb}])) * 3600',
    "skysat_rate": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program=~"skysat.*", status="complete"
        }[{lb}])) * 3600
    """,
    "pelican_tanager_rate": """
        sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{
            namespace="live", program=~"pelican.*|tanager.*", status="complete"
        }[{lb}])) * 3600
    """,
    "subs_rate": 'sum(rate(iris_prom_event_completed_count{env="live"}[{lb}])) * 3600',
    "subs_queued": "sum(fair_queue_statistics_visible_message_count)",
    "subs_success_rate": """
        (sum(rate(fair_queue_message_actions{action="ack"}[{lb}]))
        /
        (sum(rate(fair_queue_message_actions{action="ack"}[{lb}]))
         + sum(rate(fair_queue_message_actions{action="nack"}[{lb}])))) * 100
    """,
    "subs_latency_p50": """
        histogram_quantile(0.5,
            sum(rate(fair_queue_message_time_in_queue_ms_bucket[{lb}])) by (le))
    """,
}

_LOOKBACK_PROGRAM_QUERY = """
    sum by (program, status) (
        rate(planet_pipeline_jobs_api_objects_jobs_completed{namespace="live"}[{lb}])
    ) * 3600
"""

_LOOKBACK_MULTI_QUERIES = {
    "g4_clusters": 'sort_desc(sum by (g4_cluster) (g4_pool_pool_running_size))',
    "k8s_nodes": 'count by (kubernetes_cluster) (kube_node_info)',
    "k8s_pods": 'count by (kubernetes_cluster) (kube_pod_info)',
    "queue_by_program": 'sum by (program) (jobs_jobs{namespace="live",status="queued"})',
    "queue_wait_by_program": 'avg by (program) (planet_pipeline_jobs_api_time_to_schedule_mean{namespace="live"})',
    "g4_task_success": 'sum by (g4_cluster) (g4_executor_task_instance_total_rate2m{result="success"})',
    "g4_task_failure": 'sum by (g4_cluster) (g4_executor_task_instance_total_rate2m{result="failure"})',
}

# Product mapping (same as heartbeat-collector.py)
_PRODUCT_PROGRAMS = {
    "PlanetScope": ["ps_ingest", "ps_ingest_back", "ps_all_anchor_operations", "ps_s2s_correspondences",
        "ps_estimated_fsm", "ps_block_bundle_adjust", "ps_sr_republish_exec", "strip-stats",
        "strip-stats-back", "strip_exec", "product-processor", "product-processor-ppc",
        "product-processor-ppc-mda", "cloud-map", "bundle-adjust", "calibration_crossovers",
        "ingestor_executive", "command", "worker_update", "ppc", "batch_ppc"],
    "SkySat": ["skysat_process_anchor_npl", "skysat_process_collect", "skysat_process_collect_back",
        "skysat_process_collect_exec", "skysat_process_video", "skysat_pipeline_latency",
        "skysat_payload_channel_monitoring"],
    "Pelican": ["pelican_process_collect", "pelican_process_collect_exec", "pelican_cloudmap",
        "pelican_b2b_spatial_correction", "pelican_raster_metrics", "pelican_metrics_exec",
        "pelican_bundle_adjust"],
    "Tanager": ["tanager_ingest", "tanager_ingest_exec", "tanager_process_collect",
        "tanager_process_collect_exec", "tanager_raster_metrics", "tanager_spectral_metrics",
        "tanager_sr", "tanager_sr_analytics", "tanager_sr_watcher_exec", "tanager_cloud_map",
        "tanager_mql_analytics", "tanager_mql_exec", "tanager_mql_message_exec",
        "tanager_export_calval_metrics", "tanager_metrics_exec", "tanager_mock_decryption",
        "tanager_pipeline_latency_detailed", "tanager_uningested", "tanager_reingest"],
    "Fusion (L3H)": ["l3h-asset-activation", "l3h-blending", "l3h-caboose", "l3h-command",
        "l3h-tile-tests", "l3h-catalogs-01", "l3h-catalogs-02", "l3h-catalogs-03",
        "l3h-collect-sources-forwardfill-01", "l3h-collect-sources-forwardfill-02",
        "l3h-collect-sources-forwardfill-03", "l3h-collect-sources-backfill-01",
        "l3h-collect-sources-backfill-03", "l3h-collect-sources-monthly-02",
        "l3h-collect-sources-monthly-03", "l3h-cestemaoi-forwardfill-01",
        "l3h-cestemaoi-forwardfill-02", "l3h-cestemaoi-forwardfill-03",
        "l3h-cestemaoi-backfill-01", "l3h-cestemaoi-backfill-03",
        "l3h-cestemaoi-monthly-02", "l3h-cestemaoi-monthly-03",
        "l3h-daily-metrics-01", "l3h-daily-metrics-02", "l3h-daily-metrics-03"],
    "Mosaics": ["mosaic", "mosaic-big", "mosaic_bitmap_gen", "mosaic_completeness",
        "mosaic_compress", "mosaic_cost", "mosaic_delete", "mosaic_exec",
        "mosaic_merge", "mosaic_monitor", "mosaic_supervisor",
        "mosaic_transfer", "mosaic_transfer_bucket_stats",
        "mosaic_wait_on_overviews", "time_lapse_mosaic"],
    "Rectification": ["rectify", "rectify-runner", "rectify-runner-pelican",
        "rectify-runner-tanager", "rectify-ss", "rectify_failure_analyze",
        "rectify_unattempted", "rectification_accuracy",
        "rectification_alerts", "rectification-full-assessment",
        "rectification_assessment_submitter", "rerectify", "rer", "rer_exec",
        "post_process_rectified"],
}


def _get_grafana_token():
    """Get Grafana token from Keychain or file fallback."""
    try:
        r = subprocess.run(["security", "find-generic-password", "-a", "aaryn",
                           "-s", "grafana-api-token", "-w"],
                          capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    try:
        with open("/Users/aaryn/.config/grafana-token") as f:
            return f.read().strip()
    except Exception:
        return None


def _prom_query(promql, token):
    """Query Prometheus instant API, return raw results list."""
    try:
        import time as _time
        r = subprocess.run([
            "curl", "-s", "-G", "--max-time", "10",
            "-H", f"Authorization: Bearer {token}",
            "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
            "--data-urlencode", f"query={promql.strip()}",
            "--data-urlencode", f"time={int(_time.time())}",
        ], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        return data.get("data", {}).get("result", []) if data.get("status") == "success" else []
    except Exception:
        return []


def _prom_scalar(promql, token):
    """Query Prometheus and return single scalar value."""
    results = _prom_query(promql, token)
    if not results:
        return None
    try:
        v = float(results[0]["value"][1])
        return v if v == v else None  # filter NaN
    except (IndexError, KeyError, ValueError, TypeError):
        return None


def _sync_live_heartbeat(lookback: str) -> Optional[HeartbeatSnapshot]:
    """Query Prometheus directly with a variable lookback window."""
    from collections import defaultdict

    token = _get_grafana_token()
    if not token:
        return None

    # Scalar metrics
    metrics = {}
    for name, tmpl in _LOOKBACK_QUERIES.items():
        promql = tmpl.replace("{lb}", lookback)
        val = _prom_scalar(promql, token)
        metrics[name] = round(val, 4) if val is not None else None

    # Per-program breakdown
    prog_query = _LOOKBACK_PROGRAM_QUERY.replace("{lb}", lookback)
    prog_results = _prom_query(prog_query, token)
    programs_raw = defaultdict(lambda: {"complete": 0, "failed": 0})
    for r in (prog_results or []):
        prog = r["metric"].get("program", "unknown")
        status = r["metric"].get("status", "unknown")
        rate_val = float(r["value"][1]) if r["value"][1] != "NaN" else 0
        programs_raw[prog][status] = rate_val

    prog_breakdown = {}
    for prog, rates in programs_raw.items():
        total = rates["complete"] + rates["failed"]
        if total < 0.001:  # include low-volume programs
            continue
        prog_breakdown[prog] = {
            "complete_per_hour": round(rates["complete"], 1),
            "failed_per_hour": round(rates["failed"], 1),
            "total_per_hour": round(total, 1),
            "success_rate": round(100 * rates["complete"] / total, 2) if total > 0 else 0,
        }
    prog_breakdown = dict(sorted(prog_breakdown.items(), key=lambda x: x[1]["total_per_hour"], reverse=True))

    # Product breakdown
    prog_to_product = {}
    for product, progs in _PRODUCT_PROGRAMS.items():
        for p in progs:
            prog_to_product[p] = product
    products_agg = defaultdict(lambda: {"complete": 0, "failed": 0, "programs": []})
    for prog_name, data in prog_breakdown.items():
        product = prog_to_product.get(prog_name, "Other")
        products_agg[product]["complete"] += data["complete_per_hour"]
        products_agg[product]["failed"] += data["failed_per_hour"]
        products_agg[product]["programs"].append(prog_name)
    prod_breakdown = {}
    for product, data in products_agg.items():
        total = data["complete"] + data["failed"]
        prod_breakdown[product] = {
            "complete_per_hour": round(data["complete"], 1),
            "failed_per_hour": round(data["failed"], 1),
            "total_per_hour": round(total, 1),
            "success_rate": round(100 * data["complete"] / total, 2) if total > 0 else 100.0,
            "program_count": len(data["programs"]),
        }

    # Multi-series queries (infrastructure)
    infra = {}
    for name, promql in _LOOKBACK_MULTI_QUERIES.items():
        results = _prom_query(promql, token)
        if results:
            infra[name] = {}
            for r in results:
                labels = {k: v for k, v in r["metric"].items() if k != "__name__"}
                key = list(labels.values())[0] if labels else "unknown"
                val = float(r["value"][1]) if r["value"][1] != "NaN" else 0
                if val > 0:
                    infra[name][key] = val

    # Alert level
    ph = metrics.get("platform_health")
    alert_level = "healthy"
    alert_reason = ""
    if ph is not None:
        if ph < 95:
            alert_level = "critical"
            alert_reason = f"Platform health {ph:.1f}%"
        elif ph < 98:
            alert_level = "warning"
            alert_reason = f"Platform health {ph:.1f}%"

    top_failing = None
    failing_progs = [(p, d) for p, d in prog_breakdown.items() if d["failed_per_hour"] > 0]
    if failing_progs:
        top_failing = max(failing_progs, key=lambda x: x[1]["failed_per_hour"])[0]

    ec = metrics.get("error_concentration")
    error_type = "customer" if ec is not None and ec > 0.5 else "platform"

    from datetime import datetime, timezone
    programs = [ProgramHealth(name=n, **{k: d[k] for k in ("complete_per_hour", "failed_per_hour", "total_per_hour", "success_rate")})
                for n, d in prog_breakdown.items()]
    products = [ProductHealth(name=n, **{k: d[k] for k in ("complete_per_hour", "failed_per_hour", "total_per_hour", "success_rate", "program_count")})
                for n, d in sorted(prod_breakdown.items(), key=lambda x: x[1]["total_per_hour"], reverse=True)]

    return HeartbeatSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        platform_health=metrics.get("platform_health"),
        overall_success_rate=metrics.get("overall_success_rate"),
        error_concentration=metrics.get("error_concentration"),
        programs_failing=int(metrics["programs_failing"]) if metrics.get("programs_failing") else None,
        total_jobs_per_hour=metrics.get("total_jobs_per_hour"),
        total_failures_per_hour=metrics.get("total_failures_per_hour"),
        ingest_per_hour=metrics.get("ingest_per_hour"),
        processing_per_hour=metrics.get("processing_per_hour"),
        rectify_per_hour=metrics.get("rectify_per_hour"),
        anchor_ops_per_hour=metrics.get("anchor_ops_per_hour"),
        alloy_rx_rate=metrics.get("alloy_rx_rate"),
        queued_jobs=metrics.get("queued_jobs"),
        wx_api_rate=metrics.get("wx_api_rate"),
        orders_rate=metrics.get("orders_rate"),
        orders_queued=metrics.get("orders_queued"),
        orders_running=metrics.get("orders_running"),
        orders_success_rate=metrics.get("orders_success_rate"),
        orders_latency_p50=metrics.get("orders_latency_p50"),
        subs_rate=metrics.get("subs_rate"),
        subs_queued=metrics.get("subs_queued"),
        subs_success_rate=metrics.get("subs_success_rate"),
        subs_latency_p50=metrics.get("subs_latency_p50"),
        publish_latency_ms=metrics.get("publish_latency_ms"),
        publish_rate=metrics.get("publish_rate"),
        skysat_rate=metrics.get("skysat_rate"),
        pelican_tanager_rate=metrics.get("pelican_tanager_rate"),
        alert_level=alert_level,
        alert_reason=alert_reason,
        error_type=error_type,
        top_failing_program=top_failing,
        programs=programs,
        products=products,
        g4_clusters=infra.get("g4_clusters", {}),
        k8s_nodes=infra.get("k8s_nodes", {}),
        k8s_pods=infra.get("k8s_pods", {}),
        queue_by_program=infra.get("queue_by_program", {}),
        queue_wait_by_program=infra.get("queue_wait_by_program", {}),
        g4_task_success=infra.get("g4_task_success", {}),
        g4_task_failure=infra.get("g4_task_failure", {}),
    )


@router.get("/current", response_model=HeartbeatResponse)
async def get_heartbeat(
    hours: int = Query(default=6, le=168),
    lookback: str = Query(default="5m"),
    db: AsyncSession = Depends(get_db),
):
    """Get current heartbeat with trend and history.

    lookback: Prometheus rate() window — "5m", "30m", "1h", "1d", etc.
    For "5m", uses the cached 60s snapshot. For other windows, queries Prometheus live.
    """
    if lookback not in VALID_LOOKBACKS:
        lookback = "5m"

    if lookback == "5m":
        # Use cached snapshot from collector
        result = await db.execute(text(
            "SELECT * FROM heartbeat_snapshots ORDER BY timestamp DESC LIMIT 1"
        ))
        latest = result.first()
        current = _row_to_snapshot(latest) if latest else None
    else:
        # Query Prometheus live with the requested lookback window
        import asyncio
        current = await asyncio.to_thread(_sync_live_heartbeat, lookback)

    # 1h ago for trend
    result = await db.execute(text("""
        SELECT platform_health, total_jobs_per_hour, ingest_per_hour
        FROM heartbeat_snapshots
        WHERE timestamp >= NOW() - INTERVAL '65 minutes'
          AND timestamp <= NOW() - INTERVAL '55 minutes'
        ORDER BY timestamp DESC LIMIT 1
    """))
    hour_ago = result.first()

    # History
    result = await db.execute(text("""
        SELECT timestamp, platform_health, overall_success_rate,
               total_jobs_per_hour, total_failures_per_hour,
               ingest_per_hour, processing_per_hour,
               alert_level, programs_failing
        FROM heartbeat_snapshots
        WHERE timestamp >= NOW() - make_interval(hours => :hours)
        ORDER BY timestamp
    """), {"hours": hours})
    history_rows = result.fetchall()

    trend = None
    if hour_ago:
        latest_for_trend = await db.execute(text(
            "SELECT platform_health, total_jobs_per_hour, ingest_per_hour FROM heartbeat_snapshots ORDER BY timestamp DESC LIMIT 1"
        ))
        latest_row = latest_for_trend.first()
        if latest_row:
            trend = HeartbeatTrend(
                platform_health_trend=(latest_row.platform_health or 0) - (hour_ago.platform_health or 0),
                jobs_trend=(latest_row.total_jobs_per_hour or 0) - (hour_ago.total_jobs_per_hour or 0),
                ingest_trend=(latest_row.ingest_per_hour or 0) - (hour_ago.ingest_per_hour or 0),
            )

    history = [
        {
            "timestamp": r.timestamp.isoformat(),
            "platform_health": r.platform_health,
            "overall_success_rate": r.overall_success_rate,
            "total_jobs_per_hour": r.total_jobs_per_hour,
            "ingest_per_hour": r.ingest_per_hour,
            "alert_level": r.alert_level,
        }
        for r in (history_rows or [])
    ]

    return HeartbeatResponse(current=current, trend=trend, history=history)


# ── G4 Operations Detail ──

class G4OperationDetail(BaseModel):
    operation: str
    throughput_hr: float = 0
    failure_rate_hr: float = 0
    success_rate_pct: float = 100
    # per-cluster breakdown
    clusters: dict[str, float] = {}


class G4ClusterDetail(BaseModel):
    cluster: str
    pool_size: float = 0
    operations: list[G4OperationDetail] = []
    total_throughput_hr: float = 0
    scheduler_health: Optional[float] = None


@router.get("/g4-detail/{cluster_group}")
async def get_g4_detail(cluster_group: str, lookback: str = Query(default="5m"), db: AsyncSession = Depends(get_db)):
    """Get G4 operations breakdown for a cluster group (orders/subs/fusion/all)."""
    if lookback not in VALID_LOOKBACKS:
        lookback = "5m"
    import subprocess as _sp
    import json as _json

    # Cluster group mapping
    GROUPS = {
        "orders": ["g4c-live-03", "g4c-pioneer-05"],
        "subs": ["g4c-sub-01", "g4c-sub-03", "g4c-sub-04"],
        "fusion": ["g4c-fusion-01", "g4c-fusion-02", "g4c-fusion-03"],
        "skysat": ["g4c-skysat-01"],
        "analytics": ["g4c-analytics-01"],
        "all": [],  # empty = all clusters
    }

    clusters = GROUPS.get(cluster_group, [])
    cluster_filter = "|".join(clusters) if clusters else ".*"

    def _get_grafana_token():
        try:
            r = _sp.run(["security", "find-generic-password", "-a", "aaryn", "-s", "grafana-api-token", "-w"],
                       capture_output=True, text=True, timeout=5)
            if r.returncode == 0: return r.stdout.strip()
        except: pass
        try:
            with open("/Users/aaryn/.config/grafana-token") as f: return f.read().strip()
        except: return None

    token = _get_grafana_token()
    if not token:
        return {"error": "No Grafana token"}

    def _prom_query(promql):
        try:
            r = _sp.run([
                "curl", "-s", "-G", "--max-time", "10",
                "-H", f"Authorization: Bearer {token}",
                "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
                "--data-urlencode", f"query={promql}",
                "--data-urlencode", f"time={int(__import__('time').time())}",
            ], capture_output=True, text=True, timeout=15)
            if r.returncode != 0: return []
            data = _json.loads(r.stdout)
            return data.get("data", {}).get("result", []) if data.get("status") == "success" else []
        except:
            return []

    # Exclude cestem/fusion operations from non-fusion cluster groups
    op_filter = ', operation!~"cestem_.*"' if cluster_group not in ("fusion", "all") else ""

    # Use pre-computed rate2m gauge instead of raw timing_count counter.
    # The raw counter resets every 30-60min when G4 pods recycle, making
    # rate() unreliable. rate2m is computed server-side and survives restarts.
    success_results = _prom_query(
        f'sort_desc(sum by (operation) (g4_executor_task_instance_total_rate2m{{g4_cluster=~"{cluster_filter}", result="success"{op_filter}}})) * 3600'
    )
    failure_results = _prom_query(
        f'sum by (operation) (g4_executor_task_instance_total_rate2m{{g4_cluster=~"{cluster_filter}", result="failure"{op_filter}}}) * 3600'
    )
    # Per-cluster breakdown
    cluster_results = _prom_query(
        f'sort_desc(sum by (operation, g4_cluster) (g4_executor_task_instance_total_rate2m{{g4_cluster=~"{cluster_filter}", result="success"{op_filter}}})) * 3600'
    )
    # Pool sizes
    pool_results = _prom_query(
        f'sum by (g4_cluster) (g4_pool_pool_running_size{{g4_cluster=~"{cluster_filter}"}})'
    )
    # Queue time P50
    queue_results = _prom_query(
        f'histogram_quantile(0.5, sum by (le) (g4_api_workload_process_queued_time_ms_bucket{{g4_cluster=~"{cluster_filter}"}}))'
    )

    # Build operations
    failures = {r["metric"]["operation"]: float(r["value"][1]) for r in failure_results if r["value"][1] != "NaN"}
    ops = []
    for r in success_results:
        op = r["metric"]["operation"]
        rate = float(r["value"][1])
        if rate < 0.1: continue
        fail = failures.get(op, 0)
        total = rate + fail
        ops.append(G4OperationDetail(
            operation=op,
            throughput_hr=round(rate, 1),
            failure_rate_hr=round(fail, 1),
            success_rate_pct=round(100 * rate / total, 1) if total > 0 else 100,
            clusters={r2["metric"]["g4_cluster"]: round(float(r2["value"][1]), 1)
                      for r2 in cluster_results
                      if r2["metric"]["operation"] == op and float(r2["value"][1]) > 0.1},
        ))

    pools = {r["metric"]["g4_cluster"]: float(r["value"][1]) for r in pool_results}
    queue_p50_ms = float(queue_results[0]["value"][1]) if queue_results else None

    total = sum(o.throughput_hr for o in ops)

    return {
        "cluster_group": cluster_group,
        "clusters": clusters or list(pools.keys()),
        "pool_sizes": pools,
        "total_pool": sum(pools.values()),
        "total_throughput_hr": round(total, 1),
        "queue_wait_p50_ms": queue_p50_ms,
        "operations": [o.model_dump() for o in ops],
    }


# ── Orders (OrdersV2) Detail ──

@router.get("/orders-detail")
async def get_orders_detail(lookback: str = Query(default="5m"), db: AsyncSession = Depends(get_db)):
    """Get OrdersV2 SLI metrics — request-to-queue, queue-to-workflow, create-to-finish."""
    if lookback not in VALID_LOOKBACKS:
        lookback = "5m"
    lb = lookback
    import subprocess as _sp
    import json as _json

    def _get_token():
        try:
            r = _sp.run(["security", "find-generic-password", "-a", "aaryn", "-s", "grafana-api-token", "-w"],
                       capture_output=True, text=True, timeout=5)
            if r.returncode == 0: return r.stdout.strip()
        except: pass
        try:
            with open("/Users/aaryn/.config/grafana-token") as f: return f.read().strip()
        except: return None

    token = _get_token()
    if not token:
        return {"error": "No Grafana token"}

    def _q(promql):
        try:
            r = _sp.run(["curl", "-s", "-G", "--max-time", "10",
                "-H", f"Authorization: Bearer {token}",
                "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
                "--data-urlencode", f"query={promql}",
                "--data-urlencode", f"time={int(__import__('time').time())}",
            ], capture_output=True, text=True, timeout=15)
            if r.returncode != 0: return None
            data = _json.loads(r.stdout)
            res = data.get("data", {}).get("result", [])
            if res:
                v = float(res[0]["value"][1])
                return v if v == v else None  # filter NaN
        except: pass
        return None

    return {
        "service": "OrdersV2",
        "lookback": lb,
        "grafana_url": "https://planet.grafana.net/d/iqRkSMa4z/ordersv2-slis?orgId=1&var-env=live",
        "slis": {
            "request_to_queue": {
                "p50": _q(f'histogram_quantile(0.50, sum(rate(ordersv2_control_plane_api_request_to_queue_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
                "p95": _q(f'histogram_quantile(0.95, sum(rate(ordersv2_control_plane_api_request_to_queue_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
            },
            "queue_to_workflow": {
                "p50": _q(f'histogram_quantile(0.50, sum(rate(ordersv2_control_plane_api_queue_to_worklow_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
                "p95": _q(f'histogram_quantile(0.95, sum(rate(ordersv2_control_plane_api_queue_to_worklow_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
            },
            "create_to_start": {
                "p50": _q(f'histogram_quantile(0.50, sum(rate(ordersv2_worker_order_create_to_uow_start_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
                "p95": _q(f'histogram_quantile(0.95, sum(rate(ordersv2_worker_order_create_to_uow_start_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
            },
            "create_to_finish": {
                "p50": _q(f'histogram_quantile(0.50, sum(rate(ordersv2_worker_order_create_to_uow_finish_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
                "p95": _q(f'histogram_quantile(0.95, sum(rate(ordersv2_worker_order_create_to_uow_finish_duration_secs_bucket{{env="live"}}[{lb}])) by (le))'),
            },
        },
        "throughput": {
            "products_delivered_hr": _q(f'sum(rate(ordersv2_worker_order_products_success_count[{lb}]))*3600'),
            "products_failed_hr": _q(f'sum(rate(ordersv2_worker_order_products_failed_count[{lb}]))*3600'),
            "queue_size": _q('{__name__="ordersv2_queuingservice_live_queue_in_queue", via="vector"}'),
            "burn_rate_hr": _q(f'sum(rate(ordersv2_worker_order_create_to_uow_finish_duration_secs_count{{env="live"}}[{lb}])) * 3600'),
        },
    }


# ── Subscriptions (Iris) Detail ──


def _sync_subs_detail(lb: str = "5m"):
    """Synchronous implementation — runs in thread to avoid blocking event loop."""

    def _get_token():
        try:
            r = subprocess.run(["security", "find-generic-password", "-a", "aaryn", "-s", "grafana-api-token", "-w"],
                       capture_output=True, text=True, timeout=5)
            if r.returncode == 0: return r.stdout.strip()
        except: pass
        try:
            with open("/Users/aaryn/.config/grafana-token") as f: return f.read().strip()
        except: return None

    token = _get_token()
    if not token:
        return {"error": "No Grafana token"}

    GRP = "subscriptions.*|ftl.*"

    def _q(promql):
        try:
            r = subprocess.run(["curl", "-s", "-G", "--max-time", "10",
                "-H", f"Authorization: Bearer {token}",
                "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
                "--data-urlencode", f"query={promql}",
                "--data-urlencode", f"time={int(__import__('time').time())}",
            ], capture_output=True, text=True, timeout=15)
            if r.returncode != 0: return None
            data = json.loads(r.stdout)
            res = data.get("data", {}).get("result", [])
            if res:
                v = float(res[0]["value"][1])
                return v if v == v else None
        except: pass
        return None

    def _q_multi(promql):
        try:
            r = subprocess.run(["curl", "-s", "-G", "--max-time", "10",
                "-H", f"Authorization: Bearer {token}",
                "https://planet.grafana.net/api/datasources/proxy/12/api/v1/query",
                "--data-urlencode", f"query={promql}",
                "--data-urlencode", f"time={int(__import__('time').time())}",
            ], capture_output=True, text=True, timeout=15)
            if r.returncode != 0: return {}
            data = json.loads(r.stdout)
            result = {}
            for r2 in data.get("data", {}).get("result", []):
                key = r2["metric"].get("group") or r2["metric"].get("routing_key") or r2["metric"].get("action", "?")
                v = float(r2["value"][1])
                if v == v and v > 0:
                    result[key] = round(v, 1)
            return result
        except: return {}

    return {
        "service": "Subscriptions (fair-queue)",
        "lookback": lb,
        "grafana_url": "https://planet.grafana.net/d/bdc411a1c33a5767d31d3bcf30d8f81b23900fa4/fair-queue?orgId=1&var-namespace=live&var-environment=live",
        "throughput": {
            "pushed_hr": _q(f'sum(rate(fair_queue_messages_pushed{{environment="live",group=~"{GRP}"}}[{lb}]))*3600'),
            "pulled_hr": _q(f'sum(rate(fair_queue_messages_pulled{{environment="live",group=~"{GRP}"}}[{lb}]))*3600'),
            "ack_hr": _q(f'sum(rate(fair_queue_message_actions{{action="ack",environment="live",group=~"{GRP}"}}[{lb}]))*3600'),
            "nack_hr": _q(f'sum(rate(fair_queue_message_actions{{action="nack",environment="live",group=~"{GRP}"}}[{lb}]))*3600'),
        },
        "queue": {
            "depth": _q(f'sum(fair_queue_statistics_message_count{{environment="live",group=~"{GRP}"}})'),
            "visible": _q(f'sum(fair_queue_statistics_visible_message_count{{environment="live",group=~"{GRP}"}})'),
            "oldest_msg_s": _q(f'max(fair_queue_statistics_oldest_message_time_ms{{environment="live",group=~"{GRP}"}})/1000'),
            "wait_p50_ms": _q(f'histogram_quantile(0.50, sum(rate(fair_queue_message_time_in_queue_ms_bucket{{environment="live",group=~"{GRP}"}}[{lb}])) by (le))'),
            "wait_p95_ms": _q(f'histogram_quantile(0.95, sum(rate(fair_queue_message_time_in_queue_ms_bucket{{environment="live",group=~"{GRP}"}}[{lb}])) by (le))'),
        },
        "by_group": {
            "ack_rate": _q_multi(f'sort_desc(sum by (group) (rate(fair_queue_message_actions{{action="ack",environment="live",group=~"{GRP}"}}[{lb}]))*3600)'),
            "queue_depth": _q_multi(f'sort_desc(sum by (group) (fair_queue_statistics_message_count{{environment="live",group=~"{GRP}"}}))'),
        },
    }


@router.get("/subs-detail")
async def get_subs_detail(lookback: str = Query(default="5m"), db: AsyncSession = Depends(get_db)):
    """Get Subscriptions lifecycle metrics — runs sync queries in thread."""
    if lookback not in VALID_LOOKBACKS:
        lookback = "5m"
    import asyncio
    return await asyncio.to_thread(_sync_subs_detail, lookback)


# ── PromQL Test Endpoint ──

@router.get("/test-query")
async def test_promql(query: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Test a PromQL query against Grafana/Prometheus and return results."""
    import asyncio

    def _run():
        token = _get_grafana_token()
        if not token:
            return {"error": "No Grafana token"}
        results = _prom_query(query, token)
        if results is None:
            return {"error": "Query failed", "query": query}
        # Format results
        formatted = []
        for r in results[:50]:  # limit to 50 series
            labels = {k: v for k, v in r.get("metric", {}).items() if k != "__name__"}
            val = r.get("value", [None, None])
            try:
                v = float(val[1])
                formatted.append({"labels": labels, "value": v, "value_fmt": f"{v:,.2f}" if v < 1000 else f"{v:,.0f}"})
            except (TypeError, ValueError, IndexError):
                formatted.append({"labels": labels, "value": None, "value_fmt": "NaN"})
        scalar = None
        if len(formatted) == 1 and not formatted[0]["labels"]:
            scalar = formatted[0]["value"]
        return {
            "query": query,
            "series_count": len(results),
            "scalar": scalar,
            "scalar_fmt": formatted[0]["value_fmt"] if scalar is not None else None,
            "results": formatted,
        }

    return await asyncio.to_thread(_run)
