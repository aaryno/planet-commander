import { useState, useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { GoogleDriveDocCard } from "./GoogleDriveDocCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FileText, Search, RefreshCw, AlertTriangle } from "lucide-react";

export function GoogleDriveDocsGrid() {
  const [searchQuery, setSearchQuery] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [staleOnly, setStaleOnly] = useState(false);

  const fetcher = useCallback(() => {
    if (searchQuery) {
      return api.googleDriveSearch(
        searchQuery,
        undefined,
        kindFilter || undefined,
        projectFilter || undefined,
        50
      );
    }
    // For listing, we use the documents endpoint with filters
    return api
      .googleDriveDocuments(
        undefined,
        kindFilter || undefined,
        projectFilter || undefined,
        100
      )
      .then((response) => {
        // Client-side stale filter if needed
        if (staleOnly) {
          return {
            documents: response.documents.filter((doc) => doc.is_stale),
            total: response.documents.filter((doc) => doc.is_stale).length,
          };
        }
        return response;
      });
  }, [searchQuery, projectFilter, kindFilter, staleOnly]);

  const { data, loading, error, refresh } = usePoll(fetcher, 600_000); // 10 min

  const stickyHeader = (
    <div className="space-y-3">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2 top-2 h-4 w-4 text-zinc-500" />
        <Input
          placeholder="Search Google Drive docs..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      {/* Stats and Filters */}
      <div className="flex justify-between items-center text-xs">
        <span className="text-zinc-500">
          {data?.total || 0} document{data?.total !== 1 ? "s" : ""}
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

      {/* Filters */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Project</label>
          <select
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All projects</option>
            <option value="wx">WorkExchange</option>
            <option value="jobs">Jobs</option>
            <option value="g4">G4</option>
            <option value="temporal">Temporal</option>
            <option value="eso">ESO</option>
            <option value="fusion">Fusion/Tardis</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">Document Type</label>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
            className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-zinc-200"
          >
            <option value="">All types</option>
            <option value="postmortem">Postmortems</option>
            <option value="rfd">RFDs/RFCs</option>
            <option value="meeting-notes">Meeting Notes</option>
            <option value="on-call-log">On-Call Logs</option>
          </select>
        </div>
      </div>

      {/* Active Filters */}
      {(projectFilter || kindFilter || searchQuery || staleOnly) && (
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
          {kindFilter && (
            <Badge
              variant="outline"
              className="text-xs cursor-pointer"
              onClick={() => setKindFilter("")}
            >
              Type: {kindFilter} ×
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
              setProjectFilter("");
              setKindFilter("");
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
      label: "Scan Drive",
      onClick: async () => {
        await api.googleDriveScan();
        refresh();
      },
      icon: <Search className="w-3 h-3" />,
    },
  ];

  return (
    <ScrollableCard
      title="Google Drive Documents"
      icon={<FileText className="w-5 h-5" />}
      menuItems={menuItems}
      stickyHeader={stickyHeader}
    >
      {loading && <p className="text-xs text-zinc-500">Loading documents...</p>}
      {error && <p className="text-xs text-red-400">Error loading documents</p>}
      {!loading && data && data.documents.length === 0 && (
        <p className="text-xs text-zinc-500">No documents found</p>
      )}
      {data && data.documents.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          {data.documents.map((doc) => (
            <GoogleDriveDocCard key={doc.id} doc={doc} />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
