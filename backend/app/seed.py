"""Seed database with canonical labels and project links."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import Base
from app.models.label import Label
from app.models.layout import DashboardLayout, ProjectLink

CANONICAL_LABELS = [
    # Project labels
    ("wx", "project", "#3B82F6", "Work Exchange platform"),
    ("g4", "project", "#8B5CF6", "G4 processing pipeline"),
    ("jobs", "project", "#F59E0B", "Jobs compute platform"),
    ("temporal", "project", "#10B981", "Temporal workflow orchestration"),
    # Task-type labels
    ("investigation", "task-type", "#EF4444", "Production investigation or debugging"),
    ("code-review", "task-type", "#6366F1", "Merge request review"),
    ("incident", "task-type", "#DC2626", "Production incident response"),
    ("feature", "task-type", "#22C55E", "New feature development"),
    ("bug-fix", "task-type", "#F97316", "Bug fix"),
    ("analysis", "task-type", "#06B6D4", "Data or system analysis"),
    ("documentation", "task-type", "#8B5CF6", "Documentation work"),
    ("deployment", "task-type", "#F59E0B", "Deployment or release"),
    ("refactor", "task-type", "#64748B", "Code refactoring"),
    ("planning", "task-type", "#A855F7", "Planning or design work"),
    ("review", "task-type", "#6366F1", "Code or doc review"),
    # Priority labels
    ("critical", "priority", "#DC2626", "Critical priority"),
    ("high", "priority", "#F97316", "High priority"),
    ("medium", "priority", "#EAB308", "Medium priority"),
    ("low", "priority", "#6B7280", "Low priority"),
    # Scope labels
    ("single-file", "scope", "#94A3B8", "Single file change"),
    ("multi-file", "scope", "#64748B", "Multiple file changes"),
    ("cross-repo", "scope", "#475569", "Spans multiple repositories"),
    ("cross-project", "scope", "#1E293B", "Spans multiple projects"),
    # Status labels
    ("blocked", "status", "#EF4444", "Work is blocked"),
    ("needs-review", "status", "#F59E0B", "Awaiting review"),
    ("follow-up", "status", "#3B82F6", "Requires follow-up"),
]

PROJECT_LINKS = [
    # WX
    ("wx", "git", "wx (monorepo)", "https://hello.planet.com/code/wx/wx", "git-branch", 0),
    ("wx", "git", "eso-golang", "https://hello.planet.com/code/wx/eso-golang", "git-branch", 1),
    ("wx", "slack", "#wx-users", "#", "message-circle", 0),
    ("wx", "slack", "#compute-platform", "#", "message-circle", 1),
    ("wx", "grafana", "WX Tasks", "https://planet.grafana.net/d/wx-tasks", "bar-chart", 0),
    ("wx", "grafana", "WX Workers", "https://planet.grafana.net/d/wx-workers", "bar-chart", 1),
    ("wx", "jira", "WX Board", "https://hello.planet.com/jira/secure/RapidBoard.jspa", "layout", 0),
    ("wx", "docs", "WX Architecture", "#", "file-text", 0),
    ("wx", "docs", "WX Runbook", "#", "book", 1),
    # G4
    ("g4", "git", "g4 (main)", "https://hello.planet.com/code/product/g4-wk/g4", "git-branch", 0),
    ("g4", "git", "g4-task", "https://hello.planet.com/code/product/g4-wk/g4-task", "git-branch", 1),
    ("g4", "slack", "#g4-users", "#", "message-circle", 0),
    ("g4", "grafana", "G4 Cluster Overview", "https://planet.grafana.net/d/g4-cluster", "bar-chart", 0),
    ("g4", "grafana", "G4 Tasks", "https://planet.grafana.net/d/g4-tasks", "bar-chart", 1),
    ("g4", "grafana", "G4 Pools", "https://planet.grafana.net/d/g4-pools", "bar-chart", 2),
    ("g4", "grafana", "G4 Data Collects", "https://planet.grafana.net/d/g4-dc", "bar-chart", 3),
    ("g4", "grafana", "G4 SLIs", "https://planet.grafana.net/d/g4-sli", "bar-chart", 4),
    ("g4", "jira", "G4 Board", "https://hello.planet.com/jira/secure/RapidBoard.jspa", "layout", 0),
    ("g4", "docs", "G4 Architecture", "#", "file-text", 0),
    ("g4", "docs", "G4 Dashboards Guide", "#", "book", 1),
    # Jobs
    ("jobs", "git", "jobs", "https://hello.planet.com/code/jobs", "git-branch", 0),
    ("jobs", "slack", "#jobs-users", "#", "message-circle", 0),
    ("jobs", "grafana", "Jobs 3E", "https://planet.grafana.net/d/jobs-3e", "bar-chart", 0),
    ("jobs", "grafana", "Jobs Alerts", "https://planet.grafana.net/d/jobs-alerts", "bar-chart", 1),
    ("jobs", "jira", "Jobs Board", "https://hello.planet.com/jira/secure/RapidBoard.jspa", "layout", 0),
    ("jobs", "docs", "Jobs Architecture", "#", "file-text", 0),
    # Temporal
    ("temporal", "git", "temporalio-cloud", "https://hello.planet.com/code/temporal/temporalio-cloud", "git-branch", 0),
    ("temporal", "slack", "#temporal", "#", "message-circle", 0),
    ("temporal", "grafana", "Temporal Metrics", "https://planet.grafana.net/d/temporal", "bar-chart", 0),
    ("temporal", "jira", "Temporal Board", "https://hello.planet.com/jira/secure/RapidBoard.jspa", "layout", 0),
    ("temporal", "docs", "Temporal Operations Guide", "#", "file-text", 0),
]

DEFAULT_LAYOUT = {
    "layout": [
        {"i": "slack", "x": 0, "y": 0, "w": 6, "h": 4},
        {"i": "mrs", "x": 6, "y": 0, "w": 6, "h": 4},
        {"i": "jira", "x": 0, "y": 4, "w": 4, "h": 4},
        {"i": "oncall", "x": 4, "y": 4, "w": 4, "h": 3},
        {"i": "traffic", "x": 8, "y": 4, "w": 4, "h": 4},
        {"i": "workload", "x": 0, "y": 8, "w": 6, "h": 4},
        {"i": "docs", "x": 6, "y": 8, "w": 6, "h": 4},
    ]
}


def seed():
    engine = create_engine(settings.database_url_sync)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Seed labels (skip if already exist)
        existing = {l.name for l in session.query(Label).all()}
        for name, category, color, description in CANONICAL_LABELS:
            if name not in existing:
                session.add(Label(
                    name=name,
                    category=category,
                    color=color,
                    description=description,
                    is_canonical=True,
                    created_by="system",
                ))
        session.commit()
        print(f"Labels: {session.query(Label).count()} total")

        # Seed project links (clear and re-add)
        session.query(ProjectLink).delete()
        for project, category, label_text, url, icon, sort in PROJECT_LINKS:
            session.add(ProjectLink(
                project=project,
                category=category,
                label=label_text,
                url=url,
                icon=icon,
                sort_order=sort,
            ))
        session.commit()
        print(f"Project links: {session.query(ProjectLink).count()} total")

        # Seed default layout
        existing_layout = session.query(DashboardLayout).filter_by(name="default").first()
        if not existing_layout:
            session.add(DashboardLayout(
                name="default",
                layout_json=DEFAULT_LAYOUT,
                collapsed_sections=[],
            ))
            session.commit()
            print("Default layout created")
        else:
            print("Default layout already exists")

    print("Seed complete!")


if __name__ == "__main__":
    seed()
