"""URL type enumeration for URL classification."""
import enum


class URLType(str, enum.Enum):
    """Types of URLs that can be extracted and classified."""

    # GitLab
    GITLAB_JOB = "gitlab_job"                    # /code/api/v4/jobs/{job_id}
    GITLAB_MR = "gitlab_mr"                      # /code/{project}/{repo}/-/merge_requests/{mr_id}
    GITLAB_BRANCH = "gitlab_branch"              # /code/{project}/{repo}/-/tree/{branch}
    GITLAB_COMMIT = "gitlab_commit"              # /code/{project}/{repo}/-/commit/{sha}
    GITLAB_ISSUE = "gitlab_issue"                # /code/{project}/{repo}/-/issues/{issue_id}
    GITLAB_PIPELINE = "gitlab_pipeline"          # /code/{project}/{repo}/-/pipelines/{pipeline_id}
    GITLAB_FILE = "gitlab_file"                  # /code/{project}/{repo}/-/blob/{branch}/{path}

    # JIRA
    JIRA_ISSUE = "jira_issue"                    # /jira/browse/{TICKET-123}

    # Google
    GOOGLE_DOC = "google_doc"                    # docs.google.com/document/d/{id}
    GOOGLE_SHEET = "google_sheet"                # docs.google.com/spreadsheets/d/{id}
    GOOGLE_SLIDE = "google_slide"                # docs.google.com/presentation/d/{id}
    GOOGLE_DRIVE = "google_drive"                # drive.google.com/file/d/{id}

    # Slack
    SLACK_MESSAGE = "slack_message"              # planet.slack.com/archives/{channel}/p{timestamp}
    SLACK_THREAD = "slack_thread"                # planet.slack.com/archives/{channel}/p{thread_ts}

    # Grafana
    GRAFANA_DASHBOARD = "grafana_dashboard"      # grafana.com/d/{id}
    GRAFANA_EXPLORE = "grafana_explore"          # grafana.com/explore
    GRAFANA_ALERT = "grafana_alert"              # grafana.com/alerting/list

    # PagerDuty
    PAGERDUTY_INCIDENT = "pagerduty_incident"    # pagerduty.com/incidents/{id}

    # GitHub (for reference)
    GITHUB_REPO = "github_repo"                  # github.com/{org}/{repo}
    GITHUB_ISSUE = "github_issue"                # github.com/{org}/{repo}/issues/{id}
    GITHUB_PR = "github_pr"                      # github.com/{org}/{repo}/pull/{id}

    # Other
    UNKNOWN = "unknown"                          # Unrecognized pattern
