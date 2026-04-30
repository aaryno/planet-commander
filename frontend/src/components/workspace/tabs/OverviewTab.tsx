"use client";

import { FileText, MessageSquare, GitBranch, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { WorkspaceDetail, Agent } from "@/lib/api";
import type { TabId } from "../WorkspaceTabs";
import { jiraUrl } from "@/lib/urls";

interface OverviewTabProps {
  workspace: WorkspaceDetail;
  onUpdate?: (workspace: WorkspaceDetail) => void;
  onOpenAgent?: (agent: Agent) => void;
  onTabChange?: (tab: TabId) => void;
}

export function OverviewTab({ workspace, onOpenAgent, onTabChange }: OverviewTabProps) {
  const primaryTicket = workspace.jira_tickets.find(t => t.is_primary);
  const relatedTickets = workspace.jira_tickets.filter(t => !t.is_primary);
  const activeBranch = workspace.branches.find(b => b.is_active);
  const pinnedAgents = workspace.agents.filter(a => a.is_pinned);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        {/* Primary JIRA Ticket */}
        {primaryTicket && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-cyan-400" />
              <h3 className="text-sm font-medium text-zinc-300">Primary Ticket</h3>
            </div>
            <div
              className="bg-cyan-500/5 border border-cyan-700/50 rounded-lg p-3 cursor-pointer hover:bg-cyan-500/10 transition-colors"
              onClick={() => onTabChange?.("jira")}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-xs font-mono">
                    {primaryTicket.key}
                  </Badge>
                  <a
                    href={jiraUrl(primaryTicket.key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-zinc-500 hover:text-zinc-300 transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
                <span className="text-xs text-zinc-500">Click to view all tickets</span>
              </div>
            </div>
          </div>
        )}

        {/* Related Tickets */}
        {relatedTickets.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-zinc-400" />
              <h3 className="text-sm font-medium text-zinc-300">Related Tickets</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {relatedTickets.length}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {relatedTickets.map((ticket) => (
                <Badge
                  key={ticket.key}
                  variant="outline"
                  className="text-xs font-mono cursor-pointer hover:bg-zinc-800"
                  onClick={() => onTabChange?.("jira")}
                >
                  {ticket.key}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Active Agents */}
        {pinnedAgents.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare className="h-4 w-4 text-purple-400" />
              <h3 className="text-sm font-medium text-zinc-300">Active Chats</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {pinnedAgents.length}
              </Badge>
            </div>
            <div className="space-y-2">
              {pinnedAgents.slice(0, 3).map((agent) => (
                <div
                  key={agent.id}
                  className="bg-zinc-800/30 rounded p-2 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                  onClick={() => onTabChange?.("chats")}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Badge
                        variant="outline"
                        className={`text-[10px] px-1.5 py-0 shrink-0 ${
                          agent.status === "live"
                            ? "text-emerald-400 border-emerald-600/50"
                            : agent.status === "idle"
                            ? "text-blue-400 border-blue-600/50"
                            : "text-zinc-500 border-zinc-600/50"
                        }`}
                      >
                        {agent.status}
                      </Badge>
                      <span className="text-xs text-zinc-300 truncate">
                        {agent.title || agent.first_prompt?.slice(0, 50) || "Untitled"}
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-500 shrink-0">{agent.message_count} msgs</span>
                  </div>
                </div>
              ))}
              {pinnedAgents.length > 3 && (
                <button
                  onClick={() => onTabChange?.("chats")}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  +{pinnedAgents.length - 3} more chats
                </button>
              )}
            </div>
          </div>
        )}

        {/* Active Branch */}
        {activeBranch && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-green-400" />
              <h3 className="text-sm font-medium text-zinc-300">Active Branch</h3>
            </div>
            <div
              className="bg-green-500/5 border border-green-700/50 rounded-lg p-3 cursor-pointer hover:bg-green-500/10 transition-colors"
              onClick={() => onTabChange?.("code")}
            >
              <div className="flex items-center justify-between">
                <code className="text-xs text-green-400 font-mono">{activeBranch.name}</code>
                {activeBranch.worktree_path && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-zinc-500">
                    worktree
                  </Badge>
                )}
              </div>
            </div>
          </div>
        )}

        {/* All Branches */}
        {workspace.branches.length > 0 && !activeBranch && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-green-400" />
              <h3 className="text-sm font-medium text-zinc-300">Branches</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {workspace.branches.length}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {workspace.branches.map((branch) => (
                <Badge
                  key={branch.name}
                  variant="outline"
                  className="text-xs font-mono cursor-pointer hover:bg-zinc-800"
                  onClick={() => onTabChange?.("code")}
                >
                  {branch.name.split("/").pop()}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Open MRs */}
        {workspace.merge_requests.filter(mr => mr.status === "open").length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-blue-400" />
              <h3 className="text-sm font-medium text-zinc-300">Open MRs</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {workspace.merge_requests.filter(mr => mr.status === "open").length}
              </Badge>
            </div>
            <div className="space-y-2">
              {workspace.merge_requests
                .filter(mr => mr.status === "open")
                .map((mr) => (
                  <div
                    key={`${mr.project}-${mr.iid}`}
                    className="bg-blue-500/5 border border-blue-700/50 rounded p-2 cursor-pointer hover:bg-blue-500/10 transition-colors"
                    onClick={() => {
                      if (mr.url) window.open(mr.url, "_blank");
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-blue-400 font-mono">!{mr.iid}</span>
                      <code className="text-xs text-zinc-400">{mr.branch_name.split("/").pop()}</code>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Deployments */}
        {workspace.deployments.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-amber-400" />
              <h3 className="text-sm font-medium text-zinc-300">Deployments</h3>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {workspace.deployments.length}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              {workspace.deployments.map((dep) => (
                <Badge
                  key={`${dep.environment}-${dep.namespace}`}
                  variant="outline"
                  className="text-xs cursor-pointer hover:bg-zinc-800"
                  onClick={() => onTabChange?.("deployments")}
                >
                  {dep.environment}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {workspace.jira_tickets.length === 0 &&
          workspace.agents.length === 0 &&
          workspace.branches.length === 0 &&
          workspace.deployments.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-zinc-500">No resources in this workspace yet</p>
              <p className="text-xs text-zinc-600 mt-1">Add JIRA tickets, agents, or branches to get started</p>
            </div>
          )}
      </div>
    </div>
  );
}
