"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, ArrowUpToLine, ChevronDown, ChevronRight, ChevronsDown, ChevronsUp, ExternalLink, EyeOff, FileText, LayoutGrid, Loader2, Link as LinkIcon, Paperclip, ShoppingCart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getLabelColor } from "@/lib/label-colors";
import type { Agent, AgentSummary, ChatMessage as ChatMessageType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { JiraCard } from "./JiraCard";
import { useAgentChat, type PermissionDenialEvent } from "@/hooks/useAgentChat";
import { PermissionDialog } from "./PermissionDialog";
import { addAgentToAMV } from "@/lib/amv";
import { parseTitle } from "@/lib/parse-title";
import { Bot, Ticket } from "lucide-react";
import { useCart } from "@/lib/cart";
import { useToast } from "@/components/ui/toast-simple";
import { RepoProvider, resolveGitLabProject } from "@/lib/repo-context";
import type { RepoInfo } from "@/lib/repo-context";
import { ArtifactModal } from "./ArtifactModal";
import Link from "next/link";

interface ChatViewProps {
  agent: Agent;
  /** Render a header action slot (e.g. close button, breakout link) */
  headerActions?: React.ReactNode;
  /** Additional CSS classes for the outer container */
  className?: string;
  /** Callback to hide this agent */
  onHide?: (id: string) => void;
  /** Hide the "Add to AMV" button (when already inside AMV) */
  hideAMVButton?: boolean;
  /** Compact mode — hide the header (used when embedded in MRAgentPane which has its own header) */
  compact?: boolean;
  /** UI source context — injected into messages so the agent knows its environment */
  source?: "sidebar" | "amv" | "mr-review" | "agents";
}

export function ChatView({ agent, headerActions, className = "", onHide, hideAMVButton, compact, source }: ChatViewProps) {
  const [historicalMessages, setHistoricalMessages] = useState<ChatMessageType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Track whether this agent is dashboard-managed (can chat) or VS Code-managed (read-only)
  const [dashboardManaged, setDashboardManaged] = useState(agent.managed_by === "dashboard");
  const [localStatus, setLocalStatus] = useState(agent.status);
  const [resuming, setResuming] = useState(false);
  const [summary, setSummary] = useState<AgentSummary | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryLevel, setSummaryLevel] = useState<"phrase" | "short" | "detailed">("phrase");
  const [extracting, setExtracting] = useState(false);
  const { addItem: addToCart, removeItem: removeFromCart, isInCart } = useCart();
  const [extractResult, setExtractResult] = useState<{ urls_found: number; links_created: number } | null>(null);
  const [messageQueue, setMessageQueue] = useState<string[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const [slackQueueCount, setSlackQueueCount] = useState(0);
  const [viewingArtifact, setViewingArtifact] = useState<string | null>(null);
  const [pendingDenial, setPendingDenial] = useState<PermissionDenialEvent | null>(null);
  const [artifactsDropdownOpen, setArtifactsDropdownOpen] = useState(false);
  const toast = useToast();

  // Message type filters
  const [showUser, setShowUser] = useState(true);
  const [showAssistant, setShowAssistant] = useState(true);
  const [showToolOutput, setShowToolOutput] = useState(false);
  const [showThinking, setShowThinking] = useState(false);

  // JIRA card state - auto-open if agent has JIRA key
  const [showJiraCard, setShowJiraCard] = useState(!!agent.jira_key);

  // Message collapse state - track by index
  const [collapsedMessages, setCollapsedMessages] = useState<Set<number>>(new Set());
  const [allCollapsed, setAllCollapsed] = useState(false);

  // Pinned state - JIRA card pinned by default if auto-opened
  const [jiraPinned, setJiraPinned] = useState(!!agent.jira_key);
  const [pinnedMessages, setPinnedMessages] = useState<Set<number>>(new Set());
  const [pinnedSectionCollapsed, setPinnedSectionCollapsed] = useState(false);

  // JIRA card state (preserved across pin/unpin)
  const [jiraDescriptionExpanded, setJiraDescriptionExpanded] = useState(false);
  const [jiraHeight, setJiraHeight] = useState(400);

  // Whimsical verbs for "Claude is thinking" animation
  const CLAUDE_VERBS = [
    { verb: "flibbertiggoogling", def: "searching aimlessly while spinning in circles" },
    { verb: "wibblescarfing", def: "consuming tea sideways through one's ear" },
    { verb: "snozzlewumping", def: "sneezing in seven colors simultaneously" },
    { verb: "nimblefrosting", def: "dancing as if your knees were made of jelly" },
    { verb: "quozzleplunking", def: "dropping thoughts into puddles to watch them ripple" },
    { verb: "shrimblegateing", def: "walking backwards through Tuesday" },
    { verb: "twidderscooping", def: "collecting moonbeams in a thimble" },
    { verb: "flumplewhacking", def: "hiccupping butterflies" },
    { verb: "grimscrozzling", def: "folding time like origami" },
    { verb: "wobblequaffing", def: "drinking from a cloud" },
    { verb: "shimmerblonking", def: "thinking so hard your hair turns translucent" },
    { verb: "pogglesnapping", def: "jumping through a mirror and arriving yesterday" },
    { verb: "zibberfluxing", def: "flowing upstream through solid objects" },
    { verb: "mumblewarping", def: "speaking in spirals" },
    { verb: "bamboozling", def: "confusing people delightfully" },
    { verb: "discombobulating", def: "scrambling someone's brain gently" },
    { verb: "extrapolating", def: "stretching reality beyond recognition" },
    { verb: "gobsmacking", def: "stunning people speechless with wonder" },
    { verb: "jiggerypokerying", def: "fixing things with magical tinkering" },
    { verb: "shenaniganning", def: "plotting mischief elaborately" },
    { verb: "absquatulating", def: "leaving abruptly in a weird direction" },
    { verb: "cavorting", def: "leaping about with wild abandon" },
  ];
  const [currentVerbIndex, setCurrentVerbIndex] = useState(0);

  // Check for cached summary on mount
  useEffect(() => {
    api.agentSummary(agent.id).then((s) => {
      if (s.status === "ready") setSummary(s);
      else if (s.status === "in_progress") setSummarizing(true);
    }).catch(() => {});
  }, [agent.id]);

  // Poll when summarizing
  useEffect(() => {
    if (!summarizing) return;
    const interval = setInterval(async () => {
      try {
        const s = await api.agentSummary(agent.id);
        if (s.status === "ready") {
          setSummary(s);
          setSummarizing(false);
        } else if (s.status === "none") {
          setSummarizing(false);
        }
      } catch {
        setSummarizing(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [summarizing, agent.id]);

  // Close artifacts dropdown on outside click
  useEffect(() => {
    if (!artifactsDropdownOpen) return;
    const handler = () => setArtifactsDropdownOpen(false);
    // Delay to avoid closing on the click that opened it
    const timer = setTimeout(() => document.addEventListener("click", handler), 0);
    return () => { clearTimeout(timer); document.removeEventListener("click", handler); };
  }, [artifactsDropdownOpen]);

  // Poll for pending Slack context queue
  useEffect(() => {
    const checkQueue = async () => {
      try {
        const data = await api.agentContextQueue(agent.id);
        setSlackQueueCount(data.pending_count);
      } catch {}
    };
    checkQueue();
    const interval = setInterval(checkQueue, 30_000);
    return () => clearInterval(interval);
  }, [agent.id]);

  const handleSummarize = useCallback(async () => {
    setSummarizing(true);
    setSummary(null);
    try {
      const result = await api.agentSummarize(agent.id);
      if (result.status === "ready") {
        setSummary(result);
        setSummarizing(false);
      }
      // If still in_progress, the polling effect above will pick it up
    } catch {
      setSummarizing(false);
    }
  }, [agent.id]);

  const handleAddToAMV = useCallback(() => {
    addAgentToAMV(agent);
    toast.showToast({
      message: "Agent added to Multi-View",
      link: { label: "Go to AMV", href: "/multiview" },
    });
  }, [agent, toast]);

  const handleExtractUrls = useCallback(async () => {
    setExtracting(true);
    setExtractResult(null);
    try {
      const result = await api.agentExtractUrls(agent.id);
      setExtractResult({ urls_found: result.urls_found, links_created: result.links_created });
      // Auto-hide after 5 seconds
      setTimeout(() => setExtractResult(null), 5000);
    } catch (error) {
      console.error("Failed to extract URLs:", error);
    } finally {
      setExtracting(false);
    }
  }, [agent.id]);

  const handleCancel = useCallback(async () => {
    setCancelling(true);
    try {
      await api.agentStop(agent.id);
      setLocalStatus("idle");
    } catch (error) {
      console.error("Failed to cancel:", error);
    } finally {
      setCancelling(false);
    }
  }, [agent.id]);

  const handleRemoveFromQueue = useCallback((index: number) => {
    setMessageQueue(prev => prev.filter((_, i) => i !== index));
  }, []);

  // WebSocket hook - only connect for dashboard-managed agents
  const ws = useAgentChat(agent.id, dashboardManaged, setPendingDenial);
  const isProcessing = ws.isProcessing;

  // Fetch historical messages via HTTP
  const initialLoadDone = useRef(false);
  const fetchHistory = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const data = await api.agentHistory(agent.id, expanded);
      setHistoricalMessages(data.messages);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      if (!silent) setLoading(false);
      initialLoadDone.current = true;
    }
  }, [agent.id, expanded]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Retry once if first load returned empty (handles JSONL flush timing after spawn/send)
  const retried = useRef(false);
  useEffect(() => {
    if (!loading && historicalMessages.length === 0 && !retried.current) {
      retried.current = true;
      const timer = setTimeout(() => fetchHistory(true), 1500);
      return () => clearTimeout(timer);
    }
  }, [loading, historicalMessages.length, fetchHistory]);

  // Re-fetch history when processing completes + drain message queue
  const prevProcessing = useRef(false);
  useEffect(() => {
    if (prevProcessing.current && !isProcessing) {
      // Processing just finished - delay to allow JSONL flush, then silent refetch
      const timer = setTimeout(() => {
        fetchHistory(true);
        // Drain queue: send next message if any
        setMessageQueue(prev => {
          if (prev.length > 0) {
            const [next, ...rest] = prev;
            // Send via HTTP (queue always uses HTTP for reliability)
            const userMsg: ChatMessageType = {
              role: "user",
              timestamp: new Date().toISOString(),
              content: next,
            };
            setHistoricalMessages(h => [...h, userMsg]);
            api.agentChat(agent.id, next).catch(console.error);
            return rest;
          }
          return prev;
        });
      }, 800);
      return () => clearTimeout(timer);
    }
    prevProcessing.current = isProcessing;
  }, [isProcessing, fetchHistory, agent.id]);

  // Rotate through verbs while processing
  useEffect(() => {
    if (!isProcessing) return;

    const interval = setInterval(() => {
      setCurrentVerbIndex((prev) => (prev + 1) % CLAUDE_VERBS.length);
    }, 5000);

    return () => clearInterval(interval);
  }, [isProcessing, CLAUDE_VERBS.length]);

  // Combine historical + WebSocket messages, deduplicate, sort by timestamp
  const allMessages = useMemo(() => {
    const combined = [...historicalMessages, ...ws.messages];
    // Deduplicate: same role + same content (normalized) = duplicate
    // Keep the version with more data (longer content, has tool_calls, etc.)
    const byKey = new Map<string, ChatMessageType>();
    for (const msg of combined) {
      const text = (msg.content || msg.summary || "").replace(/\s+/g, " ").trim();
      const key = `${msg.role}|${text.slice(0, 300)}`;
      const existing = byKey.get(key);
      if (!existing) {
        byKey.set(key, msg);
      } else {
        // Keep the one with more detail
        const existingLen = (existing.content || "").length + (existing.tool_call_count || 0);
        const newLen = (msg.content || "").length + (msg.tool_call_count || 0);
        if (newLen > existingLen) {
          byKey.set(key, msg);
        }
      }
    }
    const deduped = Array.from(byKey.values());
    deduped.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    return deduped;
  }, [historicalMessages, ws.messages]);

  // Filter messages based on type toggles
  const messages = allMessages.filter((msg) => {
    if (msg.role === "user") return showUser;
    if (msg.role === "assistant") return showAssistant;
    return true;
  });

  // Collect all artifacts across all messages (deduped by path)
  const allArtifacts = useMemo(() => {
    const seen = new Set<string>();
    const result: Array<{ path: string; type: string; tool: string; timestamp: string }> = [];
    for (const msg of allMessages) {
      for (const a of msg.artifacts || []) {
        if (!seen.has(a.path)) {
          seen.add(a.path);
          result.push({ ...a, timestamp: msg.timestamp });
        }
      }
    }
    return result;
  }, [allMessages]);

  // Auto-scroll to bottom only if user is already near the bottom
  const isNearBottom = useRef(true);
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    isNearBottom.current = scrollHeight - scrollTop - clientHeight < 100;
  }, []);

  useEffect(() => {
    if (scrollRef.current && isNearBottom.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  // Show initial prompt as first message for dashboard agents with no JSONL history
  useEffect(() => {
    if (!loading && historicalMessages.length === 0 && agent.first_prompt && agent.managed_by === "dashboard") {
      setHistoricalMessages([{
        role: "user",
        timestamp: agent.created_at || new Date().toISOString(),
        content: agent.first_prompt,
      }]);
    }
  }, [loading, historicalMessages.length, agent.first_prompt, agent.managed_by, agent.created_at]);

  // Handle sending messages
  const handleSend = useCallback(
    async (message: string, model?: string) => {
      // Queue if currently processing
      if (isProcessing) {
        setMessageQueue(prev => [...prev, message]);
        return;
      }

      if (dashboardManaged && ws.isConnected) {
        // Send via WebSocket for dashboard-managed agents
        // TODO: WebSocket protocol doesn't support model selection yet — fall through to HTTP
        const success = ws.sendMessage(message, source);
        if (!success) {
          setError(new Error("Failed to send message via WebSocket"));
        }
      } else {
        // Fall back to HTTP (works for both VS Code agents and dashboard agents where WS isn't ready)
        const userMsg: ChatMessageType = {
          role: "user",
          timestamp: new Date().toISOString(),
          content: message,
        };
        setHistoricalMessages((prev) => [...prev, userMsg]);

        try {
          const result = await api.agentChat(agent.id, message, model, source);

          if (result.sent) {
            // If this was a VS Code session, the backend auto-took-over — switch to dashboard mode
            if (!dashboardManaged) {
              setDashboardManaged(true);
              setLocalStatus("live");
            }
          } else {
            const infoMsg: ChatMessageType = {
              role: "assistant",
              timestamp: new Date().toISOString(),
              summary: `${result.message}`,
            };
            setHistoricalMessages((prev) => [...prev, infoMsg]);
          }
        } catch (chatError) {
          console.error("Failed to send message:", chatError);
          const errorMsg: ChatMessageType = {
            role: "assistant",
            timestamp: new Date().toISOString(),
            summary: `Failed to send: ${chatError instanceof Error ? chatError.message : String(chatError)}`,
          };
          setHistoricalMessages((prev) => [...prev, errorMsg]);
        }
      }
    },
    [agent.id, dashboardManaged, ws]
  );

  const handleResume = useCallback(async (message?: string) => {
    setResuming(true);
    try {
      const result = await api.agentResume(agent.id);
      console.log("Resume result:", result);
      // Now dashboard-managed, enable WebSocket and update local status
      setDashboardManaged(true);
      setLocalStatus("idle");

      // If a message was provided, send it after resuming
      if (message) {
        const userMsg: ChatMessageType = {
          role: "user",
          timestamp: new Date().toISOString(),
          content: message,
        };
        setHistoricalMessages((prev) => [...prev, userMsg]);

        try {
          await api.agentChat(agent.id, message);
          setLocalStatus("live");
        } catch (chatError) {
          console.error("Failed to send message after resume:", chatError);
          const errorMsg: ChatMessageType = {
            role: "assistant",
            timestamp: new Date().toISOString(),
            summary: `Failed to send: ${chatError instanceof Error ? chatError.message : String(chatError)}`,
          };
          setHistoricalMessages((prev) => [...prev, errorMsg]);
        }
      }
    } catch (error) {
      console.error("Failed to resume agent:", error);
      setError(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setResuming(false);
    }
  }, [agent.id]);

  const handleToggleMessageCollapse = useCallback((index: number) => {
    setCollapsedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const handleCollapseAll = useCallback(() => {
    if (allCollapsed) {
      // Expand all
      setCollapsedMessages(new Set());
      setAllCollapsed(false);
    } else {
      // Collapse all
      const allIndices = new Set(messages.map((_, i) => i));
      setCollapsedMessages(allIndices);
      setAllCollapsed(true);
    }
  }, [allCollapsed, messages.length]);

  const handleToggleMessagePin = useCallback((index: number) => {
    setPinnedMessages((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  // Build repo context for file path → GitLab URL conversion in Linkify
  const repoInfo = useMemo((): RepoInfo | null => {
    if (!agent.project) return null;
    const gitlabProject = resolveGitLabProject(agent.project);
    const branch = agent.git_branch || "main";
    const workDirs: string[] = [];
    if (agent.worktree_path) workDirs.push(agent.worktree_path);
    if (agent.working_directory) workDirs.push(agent.working_directory);
    if (workDirs.length === 0) return null;
    return { gitlabProject, branch, workDirs };
  }, [agent.project, agent.git_branch, agent.worktree_path, agent.working_directory]);

  return (
    <RepoProvider value={repoInfo}>
    <div className={`flex flex-col ${className}`}>
      {/* Header — hidden in compact mode (MRAgentPane provides its own) */}
      {!compact && <div className="shrink-0 border-b border-zinc-800 p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            {(() => {
              const raw = agent.title || agent.first_prompt || "";
              const tp = parseTitle(raw);
              const fallback = tp.cleanTitle === "(agent)" && agent.first_prompt ? parseTitle(agent.first_prompt) : tp;
              return (
                <div className="flex items-center gap-1.5 pr-8">
                  {fallback.hasCommander && (
                    <span className="shrink-0" title={fallback.commanderText}>
                      <Badge variant="outline" className="text-[9px] px-1 py-0 border-cyan-700/50 bg-cyan-500/5 text-cyan-500 cursor-help">
                        <Bot className="h-2.5 w-2.5 mr-0.5" />cmd
                      </Badge>
                    </span>
                  )}
                  {fallback.jiraKey && (
                    <a href={`https://hello.planet.com/jira/browse/${fallback.jiraKey}`} target="_blank" rel="noopener noreferrer" className="shrink-0" title={fallback.jiraText}>
                      <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-700/50 bg-amber-500/5 text-amber-500 cursor-pointer hover:bg-amber-500/10">
                        <Ticket className="h-2.5 w-2.5 mr-0.5" />{fallback.jiraKey}
                      </Badge>
                    </a>
                  )}
                  <h2 className="text-sm font-semibold text-zinc-200 truncate">
                    {fallback.cleanTitle}
                  </h2>
                </div>
              );
            })()}
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <AgentStatusBadge status={localStatus} />
              <Badge
                variant="outline"
                className={`${getLabelColor(agent.project, "project")} border text-[10px] px-1.5 py-0`}
              >
                {agent.project}
              </Badge>
              {agent.labels.map((l) => (
                <Badge
                  key={l.name}
                  variant="outline"
                  className={`${getLabelColor(l.name, l.category)} border text-[10px] px-1.5 py-0`}
                >
                  {l.name}
                </Badge>
              ))}
              {agent.jira_key && (
                <Badge
                  variant="outline"
                  className="border-cyan-600/50 bg-cyan-500/10 text-cyan-400 text-[10px] px-1.5 py-0 cursor-pointer hover:bg-cyan-500/20 transition-colors"
                  onClick={() => setShowJiraCard(!showJiraCard)}
                  title="Click to view JIRA details"
                >
                  {agent.jira_key}
                </Badge>
              )}
              <span className="text-[10px] text-zinc-600 ml-auto">
                {agent.message_count} messages
              </span>
              {slackQueueCount > 0 && (
                <Badge className="bg-amber-500/20 text-amber-400 border-amber-600/30 text-[10px] px-1.5 py-0 animate-pulse">
                  {slackQueueCount} Slack update{slackQueueCount !== 1 ? "s" : ""} pending
                </Badge>
              )}
              <Link href={`/context/chat/${agent.id}`}>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-[10px] text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                  title="View work context"
                >
                  <LinkIcon className="h-3 w-3 mr-1" />
                  Context
                </Button>
              </Link>
              {allArtifacts.length > 0 && (
                <div className="relative">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[10px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                    onClick={() => setArtifactsDropdownOpen(!artifactsDropdownOpen)}
                    title="View artifacts"
                  >
                    <Paperclip className="h-3 w-3 mr-1" />
                    Artifacts ({allArtifacts.length})
                  </Button>
                  {artifactsDropdownOpen && (
                    <div className="absolute top-full right-0 mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl w-[340px] max-h-[300px] overflow-y-auto">
                      {allArtifacts.map((a, i) => {
                        const filename = a.path.split("/").pop() || a.path;
                        const shortPath = a.path.replace(/^\/Users\/aaryn\//, "~/");
                        const time = new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                        const date = new Date(a.timestamp).toLocaleDateString([], { month: "short", day: "numeric" });
                        return (
                          <button
                            key={i}
                            className="w-full text-left px-3 py-2 hover:bg-zinc-700/50 transition-colors flex items-start gap-2 border-b border-zinc-700/50 last:border-0"
                            onClick={() => {
                              setViewingArtifact(a.path);
                              setArtifactsDropdownOpen(false);
                            }}
                          >
                            <FileText className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs text-zinc-200 truncate">{filename}</div>
                              <div className="text-[10px] text-zinc-500 truncate">{shortPath}</div>
                            </div>
                            <div className="shrink-0 text-right">
                              <Badge variant="outline" className="text-[9px] px-1 py-0 border-zinc-600 text-zinc-500">{a.type}</Badge>
                              <div className="text-[9px] text-zinc-600 mt-0.5">{date} {time}</div>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
              {agent.files_changed && Object.keys(agent.files_changed).length > 0 && (
                <div className="relative group/files">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[10px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                    title="Files changed by this agent"
                  >
                    <FileText className="h-3 w-3 mr-1" />
                    {Object.keys(agent.files_changed).length} files
                  </Button>
                  <div className="absolute top-full right-0 mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl w-[340px] max-h-[300px] overflow-y-auto hidden group-hover/files:block">
                    {Object.entries(agent.files_changed).map(([path, action]) => {
                      const filename = path.split("/").pop() || path;
                      const shortPath = path.replace(/^\/Users\/\w+\//, "~/");
                      return (
                        <div
                          key={path}
                          className="px-3 py-2 hover:bg-zinc-700/50 transition-colors flex items-center gap-2 border-b border-zinc-700/50 last:border-0"
                        >
                          <FileText className={`h-3.5 w-3.5 shrink-0 ${action === "created" ? "text-emerald-400" : "text-blue-400"}`} />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs text-zinc-200 truncate">{filename}</div>
                            <div className="text-[10px] text-zinc-500 truncate">{shortPath}</div>
                          </div>
                          <span className="text-[10px] text-zinc-600 shrink-0">{action}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              {!hideAMVButton && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-[10px] text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                  onClick={handleAddToAMV}
                  title="Add to Agent Multi-View"
                >
                  <LayoutGrid className="h-3 w-3 mr-1" />
                  Add to AMV
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                className={`h-6 px-2 text-[10px] ${
                  isInCart(agent.id)
                    ? "text-cyan-400 bg-cyan-500/10 hover:bg-cyan-500/20"
                    : "text-cyan-400/60 hover:text-cyan-400 hover:bg-cyan-500/10"
                }`}
                onClick={() =>
                  isInCart(agent.id) ? removeFromCart(agent.id) : addToCart(agent)
                }
                title={isInCart(agent.id) ? "Remove from Cart" : "Add to Context Cart"}
              >
                <ShoppingCart className="h-3 w-3 mr-1" />
                {isInCart(agent.id) ? "In Cart" : "Cart"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[10px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                onClick={handleExtractUrls}
                disabled={extracting}
                title="Extract URLs and create entity links"
              >
                {extracting ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <LinkIcon className="h-3 w-3 mr-1" />
                )}
                {extracting ? "Extracting..." : "Extract URLs"}
              </Button>
              {extractResult && (
                <span className="text-[10px] text-emerald-400">
                  Found {extractResult.urls_found} URLs, created {extractResult.links_created} links
                </span>
              )}
              {onHide && !agent.hidden_at && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 w-6 p-0 text-zinc-600 hover:text-zinc-400"
                  onClick={() => onHide(agent.id)}
                  title="Hide agent"
                >
                  <EyeOff className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>
          {headerActions && (
            <div className="shrink-0 flex items-center gap-1">
              {headerActions}
            </div>
          )}
        </div>
        {/* Expand toggle + Message type filters + Summary */}
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <label className="flex items-center gap-1.5 text-[10px] text-zinc-500 cursor-pointer">
            <input
              type="checkbox"
              checked={expanded}
              onChange={(e) => setExpanded(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-800 h-3 w-3"
            />
            Expand details
          </label>

          {/* Message type toggles */}
          <div className="flex items-center gap-1.5 ml-2">
            <span className="text-[10px] text-zinc-600">Show:</span>
            <Badge
              variant="outline"
              className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
                showUser
                  ? "bg-blue-500/20 border-blue-500/50 text-blue-300"
                  : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
              }`}
              onClick={() => setShowUser(!showUser)}
            >
              User
            </Badge>
            <Badge
              variant="outline"
              className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
                showAssistant
                  ? "bg-violet-500/20 border-violet-500/50 text-violet-300"
                  : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
              }`}
              onClick={() => setShowAssistant(!showAssistant)}
            >
              Claude
            </Badge>
            <Badge
              variant="outline"
              className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
                showToolOutput
                  ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300"
                  : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
              }`}
              onClick={() => setShowToolOutput(!showToolOutput)}
            >
              Tools
            </Badge>
            <Badge
              variant="outline"
              className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
                showThinking
                  ? "bg-amber-500/20 border-amber-500/50 text-amber-300"
                  : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
              }`}
              onClick={() => setShowThinking(!showThinking)}
            >
              Thinking
            </Badge>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={handleCollapseAll}
              title={allCollapsed ? "Expand all messages" : "Collapse all messages"}
            >
              {allCollapsed ? <ChevronsDown className="h-3 w-3" /> : <ChevronsUp className="h-3 w-3" />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={() => scrollRef.current && (scrollRef.current.scrollTop = 0)}
              title="Jump to top"
            >
              <ArrowUpToLine className="h-3 w-3" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={() => scrollRef.current && (scrollRef.current.scrollTop = scrollRef.current.scrollHeight)}
              title="Jump to bottom"
            >
              <ArrowDownToLine className="h-3 w-3" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-6 text-[10px] px-2 border-zinc-700 text-zinc-400 hover:bg-zinc-800"
              onClick={handleSummarize}
              disabled={summarizing}
            >
              {summarizing ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <FileText className="h-3 w-3 mr-1" />
              )}
              Summary
            </Button>
          </div>
        </div>
        {/* Summary display */}
        {(summary || summarizing) && (
          <div className="mt-2 rounded-md border border-zinc-800 bg-zinc-950/50 px-3 py-2">
            {summarizing ? (
              <div className="flex items-center gap-2 text-zinc-400">
                <Loader2 className="h-3 w-3 animate-spin text-blue-400" />
                <span className="text-[10px]">Generating summary...</span>
              </div>
            ) : summary?.status === "ready" ? (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <button
                    onClick={() => setSummaryLevel("phrase")}
                    className={`text-[10px] transition-colors ${
                      summaryLevel === "phrase" ? "text-zinc-200 font-medium" : "text-zinc-500 hover:text-zinc-400"
                    }`}
                  >
                    phrase
                  </button>
                  <span className="text-zinc-700">|</span>
                  <button
                    onClick={() => setSummaryLevel("short")}
                    className={`text-[10px] transition-colors ${
                      summaryLevel === "short" ? "text-zinc-200 font-medium" : "text-zinc-500 hover:text-zinc-400"
                    }`}
                  >
                    short
                  </button>
                  <span className="text-zinc-700">|</span>
                  <button
                    onClick={() => setSummaryLevel("detailed")}
                    className={`text-[10px] transition-colors ${
                      summaryLevel === "detailed" ? "text-zinc-200 font-medium" : "text-zinc-500 hover:text-zinc-400"
                    }`}
                  >
                    detailed
                  </button>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {summaryLevel === "phrase" && summary.phrase}
                  {summaryLevel === "short" && summary.short}
                  {summaryLevel === "detailed" && summary.detailed}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </div>}

      {/* Compact filter bar — shown in compact mode (e.g. MRAgentPane) */}
      {compact && (
        <div className="shrink-0 border-b border-zinc-800 px-3 py-1.5 flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-zinc-600">Show:</span>
          <Badge
            variant="outline"
            className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
              showUser
                ? "bg-blue-500/20 border-blue-500/50 text-blue-300"
                : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
            }`}
            onClick={() => setShowUser(!showUser)}
          >
            User
          </Badge>
          <Badge
            variant="outline"
            className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
              showAssistant
                ? "bg-violet-500/20 border-violet-500/50 text-violet-300"
                : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
            }`}
            onClick={() => setShowAssistant(!showAssistant)}
          >
            Claude
          </Badge>
          <Badge
            variant="outline"
            className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
              showToolOutput
                ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300"
                : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
            }`}
            onClick={() => setShowToolOutput(!showToolOutput)}
          >
            Tools
          </Badge>
          <Badge
            variant="outline"
            className={`cursor-pointer text-[10px] px-1.5 py-0 transition-colors ${
              showThinking
                ? "bg-amber-500/20 border-amber-500/50 text-amber-300"
                : "border-zinc-700 text-zinc-600 hover:text-zinc-400"
            }`}
            onClick={() => setShowThinking(!showThinking)}
          >
            Thinking
          </Badge>
          <label className="flex items-center gap-1 text-[10px] text-zinc-500 cursor-pointer ml-1">
            <input
              type="checkbox"
              checked={expanded}
              onChange={(e) => setExpanded(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-800 h-3 w-3"
            />
            Expand
          </label>
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={handleCollapseAll}
              title={allCollapsed ? "Expand all messages" : "Collapse all messages"}
            >
              {allCollapsed ? <ChevronsDown className="h-3 w-3" /> : <ChevronsUp className="h-3 w-3" />}
            </Button>
            <span className="text-[10px] text-zinc-600">{allMessages.length} msgs</span>
          </div>
        </div>
      )}

      {/* Scrollable chat history */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-4 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center h-full py-12">
            <Loader2 className="h-6 w-6 text-zinc-500 animate-spin" />
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full py-12">
            <p className="text-sm text-red-400">Failed to load history: {error.message}</p>
          </div>
        ) : messages.length === 0 && !showJiraCard ? (
          <div className="flex items-center justify-center h-full py-12">
            <p className="text-sm text-zinc-500">No messages in this session.</p>
          </div>
        ) : (
          <div>
            {/* Pinned items - sticky at top with accordion */}
            {(jiraPinned || pinnedMessages.size > 0) && (
              <div className="sticky top-0 z-10 bg-zinc-900 mb-2 border-b border-zinc-800">
                {/* Accordion Header */}
                <div
                  className="flex items-center justify-between py-1.5 px-2 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                  onClick={() => setPinnedSectionCollapsed(!pinnedSectionCollapsed)}
                >
                  <div className="flex items-center gap-2">
                    {pinnedSectionCollapsed ? (
                      <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
                    )}
                    <span className="text-[10px] font-medium text-zinc-400">
                      Pinned ({(jiraPinned ? 1 : 0) + pinnedMessages.size})
                    </span>
                  </div>
                  <span className="text-[9px] text-zinc-600">
                    {pinnedSectionCollapsed ? "Expand" : "Collapse"}
                  </span>
                </div>

                {/* Collapsible Content */}
                {!pinnedSectionCollapsed && (
                  <div className="pb-2">
                    {jiraPinned && showJiraCard && agent.jira_key && (
                      <JiraCard
                        jiraKey={agent.jira_key}
                        onClose={() => setShowJiraCard(false)}
                        isPinned={jiraPinned}
                        onTogglePin={() => setJiraPinned(!jiraPinned)}
                        showDescription={jiraDescriptionExpanded}
                        onToggleDescription={() => setJiraDescriptionExpanded(!jiraDescriptionExpanded)}
                        height={jiraHeight}
                        onHeightChange={setJiraHeight}
                      />
                    )}
                    {messages.map((msg, i) => {
                      if (!pinnedMessages.has(i)) return null;
                      return (
                        <ChatMessage
                          key={`pinned-${msg.timestamp}-${i}`}
                          message={msg}
                          defaultExpanded={expanded}
                          showToolOutput={showToolOutput}
                          showThinking={showThinking}
                          useColoredBg={true}
                          collapsed={collapsedMessages.has(i)}
                          onToggleCollapse={() => handleToggleMessageCollapse(i)}
                          isPinned={true}
                          onTogglePin={() => handleToggleMessagePin(i)}
                          resizable={true}
                          onViewArtifact={setViewingArtifact}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* JIRA Card (if not pinned) */}
            {showJiraCard && agent.jira_key && !jiraPinned && (
              <JiraCard
                jiraKey={agent.jira_key}
                onClose={() => setShowJiraCard(false)}
                isPinned={jiraPinned}
                onTogglePin={() => setJiraPinned(!jiraPinned)}
                showDescription={jiraDescriptionExpanded}
                onToggleDescription={() => setJiraDescriptionExpanded(!jiraDescriptionExpanded)}
                height={jiraHeight}
                onHeightChange={setJiraHeight}
              />
            )}

            {/* All messages */}
            {messages.map((msg, i) => {
              // Skip if pinned (already rendered above)
              if (pinnedMessages.has(i)) return null;

              return (
                <ChatMessage
                  key={`${msg.timestamp}-${i}`}
                  message={msg}
                  defaultExpanded={expanded}
                  showToolOutput={showToolOutput}
                  showThinking={showThinking}
                  useColoredBg={true}
                  collapsed={collapsedMessages.has(i)}
                  onToggleCollapse={() => handleToggleMessageCollapse(i)}
                  isPinned={false}
                  onTogglePin={() => handleToggleMessagePin(i)}
                  resizable={true}
                  onViewArtifact={setViewingArtifact}
                />
              );
            })}
            {isProcessing && (
              <div className="flex items-center gap-2 py-3 px-3 -mx-3 rounded-md bg-violet-500/10 border-l-2 border-violet-500/30 animate-pulse">
                <div className="shrink-0 h-6 w-6 rounded-full bg-violet-500/20 flex items-center justify-center">
                  <Loader2 className="h-3.5 w-3.5 text-violet-400 animate-spin" />
                </div>
                <div className="flex items-center gap-1">
                  <span
                    className="text-xs text-violet-300 cursor-help"
                    title={CLAUDE_VERBS[currentVerbIndex].def}
                  >
                    {CLAUDE_VERBS[currentVerbIndex].verb.charAt(0).toUpperCase() + CLAUDE_VERBS[currentVerbIndex].verb.slice(1)}
                  </span>
                  <span className="flex gap-0.5">
                    <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                    <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                    <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sticky chat input bar */}
      <div className="shrink-0 border-t border-zinc-800 p-3">
        <ChatInput
          agentStatus={localStatus}
          managedBy={dashboardManaged ? "dashboard" : agent.managed_by}
          onSend={handleSend}
          onResume={handleResume}
          onCancel={handleCancel}
          disabled={resuming || cancelling}
          processing={isProcessing}
          queue={messageQueue}
          onRemoveFromQueue={handleRemoveFromQueue}
        />
      </div>
    </div>
    {viewingArtifact && (
      <ArtifactModal
        agentId={agent.id}
        path={viewingArtifact}
        onClose={() => setViewingArtifact(null)}
      />
    )}
    <PermissionDialog
      denial={pendingDenial}
      onClose={() => setPendingDenial(null)}
      onGranted={() => {}}
    />
    </RepoProvider>
  );
}
