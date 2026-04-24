"""URL handler system for extracting metadata and creating entity links."""

from app.services.url_handlers.base import URLHandler, HandlerResult
from app.services.url_handlers.gitlab_job import GitLabJobHandler
from app.services.url_handlers.gitlab_mr import GitLabMRHandler
from app.services.url_handlers.gitlab_branch import GitLabBranchHandler
from app.services.url_handlers.jira_issue import JiraIssueHandler
from app.services.url_handlers.google_doc import GoogleDocHandler
from app.services.url_handlers.unknown import UnknownURLHandler

__all__ = [
    "URLHandler",
    "HandlerResult",
    "GitLabJobHandler",
    "GitLabMRHandler",
    "GitLabBranchHandler",
    "JiraIssueHandler",
    "GoogleDocHandler",
    "UnknownURLHandler",
]
