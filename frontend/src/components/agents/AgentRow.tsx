"use client";

import { useEffect, useState } from "react";
import { GitBranch, FolderOpen, MessageSquare, ChevronDown, ChevronRight, EyeOff, Eye, Zap, Hash, ExternalLink, Terminal, LayoutGrid, ShoppingCart, PanelRight } from "lucide-react";
import { ExpandableRow } from "@/components/shared/ExpandableRow";
import { AgentExpanded } from "@/components/expanded/AgentExpanded";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getLabelColor } from "@/lib/label-colors";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { useSettings } from "@/hooks/useSettings";
import { addAgentToAMV } from "@/lib/amv";
import { useToast } from "@/components/ui/toast-simple";
import { useCart } from "@/lib/cart";
import { JIRA_STATUS_COLORS } from "@/lib/status-colors";

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function getDefaultTerminalCommand(app: string): string {
  const commands: Record<string, string> = {
    ghostty: "open -a Ghostty {path}",
    iterm2: "open -a iTerm {path}",
    terminal: "open -a Terminal {path}",
    warp: "open -a Warp {path}",
    kitty: "open -a Kitty {path}",
  };
  return commands[app] || "";
}

function formatTokens(n: number): string {
  if (n === 0) return "0";
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}K`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

export function AgentRow({
  agent,
  onAgentClick,
  onHide,
  onUnhide,
}: {
  agent: Agent;
  onAgentClick?: (agent: Agent) => void;
  onHide?: (id: string) => void;
  onUnhide?: (id: string) => void;
}) {
  const { settings } = useSettings();
  const toast = useToast();
  const { addItem: addToCart, removeItem: removeFromCart, isInCart } = useCart();
  const [artifactsExpanded, setArtifactsExpanded] = useState(false);
  const [jiraStatus, setJiraStatus] = useState<string | null>(null);
  const [jiraLoading, setJiraLoading] = useState(false);
  const [terminalLaunching, setTerminalLaunching] = useState(false);

  // Lazy-load JIRA ticket status
  useEffect(() => {
    if (!agent.jira_key) return;
    setJiraLoading(true);
    api.jiraTicket(agent.jira_key)
      .then((t) => setJiraStatus(t.status))
      .catch(() => setJiraStatus(null))
      .finally(() => setJiraLoading(false));
  }, [agent.jira_key]);

  const handleLaunchTerminal = async () => {
    const path = agent.worktree_path || agent.working_directory;
    if (!path) {
      alert("No working directory or worktree path available for this agent");
      return;
    }

    const command = settings.terminal.customCommand || getDefaultTerminalCommand(settings.terminal.app);
    if (!command) {
      alert("Terminal command not configured. Please go to Settings to configure your terminal.");
      return;
    }

    setTerminalLaunching(true);
    try {
      await api.launchTerminal(path, command);
    } catch (error) {
      alert(`Failed to launch terminal: ${error}`);
    } finally {
      setTerminalLaunching(false);
    }
  };

  const summaryContent = (
    <div className={`group ${agent.hidden_at ? "opacity-50" : ""}`}>
      {/* Top row: status, title, time, chat button */}
      <div className="flex items-start gap-3">
        <AgentStatusBadge status={agent.status} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-zinc-200 truncate font-medium">
            {agent.title}
          </p>
          {/* Labels */}
          {agent.labels.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {agent.labels.map((l) => (
                <Badge
                  key={l.name}
                  variant="outline"
                  className={`${getLabelColor(l.name, l.category)} border text-[10px] px-1.5 py-0`}
                >
                  {l.name}
                </Badge>
              ))}
            </div>
          )}
          {/* Project badge + source badge */}
          <div className="flex flex-wrap gap-1 mt-1">
            {agent.labels.length === 0 && agent.project && (
              <Badge
                variant="outline"
                className={`${getLabelColor(agent.project, "project")} border text-[10px] px-1.5 py-0`}
              >
                {agent.project}
              </Badge>
            )}
            <Badge
              variant="outline"
              className={`border text-[10px] px-1.5 py-0 ${
                agent.managed_by === "dashboard"
                  ? "text-cyan-400 border-cyan-600/50 bg-cyan-500/5"
                  : "text-violet-400 border-violet-600/50 bg-violet-500/5"
              }`}
            >
              {agent.managed_by === "dashboard" ? "dashboard" : "vscode"}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {onAgentClick && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-blue-400/0 group-hover:text-blue-400/60 hover:!text-blue-400 hover:bg-blue-500/10 transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onAgentClick(agent);
              }}
              title="Open in sidebar"
            >
              <PanelRight className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className={`h-7 w-7 p-0 transition-colors ${
              isInCart(agent.id)
                ? "text-cyan-400"
                : "text-cyan-400/0 group-hover:text-cyan-400/60 hover:!text-cyan-400 hover:bg-cyan-500/10"
            }`}
            onClick={(e) => {
              e.stopPropagation();
              if (isInCart(agent.id)) {
                removeFromCart(agent.id);
              } else {
                addToCart(agent);
                toast.showToast({ message: "Added to Context Cart" });
              }
            }}
            title={isInCart(agent.id) ? "Remove from Cart" : "Add to Context Cart"}
          >
            <ShoppingCart className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-amber-400/0 group-hover:text-amber-400 hover:!text-amber-300 hover:bg-amber-500/10 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              addAgentToAMV(agent);
              toast.showToast({
                message: "Agent added to Multi-View",
                link: { label: "Go to AMV", href: "/multiview" },
              });
            }}
            title="Add to Agent Multi-View"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
          </Button>
          <span className="text-xs text-zinc-500">{timeAgo(agent.last_active_at)}</span>
          {agent.hidden_at ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-zinc-600 hover:text-zinc-300"
              onClick={(e) => {
                e.stopPropagation();
                onUnhide?.(agent.id);
              }}
              title="Unhide agent"
            >
              <Eye className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 text-zinc-600 hover:text-zinc-400"
              onClick={(e) => {
                e.stopPropagation();
                onHide?.(agent.id);
              }}
              title="Hide agent"
            >
              <EyeOff className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Metadata row: branch, worktree, message count */}
      <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
        {agent.git_branch && (
          <span className="flex items-center gap-1 truncate max-w-[250px]">
            <GitBranch className="h-3 w-3 shrink-0" />
            {agent.git_branch}
          </span>
        )}
        {agent.worktree_path && (
          <span className="flex items-center gap-1 truncate max-w-[200px]">
            <FolderOpen className="h-3 w-3 shrink-0" />
            {agent.worktree_path.replace(/^\/Users\/aaryn\//, "~/")}
          </span>
        )}
        <span className="flex items-center gap-1">
          <MessageSquare className="h-3 w-3" />
          {agent.message_count} msgs
        </span>
        {agent.total_tokens > 0 && (
          <span className="flex items-center gap-1" title={`${agent.total_tokens.toLocaleString()} tokens`}>
            <Zap className="h-3 w-3" />
            {formatTokens(agent.total_tokens)}
          </span>
        )}
        {agent.num_prompts > 0 && (
          <span className="flex items-center gap-1" title={`${agent.num_prompts} prompts`}>
            <Hash className="h-3 w-3" />
            {agent.num_prompts} prompts
          </span>
        )}
        {agent.jira_key && (
          <a
            href={`https://hello.planet.com/jira/browse/${agent.jira_key}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1"
            onClick={(e) => e.stopPropagation()}
          >
            <Badge
              variant="outline"
              className="text-cyan-400 border-cyan-600/50 bg-cyan-500/10 text-[10px] px-1.5 py-0.5 hover:bg-cyan-500/20 transition-colors"
            >
              {agent.jira_key}
            </Badge>
            {jiraLoading ? (
              <span className="text-[9px] text-zinc-600">...</span>
            ) : jiraStatus ? (
              <Badge
                variant="outline"
                className={`text-[9px] px-1 py-0 ${JIRA_STATUS_COLORS[jiraStatus] || "text-zinc-400 border-zinc-600/50 bg-zinc-500/10"}`}
              >
                {jiraStatus}
              </Badge>
            ) : null}
          </a>
        )}
        {agent.artifacts.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setArtifactsExpanded(!artifactsExpanded);
            }}
            className="flex items-center gap-0.5 hover:text-zinc-300 transition-colors"
          >
            {artifactsExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {agent.artifacts.length} artifacts
          </button>
        )}
      </div>

      {/* Expanded artifacts */}
      {artifactsExpanded && agent.artifacts.length > 0 && (
        <div className="mt-2 pl-4 border-l border-zinc-800 space-y-1">
          {agent.artifacts.map((a, i) => (
            <div key={i} className="text-xs text-zinc-500">
              <span className="text-zinc-600">{a.type}:</span> {a.path}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <ExpandableRow summary={summaryContent}>
      <AgentExpanded
        agent={agent}
        onJoinChat={onAgentClick ? () => onAgentClick(agent) : undefined}
        onSummarize={undefined}
      />
    </ExpandableRow>
  );
}
