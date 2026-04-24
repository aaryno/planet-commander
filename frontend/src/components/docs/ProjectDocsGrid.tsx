import { useState, useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { ProjectDocCard } from "./ProjectDocCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Search, RefreshCw, Filter, AlertTriangle } from "lucide-react";

export function ProjectDocsGrid() {
  const [searchQuery, setSearchQuery] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [staleOnly, setStaleOnly] = useState(false);

  const fetcher = useCallback(() => {
    if (searchQuery) {
      return api.searchProjectDocs(searchQuery, undefined, teamFilter || undefined, 50);
    }
    return api.projectDocs(teamFilter || undefined, staleOnly, 50);
  }, [searchQuery, teamFilter, staleOnly]);

  const { data: docs, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Search project docs..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      {/* Stats and Filters */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {docs?.length || 0} project{docs?.length !== 1 ? "s" : ""}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant={staleOnly ? "default" : "ghost"}
            size="sm"
            onClick={() => setStaleOnly(!staleOnly)}
            className="h-6 text-xs"
          >
            <AlertTriangle className="w-3 h-3 mr-1" />
            Stale only
          </Button>
        </div>
      </div>

      {/* Team Filter */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Team</label>
          <select
            value={teamFilter}
            onChange={(e) => setTeamFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All teams</option>
            <option value="compute">compute</option>
            <option value="datapipeline">datapipeline</option>
            <option value="hobbes">hobbes</option>
          </select>
        </div>
      </div>

      {/* Active Filters */}
      {(teamFilter || searchQuery || staleOnly) && (
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
          {searchQuery && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setSearchQuery("")}
            >
              Search: {searchQuery} ×
            </Badge>
          )}
          {staleOnly && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setStaleOnly(false)}
            >
              Stale only ×
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setTeamFilter("");
              setSearchQuery("");
              setStaleOnly(false);
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
    {
      label: "Scan Docs",
      onClick: async () => {
        await api.scanProjectDocs();
        refresh();
      },
      icon: <Search className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title="Project Documentation"
      icon={<BookOpen className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading project docs...</p>}
      {error && <p className="text-xs text-red-400">Error loading project docs</p>}
      {!loading && docs && docs.length === 0 && (
        <p className="text-xs text-zinc-500">No project documentation found</p>
      )}
      {docs && docs.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {docs.map((doc) => (
            <ProjectDocCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
