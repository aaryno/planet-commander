"use client";

import { useState, useCallback } from "react";
import { Plus, MessageSquare, Pin, PinOff, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceDetail, Agent } from "@/lib/api";
import { api } from "@/lib/api";
import { formatTimestampAgo } from "@/lib/time-utils";

interface ChatsTabProps {
  workspace: WorkspaceDetail;
  onUpdate?: (workspace: WorkspaceDetail) => void;
  onOpenAgent?: (agent: Agent) => void;
}

export function ChatsTab({ workspace, onUpdate, onOpenAgent }: ChatsTabProps) {
  const [filter, setFilter] = useState<string | null>(null);

  const handleRemoveAgent = useCallback(async (agentId: string) => {
    try {
      await api.workspaceRemoveAgent(workspace.id, agentId);
      // Reload workspace
      const updated = await api.workspaceGet(workspace.id);
      onUpdate?.(updated);
    } catch (error) {
      console.error("Failed to remove agent:", error);
      alert("Failed to remove agent");
    }
  }, [workspace.id, onUpdate]);

  const handleTogglePin = useCallback(async (agentId: string, isPinned: boolean) => {
    try {
      const updated = await api.workspaceUpdateAgent(workspace.id, agentId, {
        is_pinned: !isPinned,
      });
      onUpdate?.(updated);
    } catch (error) {
      console.error("Failed to toggle pin:", error);
    }
  }, [workspace.id, onUpdate]);

  const formatTimeAgo = formatTimestampAgo;
  const filteredAgents = filter
    ? workspace.agents.filter(a => {
        // TODO: Filter by linked JIRA keys when we have that data
        return true;
      })
    : workspace.agents;

  const pinnedAgents = filteredAgents.filter(a => a.is_pinned);
  const unpinnedAgents = filteredAgents.filter(a => !a.is_pinned);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        {/* Filters */}
        {workspace.jira_tickets.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-zinc-500">Filter by ticket:</span>
            <Button
              variant={filter === null ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter(null)}
              className="h-6 px-2 text-xs"
            >
              All
            </Button>
            {workspace.jira_tickets.map((ticket) => (
              <Button
                key={ticket.key}
                variant={filter === ticket.key ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(ticket.key)}
                className="h-6 px-2 text-xs font-mono"
              >
                {ticket.key}
              </Button>
            ))}
          </div>
        )}

        {/* Pinned Agents */}
        {pinnedAgents.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Pin className="h-4 w-4 text-purple-400" />
              <h3 className="text-sm font-medium text-zinc-300">Pinned Chats</h3>
            </div>
            <div className="space-y-2">
              {pinnedAgents.map((agent) => (
                <div
                  key={agent.id}
                  className="bg-purple-500/5 border border-purple-700/50 rounded-lg p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge
                          variant="outline"
                          className={`text-[10px] px-1.5 py-0 ${
                            agent.status === "live"
                              ? "text-emerald-400 border-emerald-600/50"
                              : agent.status === "idle"
                              ? "text-blue-400 border-blue-600/50"
                              : "text-zinc-500 border-zinc-600/50"
                          }`}
                        >
                          {agent.status}
                        </Badge>
                        {agent.session_id && (
                          <span className="text-[10px] text-zinc-600 font-mono">{agent.session_id.slice(0, 8)}</span>
                        )}
                      </div>
                      <p className="text-sm text-zinc-300 truncate">
                        {agent.title || agent.first_prompt || "Untitled chat"}
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                        <span>{agent.message_count} messages</span>
                        {agent.last_active_at && (
                          <span>{formatTimeAgo(agent.last_active_at)}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-purple-400 hover:text-purple-300"
                        onClick={() => handleTogglePin(agent.id, agent.is_pinned)}
                      >
                        <PinOff className="h-3.5 w-3.5" />
                      </Button>
                      {onOpenAgent && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-zinc-400 hover:text-zinc-200"
                          onClick={() => {
                            // TODO: Convert agent reference to full Agent object
                            // For now, we'll need to fetch the full agent data
                            console.log("Open agent:", agent.id);
                          }}
                        >
                          <MessageSquare className="h-3.5 w-3.5 mr-1" />
                          Open
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
                        onClick={() => handleRemoveAgent(agent.id)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Unpinned Agents */}
        {unpinnedAgents.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare className="h-4 w-4 text-zinc-500" />
              <h3 className="text-sm font-medium text-zinc-300">Other Chats</h3>
            </div>
            <div className="space-y-2">
              {unpinnedAgents.map((agent) => (
                <div
                  key={agent.id}
                  className="bg-zinc-800/30 rounded-lg p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge
                          variant="outline"
                          className={`text-[10px] px-1.5 py-0 ${
                            agent.status === "live"
                              ? "text-emerald-400 border-emerald-600/50"
                              : agent.status === "idle"
                              ? "text-blue-400 border-blue-600/50"
                              : "text-zinc-500 border-zinc-600/50"
                          }`}
                        >
                          {agent.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-zinc-300 truncate">
                        {agent.title || agent.first_prompt || "Untitled chat"}
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                        <span>{agent.message_count} messages</span>
                        {agent.last_active_at && (
                          <span>{formatTimeAgo(agent.last_active_at)}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
                        onClick={() => handleTogglePin(agent.id, agent.is_pinned)}
                      >
                        <Pin className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
                        onClick={() => handleRemoveAgent(agent.id)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {workspace.agents.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500">No chats in this workspace</p>
            <p className="text-xs text-zinc-600 mt-1">Agents will be automatically discovered from JIRA tickets</p>
          </div>
        )}
      </div>
    </div>
  );
}
