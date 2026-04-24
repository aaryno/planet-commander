"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Loader2, ExternalLink, LayoutGrid, PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, JiraTicketResult, Agent } from "@/lib/api";
import { WorkspaceActions } from "./WorkspaceActions";
import { addAgentToAMV } from "@/lib/amv";
import { useToast } from "@/components/ui/toast-simple";
import { ChatInput } from "@/components/agents/ChatInput";
import { ChatView } from "@/components/agents/ChatView";
import { getLabelColor } from "@/lib/label-colors";
import { parseJiraMarkup } from "@/lib/jira-formatting";
import { JIRA_STATUS_COLORS, JIRA_PRIORITY_COLORS } from "@/lib/status-colors";
import { formatTimestampAgo } from "@/lib/time-utils";

interface JiraWorkspaceProps {
  jiraKey: string;
  project?: string;
  onClose: () => void;
  onOpenAgent?: (agent: Agent) => void;
  onBreakoutChat?: (agent: Agent) => void;
}

const formatTimeAgo = formatTimestampAgo;

export function JiraWorkspace({ jiraKey, project, onClose, onOpenAgent, onBreakoutChat }: JiraWorkspaceProps) {
  const toast = useToast();
  const [ticket, setTicket] = useState<JiraTicketResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [descriptionExpanded, setDescriptionExpanded] = useState(true);
  const [worktreePath, setWorktreePath] = useState<string | undefined>(undefined);
  const [gitBranch, setGitBranch] = useState<string | undefined>(undefined);
  const [spawningAgent, setSpawningAgent] = useState(false);
  const [relatedAgents, setRelatedAgents] = useState<Agent[]>([]);
  const [activeTab, setActiveTab] = useState<"ticket" | "chat">("ticket");
  const [activeAgent, setActiveAgent] = useState<Agent | null>(null);

  useEffect(() => {
    // Reset state when jiraKey changes
    setTicket(null);
    setLoading(true);
    setError(null);
    setRelatedAgents([]);
    setActiveAgent(null);
    setActiveTab("ticket");

    // Load ticket details
    api.jiraTicket(jiraKey)
      .then(setTicket)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    // Search for related agents and set active agent
    api.agentsByJira(jiraKey).then((result) => {
      const agents = result.agents || [];
      setRelatedAgents(agents);
      // Pick the most recent non-dead agent, or most recent overall
      const active = agents.find((a) => a.status !== "dead") || agents[0] || null;
      setActiveAgent(active);
    }).catch((err) => {
      console.error("Failed to search for related agents:", err);
    });
  }, [jiraKey]);

  const handleWorktreeCreated = useCallback((path: string, branch: string) => {
    setWorktreePath(path);
    setGitBranch(branch);
  }, []);

  const handleSendMessage = useCallback(async (message: string, model?: string) => {
    if (activeAgent) {
      // Send to existing agent and switch to chat tab
      try {
        await api.agentChat(activeAgent.id, message, model, "sidebar");
        setActiveTab("chat");
      } catch (err) {
        console.error("Failed to send message:", err);
      }
    } else {
      // Spawn new agent
      if (!project) {
        alert("Project is required to spawn an agent");
        return;
      }

      setSpawningAgent(true);
      try {
        await api.agentSpawn({
          project,
          jira_key: jiraKey,
          initial_prompt: message,
          worktree_path: worktreePath || undefined,
          worktree_branch: gitBranch || undefined,
          source: "sidebar",
        });

        // Fetch the newly created agent
        const agentResult = await api.agentsByJira(jiraKey);
        const agents = agentResult.agents || [];
        const newAgent = agents.find((a) => a.status !== "dead") || agents[0] || null;
        if (newAgent) {
          setActiveAgent(newAgent);
          setRelatedAgents(agents);
          setActiveTab("chat");
        }
      } catch (err) {
        alert(`Failed to spawn agent: ${err}`);
      } finally {
        setSpawningAgent(false);
      }
    }
  }, [activeAgent, project, jiraKey, worktreePath, gitBranch]);

  return (
    <div className="bg-zinc-900 rounded-lg border border-zinc-800 flex flex-col h-full overflow-hidden">
      {/* Standardized Header */}
      <div className="flex items-center justify-between gap-2 p-3 border-b border-zinc-800 shrink-0 bg-zinc-900/95">
        {/* Left: Project + JIRA */}
        <div className="flex items-center gap-2">
          {/* Project badge */}
          {project && (
            <Badge
              variant="outline"
              className={`${getLabelColor(project, "project")} border text-[10px] px-1.5 py-0`}
            >
              {project}
            </Badge>
          )}

          {/* JIRA badge */}
          <Badge className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-xs font-mono">
            {jiraKey}
          </Badge>

          {/* External link */}
          <a
            href={`https://hello.planet.com/jira/browse/${jiraKey}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>

          {/* Related chats indicator */}
          {relatedAgents.length > 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-purple-400 border-purple-600/30">
              {relatedAgents.length} chat{relatedAgents.length !== 1 ? "s" : ""}
            </Badge>
          )}
        </div>

        {/* Right: Actions + Breakout + Close */}
        <div className="flex items-center gap-2">
          <WorkspaceActions
            jiraKey={jiraKey}
            project={project}
            worktreePath={worktreePath}
            onWorktreeCreated={handleWorktreeCreated}
          />
          {activeAgent && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[10px] text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
              onClick={() => {
                addAgentToAMV(activeAgent);
                toast.showToast({
                  message: "Agent added to Multi-View",
                  link: { label: "Go to AMV", href: "/multiview" },
                });
              }}
              title="Add to Agent Multi-View"
            >
              <LayoutGrid className="h-3 w-3 mr-1" />
              Open in AMV
            </Button>
          )}
          {activeAgent && onBreakoutChat && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[10px] text-violet-400 hover:text-violet-300 hover:bg-violet-500/10"
              onClick={() => onBreakoutChat(activeAgent)}
              title="Open chat in separate panel"
            >
              <PanelRight className="h-3 w-3 mr-1" />
              Break Out
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-zinc-800 shrink-0">
        <button
          onClick={() => setActiveTab("ticket")}
          className={`px-4 py-2 text-xs font-medium transition-colors ${
            activeTab === "ticket"
              ? "text-zinc-200 border-b-2 border-blue-500"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          Ticket
        </button>
        <button
          onClick={() => setActiveTab("chat")}
          className={`px-4 py-2 text-xs font-medium transition-colors ${
            activeTab === "chat"
              ? "text-zinc-200 border-b-2 border-violet-500"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          Chat {activeAgent ? `(${activeAgent.status})` : ""}
        </button>
      </div>

      {/* Tab content */}
      {activeTab === "ticket" ? (
        <div className="flex-1 overflow-y-auto p-4">
          {loading && (
            <div className="flex items-center gap-2 text-zinc-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Loading ticket...</span>
            </div>
          )}

          {error && (
            <div className="text-sm text-red-400">
              Failed to load ticket: {error}
            </div>
          )}

          {ticket && (
            <div className="space-y-4">
              {/* Title */}
              <h2 className="text-lg font-semibold text-zinc-200">
                {ticket.summary}
              </h2>

              {/* Metadata */}
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={JIRA_STATUS_COLORS[ticket.status] || "bg-zinc-500/20 text-zinc-400 border-zinc-600/50"}>
                  {ticket.status}
                </Badge>
                {ticket.priority && (
                  <span className={`text-xs ${JIRA_PRIORITY_COLORS[ticket.priority] || "text-zinc-400"}`}>
                    {ticket.priority}
                  </span>
                )}
                <span className="text-xs text-zinc-500">
                  {ticket.type}
                </span>
              </div>

              {/* Assignee */}
              <div className="flex items-center gap-2 text-sm">
                <span className="text-zinc-500">Assignee:</span>
                <div className="flex items-center gap-1.5">
                  {ticket.assignee_avatar_url ? (
                    <img
                      src={ticket.assignee_avatar_url}
                      alt={ticket.assignee}
                      className="w-5 h-5 rounded-full"
                    />
                  ) : ticket.assignee !== "Unassigned" ? (
                    <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[10px] text-zinc-400">
                      {ticket.assignee.charAt(0).toUpperCase()}
                    </div>
                  ) : null}
                  <span className="text-zinc-300">{ticket.assignee}</span>
                </div>
              </div>

              {/* Fix Versions */}
              {ticket.fix_versions.length > 0 && (
                <div className="flex items-start gap-2 text-sm">
                  <span className="text-zinc-500">Fix Version:</span>
                  <div className="flex flex-wrap gap-1">
                    {ticket.fix_versions.map((v) => (
                      <Badge key={v} variant="outline" className="text-xs">
                        {v}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Labels */}
              {ticket.labels.length > 0 && (
                <div className="flex items-start gap-2 text-sm">
                  <span className="text-zinc-500">Labels:</span>
                  <div className="flex flex-wrap gap-1">
                    {ticket.labels.map((label) => (
                      <Badge key={label} variant="outline" className="text-xs">
                        {label}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Description */}
              {ticket.description && (
                <div className="border-t border-zinc-800 pt-4">
                  <button
                    onClick={() => setDescriptionExpanded(!descriptionExpanded)}
                    className="text-sm font-medium text-zinc-400 hover:text-zinc-300 mb-2"
                  >
                    Description {descriptionExpanded ? "▼" : "▶"}
                  </button>
                  {descriptionExpanded && (
                    <div className="text-sm text-zinc-300">
                      {parseJiraMarkup(ticket.description)}
                    </div>
                  )}
                </div>
              )}

              {/* Comments */}
              {ticket.comments.length > 0 && (
                <div className="border-t border-zinc-800 pt-4">
                  <h3 className="text-sm font-medium text-zinc-400 mb-3">
                    Comments ({ticket.comments.length})
                  </h3>
                  <div className="space-y-3">
                    {ticket.comments.map((comment) => (
                      <div key={comment.id} className="bg-zinc-800/30 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          {comment.avatar_url && (
                            <img
                              src={comment.avatar_url}
                              alt={comment.author}
                              className="w-5 h-5 rounded-full"
                            />
                          )}
                          <span className="text-xs font-medium text-zinc-300">
                            {comment.author}
                          </span>
                          <span className="text-xs text-zinc-600">
                            {new Date(comment.created).toLocaleDateString()}
                          </span>
                        </div>
                        <div className="text-sm text-zinc-300">
                          {parseJiraMarkup(comment.body)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeAgent ? (
            <ChatView
              agent={activeAgent}
              className="flex-1"
              compact
              hideAMVButton
              source="sidebar"
            />
          ) : (
            <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
              <p>Send a message below to start a chat about {jiraKey}</p>
            </div>
          )}
        </div>
      )}

      {/* Chat input at bottom - always visible */}
      {project && activeTab === "ticket" && (
        <div className="shrink-0 border-t border-zinc-800 p-3 bg-zinc-900/95">
          <ChatInput
            agentStatus={activeAgent?.status || "live"}
            onSend={handleSendMessage}
            disabled={spawningAgent}
          />
        </div>
      )}
    </div>
  );
}
