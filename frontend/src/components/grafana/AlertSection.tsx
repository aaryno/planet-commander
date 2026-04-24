import { useState, useCallback, useMemo } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { AlertDefinitionCard } from "./AlertDefinitionCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Search, RefreshCw, Filter } from "lucide-react";

interface AlertSectionProps {
  team?: string;
  project?: string;
  title?: string;
  emptyMessage?: string;
  allowFilters?: boolean;
}

export function AlertSection({
  team,
  project,
  title = "Alert Definitions",
  emptyMessage = "No alerts found",
  allowFilters = true,
}: AlertSectionProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [teamFilter, setTeamFilter] = useState(team || "");
  const [projectFilter, setProjectFilter] = useState(project || "");
  const [severityFilter, setSeverityFilter] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const fetcher = useCallback(() => {
    if (searchQuery) {
      return api.searchAlertDefinitions(searchQuery, teamFilter || undefined, projectFilter || undefined, 50);
    }
    return api.alertDefinitions(teamFilter || undefined, projectFilter || undefined, severityFilter || undefined, 100);
  }, [searchQuery, teamFilter, projectFilter, severityFilter]);

  const { data: alerts, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  // Get unique teams, projects, severities for filter dropdowns
  const uniqueTeams = useMemo(() => {
    if (!alerts) return [];
    const teams = new Set(
      alerts.map((a) => a.team).filter((t): t is string => Boolean(t))
    );
    return Array.from(teams).sort();
  }, [alerts]);

  const uniqueProjects = useMemo(() => {
    if (!alerts) return [];
    const projects = new Set(
      alerts.map((a) => a.project).filter((p): p is string => Boolean(p))
    );
    return Array.from(projects).sort();
  }, [alerts]);

  const uniqueSeverities = useMemo(() => {
    if (!alerts) return [];
    const severities = new Set(
      alerts.map((a) => a.severity).filter((s): s is string => Boolean(s))
    );
    return Array.from(severities).sort();
  }, [alerts]);

  const stickyHeader = (
    <div className="space-y-2">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Search alerts..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      {/* Filters Toggle and Stats */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {alerts?.length || 0} alert{alerts?.length !== 1 ? "s" : ""}
        </span>
        {allowFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            className="h-6 text-xs"
          >
            <Filter className="w-3 h-3 mr-1" />
            Filters
          </Button>
        )}
      </div>

      {/* Filter Controls */}
      {allowFilters && showFilters && (
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-800">
          {/* Team Filter */}
          <div>
            <label className="text-xs text-zinc-500 mb-1 block">Team</label>
            <select
              value={teamFilter}
              onChange={(e) => setTeamFilter(e.target.value)}
              className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
            >
              <option value="">All teams</option>
              {uniqueTeams.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Project Filter */}
          <div>
            <label className="text-xs text-zinc-500 mb-1 block">Project</label>
            <select
              value={projectFilter}
              onChange={(e) => setProjectFilter(e.target.value)}
              className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
            >
              <option value="">All projects</option>
              {uniqueProjects.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Severity Filter */}
          <div>
            <label className="text-xs text-zinc-500 mb-1 block">Severity</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
            >
              <option value="">All severities</option>
              {uniqueSeverities.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Active Filters */}
      {(teamFilter || projectFilter || severityFilter || searchQuery) && (
        <div className="flex items-center gap-1 flex-wrap pt-1">
          {teamFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setTeamFilter("")}
            >
              Team: {teamFilter} ×
            </Badge>
          )}
          {projectFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setProjectFilter("")}
            >
              Project: {projectFilter} ×
            </Badge>
          )}
          {severityFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setSeverityFilter("")}
            >
              Severity: {severityFilter} ×
            </Badge>
          )}
          {searchQuery && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setSearchQuery("")}
            >
              Search: {searchQuery} ×
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setTeamFilter("");
              setProjectFilter("");
              setSeverityFilter("");
              setSearchQuery("");
            }}
            className="h-5 text-xs"
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  );

  const menuItems = [
    {
      label: "Refresh",
      onClick: refresh,
      icon: <RefreshCw className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title={title}
      icon={<AlertTriangle className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading alerts...</p>}
      {error && <p className="text-xs text-red-400">Error loading alerts</p>}
      {!loading && alerts && alerts.length === 0 && (
        <p className="text-xs text-zinc-500">{emptyMessage}</p>
      )}
      {alerts && alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <AlertDefinitionCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
