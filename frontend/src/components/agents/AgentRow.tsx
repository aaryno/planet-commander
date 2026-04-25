"use client";

import { useEffect, useState } from "react";
import { FileText, GitBranch, FolderOpen, MessageSquare, ChevronDown, ChevronRight, EyeOff, Eye, Zap, Hash, ExternalLink, Terminal, LayoutGrid, ShoppingCart, PanelRight, Bot, Ticket } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

interface TitleParts {
  cleanTitle: string;
  hasCommander: boolean;
  commanderText: string;
  jiraKey: string | null;
  jiraText: string;
  mrNumber: string | null;
  mrRepo: string | null;
  mrUrl: string | null;
}

function parseTitle(raw: string): TitleParts {
  let text = raw;
  let hasCommander = false;
  let commanderText = "";
  let jiraKey: string | null = null;
  let jiraText = "";
  let mrNumber: string | null = null;
  let mrRepo: string | null = null;
  let mrUrl: string | null = null;

  // Extract [Commander: ...] block (may be truncated without closing ])
  const cmdMatch = text.match(/\[Commander:([^\]]*)\]?/);
  if (cmdMatch) {
    hasCommander = true;
    commanderText = cmdMatch[0];
    text = text.replace(cmdMatch[0], "").trim();
  }

  // Extract [Context: ... JIRA ticket XXX-NNN ...] (may be truncated)
  const ctxMatch = text.match(/\[Context:([^\]]*)\]?/);
  if (ctxMatch) {
    const keyMatch = ctxMatch[1].match(/([A-Z]+-\d+)/);
    if (keyMatch) {
      jiraKey = keyMatch[1];
      jiraText = ctxMatch[0];
    }
    text = text.replace(ctxMatch[0], "").trim();
  }

  // Extract other context blocks (may be truncated)
  text = text.replace(/\[Project Context:[^\]]*\]?/g, "").trim();
  text = text.replace(/\[JIRA Ticket:[^\]]*\]?/g, (m) => {
    const km = m.match(/([A-Z]+-\d+)/);
    if (km && !jiraKey) { jiraKey = km[1]; jiraText = m; }
    return "";
  }).trim();
  text = text.replace(/\[MR Context:[^\]]*\]?/g, "").trim();
  text = text.replace(/\[Slack Context:[^\]]*\]?/g, "").trim();

  // Extract JIRA key from clean text (e.g. "Fix COMPUTE-1234 bug")
  if (!jiraKey) {
    const jm = text.match(/\b([A-Z]{2,}-\d+)\b/);
    if (jm) jiraKey = jm[1];
  }

  // Extract MR reference (e.g. "!779" or "MR !779")
  const mrMatch = text.match(/!(\d+)/);
  if (mrMatch) {
    mrNumber = mrMatch[1];
  }

  // Extract repo from title patterns like "review product/avatarg4-deploy Merge requests !779"
  // or "Review MR !123 in wx/wx"
  const repoPatterns = [
    /review\s+([\w-]+\/[\w-]+)\s+/i,
    /in\s+([\w-]+\/[\w-]+)/i,
    /([\w-]+\/[\w-]+)\s+(?:Merge|MR|merge)/i,
  ];
  for (const pat of repoPatterns) {
    const rm = text.match(pat);
    if (rm) {
      mrRepo = rm[1];
      break;
    }
  }

  // Also check working_directory patterns for repo
  // (handled in the component since we need agent data)

  if (mrRepo && mrNumber) {
    mrUrl = `https://hello.planet.com/code/${mrRepo}/-/merge_requests/${mrNumber}`;
  }

  // Collapse whitespace
  text = text.replace(/\s+/g, " ").trim();

  if (!text) text = "(agent)";
  if (text.length > 120) text = text.slice(0, 117) + "...";
  return { cleanTitle: text, hasCommander, commanderText, jiraKey, jiraText, mrNumber, mrRepo, mrUrl };
}

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

  const rawParts = parseTitle(agent.title || "");
  const titleParts = rawParts.cleanTitle === "(agent)" && agent.first_prompt
    ? parseTitle(agent.first_prompt)
    : rawParts;

  const summaryContent = (
    <div className={`group ${agent.hidden_at ? "opacity-50" : ""}`}>
      {/* Top row: status, title, time, chat button */}
      <div className="flex items-start gap-3">
        <AgentStatusBadge status={agent.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            {titleParts.hasCommander && (
              <span className="shrink-0" title={titleParts.commanderText}>
                <Badge variant="outline" className="text-[9px] px-1 py-0 border-cyan-700/50 bg-cyan-500/5 text-cyan-500 cursor-help">
                  <Bot className="h-2.5 w-2.5 mr-0.5" />cmd
                </Badge>
              </span>
            )}
            {titleParts.jiraKey && (
              <a
                href={`https://hello.planet.com/jira/browse/${titleParts.jiraKey}`}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0"
                title={titleParts.jiraText || titleParts.jiraKey}
                onClick={e => e.stopPropagation()}
              >
                <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-700/50 bg-amber-500/5 text-amber-500 cursor-pointer hover:bg-amber-500/10">
                  <Ticket className="h-2.5 w-2.5 mr-0.5" />{titleParts.jiraKey}
                </Badge>
              </a>
            )}
            {titleParts.mrNumber && (
              <a
                href={titleParts.mrUrl || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0"
                title={titleParts.mrRepo ? `${titleParts.mrRepo} !${titleParts.mrNumber}` : `MR !${titleParts.mrNumber}`}
                onClick={e => e.stopPropagation()}
              >
                <Badge variant="outline" className="text-[9px] px-1 py-0 border-violet-700/50 bg-violet-500/5 text-violet-400 cursor-pointer hover:bg-violet-500/10">
                  <GitBranch className="h-2.5 w-2.5 mr-0.5" />!{titleParts.mrNumber}
                </Badge>
              </a>
            )}
            {titleParts.mrRepo && (
              <span className="shrink-0">
                <Badge variant="outline" className="text-[9px] px-1 py-0 border-zinc-700/50 bg-zinc-500/5 text-zinc-400">
                  {titleParts.mrRepo}
                </Badge>
              </span>
            )}
            <p className="text-sm text-zinc-200 truncate font-medium">
              {titleParts.cleanTitle}
            </p>
          </div>
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
          {/* Files changed badges */}
          {agent.files_changed && Object.keys(agent.files_changed).length > 0 && (() => {
            const files = Object.entries(agent.files_changed);
            const maxShow = 2;
            return (
              <div className="flex flex-wrap gap-1 mt-1">
                {files.length <= maxShow ? (
                  files.map(([path, action]) => (
                    <Badge
                      key={path}
                      variant="outline"
                      className={`text-[10px] px-1.5 py-0 gap-1 max-w-[200px] ${
                        action === "created"
                          ? "text-emerald-400 border-emerald-600/50 bg-emerald-500/5"
                          : "text-blue-400 border-blue-600/50 bg-blue-500/5"
                      }`}
                      title={`${action}: ${path}`}
                    >
                      <FileText className="h-2.5 w-2.5 shrink-0" />
                      <span className="truncate">{path.split("/").pop()}</span>
                    </Badge>
                  ))
                ) : (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="inline-flex items-center gap-1 rounded-md border border-emerald-600/50 bg-emerald-500/5 text-emerald-400 text-[10px] px-1.5 py-0.5 hover:bg-emerald-500/10 transition-colors">
                        <FileText className="h-2.5 w-2.5" />
                        {files.length} files changed
                        <ChevronDown className="h-2.5 w-2.5" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="bg-zinc-900 border-zinc-700 max-w-sm max-h-64 overflow-y-auto">
                      {files.map(([path, action]) => (
                        <DropdownMenuItem key={path} className="text-zinc-300 text-xs focus:bg-zinc-800">
                          <FileText className={`h-3 w-3 mr-2 shrink-0 ${action === "created" ? "text-emerald-400" : "text-blue-400"}`} />
                          <span className="truncate">{path.split("/").pop()}</span>
                          <span className="text-zinc-600 ml-auto text-[10px] shrink-0">{action}</span>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            );
          })()}
          {/* MR reference badges */}
          {agent.mr_references && agent.mr_references.length > 0 && (() => {
            const mrs = agent.mr_references;
            const maxShow = 2;
            return (
              <div className="flex flex-wrap gap-1 mt-1">
                {mrs.length <= maxShow ? (
                  mrs.map((mr) => (
                    <a
                      key={`${mr.repo}!${mr.iid}`}
                      href={mr.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                    >
                      <Badge
                        variant="outline"
                        className="text-[10px] px-1.5 py-0 gap-1 text-violet-400 border-violet-600/50 bg-violet-500/5 cursor-pointer hover:bg-violet-500/10"
                        title={`${mr.repo} !${mr.iid}`}
                      >
                        <GitBranch className="h-2.5 w-2.5 shrink-0" />
                        !{mr.iid}
                      </Badge>
                    </a>
                  ))
                ) : (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        className="inline-flex items-center gap-1 rounded-md border border-violet-600/50 bg-violet-500/5 text-violet-400 text-[10px] px-1.5 py-0.5 hover:bg-violet-500/10 transition-colors"
                        onClick={e => e.stopPropagation()}
                      >
                        <GitBranch className="h-2.5 w-2.5" />
                        {mrs.length} MRs
                        <ChevronDown className="h-2.5 w-2.5" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="bg-zinc-900 border-zinc-700 max-w-sm max-h-64 overflow-y-auto">
                      {mrs.map((mr) => (
                        <DropdownMenuItem
                          key={`${mr.repo}!${mr.iid}`}
                          asChild
                          className="text-zinc-300 text-xs focus:bg-zinc-800"
                        >
                          <a href={mr.url} target="_blank" rel="noopener noreferrer">
                            <GitBranch className="h-3 w-3 text-violet-400 mr-2 shrink-0" />
                            <span className="truncate">{mr.repo}</span>
                            <span className="text-violet-400 ml-auto shrink-0">!{mr.iid}</span>
                          </a>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            );
          })()}
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
