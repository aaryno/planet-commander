import { useState, useCallback, useMemo } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { ArtifactCard } from "./ArtifactCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, Search, RefreshCw, Filter } from "lucide-react";
import type { InvestigationArtifact } from "@/lib/api";

interface ArtifactSectionProps {
  contextId?: string;
  jiraKey?: string;
  project?: string;
  title?: string;
  emptyMessage?: string;
  allowFilters?: boolean;
}

export function ArtifactSection({
  contextId,
  jiraKey,
  project,
  title = "Related Artifacts",
  emptyMessage = "No artifacts found",
  allowFilters = true,
}: ArtifactSectionProps) {
  const [keywordFilter, setKeywordFilter] = useState("");
  const [projectFilter, setProjectFilter] = useState(project || "");
  const [typeFilter, setTypeFilter] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const fetcher = useCallback(() => {
    if (contextId) {
      return api.contextArtifacts(contextId);
    } else if (jiraKey) {
      return api.searchArtifacts(jiraKey);
    } else {
      // Use list endpoint with filters
      return api.artifacts(
        projectFilter || undefined,
        typeFilter || undefined,
        keywordFilter || undefined,
        50
      );
    }
  }, [contextId, jiraKey, projectFilter, typeFilter, keywordFilter]);

  const { data: artifacts, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  // Local filtering for additional keyword search
  const filteredArtifacts = useMemo(() => {
    if (!artifacts) return [];
    if (!keywordFilter && !contextId && !jiraKey) return artifacts;

    return artifacts.filter((a) => {
      if (!keywordFilter) return true;
      const searchText = `${a.title} ${a.description} ${a.keywords.join(" ")}`.toLowerCase();
      return searchText.includes(keywordFilter.toLowerCase());
    });
  }, [artifacts, keywordFilter, contextId, jiraKey]);

  // Get unique projects and types for filter dropdowns
  const uniqueProjects = useMemo(() => {
    if (!artifacts) return [];
    const projects = new Set(
      artifacts.map((a) => a.project).filter((p): p is string => Boolean(p))
    );
    return Array.from(projects).sort();
  }, [artifacts]);

  const uniqueTypes = useMemo(() => {
    if (!artifacts) return [];
    const types = new Set(
      artifacts.map((a) => a.artifact_type).filter((t): t is string => Boolean(t))
    );
    return Array.from(types).sort();
  }, [artifacts]);

  const stickyHeader = (
    <div className="space-y-2">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Filter by keywords..."
          value={keywordFilter}
          onChange={(e) => setKeywordFilter(e.target.value)}
          className="pl-8"
        />
      </div>

      {/* Filters Toggle and Stats */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {filteredArtifacts?.length || 0} artifact{filteredArtifacts?.length !== 1 ? "s" : ""}
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
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800">
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

          {/* Type Filter */}
          <div>
            <label className="text-xs text-zinc-500 mb-1 block">Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
            >
              <option value="">All types</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Active Filters */}
      {(projectFilter || typeFilter || keywordFilter) && (
        <div className="flex items-center gap-1 flex-wrap pt-1">
          {projectFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setProjectFilter("")}
            >
              Project: {projectFilter} ×
            </Badge>
          )}
          {typeFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setTypeFilter("")}
            >
              Type: {typeFilter} ×
            </Badge>
          )}
          {keywordFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setKeywordFilter("")}
            >
              Keywords: {keywordFilter} ×
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setProjectFilter("");
              setTypeFilter("");
              setKeywordFilter("");
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
      icon={<FileText className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading artifacts...</p>}
      {error && <p className="text-xs text-red-400">Error loading artifacts</p>}
      {!loading && filteredArtifacts && filteredArtifacts.length === 0 && (
        <p className="text-xs text-zinc-500">{emptyMessage}</p>
      )}
      {filteredArtifacts && filteredArtifacts.length > 0 && (
        <div className="space-y-2">
          {filteredArtifacts.map((artifact) => (
            <ArtifactCard key={artifact.id} artifact={artifact} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
