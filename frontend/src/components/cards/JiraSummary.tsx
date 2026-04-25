"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { CheckSquare, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { JiraTicketCard } from "@/components/jira/JiraTicketCard";
import { ExpandableRow } from "@/components/shared/ExpandableRow";
import { JiraTicketExpanded } from "@/components/expanded/JiraTicketExpanded";
import { usePoll } from "@/lib/polling";
import { api, JiraSummaryResponse, JiraTicketEnhanced } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { useUrlParam, useUrlArrayParam } from "@/lib/use-url-state";

type AssigneeFilter = "all" | "me" | string; // "all", "me", or team key

// Team definitions for assignee filtering
const TEAMS: Record<string, { label: string; members: string[] }> = {
  compute: {
    label: "Compute",
    members: [
      "Aaryn Olsson", "Justin Smalkowski", "Chad Bohannan",
      "Ryan Cleere", "Dharma Bellamkonda", "Agata Kargol",
    ],
  },
  dnd: {
    label: "DnD",
    members: ["Jacob Straszynski", "Michael Marriott"],
  },
};

// Internal team labels used to filter COMPUTE tickets in summary view
const LABEL_FILTERS = [
  { key: "all", label: "All" },
  { key: "wx", label: "WX" },
  { key: "temporal", label: "Temporal" },
  { key: "g4", label: "G4" },
  { key: "jobs", label: "Jobs" },
  { key: "cost", label: "Cost" },
  { key: "infra", label: "Infra" },
  { key: "security", label: "Security" },
  { key: "dx", label: "DX" },
  { key: "observability", label: "Observability" },
];

// JIRA projects available for search (multiselect)
const JIRA_PROJECTS = [
  { key: "COMPUTE", label: "Compute" },
  { key: "PLTFRMOPS", label: "PlatformOps" },
  { key: "PE", label: "PE" },
  { key: "CORPENG", label: "CorpEng" },
  { key: "DND", label: "DnD" },
  { key: "AN", label: "AN" },
  { key: "CP", label: "CP" },
  { key: "CSS", label: "CSS" },
];

const STATUS_FILTERS = [
  { key: "backlog", label: "Backlog", color: "text-zinc-400 border-zinc-600/40 bg-zinc-500/5" },          // Backlog (lightest)
  { key: "selected", label: "Selected", color: "text-blue-200 border-blue-400/30 bg-blue-400/5" },        // Lightest
  { key: "in_progress", label: "In Progress", color: "text-blue-300 border-blue-500/40 bg-blue-500/10" },  // Light
  { key: "in_review", label: "In Review", color: "text-blue-400 border-blue-500/50 bg-blue-500/15" },     // Medium
  { key: "ready_to_deploy", label: "Ready to Deploy", color: "text-blue-500 border-blue-600/60 bg-blue-500/20" }, // Medium-dark
  { key: "monitoring", label: "Monitoring", color: "text-blue-600 border-blue-600/70 bg-blue-500/25" },   // Dark
  { key: "done", label: "Done", color: "text-emerald-500 border-emerald-600/70 bg-emerald-500/20" },      // Done (green)
];

const DEFAULT_STATUSES = ["selected", "in_progress", "in_review", "ready_to_deploy", "monitoring"];

interface JiraSummaryProps {
  hideProjectFilter?: boolean;
  onTicketClick?: (jiraKey: string) => void;
  /** URL param prefix to avoid collisions when used on multiple pages */
  urlPrefix?: string;
  /** Override default JIRA project keys (from project config) */
  jiraProjectKeys?: string[];
}

type SortField = "key" | "summary" | "status" | "assignee" | "age";
type SortDirection = "asc" | "desc";

export function JiraSummary({ hideProjectFilter = false, onTicketClick, urlPrefix = "jira", jiraProjectKeys }: JiraSummaryProps) {
  const p = urlPrefix ? `${urlPrefix}.` : "";
  const defaultKeys = jiraProjectKeys && jiraProjectKeys.length > 0 ? jiraProjectKeys : ["COMPUTE"];
  const [assigneeFilter, setAssigneeFilter] = useUrlParam(`${p}assignee`, "all") as [AssigneeFilter, (v: string) => void];
  const [selectedLabel, setSelectedLabel] = useUrlParam(`${p}label`, "all");
  const [selectedStatuses, setSelectedStatuses] = useUrlArrayParam(`${p}statuses`, DEFAULT_STATUSES);
  const [searchQuery, setSearchQuery] = useState("");
  const [jiraProjects, setJiraProjects] = useUrlArrayParam(`${p}projects`, defaultKeys);
  const [showProjectFilter, setShowProjectFilter] = useState(false);
  const [sortField, setSortField] = useUrlParam(`${p}sort`, "age") as [SortField, (v: string) => void];
  const [sortDirection, setSortDirection] = useUrlParam(`${p}sortDir`, "asc") as [SortDirection, (v: string) => void];
  const [searchResults, setSearchResults] = useState<JiraTicketEnhanced[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const fetcher = useCallback(() => {
    // Pass first selected JIRA project to summary endpoint
    const project = jiraProjects.length > 0 ? jiraProjects[0] : undefined;
    return api.jiraSummary(project);
  }, [jiraProjects]);

  const { data, loading, error, refresh } = usePoll<JiraSummaryResponse>(
    fetcher,
    300_000 // 5 minutes
  );

  // Client-side search of already-loaded tickets
  const localSearchResults = useMemo(() => {
    if (!searchQuery.trim() || !data) return [];
    const q = searchQuery.trim().toLowerCase();

    // Collect all loaded tickets (me + team)
    const allTickets: JiraTicketEnhanced[] = [
      ...data.me.assigned,
      ...data.me.watching,
      ...data.me.paired,
      ...data.me.mr_reviewed,
      ...data.me.slack_discussed,
      ...data.team.by_status.backlog,
      ...data.team.by_status.selected,
      ...data.team.by_status.in_progress,
      ...data.team.by_status.in_review,
      ...data.team.by_status.ready_to_deploy,
      ...data.team.by_status.monitoring,
      ...data.team.by_status.done,
    ];

    // Deduplicate by key
    const seen = new Set<string>();
    const unique = allTickets.filter(t => {
      if (seen.has(t.key)) return false;
      seen.add(t.key);
      return true;
    });

    // Search across key, summary, labels, assignee, status
    return unique.filter(t =>
      t.key.toLowerCase().includes(q) ||
      t.summary.toLowerCase().includes(q) ||
      t.assignee.toLowerCase().includes(q) ||
      t.status.toLowerCase().includes(q) ||
      (t.labels || []).some(l => l.toLowerCase().includes(q))
    );
  }, [searchQuery, data]);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    try {
      // If query looks like a ticket key (e.g. PLTFRMOPS-2775), search all projects
      const isTicketKey = /^[A-Za-z]+-\d+$/.test(searchQuery.trim());
      const projectFilter = isTicketKey ? undefined : (jiraProjects.length > 0 ? jiraProjects : undefined);
      const result = await api.jiraSearch(searchQuery, projectFilter);

      // Convert search results to enhanced format
      const apiResults: JiraTicketEnhanced[] = result.tickets.map(t => ({
        ...t,
        my_relationships: {
          assigned: false,
          watching: false,
          paired: false,
          mr_reviewed: false,
          slack_discussed: false,
        },
        linked_mrs: [],
        slack_mentions: [],
        age_days: 0,
        last_updated: "",
      }));

      // Merge local + API results, preferring local (has relationship data)
      const localKeys = new Set(localSearchResults.map(t => t.key));
      const apiOnly = apiResults.filter(t => !localKeys.has(t.key));
      setSearchResults([...localSearchResults, ...apiOnly]);
    } catch (err) {
      console.error("Search failed:", err);
      // On API failure, still show local results
      setSearchResults(localSearchResults);
    } finally {
      setIsSearching(false);
    }
  }, [searchQuery, jiraProjects, localSearchResults]);

  // Auto-search backend (local DB + JIRA API fallback) when local results are empty
  useEffect(() => {
    const q = searchQuery.trim();
    if (!q || q.length < 2) return;
    if (localSearchResults.length > 0 || searchResults.length > 0 || isSearching) return;
    // Debounce to avoid firing on every keystroke
    const timer = setTimeout(() => handleSearch(), 300);
    return () => clearTimeout(timer);
  }, [searchQuery, localSearchResults.length, searchResults.length, isSearching, handleSearch]);

  const handleClearSearch = useCallback(() => {
    setSearchQuery("");
    setSearchResults([]);
  }, []);

  const handleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  }, [sortField, sortDirection, setSortField, setSortDirection]);

  const sortedSearchResults = useMemo(() => {
    const source = searchResults.length > 0 ? searchResults : localSearchResults;
    if (source.length === 0) return [];

    return [...source].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case "key":
          comparison = a.key.localeCompare(b.key);
          break;
        case "summary":
          comparison = a.summary.localeCompare(b.summary);
          break;
        case "status":
          comparison = a.status.localeCompare(b.status);
          break;
        case "assignee":
          comparison = a.assignee.localeCompare(b.assignee);
          break;
        case "age":
          comparison = a.age_days - b.age_days;
          break;
      }

      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [searchResults, localSearchResults, sortField, sortDirection]);

  // Combined ticket filter (label + assignee)
  const ticketFilter = useCallback((ticket: JiraTicketEnhanced) => {
    // Label filter
    if (selectedLabel !== "all") {
      if (!(ticket.labels || []).some(l => l.toLowerCase() === selectedLabel)) return false;
    }
    // Assignee filter
    if (assigneeFilter === "all") return true;
    if (assigneeFilter === "me") return ticket.assignee === "Aaryn Olsson";
    // Team filter
    const team = TEAMS[assigneeFilter];
    if (team) return team.members.includes(ticket.assignee);
    return true;
  }, [selectedLabel, assigneeFilter]);

  // Apply filters to data
  const filteredData = useMemo(() => {
    if (!data) return data;
    const f = ticketFilter;
    const filterStatus = (tickets: JiraTicketEnhanced[]) => tickets.filter(f);
    return {
      ...data,
      me: {
        assigned: filterStatus(data.me.assigned),
        watching: filterStatus(data.me.watching),
        paired: filterStatus(data.me.paired),
        mr_reviewed: filterStatus(data.me.mr_reviewed),
        slack_discussed: filterStatus(data.me.slack_discussed),
      },
      team: {
        ...data.team,
        by_status: {
          backlog: filterStatus(data.team.by_status.backlog),
          selected: filterStatus(data.team.by_status.selected),
          in_progress: filterStatus(data.team.by_status.in_progress),
          in_review: filterStatus(data.team.by_status.in_review),
          ready_to_deploy: filterStatus(data.team.by_status.ready_to_deploy),
          monitoring: filterStatus(data.team.by_status.monitoring),
          done: filterStatus(data.team.by_status.done),
        },
        stats: {
          backlog_count: filterStatus(data.team.by_status.backlog).length,
          selected_count: filterStatus(data.team.by_status.selected).length,
          in_progress_count: filterStatus(data.team.by_status.in_progress).length,
          in_review_count: filterStatus(data.team.by_status.in_review).length,
          ready_to_deploy_count: filterStatus(data.team.by_status.ready_to_deploy).length,
          monitoring_count: filterStatus(data.team.by_status.monitoring).length,
          done_count: filterStatus(data.team.by_status.done).length,
        },
      },
    };
  }, [data, ticketFilter]);

  const teamCounts = useMemo(() => {
    if (!filteredData) return { total: 0 };
    return {
      total: filteredData.team.stats.backlog_count + filteredData.team.stats.selected_count + filteredData.team.stats.in_progress_count + filteredData.team.stats.in_review_count + filteredData.team.stats.ready_to_deploy_count + filteredData.team.stats.monitoring_count,
    };
  }, [filteredData]);

  const toggleStatus = (statusKey: string) => {
    setSelectedStatuses(
      selectedStatuses.includes(statusKey)
        ? selectedStatuses.filter(s => s !== statusKey)
        : [...selectedStatuses, statusKey]
    );
  };

  const toggleAllStatuses = () => {
    if (selectedStatuses.length === 0) {
      // If none selected, select all
      setSelectedStatuses(STATUS_FILTERS.map(s => s.key));
    } else {
      // If any selected, deselect all
      setSelectedStatuses([]);
    }
  };

  const toggleAllLabels = () => {
    if (selectedLabel === "all") {
      setSelectedLabel(LABEL_FILTERS[1].key); // Skip "all", go to "wx"
    } else {
      setSelectedLabel("all");
    }
  };

  const assigneeLabel = assigneeFilter === "all" ? "All" : assigneeFilter === "me" ? "Me" : TEAMS[assigneeFilter]?.label ?? assigneeFilter;

  const displayedResults = sortedSearchResults;
  const showSearchResults = searchQuery.trim().length > 0;

  // Sticky filters section
  const stickyHeader = (
    <div className="space-y-2">
        {/* Search bar */}
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
              if (e.key === "Escape") handleClearSearch();
            }}
            placeholder="Search JIRA tickets... (Enter to search, Esc to clear)"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {showSearchResults && (
            <button
              onClick={handleClearSearch}
              className="text-xs text-zinc-500 hover:text-zinc-300 px-2 transition-colors"
            >
              Clear
            </button>
          )}
        </div>

        {/* JIRA Project filter (collapsible, collapsed by default) */}
        <div className="flex gap-3">
          <button
            onClick={() => setShowProjectFilter(!showProjectFilter)}
            className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors flex items-center gap-1"
          >
            Project
            {showProjectFilter ? <ChevronUp className="h-2.5 w-2.5" /> : <ChevronDown className="h-2.5 w-2.5" />}
          </button>
          {!showProjectFilter && (
            <span className="text-[10px] text-zinc-600">{jiraProjects.join(", ")}</span>
          )}
        </div>
        {showProjectFilter && (
          <div className="flex gap-3">
            <span className="w-20 shrink-0" />
            <div className="flex items-center gap-1.5 flex-wrap">
              {JIRA_PROJECTS.map(proj => (
                <button
                  key={proj.key}
                  onClick={() => {
                    setJiraProjects(
                      jiraProjects.includes(proj.key)
                        ? jiraProjects.filter(p => p !== proj.key)
                        : [...jiraProjects, proj.key]
                    );
                  }}
                  className={`${
                    jiraProjects.includes(proj.key)
                      ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                      : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                  } text-[10px] font-medium px-2 py-0.5 rounded transition-colors hover:opacity-80`}
                >
                  {proj.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Assignee filter - hide during search */}
        {!showSearchResults && (
        <div className="flex gap-3">
          <button
            onClick={() => setAssigneeFilter("all")}
            className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors"
          >
            Assignee
          </button>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setAssigneeFilter("all")}
              className={`${
                assigneeFilter === "all"
                  ? "bg-zinc-500/20 text-zinc-300 border border-zinc-600/50"
                  : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
              } text-[10px] font-medium px-2.5 py-0.5 rounded-full transition-colors hover:opacity-80`}
            >
              All
            </button>
            <button
              onClick={() => setAssigneeFilter("me")}
              className={`${
                assigneeFilter === "me"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-600/50"
                  : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
              } text-[10px] font-medium px-2.5 py-0.5 rounded-full transition-colors hover:opacity-80`}
            >
              Me
            </button>
            {Object.entries(TEAMS).map(([key, team]) => (
              <button
                key={key}
                onClick={() => setAssigneeFilter(assigneeFilter === key ? "all" : key)}
                className={`${
                  assigneeFilter === key
                    ? "bg-blue-500/20 text-blue-400 border border-blue-600/50"
                    : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                } text-[10px] font-medium px-2.5 py-0.5 rounded-full transition-colors hover:opacity-80`}
              >
                {team.label}
              </button>
            ))}
          </div>
        </div>
        )}

        {/* Label filter (wx, g4, jobs, temporal) */}
        {!showSearchResults && !hideProjectFilter && (
          <div className="flex gap-3">
            <button
              onClick={toggleAllLabels}
              className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors"
            >
              Label
            </button>
            <div className="flex items-center gap-2 flex-wrap">
              {LABEL_FILTERS.map(lf => (
                <button
                  key={lf.key}
                  onClick={() => setSelectedLabel(lf.key)}
                  className={`${
                    selectedLabel === lf.key
                      ? "bg-zinc-500/20 text-zinc-300 border border-zinc-600/50"
                      : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                  } text-[10px] font-medium px-2 py-1 rounded transition-colors hover:opacity-80`}
                >
                  {lf.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Status filter */}
        {!showSearchResults && (
          <div className="flex gap-3">
            <button
              onClick={toggleAllStatuses}
              className="text-[10px] text-zinc-500 font-medium uppercase w-20 text-left hover:text-zinc-300 transition-colors"
            >
              Status
            </button>
            <div className="flex items-center gap-2 flex-wrap">
              {STATUS_FILTERS.map(status => (
                <button
                  key={status.key}
                  onClick={() => toggleStatus(status.key)}
                  className={`${
                    selectedStatuses.includes(status.key)
                      ? status.color
                      : "bg-zinc-500/10 text-zinc-500 border border-zinc-600/30"
                  } text-[10px] font-medium px-2.5 py-0.5 rounded-full transition-colors hover:opacity-80`}
                >
                  {status.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
  );

  return (
    <ScrollableCard
      title={`JIRA${filteredData ? ` (${teamCounts.total} ${assigneeLabel})` : ""}`}
      icon={<CheckSquare className="h-4 w-4" />}
      menuItems={[{ label: "Refresh", onClick: refresh }]}
      stickyHeader={stickyHeader}
    >
      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-2 text-zinc-400 py-4">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-xs">Loading JIRA tickets...</span>
        </div>
      )}

      {/* Error state */}
      {error && <p className="text-xs text-red-400">Failed to load JIRA data</p>}

      {/* Search Results */}
      {showSearchResults && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-300">
              Search Results ({displayedResults.length})
            </h3>
            {isSearching && (
              <Loader2 className="h-3 w-3 animate-spin text-zinc-500" />
            )}
          </div>

          {displayedResults.length === 0 && !isSearching && (
            <p className="text-xs text-zinc-500">No results found. Press Enter to search JIRA API.</p>
          )}

          {displayedResults.length > 0 && (
            <div>
              {/* Table header */}
              <div className="grid grid-cols-12 gap-2 text-[10px] text-zinc-600 font-medium pb-1 border-b border-zinc-800 mb-2">
                <button
                  onClick={() => handleSort("key")}
                  className="col-span-2 text-left hover:text-zinc-400 transition-colors flex items-center gap-1"
                >
                  Key
                  {sortField === "key" && (sortDirection === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
                <button
                  onClick={() => handleSort("summary")}
                  className="col-span-4 text-left hover:text-zinc-400 transition-colors flex items-center gap-1"
                >
                  Summary
                  {sortField === "summary" && (sortDirection === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
                <button
                  onClick={() => handleSort("status")}
                  className="col-span-2 text-left hover:text-zinc-400 transition-colors flex items-center gap-1"
                >
                  Status
                  {sortField === "status" && (sortDirection === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
                <button
                  onClick={() => handleSort("assignee")}
                  className="col-span-2 text-left hover:text-zinc-400 transition-colors flex items-center gap-1"
                >
                  Assignee
                  {sortField === "assignee" && (sortDirection === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
                <button
                  onClick={() => handleSort("age")}
                  className="col-span-2 text-left hover:text-zinc-400 transition-colors flex items-center gap-1"
                >
                  Age
                  {sortField === "age" && (sortDirection === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
              </div>

              {/* Results */}
              <div className="space-y-1">
                {displayedResults.map(ticket => (
                  <ExpandableRow
                    key={ticket.key}
                    summary={<JiraTicketCard ticket={ticket} compact />}
                  >
                    <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                  </ExpandableRow>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {!showSearchResults && filteredData && (
        <div className="space-y-4">
          {/* By Status Section */}
          <div className="space-y-3">
                {/* Backlog */}
                {selectedStatuses.includes("backlog") && filteredData.team.by_status.backlog.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        Backlog
                      </h4>
                      <Badge className="bg-zinc-600/20 text-zinc-400 border-zinc-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.backlog_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.backlog.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* Selected for Development */}
                {selectedStatuses.includes("selected") && filteredData.team.by_status.selected.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        Selected for Development
                      </h4>
                      <Badge className="bg-zinc-600/20 text-zinc-400 border-zinc-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.selected_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.selected.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* In Progress */}
                {selectedStatuses.includes("in_progress") && filteredData.team.by_status.in_progress.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        In Progress
                      </h4>
                      <Badge className="bg-blue-600/20 text-blue-400 border-blue-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.in_progress_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.in_progress.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* In Review */}
                {selectedStatuses.includes("in_review") && filteredData.team.by_status.in_review.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        In Review
                      </h4>
                      <Badge className="bg-purple-600/20 text-purple-400 border-purple-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.in_review_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.in_review.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ready to Deploy */}
                {selectedStatuses.includes("ready_to_deploy") && filteredData.team.by_status.ready_to_deploy.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        Ready to Deploy
                      </h4>
                      <Badge className="bg-amber-600/20 text-amber-400 border-amber-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.ready_to_deploy_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.ready_to_deploy.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* Monitoring */}
                {selectedStatuses.includes("monitoring") && filteredData.team.by_status.monitoring.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        Monitoring
                      </h4>
                      <Badge className="bg-cyan-600/20 text-cyan-400 border-cyan-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.monitoring_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.monitoring.map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                    </div>
                  </div>
                )}

                {/* Done */}
                {selectedStatuses.includes("done") && filteredData.team.by_status.done.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <h4 className="text-xs font-medium text-zinc-400">
                        Done
                      </h4>
                      <Badge className="bg-emerald-600/20 text-emerald-400 border-emerald-600/30 text-[10px] px-1.5 py-0">
                        {filteredData.team.stats.done_count}
                      </Badge>
                    </div>
                    <div className="space-y-1">
                      {filteredData.team.by_status.done.slice(0, 5).map(ticket => (
                        <ExpandableRow
                          key={ticket.key}
                          summary={<JiraTicketCard ticket={ticket} compact />}
                        >
                          <JiraTicketExpanded jiraKey={ticket.key} onOpenInSidebar={onTicketClick} />
                        </ExpandableRow>
                      ))}
                      {filteredData.team.by_status.done.length > 5 && (
                        <p className="text-[10px] text-zinc-600 pl-2">
                          +{filteredData.team.by_status.done.length - 5} more
                        </p>
                      )}
                    </div>
                  </div>
                )}
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
