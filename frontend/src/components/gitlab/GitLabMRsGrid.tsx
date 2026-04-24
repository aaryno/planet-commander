import { useState, useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { GitLabMRCard } from "./GitLabMRCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GitMerge, Search, RefreshCw } from "lucide-react";

export function GitLabMRsGrid() {
  const [searchQuery, setSearchQuery] = useState("");
  const [repositoryFilter, setRepositoryFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("opened");
  const [authorFilter, setAuthorFilter] = useState("");

  const fetcher = useCallback(() => {
    if (searchQuery) {
      return api.gitlabMRSearch(
        searchQuery,
        repositoryFilter || undefined,
        stateFilter || undefined,
        100
      );
    }
    return api.gitlabMRs(
      repositoryFilter || undefined,
      stateFilter || undefined,
      authorFilter || undefined,
      undefined,
      100
    );
  }, [searchQuery, repositoryFilter, stateFilter, authorFilter]);

  const { data, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Search merge requests..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      {/* Stats and Filters */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {data?.total || 0} MR{data?.total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Repository</label>
          <select
            value={repositoryFilter}
            onChange={(e) => setRepositoryFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All repos</option>
            <option value="wx/wx">WX</option>
            <option value="product/g4-wk/g4">G4</option>
            <option value="jobs/jobs">Jobs</option>
            <option value="temporal/temporalio-cloud">Temporal</option>
            <option value="eso/eso-golang">ESO</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">State</label>
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All states</option>
            <option value="opened">Opened</option>
            <option value="merged">Merged</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Author</label>
          <Input
            placeholder="username"
            value={authorFilter}
            onChange={(e) => setAuthorFilter(e.target.value)}
            className="text-xs h-7"
          />
        </div>
      </div>

      {/* Active Filters */}
      {(repositoryFilter || stateFilter || searchQuery || authorFilter) && (
        <div className="flex items-center gap-1 flex-wrap pt-1">
          {repositoryFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setRepositoryFilter("")}
            >
              Repo: {repositoryFilter.split("/").pop()} ×
            </Badge>
          )}
          {stateFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setStateFilter("")}
            >
              State: {stateFilter} ×
            </Badge>
          )}
          {authorFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setAuthorFilter("")}
            >
              Author: {authorFilter} ×
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
              setRepositoryFilter("");
              setStateFilter("");
              setAuthorFilter("");
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
    {
      label: "Scan MRs",
      onClick: async () => {
        await api.gitlabMRScan();
        refresh();
      },
      icon: <Search className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title="GitLab Merge Requests"
      icon={<GitMerge className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading merge requests...</p>}
      {error && <p className="text-xs text-red-400">Error loading merge requests</p>}
      {!loading && data && data.mrs.length === 0 && (
        <p className="text-xs text-zinc-500">No merge requests found</p>
      )}
      {data && data.mrs.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {data.mrs.map((mr) => (
            <GitLabMRCard key={mr.id} mr={mr} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
