from fastapi import APIRouter

router = APIRouter()

STUB_LINKS = {
    "wx": {
        "git": [
            {"label": "wx (monorepo)", "url": "https://hello.planet.com/code/wx/wx", "icon": "git-branch"},
            {"label": "eso-golang", "url": "https://hello.planet.com/code/wx/eso-golang", "icon": "git-branch"},
        ],
        "slack": [
            {"label": "#wx-users", "url": "#", "icon": "message-circle"},
            {"label": "#compute-platform", "url": "#", "icon": "message-circle"},
        ],
        "grafana": [
            {"label": "WX Tasks", "url": "https://planet.grafana.net/d/wx-tasks", "icon": "bar-chart"},
            {"label": "WX Workers", "url": "https://planet.grafana.net/d/wx-workers", "icon": "bar-chart"},
        ],
        "jira": [
            {"label": "WX Board", "url": "https://hello.planet.com/jira/secure/RapidBoard.jspa", "icon": "layout"},
            {"label": "My WX Tickets", "url": "https://hello.planet.com/jira/issues/?jql=project%3DCOMPUTE", "icon": "check-square"},
        ],
        "docs": [
            {"label": "WX Architecture", "url": "#", "icon": "file-text"},
            {"label": "WX Runbook", "url": "#", "icon": "book"},
        ],
    },
    "g4": {
        "git": [
            {"label": "g4 (main)", "url": "https://hello.planet.com/code/product/g4-wk/g4", "icon": "git-branch"},
            {"label": "g4-task", "url": "https://hello.planet.com/code/product/g4-wk/g4-task", "icon": "git-branch"},
        ],
        "slack": [
            {"label": "#g4-users", "url": "#", "icon": "message-circle"},
        ],
        "grafana": [
            {"label": "G4 Cluster Overview", "url": "https://planet.grafana.net/d/g4-cluster", "icon": "bar-chart"},
            {"label": "G4 Tasks", "url": "https://planet.grafana.net/d/g4-tasks", "icon": "bar-chart"},
            {"label": "G4 Pools", "url": "https://planet.grafana.net/d/g4-pools", "icon": "bar-chart"},
            {"label": "G4 Data Collects", "url": "https://planet.grafana.net/d/g4-dc", "icon": "bar-chart"},
            {"label": "G4 SLIs", "url": "https://planet.grafana.net/d/g4-sli", "icon": "bar-chart"},
        ],
        "jira": [
            {"label": "G4 Board", "url": "https://hello.planet.com/jira/secure/RapidBoard.jspa", "icon": "layout"},
        ],
        "docs": [
            {"label": "G4 Architecture", "url": "#", "icon": "file-text"},
            {"label": "G4 Dashboards Guide", "url": "#", "icon": "book"},
        ],
    },
    "jobs": {
        "git": [
            {"label": "jobs", "url": "https://hello.planet.com/code/jobs", "icon": "git-branch"},
        ],
        "slack": [
            {"label": "#jobs-users", "url": "#", "icon": "message-circle"},
        ],
        "grafana": [
            {"label": "Jobs 3E", "url": "https://planet.grafana.net/d/jobs-3e", "icon": "bar-chart"},
            {"label": "Jobs Alerts", "url": "https://planet.grafana.net/d/jobs-alerts", "icon": "bar-chart"},
        ],
        "jira": [
            {"label": "Jobs Board", "url": "https://hello.planet.com/jira/secure/RapidBoard.jspa", "icon": "layout"},
        ],
        "docs": [
            {"label": "Jobs Architecture", "url": "#", "icon": "file-text"},
        ],
    },
    "temporal": {
        "git": [
            {"label": "temporalio-cloud", "url": "https://hello.planet.com/code/temporal/temporalio-cloud", "icon": "git-branch"},
        ],
        "slack": [
            {"label": "#temporal", "url": "#", "icon": "message-circle"},
        ],
        "grafana": [
            {"label": "Temporal Metrics", "url": "https://planet.grafana.net/d/temporal", "icon": "bar-chart"},
        ],
        "jira": [
            {"label": "Temporal Board", "url": "https://hello.planet.com/jira/secure/RapidBoard.jspa", "icon": "layout"},
        ],
        "docs": [
            {"label": "Temporal Operations Guide", "url": "#", "icon": "file-text"},
        ],
    },
}


@router.get("/{project}/links")
async def get_project_links(project: str):
    links = STUB_LINKS.get(project, {})
    return {"project": project, "links": links}
