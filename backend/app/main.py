import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import agents, artifacts, audits, automation, coach, config_api, contexts, docs, enrich, fs, gitlab, gitlab_mrs, google_drive, grafana, grafana_alerts, health, infra, investigations, jira, jobs, labels, layout, links, pagerduty, pcg, permissions, processes, project_docs, projects, service_health, skills, slack, slack_threads, summaries, sync, temporal, terminal, urls, warnings, workspaces, worktrees, wx
from app.services.sync_scheduler import scheduler
from app.services.process_manager import process_manager
from app.services.background_jobs import job_service
from app.jobs.git_scanner import scan_git_repositories
from app.jobs.jira_sync import sync_jira_cache
from app.jobs.jira_enrichment import enrich_jira_tickets
from app.jobs.link_inference import infer_entity_links
from app.jobs.health_audit import run_health_audit
from app.jobs.pagerduty_sync import sync_pagerduty_incidents
from app.jobs.pagerduty_enrichment import enrich_pagerduty_references
from app.jobs.artifact_indexing import index_artifacts, link_artifacts_to_jira
from app.jobs.grafana_sync import sync_alert_definitions, link_alerts_to_jira
from app.jobs.project_doc_sync import sync_project_docs, link_projects_to_entities
from app.jobs.google_drive_sync import sync_google_drive, link_google_drive_to_jira
from app.jobs.gitlab_mr_sync import sync_gitlab_mrs, link_mrs_to_jira
from app.jobs.slack_thread_sync import sync_slack_threads
from app.jobs.slack_thread_enrichment import enrich_slack_thread_links
from app.jobs.skill_suggestion_refresh import refresh_skill_suggestions
from app.jobs.warning_monitoring import monitor_warning_channels
from app.jobs.escalation_metrics_update import update_escalation_metrics
from app.jobs.url_extraction import extract_urls_from_recent_chats
from app.jobs.incident_spider_enrichment import spider_incident_references


async def cleanup_context_queue():
    """TTL cleanup for agent context queue items."""
    from app.database import async_session
    from app.services.agent_context_queue import AgentContextQueueService
    async with async_session() as db:
        service = AgentContextQueueService(db)
        deleted = await service.cleanup_expired()
        await db.commit()
        if deleted:
            logging.info(f"Cleaned up {deleted} expired context queue items")

logging.basicConfig(level=logging.INFO, format="%(levelname)-5s [%(name)s] %(message)s")
# Quiet down noisy loggers
logging.getLogger("watchfiles").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start sync scheduler (existing)
    scheduler.start()

    # Start background job service
    job_service.start()

    # Register background jobs
    # Git scanner: every 30 minutes
    job_service.add_interval_job(
        scan_git_repositories,
        job_id="git_scanner",
        minutes=30
    )

    # JIRA sync: every 15 minutes
    job_service.add_interval_job(
        sync_jira_cache,
        job_id="jira_sync",
        minutes=15
    )

    # JIRA enrichment: every 1 hour
    job_service.add_interval_job(
        enrich_jira_tickets,
        job_id="jira_enrichment",
        hours=1
    )

    # Link inference: every hour
    job_service.add_interval_job(
        infer_entity_links,
        job_id="link_inference",
        hours=1
    )

    # PagerDuty incident sync: every 30 minutes
    job_service.add_interval_job(
        sync_pagerduty_incidents,
        job_id="pagerduty_incident_sync",
        minutes=30
    )

    # PagerDuty enrichment: every 1 hour
    job_service.add_interval_job(
        enrich_pagerduty_references,
        job_id="pagerduty_enrichment",
        hours=1
    )

    # Artifact indexing: every 1 hour
    job_service.add_interval_job(
        index_artifacts,
        job_id="artifact_indexing",
        hours=1
    )

    # Artifact → JIRA linking: every 1 hour
    job_service.add_interval_job(
        link_artifacts_to_jira,
        job_id="artifact_jira_linking",
        hours=1
    )

    # Grafana alert sync: every 1 hour
    job_service.add_interval_job(
        sync_alert_definitions,
        job_id="grafana_alert_sync",
        hours=1
    )

    # Alert → JIRA linking: every 1 hour
    job_service.add_interval_job(
        link_alerts_to_jira,
        job_id="alert_jira_linking",
        hours=1
    )

    # Project docs sync: every 1 hour
    job_service.add_interval_job(
        sync_project_docs,
        job_id="project_doc_sync",
        hours=1
    )

    # Project → entity linking: every 1 hour
    job_service.add_interval_job(
        link_projects_to_entities,
        job_id="project_doc_linking",
        hours=1
    )

    # Google Drive sync: every 6 hours
    job_service.add_interval_job(
        sync_google_drive,
        job_id="google_drive_sync",
        hours=6
    )

    # Google Drive → JIRA linking: every 6 hours
    job_service.add_interval_job(
        link_google_drive_to_jira,
        job_id="google_drive_jira_linking",
        hours=6
    )

    # GitLab MR sync: every 30 minutes
    job_service.add_interval_job(
        sync_gitlab_mrs,
        job_id="gitlab_mr_sync",
        minutes=30
    )

    # GitLab MR → JIRA linking: every 30 minutes
    job_service.add_interval_job(
        link_mrs_to_jira,
        job_id="gitlab_mr_jira_linking",
        minutes=30
    )

    # Slack thread sync: every 1 hour
    job_service.add_interval_job(
        sync_slack_threads,
        job_id="slack_thread_sync",
        hours=1
    )

    # Slack thread enrichment: every 1 hour
    job_service.add_interval_job(
        enrich_slack_thread_links,
        job_id="slack_thread_enrichment",
        hours=1
    )

    # Skill suggestion refresh: every 2 hours
    job_service.add_interval_job(
        refresh_skill_suggestions,
        job_id="skill_suggestion_refresh",
        hours=2
    )

    # Context queue cleanup: every 6 hours
    job_service.add_interval_job(
        cleanup_context_queue,
        job_id="context_queue_cleanup",
        hours=6
    )

    # Warning channel monitoring: every 5 minutes (near-real-time)
    job_service.add_interval_job(
        monitor_warning_channels,
        job_id="warning_monitoring",
        minutes=5
    )

    # Escalation metrics update: every 6 hours (learning)
    job_service.add_interval_job(
        update_escalation_metrics,
        job_id="escalation_metrics_update",
        hours=6
    )

    # Health audit: every 6 hours
    job_service.add_interval_job(
        run_health_audit,
        job_id="health_audit",
        hours=6
    )

    # URL extraction from chats: every 1 hour
    job_service.add_interval_job(
        extract_urls_from_recent_chats,
        job_id="url_extraction",
        hours=1
    )

    # Incident spider: PD → JIRA → Slack/GitLab/Grafana: every 30 min
    job_service.add_interval_job(
        spider_incident_references,
        job_id="incident_spider",
        minutes=30
    )

    logging.info("Background jobs registered: git_scanner (30m), jira_sync (15m), link_inference (1h), pagerduty_incident_sync (30m), pagerduty_enrichment (1h), artifact_indexing (1h), artifact_jira_linking (1h), grafana_alert_sync (1h), alert_jira_linking (1h), project_doc_sync (1h), project_doc_linking (1h), google_drive_sync (6h), google_drive_jira_linking (6h), gitlab_mr_sync (30m), gitlab_mr_jira_linking (30m), slack_thread_sync (1h), slack_thread_enrichment (1h), skill_suggestion_refresh (2h), health_audit (6h), url_extraction (1h), incident_spider (30m)")

    yield

    # Cleanup
    await scheduler.stop()
    job_service.stop()
    await process_manager.shutdown_all()


app = FastAPI(title="Planet Ops Dashboard", version="0.1.0", lifespan=lifespan)


class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    """Records web activity for the sync scheduler's active/idle mode."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            scheduler.record_web_activity()
        return await call_next(request)


app.add_middleware(ActivityTrackingMiddleware)
# CORS must be added LAST — Starlette runs middleware in reverse order (last added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:9300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(artifacts.router)  # Router has /api/artifacts prefix
app.include_router(audits.router, prefix="/api")  # Router has /audits prefix
app.include_router(automation.router, prefix="/api")  # Router has /automation prefix
app.include_router(coach.router, prefix="/api")  # Router has /coach prefix
app.include_router(investigations.router, prefix="/api")  # Router has /investigations prefix
app.include_router(contexts.router, prefix="/api")  # Router has /contexts prefix
app.include_router(enrich.router)  # Router has /api/enrich prefix
app.include_router(labels.router, prefix="/api/labels", tags=["labels"])
app.include_router(layout.router, prefix="/api/layout", tags=["layout"])
app.include_router(links.router, prefix="/api")  # Router has /links prefix
app.include_router(slack.router, prefix="/api/slack", tags=["slack"])
app.include_router(slack_threads.router)  # Router has /api/slack/threads prefix
app.include_router(gitlab.router, prefix="/api/mrs", tags=["merge-requests"])
app.include_router(gitlab_mrs.router, prefix="/api")  # Router has /gitlab/mrs prefix
app.include_router(jira.router, prefix="/api/jira", tags=["jira"])
app.include_router(grafana.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(grafana_alerts.router)  # Router has /api/grafana/alerts prefix
# heartbeat routes moved to separate repo
app.include_router(health.router, prefix="/api")  # Router has /health prefix
app.include_router(summaries.router, prefix="/api")  # Router has /summaries prefix
app.include_router(pagerduty.router, prefix="/api/pagerduty", tags=["pagerduty"])
app.include_router(fs.router)  # Router has /api/fs prefix
app.include_router(permissions.router)  # Router has /api/permissions prefix
app.include_router(project_docs.router)  # Router has /api/project-docs prefix
app.include_router(google_drive.router, prefix="/api")  # Router has /google-drive prefix
app.include_router(docs.router, prefix="/api/docs", tags=["docs"])
app.include_router(jobs.router, prefix="/api")
app.include_router(projects.router)  # Router has /api/projects prefix
app.include_router(config_api.router)  # Router has /api/config prefix
app.include_router(processes.router, prefix="/api/processes", tags=["processes"])
app.include_router(skills.router)  # Router has /api/skills prefix
app.include_router(temporal.router, prefix="/api/temporal", tags=["temporal"])
app.include_router(terminal.router, prefix="/api/terminal", tags=["terminal"])
app.include_router(urls.router, prefix="/api")  # Router has /urls prefix
app.include_router(warnings.router)  # Router has /api/warnings prefix
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(service_health.router)  # Router has /api/service-health prefix
app.include_router(sync.router)  # Router has /api/sync prefix
app.include_router(worktrees.router, prefix="/api/worktrees", tags=["worktrees"])
app.include_router(wx.router, prefix="/api/wx", tags=["wx"])
app.include_router(infra.router)  # Router has /api/infra prefix

# Planet Code Graph (PCG) integration is optional. Off by default so a
# vanilla Commander install (without PCG indexing into planet_ops) doesn't
# expose endpoints that crash with missing-table errors. Enable via
# PLANET_OPS_ENABLE_PCG_INTEGRATION=true or
# ~/.config/planet-commander/config.yaml: { enable_pcg_integration: true }.
from app.config import settings as _settings  # local import — avoid top-level cycle
if _settings.enable_pcg_integration:
    app.include_router(pcg.router)  # Router has /api/pcg prefix


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "sync": scheduler.status(),
    }
