"use client";

import { useCallback, useState } from "react";
import { Bot, RefreshCw, Search, X } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import { AgentRow } from "./AgentRow";

interface ProjectAgentsProps {
  project?: string; // undefined = all agents
  onAgentClick?: (agent: Agent) => void;
  onHide?: (id: string) => void;
  onUnhide?: (id: string) => void;
}

export function ProjectAgents({ project, onAgentClick, onHide, onUnhide }: ProjectAgentsProps) {
  const [search, setSearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetcher = useCallback(
    () => api.agents(project),
    [project],
  );

  const { data, loading, error, refresh } = usePoll(fetcher, 30000);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refresh();
    setTimeout(() => setRefreshing(false), 500); // Show feedback for at least 500ms
  };

  const allAgents = data?.agents ?? [];
  const total = data?.total ?? 0;

  // Filter agents by search
  const agents = search
    ? allAgents.filter(
        (a: Agent) =>
          a.title.toLowerCase().includes(search.toLowerCase()) ||
          (a.git_branch && a.git_branch.toLowerCase().includes(search.toLowerCase())) ||
          (a.first_prompt && a.first_prompt.toLowerCase().includes(search.toLowerCase())) ||
          (a.jira_key && a.jira_key.toLowerCase().includes(search.toLowerCase()))
      )
    : allAgents;

  // Sticky header content (search and filters)
  const stickyHeader = (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-500" />
        <Input
          placeholder="Search agents, branches, JIRA keys..."
          className="pl-9 pr-8 h-8 bg-zinc-800 border-zinc-700 text-sm text-zinc-200 placeholder:text-zinc-500"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors"
            title="Clear search"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Count and refresh */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-500">
          {agents.length} / {total} agent{total !== 1 ? "s" : ""}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-zinc-500 hover:text-zinc-300"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`h-3 w-3 mr-1 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing..." : "Refresh"}
        </Button>
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title="Agents"
      icon={<Bot className="h-4 w-4" />}
      stickyHeader={stickyHeader}
    >
      {/* Loading state */}
      {loading && agents.length === 0 && (
        <div className="flex items-center justify-center gap-2 text-zinc-500 py-8">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span className="text-sm">Loading agents...</span>
        </div>
      )}

      {/* Error state */}
      {error && agents.length === 0 && (
        <p className="text-sm text-red-400 text-center py-8">
          Failed to load agents: {error.message}
        </p>
      )}

      {/* Empty state */}
      {allAgents.length === 0 && !loading && !error && (
        <div className="flex flex-col items-center justify-center gap-2 py-8">
          <Bot className="h-8 w-8 text-zinc-700" />
          <p className="text-sm text-zinc-500">No agents found.</p>
          <p className="text-xs text-zinc-600">
            Run agent sync to discover sessions.
          </p>
        </div>
      )}

      {/* No search results */}
      {agents.length === 0 && search && allAgents.length > 0 && (
        <p className="text-sm text-zinc-500 text-center py-8">
          No agents match "{search}"
        </p>
      )}

      {/* Agent list */}
      {agents.length > 0 && (
        <div className="space-y-2">
          {agents.map((agent: Agent) => (
            <AgentRow
              key={agent.id}
              agent={agent}
              onAgentClick={onAgentClick}
              onHide={onHide}
              onUnhide={onUnhide}
            />
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
