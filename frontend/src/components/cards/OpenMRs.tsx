"use client";

import { useState, useCallback, useMemo } from "react";
import { GitPullRequest, CheckCircle, AlertCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { ExpandableRow } from "@/components/shared/ExpandableRow";
import { MRExpanded } from "@/components/expanded/MRExpanded";
import { usePoll } from "@/lib/polling";
import { api, DetailedMR } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { extractJiraKey } from "@/lib/utils";
import { formatHoursAgo } from "@/lib/time-utils";

type SortField = "created" | "updated" | "project" | "author" | "status";
type SortDirection = "asc" | "desc";

const PROJECTS = [
  { key: "wx", label: "WX", color: "text-blue-400 border-blue-600/50 bg-blue-500/10" },
  { key: "jobs", label: "Jobs", color: "text-purple-400 border-purple-600/50 bg-purple-500/10" },
  { key: "g4", label: "G4", color: "text-orange-400 border-orange-600/50 bg-orange-500/10" },
  { key: "temporal", label: "Temporal", color: "text-pink-400 border-pink-600/50 bg-pink-500/10" },
];

const MR_TYPES = [
  { key: "feat", label: "feat", color: "text-emerald-400 border-emerald-600/50 bg-emerald-500/10" },
  { key: "fix", label: "fix", color: "text-red-400 border-red-600/50 bg-red-500/10" },
  { key: "docs", label: "docs", color: "text-blue-400 border-blue-600/50 bg-blue-500/10" },
  { key: "chore", label: "chore", color: "text-zinc-400 border-zinc-600/50 bg-zinc-500/10" },
  { key: "refactor", label: "refactor", color: "text-purple-400 border-purple-600/50 bg-purple-500/10" },
  { key: "test", label: "test", color: "text-yellow-400 border-yellow-600/50 bg-yellow-500/10" },
  { key: "ci", label: "ci", color: "text-cyan-400 border-cyan-600/50 bg-cyan-500/10" },
  { key: "deploy", label: "deploy", color: "text-orange-400 border-orange-600/50 bg-orange-500/10" },
  { key: "build", label: "build", color: "text-amber-400 border-amber-600/50 bg-amber-500/10" },
  { key: "perf", label: "perf", color: "text-lime-400 border-lime-600/50 bg-lime-500/10" },
  { key: "style", label: "style", color: "text-pink-400 border-pink-600/50 bg-pink-500/10" },
  { key: "revert", label: "revert", color: "text-rose-400 border-rose-600/50 bg-rose-500/10" },
  { key: "other", label: "other", color: "text-slate-400 border-slate-600/50 bg-slate-500/10" },
] as const;

const MR_STATUSES = [
  { key: "draft", label: "draft", color: "text-zinc-400 border-zinc-600/50 bg-zinc-500/10" },
  { key: "unreviewed", label: "unreviewed", color: "text-yellow-400 border-yellow-600/50 bg-yellow-500/10" },
  { key: "needs-review", label: "needs-review", color: "text-amber-400 border-amber-600/50 bg-amber-500/10" },
  { key: "reviewed", label: "reviewed", color: "text-emerald-400 border-emerald-600/50 bg-emerald-500/10" },
] as const;

const MR_TYPE_COLORS: Record<string, string> = Object.fromEntries(
  MR_TYPES.map(t => [t.key, t.color])
);

function extractMRType(title: string): string | null {
  // Match conventional commit format: "type:" or "type(scope):"
  const match = title.match(/^(feat|fix|docs|chore|refactor|test|ci|deploy|build|perf|style|revert)(\(|:)/i);
  return match ? match[1].toLowerCase() : null;
}

function cleanTitle(title: string): string {
  // Remove "Draft: " prefix
  let cleaned = title.replace(/^Draft:\s*/i, "");

  // Remove "[DRAFT]" anywhere
  cleaned = cleaned.replace(/\[DRAFT\]\s*/gi, "");

  // Remove type prefix (e.g., "fix: ", "feat(scope): ")
  cleaned = cleaned.replace(/^(feat|fix|docs|chore|refactor|test|ci|deploy|build|perf|style|revert)(\([^)]*\))?:\s*/i, "");

  return cleaned.trim();
}

// extractJiraKey imported from @/lib/utils

function ProjectBadge({ projectKey }: { projectKey: string }) {
  const project = PROJECTS.find(p => p.key === projectKey);
  if (!project) return <span className="text-zinc-500 text-xs">{projectKey}</span>;

  return (
    <span className={`${project.color} border text-[10px] font-medium px-1.5 py-0.5 rounded uppercase`}>
      {project.label}
    </span>
  );
}

function MRTypeBadge({ title }: { title: string }) {
  const type = extractMRType(title);
  if (!type) return null;

  const color = MR_TYPE_COLORS[type] || "text-zinc-400 border-zinc-600/50 bg-zinc-500/10";
  return (
    <span className={`${color} border text-[10px] font-medium px-1.5 py-0.5 rounded`}>
      {type}
    </span>
  );
}

function DraftBadge() {
  return (
    <span className="text-zinc-400 border border-zinc-600/50 bg-zinc-500/10 text-[10px] font-medium px-1.5 py-0.5 rounded">
      DRAFT
    </span>
  );
}

function SortIcon({ field, currentField, direction }: { field: SortField; currentField: SortField; direction: SortDirection }) {
  if (field !== currentField) return null;
  return direction === "asc" ? (
    <ChevronUp className="h-3 w-3 inline ml-1" />
  ) : (
    <ChevronDown className="h-3 w-3 inline ml-1" />
  );
}

function getMRStatus(mr: DetailedMR): string[] {
  const statuses: string[] = [];

  if (mr.is_draft) {
    statuses.push("draft");
  }

  if (!mr.reviews || mr.reviews.length === 0) {
    statuses.push("unreviewed");
  } else if (mr.needs_review) {
    statuses.push("needs-review");
  } else {
    statuses.push("reviewed");
  }

  return statuses;
}

function ReviewStatus({ mr }: { mr: DetailedMR }) {
  if (!mr.reviews || mr.reviews.length === 0) {
    return <span className="text-zinc-500 text-xs">Not reviewed</span>;
  }

  if (mr.needs_review) {
    return (
      <span className="flex items-center gap-1 text-xs text-amber-400">
        <AlertCircle className="h-3 w-3" />
        Needs re-review
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1 text-xs text-emerald-400">
      <CheckCircle className="h-3 w-3" />
      Reviewed ({mr.reviews.length})
    </span>
  );
}

interface OpenMRsProps {
  hideProjectFilter?: boolean;
  hideProjectColumn?: boolean;
  /** Filter to specific repository paths (from project config) */
  repositories?: string[];
}

export function OpenMRs({ hideProjectFilter = false, hideProjectColumn = false, repositories }: OpenMRsProps) {
  const defaultProjects = repositories && repositories.length > 0 ? repositories : PROJECTS.map(p => p.key);
  const [selectedProjects, setSelectedProjects] = useState<string[]>(defaultProjects);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(MR_TYPES.map(t => t.key));
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(MR_STATUSES.map(s => s.key));
  const [sortField, setSortField] = useState<SortField>("status");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const fetcher = useCallback(
    () => {
      // If no projects selected, return empty result immediately
      if (selectedProjects.length === 0) {
        return Promise.resolve({ mrs: [], total: 0, projects: [] });
      }
      return api.mrs(selectedProjects);
    },
    [selectedProjects]
  );

  const { data, loading, error, refresh } = usePoll<{ mrs: DetailedMR[]; total: number; projects: string[] }>(
    fetcher,
    120_000 // 2 minutes
  );

  // Filter and sort MRs
  const sortedMRs = useMemo(() => {
    if (!data?.mrs) return [];

    let filtered = [...data.mrs];

    // Filter by status badges
    filtered = filtered.filter(mr => {
      const mrStatuses = getMRStatus(mr);
      return mrStatuses.some(status => selectedStatuses.includes(status));
    });

    // Filter by MR type badges
    filtered = filtered.filter(mr => {
      const mrType = extractMRType(mr.title) || "other";
      return selectedTypes.includes(mrType);
    });

    // Sort
    return filtered.sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case "created":
          comparison = a.age_created_hours - b.age_created_hours;
          break;
        case "updated":
          comparison = a.age_last_commit_hours - b.age_last_commit_hours;
          break;
        case "project":
          comparison = a.project.localeCompare(b.project);
          break;
        case "author":
          comparison = a.author.localeCompare(b.author);
          break;
        case "status":
          // Sort by review status
          if (a.needs_review && !b.needs_review) comparison = -1;
          else if (!a.needs_review && b.needs_review) comparison = 1;
          else comparison = 0;
          break;
      }

      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [data?.mrs, selectedStatuses, selectedTypes, sortField, sortDirection]);

  const toggleProject = (projectKey: string) => {
    setSelectedProjects(prev =>
      prev.includes(projectKey)
        ? prev.filter(p => p !== projectKey)
        : [...prev, projectKey]
    );
  };

  const toggleAllProjects = () => {
    if (selectedProjects.length === 0) {
      // If none selected, select all
      setSelectedProjects(PROJECTS.map(p => p.key));
    } else {
      // If any selected, deselect all
      setSelectedProjects([]);
    }
  };

  const toggleType = (typeKey: string) => {
    setSelectedTypes(prev =>
      prev.includes(typeKey)
        ? prev.filter(t => t !== typeKey)
        : [...prev, typeKey]
    );
  };

  const toggleAllTypes = () => {
    if (selectedTypes.length === 0) {
      // If none selected, select all
      setSelectedTypes(MR_TYPES.map(t => t.key));
    } else {
      // If any selected, deselect all
      setSelectedTypes([]);
    }
  };

  const toggleStatus = (statusKey: string) => {
    setSelectedStatuses(prev =>
      prev.includes(statusKey)
        ? prev.filter(s => s !== statusKey)
        : [...prev, statusKey]
    );
  };

  const toggleAllStatuses = () => {
    if (selectedStatuses.length === 0) {
      // If none selected, select all
      setSelectedStatuses(MR_STATUSES.map(s => s.key));
    } else {
      // If any selected, deselect all
      setSelectedStatuses([]);
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  return (
      <ScrollableCard
        title={`Open MRs${data?.total ? ` (${data.total})` : ""}`}
        icon={<GitPullRequest className="h-4 w-4" />}
        menuItems={[{ label: "Refresh", onClick: refresh }]}
        stickyHeader={
          <div className="space-y-2">
          {/* Project selector */}
          {!hideProjectFilter && (
            <div className="flex gap-3">
              <button
                onClick={toggleAllProjects}
                className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors shrink-0"
              >
                Projects
              </button>
              <div className="flex items-center gap-2 flex-wrap">
                {PROJECTS.map(project => (
                  <button
                    key={project.key}
                    onClick={() => toggleProject(project.key)}
                    className={`${
                      selectedProjects.includes(project.key)
                        ? `${project.color} border`
                        : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                    } text-[10px] font-medium px-2 py-1 rounded uppercase transition-colors hover:opacity-80`}
                  >
                    {project.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Type badge selector */}
          <div className="flex items-start gap-3">
            <button
              onClick={toggleAllTypes}
              className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors shrink-0 mt-0.5"
            >
              Types
            </button>
            <div className="flex flex-wrap items-center gap-2">
              {MR_TYPES.map(type => (
                <button
                  key={type.key}
                  onClick={() => toggleType(type.key)}
                  className={`${
                    selectedTypes.includes(type.key)
                      ? `${type.color} border`
                      : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                  } text-[10px] font-medium px-1.5 py-0.5 rounded transition-colors hover:opacity-80`}
                >
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* Status badge selector */}
          <div className="flex items-start gap-3">
            <button
              onClick={toggleAllStatuses}
              className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors shrink-0 mt-0.5"
            >
              Status
            </button>
            <div className="flex flex-wrap items-center gap-2">
              {MR_STATUSES.map(status => (
                <button
                  key={status.key}
                  onClick={() => toggleStatus(status.key)}
                  className={`${
                    selectedStatuses.includes(status.key)
                      ? `${status.color} border`
                      : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                  } text-[10px] font-medium px-1.5 py-0.5 rounded transition-colors hover:opacity-80`}
                >
                  {status.label}
                </button>
              ))}
            </div>
          </div>
          </div>
        }
      >
          {/* Loading/Error states */}
          {loading && <p className="text-xs text-zinc-500 shrink-0">Loading MRs...</p>}
          {error && <p className="text-xs text-red-400 shrink-0">Failed to load MRs</p>}

          {/* MR Table */}
          {data && sortedMRs.length === 0 && (
            <p className="text-xs text-zinc-500 shrink-0">No open MRs</p>
          )}

          {data && sortedMRs.length > 0 && (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Table header - sticky */}
              <div className={`grid ${hideProjectColumn ? 'grid-cols-11' : 'grid-cols-12'} gap-2 text-[10px] text-zinc-600 font-medium pb-1 border-b border-zinc-800 shrink-0 items-center sticky top-0 bg-zinc-900 z-10`}>
              {!hideProjectColumn && (
                <button
                  onClick={() => handleSort("project")}
                  className="col-span-1 text-left hover:text-zinc-400 transition-colors"
                >
                  Proj
                  <SortIcon field="project" currentField={sortField} direction={sortDirection} />
                </button>
              )}
              <div className="col-span-1">#</div>
              <div className={hideProjectColumn ? "col-span-5" : "col-span-4"}>Title</div>
              <button
                onClick={() => handleSort("author")}
                className="col-span-2 text-left hover:text-zinc-400 transition-colors"
              >
                Author
                <SortIcon field="author" currentField={sortField} direction={sortDirection} />
              </button>
              <button
                onClick={() => handleSort("created")}
                className="col-span-1 text-left hover:text-zinc-400 transition-colors"
              >
                Crtd
                <SortIcon field="created" currentField={sortField} direction={sortDirection} />
              </button>
              <button
                onClick={() => handleSort("updated")}
                className="col-span-1 text-left hover:text-zinc-400 transition-colors"
              >
                Updt
                <SortIcon field="updated" currentField={sortField} direction={sortDirection} />
              </button>
              <div className="col-span-1 text-left">
                Status
              </div>
            </div>

              {/* Table rows - scrollable */}
              <div className="flex-1 overflow-y-auto min-h-0 pb-2">
                <div className="space-y-1">
                {sortedMRs.map(mr => {
                  const jiraKey = extractJiraKey(mr.title, mr.branch);
                  return (
                    <ExpandableRow
                      key={`${mr.project}-${mr.iid}`}
                      summary={
                        <div className={`grid ${hideProjectColumn ? 'grid-cols-11' : 'grid-cols-12'} gap-2 text-xs items-center w-full`}>
                          {!hideProjectColumn && (
                            <div className="col-span-1">
                              <ProjectBadge projectKey={mr.project} />
                            </div>
                          )}
                          <div className="col-span-1">
                            <a
                              href={mr.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-zinc-500 font-mono hover:text-emerald-400 transition-colors"
                            >
                              !{mr.iid}
                            </a>
                          </div>
                          <div className={`${hideProjectColumn ? 'col-span-5' : 'col-span-4'} flex items-center gap-1 min-w-0`}>
                            {jiraKey && (
                              <Badge
                                variant="outline"
                                className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-[10px] px-1.5 py-0.5 font-mono hover:bg-cyan-500/20 transition-colors shrink-0"
                              >
                                <a
                                  href={`https://hello.planet.com/jira/browse/${jiraKey}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="hover:text-cyan-300"
                                >
                                  {jiraKey}
                                </a>
                              </Badge>
                            )}
                            <MRTypeBadge title={mr.title} />
                            {mr.is_draft && <DraftBadge />}
                            <span className={`truncate ${mr.is_draft ? 'text-zinc-500' : 'text-zinc-300'}`}>
                              {cleanTitle(mr.title)}
                            </span>
                          </div>
                          <div className="col-span-2 truncate">
                            <span className={mr.is_mine ? 'text-emerald-400' : 'text-zinc-400'}>
                              {mr.author}
                            </span>
                          </div>
                          <div className="col-span-1 text-zinc-500">
                            {formatHoursAgo(mr.age_created_hours)}
                          </div>
                          <div className="col-span-1 text-zinc-500">
                            {formatHoursAgo(mr.age_last_commit_hours)}
                          </div>
                          <div className="col-span-1">
                            <ReviewStatus mr={mr} />
                          </div>
                        </div>
                      }
                    >
                      <MRExpanded
                        project={mr.project}
                        iid={mr.iid}
                        title={mr.title}
                      />
                    </ExpandableRow>
                  );
                })}
                </div>
              </div>
            </div>
          )}
      </ScrollableCard>
  );
}
