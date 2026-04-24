"""Commander CLI - Manual control for background jobs and scanning."""
import click
import asyncio
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, desc
from app.database import async_session
from app.services.branch_tracking import BranchTrackingService
from app.services.worktree_tracking import WorktreeTrackingService
from app.services.jira_cache import JiraCacheService
from app.services.link_inference import LinkInferenceService
from app.services.url_extractor import URLExtractor
from app.services.url_classifier import URLClassifier
from app.models.job_run import JobRun
from app.models.url_type import URLType
from app.services.jira_service import search_tickets


@click.group()
def cli():
    """Planet Commander CLI - Manual background job control."""
    pass


@cli.group()
def scan():
    """Scan repositories and resources."""
    pass


@scan.command("branches")
@click.argument("repo_path", type=click.Path(exists=True))
def scan_branches(repo_path):
    """Scan git branches in a repository."""
    click.echo(f"Scanning branches in {repo_path}...")

    async def _scan():
        async with async_session() as db:
            service = BranchTrackingService(db)
            repo_path_obj = Path(repo_path).resolve()
            branches = await service.scan_repo_branches(str(repo_path_obj))
            await db.commit()
            return branches

    branches = asyncio.run(_scan())

    click.secho(f"✓ Scanned {len(branches)} branches", fg="green")

    for branch in branches:
        status_color = "green" if branch.status.value == "active" else "yellow"
        jira_info = f" → {branch.linked_ticket_key_guess}" if branch.linked_ticket_key_guess else ""
        click.secho(
            f"  {branch.branch_name} ({branch.status.value}){jira_info}",
            fg=status_color
        )


@scan.command("worktrees")
@click.argument("repo_path", type=click.Path(exists=True))
def scan_worktrees(repo_path):
    """Scan git worktrees in a repository."""
    click.echo(f"Scanning worktrees in {repo_path}...")

    async def _scan():
        async with async_session() as db:
            service = WorktreeTrackingService(db)
            repo_path_obj = Path(repo_path).resolve()
            worktrees = await service.scan_worktrees(str(repo_path_obj))
            await db.commit()
            return worktrees

    worktrees = asyncio.run(_scan())

    click.secho(f"✓ Scanned {len(worktrees)} worktrees", fg="green")

    for wt in worktrees:
        status_color = "green" if wt.status.value == "clean" else "red"
        health_info = ""
        if wt.uncommitted_changes:
            health_info += " [uncommitted changes]"
        if wt.untracked_files_count and wt.untracked_files_count > 0:
            health_info += f" [{wt.untracked_files_count} untracked]"

        click.secho(
            f"  {wt.path} ({wt.status.value}){health_info}",
            fg=status_color
        )


@cli.group()
def sync():
    """Sync external data sources."""
    pass


@sync.command("jira")
@click.option("--jql", default=None, help="Custom JQL query")
@click.option("--max-results", default=100, help="Maximum results to fetch")
def sync_jira(jql, max_results):
    """Sync JIRA issues to cache."""
    if not jql:
        jql = (
            'project = COMPUTE AND '
            'status IN ("In Progress", "In Review", "Ready to Deploy", "Monitoring") '
            'ORDER BY updated DESC'
        )

    click.echo(f"Syncing JIRA issues...")
    click.echo(f"JQL: {jql}")

    async def _sync():
        # Fetch from JIRA API
        tickets = search_tickets(jql, max_results=max_results)
        jira_keys = [t['key'] for t in tickets]

        # Sync to cache
        async with async_session() as db:
            jira_cache = JiraCacheService(db)
            synced = await jira_cache.batch_sync_issues(jira_keys)
            await db.commit()
            return len(synced)

    count = asyncio.run(_sync())
    click.secho(f"✓ Synced {count} JIRA issues", fg="green")


@cli.command("infer")
def infer_links():
    """Run link inference across all entities."""
    click.echo("Running link inference...")

    async def _infer():
        async with async_session() as db:
            inference = LinkInferenceService(db)
            results = await inference.infer_all_links()
            await db.commit()
            return results

    results = asyncio.run(_infer())

    total = results['total']
    click.secho(f"✓ Created {total} suggested links", fg="green")
    click.echo(f"  - Branch→JIRA: {results['branch_jira']}")
    click.echo(f"  - Chat→JIRA: {results['chat_jira']}")


@cli.command("status")
@click.option("--limit", default=20, help="Number of recent jobs to show")
@click.option("--job-name", default=None, help="Filter by job name")
def job_status(limit, job_name):
    """Show background job execution history."""

    async def _status():
        async with async_session() as db:
            query = select(JobRun).order_by(desc(JobRun.started_at)).limit(limit)
            if job_name:
                query = query.where(JobRun.job_name == job_name)

            result = await db.execute(query)
            return result.scalars().all()

    runs = asyncio.run(_status())

    if not runs:
        click.echo("No job runs found")
        return

    click.echo(f"\nRecent job runs ({len(runs)}):\n")

    for run in runs:
        status_color = {
            "success": "green",
            "failed": "red",
            "running": "yellow"
        }.get(run.status, "white")

        duration = f"{run.duration_seconds:.1f}s" if run.duration_seconds else "running"
        records = f"{run.records_processed} records" if run.records_processed > 0 else ""

        click.secho(
            f"  {run.job_name:20s} {run.status:10s} "
            f"{run.started_at.strftime('%Y-%m-%d %H:%M:%S'):20s} "
            f"{duration:8s} {records}",
            fg=status_color
        )

        if run.error_message:
            click.secho(f"    Error: {run.error_message}", fg="red")


@cli.group()
def urls():
    """URL extraction and classification."""
    pass


@urls.command("extract")
@click.argument("chat_id")
@click.option("--limit", default=None, type=int, help="Limit messages to scan")
def extract_urls(chat_id, limit):
    """Extract URLs from a chat's messages."""
    click.echo(f"Extracting URLs from chat {chat_id}...")

    async def _extract():
        async with async_session() as db:
            extractor = URLExtractor(db)
            try:
                agent_uuid = uuid_lib.UUID(chat_id)
            except ValueError:
                raise click.ClickException(f"Invalid chat ID: {chat_id}")

            urls = await extractor.extract_from_chat(agent_uuid, limit_messages=limit)
            return urls

    urls_found = asyncio.run(_extract())

    click.secho(f"✓ Found {len(urls_found)} URLs", fg="green")

    if not urls_found:
        return

    # Group by domain
    by_domain = {}
    for url_data in urls_found:
        from urllib.parse import urlparse
        domain = urlparse(url_data["url"]).netloc
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(url_data)

    click.echo(f"\nURLs by domain:")
    for domain, domain_urls in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        click.secho(f"\n  {domain} ({len(domain_urls)} URLs):", fg="cyan")
        for url_data in domain_urls[:5]:  # Show first 5
            click.echo(f"    {url_data['url'][:80]}")
        if len(domain_urls) > 5:
            click.echo(f"    ... and {len(domain_urls) - 5} more")


@urls.command("classify")
@click.argument("url")
def classify_url(url):
    """Classify a single URL."""
    classifier = URLClassifier()
    result = classifier.classify(url)

    click.echo(f"\nURL: {url}")
    click.echo(f"Domain: {result['domain']}")

    if result['type'] == URLType.UNKNOWN:
        click.secho(f"Type: UNKNOWN", fg="yellow")
        click.echo(f"Confidence: {result['confidence']}")
    else:
        click.secho(f"Type: {result['type'].value}", fg="green")
        click.echo(f"Confidence: {result['confidence']}")

        if result['components']:
            click.echo(f"Components:")
            for key, value in result['components'].items():
                click.echo(f"  {key}: {value}")


@urls.command("scan")
@click.argument("chat_id")
@click.option("--limit", default=None, type=int, help="Limit messages to scan")
def scan_chat_urls(chat_id, limit):
    """Extract and classify URLs from a chat."""
    click.echo(f"Scanning chat {chat_id} for URLs...")

    async def _scan():
        async with async_session() as db:
            extractor = URLExtractor(db)
            try:
                agent_uuid = uuid_lib.UUID(chat_id)
            except ValueError:
                raise click.ClickException(f"Invalid chat ID: {chat_id}")

            urls = await extractor.extract_from_chat(agent_uuid, limit_messages=limit)
            return urls

    urls_found = asyncio.run(_scan())
    click.secho(f"✓ Found {len(urls_found)} URLs", fg="green")

    if not urls_found:
        return

    # Classify each URL
    classifier = URLClassifier()
    classified = []
    for url_data in urls_found:
        result = classifier.classify(url_data["url"])
        classified.append({
            **url_data,
            **result
        })

    # Group by type
    by_type = {}
    for item in classified:
        url_type = item['type']
        if url_type not in by_type:
            by_type[url_type] = []
        by_type[url_type].append(item)

    click.echo(f"\nURLs by type:")
    for url_type, type_urls in sorted(by_type.items(), key=lambda x: -len(x[1])):
        color = "green" if url_type != URLType.UNKNOWN else "yellow"
        click.secho(f"\n  {url_type.value} ({len(type_urls)} URLs):", fg=color)

        for item in type_urls[:5]:  # Show first 5
            click.echo(f"    {item['url'][:80]}")
            if item['components']:
                comp_str = ", ".join(f"{k}={v}" for k, v in item['components'].items())
                click.echo(f"      → {comp_str}")

        if len(type_urls) > 5:
            click.echo(f"    ... and {len(type_urls) - 5} more")


if __name__ == "__main__":
    cli()
