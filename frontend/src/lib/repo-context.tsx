"use client";

import { createContext, useContext } from "react";

export interface RepoInfo {
  /** GitLab project path, e.g. "wx/wx" */
  gitlabProject: string;
  /** Git branch name */
  branch: string;
  /** Local working directory paths to match against (worktree + checkout) */
  workDirs: string[];
}

const RepoContext = createContext<RepoInfo | null>(null);

export const RepoProvider = RepoContext.Provider;
export const useRepoContext = () => useContext(RepoContext);

/** Map Commander project name to GitLab namespace/repo path */
export function resolveGitLabProject(project: string): string {
  if (project.includes("/")) return project;
  const map: Record<string, string> = {
    wx: "wx/wx",
    g4: "product/g4",
    "g4-task": "product/g4-task",
    golib: "product/golib",
    temporal: "temporal/temporalio-cloud",
    eso: "wx/eso-golang",
    "eso-golang": "wx/eso-golang",
    dashboard: "aaryn/claude",
    commander: "aaryn/claude",
  };
  return map[project] || project;
}

/**
 * Convert an absolute file path to a GitLab URL using repo context.
 * Returns null if the path doesn't match any known working directory.
 * Handles line number suffixes like :42 → #L42
 */
export function fileToGitLabUrl(
  filePath: string,
  repo: RepoInfo
): { url: string; relativePath: string; line?: number } | null {
  // Resolve ~/ to /Users/aaryn/
  const resolved = filePath.startsWith("~/")
    ? `/Users/aaryn/${filePath.slice(2)}`
    : filePath;

  // Extract line number suffix (:42)
  let lineAnchor = "";
  let line: number | undefined;
  let cleanPath = resolved;
  const lineMatch = resolved.match(/:(\d+)$/);
  if (lineMatch) {
    line = parseInt(lineMatch[1], 10);
    lineAnchor = `#L${line}`;
    cleanPath = resolved.slice(0, -lineMatch[0].length);
  }

  // Check against work directories
  for (const workDir of repo.workDirs) {
    const normalized = workDir.endsWith("/") ? workDir : workDir + "/";
    if (cleanPath.startsWith(normalized)) {
      const relativePath = cleanPath.slice(normalized.length);
      const url = `https://hello.planet.com/code/${repo.gitlabProject}/-/blob/${repo.branch}/${relativePath}${lineAnchor}`;
      return { url, relativePath, line };
    }
  }

  return null;
}
