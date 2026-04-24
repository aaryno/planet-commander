"""GitLab job URL handler."""
import logging
import re
import subprocess
from typing import Any

from sqlalchemy import select

from app.models import GitBranch, GitLabMergeRequest, JiraIssue, LinkType, LinkSourceType
from app.services.jira_cache import JiraCacheService
from app.services.url_handlers.base import URLHandler, HandlerResult

logger = logging.getLogger(__name__)


class GitLabJobHandler(URLHandler):
    """Handle GitLab job URLs - extract branch, MR, JIRA ticket."""

    async def handle(
        self,
        classified_url: dict[str, Any],
        context: dict[str, Any],
    ) -> HandlerResult:
        """Extract metadata from GitLab job and create links.

        Workflow:
        1. Fetch job metadata from GitLab API (using glab)
        2. Extract branch name, pipeline ID, commit SHA
        3. Look up branch in database (or create placeholder)
        4. Find MR for this pipeline
        5. Extract JIRA keys from MR title/description
        6. Create EntityLinks: chat → branch, chat → MR, chat → JIRA

        Args:
            classified_url: Classified URL with job_id in components
            context: Extraction context with chat_id

        Returns:
            HandlerResult with entities and links created
        """
        job_id = classified_url["components"]["job_id"]
        chat_id = context["chat_id"]
        url = classified_url["url"]

        entities_created = []
        links_created = []
        handler_metadata = {"job_id": job_id}

        try:
            # 1. Fetch job metadata using glab CLI
            job_data = await self._fetch_job_metadata(job_id)
            if not job_data:
                return HandlerResult(
                    entities_created=[],
                    links_created=[],
                    handler_metadata=handler_metadata,
                    success=False,
                    error=f"Failed to fetch job {job_id} metadata"
                )

            # Extract key fields
            branch_name = job_data.get("ref")
            pipeline_id = job_data.get("pipeline_id")
            commit_sha = job_data.get("sha")
            project_path = job_data.get("project")

            handler_metadata.update({
                "branch": branch_name,
                "pipeline_id": pipeline_id,
                "commit": commit_sha,
                "project": project_path
            })

            # 2. Link to git branch (if exists in database)
            if branch_name and project_path:
                branch = await self._find_branch(project_path, branch_name)
                if branch:
                    entities_created.append(branch)

                    # Create link: chat mentioned_in branch
                    link = await self.link_service.create_link(
                        from_type="chat",
                        from_id=str(chat_id),
                        to_type="branch",
                        to_id=str(branch.id),
                        link_type=LinkType.MENTIONED_IN,
                        source_type=LinkSourceType.URL_EXTRACTED,
                        link_metadata={
                            "url": url,
                            "job_id": job_id,
                            "extracted_from": "gitlab_job"
                        }
                    )
                    links_created.append(link)

            # 3. Find MR for this pipeline
            if pipeline_id and project_path:
                mr = await self._find_mr_for_pipeline(project_path, pipeline_id)
                if mr:
                    entities_created.append(mr)

                    # Create link: chat discussed_in MR
                    link = await self.link_service.create_link(
                        from_type="chat",
                        from_id=str(chat_id),
                        to_type="merge_request",
                        to_id=str(mr.id),
                        link_type=LinkType.DISCUSSED_IN,
                        source_type=LinkSourceType.URL_EXTRACTED,
                        link_metadata={
                            "url": url,
                            "job_id": job_id,
                            "pipeline_id": pipeline_id,
                            "extracted_from": "gitlab_job"
                        }
                    )
                    links_created.append(link)

                    # 4. Extract JIRA keys from MR
                    jira_keys = self._extract_jira_keys(mr.title + " " + (mr.description or ""))
                    for jira_key in jira_keys:
                        jira_issue = await self._find_or_sync_jira_issue(jira_key)
                        if jira_issue:
                            entities_created.append(jira_issue)

                            # Create link: chat discussed_in JIRA
                            link = await self.link_service.create_link(
                                from_type="chat",
                                from_id=str(chat_id),
                                to_type="jira_issue",
                                to_id=str(jira_issue.id),
                                link_type=LinkType.DISCUSSED_IN,
                                source_type=LinkSourceType.URL_EXTRACTED,
                                link_metadata={
                                    "url": url,
                                    "job_id": job_id,
                                    "via": "gitlab_job->mr",
                                    "jira_key": jira_key
                                }
                            )
                            links_created.append(link)

            logger.info(
                f"GitLabJobHandler: job {job_id} -> "
                f"{len(entities_created)} entities, {len(links_created)} links"
            )

            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=True
            )

        except Exception as e:
            logger.error(f"GitLabJobHandler failed for job {job_id}: {e}")
            return HandlerResult(
                entities_created=entities_created,
                links_created=links_created,
                handler_metadata=handler_metadata,
                success=False,
                error=str(e)
            )

    async def _fetch_job_metadata(self, job_id: int) -> dict | None:
        """Fetch job metadata using glab CLI.

        Args:
            job_id: GitLab job ID

        Returns:
            Job metadata dict or None if failed
        """
        try:
            # Use glab ci view to get job info
            # Format: glab ci view <job-id> -R <project>
            # For now, try without -R and see if it works
            result = subprocess.run(
                ["glab", "ci", "view", str(job_id), "--output", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"glab ci view failed for job {job_id}: {result.stderr}")
                return None

            import json
            job_data = json.loads(result.stdout)

            # Extract key fields
            return {
                "ref": job_data.get("ref"),  # branch name
                "pipeline_id": job_data.get("pipeline", {}).get("id"),
                "sha": job_data.get("commit", {}).get("id"),
                "project": job_data.get("pipeline", {}).get("project_path")
            }

        except Exception as e:
            logger.warning(f"Failed to fetch job {job_id} metadata: {e}")
            return None

    async def _find_branch(self, repo: str, branch_name: str):
        """Find git branch in database.

        Args:
            repo: Repository path (e.g., "wx/wx")
            branch_name: Branch name

        Returns:
            GitBranch or None
        """
        result = await self.db.execute(
            select(GitBranch).where(
                (GitBranch.repo == repo) & (GitBranch.branch_name == branch_name)
            )
        )
        return result.scalar_one_or_none()

    async def _find_mr_for_pipeline(self, repo: str, pipeline_id: int):
        """Find MR associated with pipeline.

        Args:
            repo: Repository path
            pipeline_id: Pipeline ID

        Returns:
            GitLabMergeRequest or None
        """
        # MRs don't currently store pipeline_id, so we can't directly look up
        # For now, return None - this would require adding pipeline tracking
        # TODO: Add pipeline_id to GitLabMergeRequest model
        return None

    def _extract_jira_keys(self, text: str) -> list[str]:
        """Extract JIRA keys from text.

        Args:
            text: Text to scan

        Returns:
            List of JIRA keys found
        """
        if not text:
            return []

        pattern = r'\b([A-Z]+-\d+)\b'
        return list(set(re.findall(pattern, text)))

    async def _find_or_sync_jira_issue(self, jira_key: str):
        """Find JIRA issue in cache or sync from JIRA API.

        Args:
            jira_key: JIRA issue key

        Returns:
            JiraIssue or None
        """
        # Check cache first
        result = await self.db.execute(
            select(JiraIssue).where(JiraIssue.external_key == jira_key)
        )
        issue = result.scalar_one_or_none()

        if issue:
            return issue

        # Not in cache - sync from JIRA
        try:
            jira_cache = JiraCacheService(self.db)
            synced = await jira_cache.sync_issue(jira_key)
            return synced if synced else None
        except Exception as e:
            logger.warning(f"Failed to sync JIRA issue {jira_key}: {e}")
            return None
