/**
 * Centralized URL configuration.
 *
 * Base URLs are loaded from the backend /api/config/urls endpoint at startup.
 * All frontend code should use these helpers instead of hardcoding URLs.
 */

interface UrlConfig {
  gitlab: string;
  jira: string;
  grafana: string;
  slack: string;
}

let _urls: UrlConfig = {
  gitlab: "",
  jira: "",
  grafana: "",
  slack: "",
};

let _loaded = false;

export async function loadUrls(): Promise<void> {
  if (_loaded) return;
  try {
    const res = await fetch("/api/config/urls");
    if (res.ok) {
      _urls = await res.json();
      _loaded = true;
    }
  } catch {
    console.warn("Failed to load URL config from backend");
  }
}

export function urls(): UrlConfig {
  return _urls;
}

export function gitlabUrl(path?: string): string {
  return path ? `${_urls.gitlab}/${path}` : _urls.gitlab;
}

export function jiraUrl(key?: string): string {
  return key ? `${_urls.jira}/browse/${key}` : _urls.jira;
}

export function grafanaUrl(path?: string): string {
  return path ? `${_urls.grafana}/${path}` : _urls.grafana;
}

export function slackUrl(path?: string): string {
  return path ? `${_urls.slack}/${path}` : _urls.slack;
}

export function gitlabMrUrl(repo: string, iid: number): string {
  return `${_urls.gitlab}/${repo}/-/merge_requests/${iid}`;
}

export function gitlabCommitUrl(repo: string, sha: string): string {
  return `${_urls.gitlab}/${repo}/-/commit/${sha}`;
}

export function gitlabBlobUrl(repo: string, branch: string, filePath: string, line?: number): string {
  const lineAnchor = line ? `#L${line}` : "";
  return `${_urls.gitlab}/${repo}/-/blob/${branch}/${filePath}${lineAnchor}`;
}

export function slackChannelUrl(channel: string): string {
  return `${_urls.slack}/channels/${channel}`;
}

export function slackTeamUrl(username: string): string {
  return `${_urls.slack}/team/${username}`;
}
