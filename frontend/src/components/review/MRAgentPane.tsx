"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, Check, CheckCircle, ChevronDown, ChevronRight, Copy, FileCode, FileText, Loader2, Maximize2, MessageSquare, Minimize2, Send, Shield, ShieldAlert, Sparkles, LayoutGrid, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AgentSummary, DetailedMR, Agent, ReviewFindings, PersonaResult } from "@/lib/api";
import { useToast } from "@/components/ui/toast-simple";
import { ChatView } from "@/components/agents/ChatView";
import { addAgentToAMV } from "@/lib/amv";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MRAgentPaneProps {
  mr: DetailedMR | null;
  jiraKey: string | null;
  selectedFile: string | null;
  selectedTab: string;
  maximized?: boolean;
  onToggleMaximize?: () => void;
  onSendToMultiView?: () => void;
  pendingPrompt?: string | null;
  onPromptConsumed?: () => void;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const PROMPT_CHIPS = [
  "Explain this MR",
  "What could break?",
  "Suggest test cases",
  "Draft review comment",
  "Is implementation complete?",
  "Summarize JIRA vs code",
];

function mockReviewSummary(mr: DetailedMR): { changes: string[]; risks: string[]; missing: string[] } {
  const fileCount = mr.description?.match(/\d+ files? changed/)?.[0] ?? "several files";
  const project = mr.project.split("/").pop() ?? mr.project;
  return {
    changes: [
      `Modified ${fileCount} in ${project}`,
      `Branch: ${mr.branch} -> ${mr.target_branch ?? "main"}`,
      mr.is_draft ? "MR is still in draft" : "MR is ready for review",
    ],
    risks: [
      "No test coverage information available yet",
      "Review agent integration pending",
    ],
    missing: [
      "Automated risk analysis (coming soon)",
      "Test coverage diff (coming soon)",
    ],
  };
}

function mockResponse(mr: DetailedMR, userMessage: string): string {
  const snippet = userMessage.length > 50 ? userMessage.slice(0, 50) + "..." : userMessage;
  return (
    `Looking at MR !${mr.iid} "${mr.title}" by ${mr.author}...\n\n` +
    `I'll analyze this based on your question: "${snippet}"\n\n` +
    `*Agent integration pending -- this is a preview of the review assistant.*`
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ContextBadge({ mr, selectedFile }: { mr: DetailedMR | null; selectedFile: string | null }) {
  if (!mr) {
    return (
      <Badge variant="outline" className="border-zinc-700 text-zinc-500 text-[10px] px-2 py-0">
        No MR selected
      </Badge>
    );
  }
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <Badge variant="outline" className="border-blue-600/40 bg-blue-500/10 text-blue-300 text-[10px] px-2 py-0">
        !{mr.iid} {mr.project.split("/").pop()}
      </Badge>
      {selectedFile && (
        <Badge variant="outline" className="border-zinc-700 text-zinc-400 text-[10px] px-2 py-0 max-w-[180px] truncate">
          <FileCode className="h-3 w-3 mr-1 shrink-0" />
          {selectedFile.split("/").pop()}
        </Badge>
      )}
    </div>
  );
}

function ReviewSummary({ mr }: { mr: DetailedMR }) {
  const [loading, setLoading] = useState(true);
  const summary = mockReviewSummary(mr);

  // Simulate brief generation delay when MR changes
  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, [mr.iid, mr.project]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-3 rounded-md bg-zinc-900/50 border border-zinc-800">
        <Loader2 className="h-3.5 w-3.5 text-violet-400 animate-spin shrink-0" />
        <span className="text-[11px] text-zinc-400 animate-pulse">Generating review summary...</span>
      </div>
    );
  }

  return (
    <div className="rounded-md bg-zinc-900/50 border border-zinc-800 p-3 space-y-2.5">
      <Section label="Key Changes" items={summary.changes} />
      <Section label="Risks" items={summary.risks} />
      <Section label="Missing" items={summary.missing} />
    </div>
  );
}

function Section({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mb-1">{label}</h4>
      <ul className="space-y-0.5">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-zinc-300 leading-relaxed flex items-start gap-1.5">
            <span className="text-zinc-600 mt-0.5">-</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const PERSONA_LABELS: Record<string, string> = {
  "code-quality": "Code Quality",
  "security": "Security",
  "architecture": "Architecture",
  "performance": "Performance",
  "adversarial": "Adversarial",
  "change-risk-score": "Risk Score",
  "dead-code": "Dead Code",
  "duplication": "Duplication",
  "accuracy": "Accuracy",
  "scope": "Scope",
  "operator-ux": "Operator UX",
  "observability": "Observability",
};

const PERSONA_MODELS: Record<string, string> = {
  "security": "opus",
  "architecture": "opus",
  "adversarial": "opus",
  "accuracy": "opus",
};

function verdictLabel(verdict?: string): string {
  switch (verdict) {
    case "approved": return "Approved";
    case "changes_required": return "Changes Required";
    case "blocked": return "Blocked";
    default: return "Pending";
  }
}

function VerdictIcon({ verdict }: { verdict?: string }) {
  switch (verdict) {
    case "approved":
      return <CheckCircle className="h-4 w-4 text-emerald-400" />;
    case "changes_required":
      return <AlertTriangle className="h-4 w-4 text-amber-400" />;
    case "blocked":
      return <XCircle className="h-4 w-4 text-red-400" />;
    default:
      return <Loader2 className="h-4 w-4 text-zinc-500 animate-spin" />;
  }
}

function riskBadgeClass(level?: string): string {
  switch (level) {
    case "high": return "border-red-600/40 bg-red-500/10 text-red-400 text-[10px]";
    case "medium": return "border-amber-600/40 bg-amber-500/10 text-amber-400 text-[10px]";
    case "low": return "border-emerald-600/40 bg-emerald-500/10 text-emerald-400 text-[10px]";
    default: return "border-zinc-700 text-zinc-500 text-[10px]";
  }
}

function severityBadgeClass(severity: string): string {
  switch (severity) {
    case "error": return "bg-red-500/20 text-red-400";
    case "warning": return "bg-amber-500/20 text-amber-400";
    case "info": return "bg-blue-500/20 text-blue-400";
    default: return "bg-zinc-800 text-zinc-400";
  }
}

function PersonaCard({ persona }: { persona: PersonaResult }) {
  const [expanded, setExpanded] = useState(false);
  const label = PERSONA_LABELS[persona.persona] ?? persona.persona;
  const isOpus = PERSONA_MODELS[persona.persona] === "opus";

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/50 overflow-hidden">
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-zinc-800/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-zinc-500 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-zinc-500 shrink-0" />
        )}
        <VerdictIcon verdict={persona.verdict} />
        <span className="text-xs font-medium text-zinc-200 flex-1">{label}</span>
        {isOpus && (
          <Badge variant="outline" className="border-violet-600/40 bg-violet-500/10 text-violet-400 text-[9px] px-1.5 py-0">
            opus
          </Badge>
        )}
        {persona.finding_count > 0 && (
          <span className="text-[10px] text-zinc-500">
            {persona.finding_count} finding{persona.finding_count !== 1 ? "s" : ""}
          </span>
        )}
        {persona.blocking_count > 0 && (
          <Badge variant="outline" className="border-red-600/40 bg-red-500/10 text-red-400 text-[9px] px-1.5 py-0">
            {persona.blocking_count} blocking
          </Badge>
        )}
      </button>

      {expanded && persona.findings.length > 0 && (
        <div className="border-t border-zinc-800 px-3 py-2 space-y-2">
          {persona.findings.map((f) => (
            <div key={f.id} className="flex items-start gap-2">
              <Badge className={`shrink-0 text-[9px] px-1.5 py-0 ${severityBadgeClass(f.severity)}`}>
                {f.severity}
              </Badge>
              <div className="min-w-0">
                <div className="text-xs text-zinc-300 font-medium">
                  {f.blocking && <ShieldAlert className="h-3 w-3 text-red-400 inline mr-1" />}
                  {f.title}
                </div>
                {f.description && (
                  <p className="text-[11px] text-zinc-500 mt-0.5 line-clamp-2">{f.description}</p>
                )}
                {f.source_file && (
                  <span className="text-[10px] text-zinc-600 font-mono">
                    {f.source_file}{f.source_line ? `:${f.source_line}` : ""}
                  </span>
                )}
              </div>
            </div>
          ))}
          {persona.duration_ms > 0 && (
            <div className="text-[10px] text-zinc-600 pt-1 border-t border-zinc-800/50">
              {(persona.duration_ms / 1000).toFixed(1)}s · ${persona.cost_usd?.toFixed(4) ?? "0"}
            </div>
          )}
        </div>
      )}

      {expanded && persona.findings.length === 0 && (
        <div className="border-t border-zinc-800 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[11px] text-emerald-400">
            <Check className="h-3 w-3" />
            No issues found
          </div>
        </div>
      )}
    </div>
  );
}

function PromptChips({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {PROMPT_CHIPS.map((chip) => (
        <button
          key={chip}
          onClick={() => onSelect(chip)}
          className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] rounded-full px-3 py-1 transition-colors cursor-pointer whitespace-nowrap"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}

function ChatBubble({ message, onCopy }: { message: Message; onCopy: (text: string) => void }) {
  const isUser = message.role === "user";
  const time = new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      className={`rounded-md px-3 py-2 border-l-2 ${
        isUser
          ? "bg-blue-500/15 border-blue-500/30"
          : "bg-violet-500/15 border-violet-500/30"
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className={`text-[10px] font-medium ${isUser ? "text-blue-400" : "text-violet-400"}`}>
          {isUser ? "You" : "Agent"}
        </span>
        <div className="flex items-center gap-1">
          {!isUser && (
            <button
              onClick={() => onCopy(message.content)}
              className="text-zinc-600 hover:text-zinc-400 transition-colors p-0.5"
              title="Copy response"
            >
              <Copy className="h-3 w-3" />
            </button>
          )}
          <span className="text-[9px] text-zinc-600">{time}</span>
        </div>
      </div>
      <div className="text-xs text-zinc-300 leading-relaxed whitespace-pre-wrap">
        {message.content}
      </div>
      {!isUser && (
        <div className="mt-1.5 flex items-center">
          <button
            className="text-[9px] text-zinc-600 hover:text-zinc-400 transition-colors"
            title="Coming soon"
            onClick={() => {}}
          >
            Send as review comment
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MRAgentPane({ mr, jiraKey, selectedFile, selectedTab, maximized, onToggleMaximize, onSendToMultiView, pendingPrompt, onPromptConsumed }: MRAgentPaneProps) {
  const { showToast } = useToast();
  const [activeAgent, setActiveAgent] = useState<Agent | null>(null);
  const [spawning, setSpawning] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [summaryCollapsed, setSummaryCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "summary">("chat");
  const [agentSummary, setAgentSummary] = useState<AgentSummary | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryLevel, setSummaryLevel] = useState<"phrase" | "short" | "detailed">("detailed");
  const [reviewFindings, setReviewFindings] = useState<ReviewFindings | null>(null);
  const [findingsLoading, setFindingsLoading] = useState(false);
  const prevMrRef = useRef<string | null>(null);

  useEffect(() => {
    if (pendingPrompt) {
      setInput(pendingPrompt);
      setActiveTab("chat");
      onPromptConsumed?.();
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [pendingPrompt, onPromptConsumed]);

  // Fetch existing summary when agent changes
  useEffect(() => {
    if (!activeAgent) { setAgentSummary(null); return; }
    api.agentSummary(activeAgent.id).then((s) => {
      if (s.status === "ready") setAgentSummary(s);
      else if (s.status === "in_progress") setSummarizing(true);
    }).catch(() => {});
  }, [activeAgent?.id]);

  // Poll while summarizing
  useEffect(() => {
    if (!summarizing || !activeAgent) return;
    const interval = setInterval(async () => {
      try {
        const s = await api.agentSummary(activeAgent.id);
        if (s.status === "ready") {
          setAgentSummary(s);
          setSummarizing(false);
        } else if (s.status === "none") {
          setSummarizing(false);
        }
      } catch {
        setSummarizing(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [summarizing, activeAgent?.id]);

  // Fetch review findings when Summary tab is active
  useEffect(() => {
    if (activeTab !== "summary" || !mr) return;
    const project = mr.project.split("/").pop() ?? mr.project;

    let cancelled = false;
    const fetchFindings = async () => {
      setFindingsLoading(true);
      try {
        const result = await api.mrReviewFindings(project, mr.iid);
        if (!cancelled) setReviewFindings(result);
      } catch {
        // Endpoint may not exist yet or MR not in DB
      } finally {
        if (!cancelled) setFindingsLoading(false);
      }
    };

    fetchFindings();
    const interval = setInterval(fetchFindings, 10_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [activeTab, mr?.iid, mr?.project]);

  const handleGenerateSummary = useCallback(async () => {
    if (!activeAgent) return;
    setSummarizing(true);
    setAgentSummary(null);
    try {
      const result = await api.agentSummarize(activeAgent.id);
      if (result.status === "ready") {
        setAgentSummary(result);
        setSummarizing(false);
      }
      // If still in_progress, the polling effect above will pick it up
    } catch {
      setSummarizing(false);
    }
  }, [activeAgent?.id]);

  // When MR changes, find existing agent for this MR
  useEffect(() => {
    const mrKey = mr ? `${mr.project}-${mr.iid}` : null;
    if (mrKey === prevMrRef.current) return;
    prevMrRef.current = mrKey;
    setActiveAgent(null);
    setInput("");

    if (!mr) return;

    // Try to find an existing agent by JIRA key or branch
    const jira = jiraKey;
    if (jira) {
      api.agentsByJira(jira).then(result => {
        const agents = result.agents || [];
        const active = agents.find((a: Agent) => a.status !== "dead") || agents[0] || null;
        setActiveAgent(active);
      }).catch(() => {});
    }
  }, [mr, jiraKey]);

  // Spawn or send to agent
  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || !mr) return;

    if (activeAgent) {
      // Send to existing agent
      try {
        await api.agentChat(activeAgent.id, trimmed);
        setInput("");
      } catch (err) {
        console.error("Failed to send:", err);
      }
    } else {
      // Spawn new agent for this MR review
      setSpawning(true);
      try {
        const spawnResult = await api.agentSpawn({
          project: mr.project,
          jira_key: jiraKey || undefined,
          initial_prompt: `Review MR !${mr.iid}: ${mr.title}\n\nBranch: ${mr.branch}\n\n${trimmed}`,
          source: "mr-review",
          mr_project: mr.project,
          mr_iid: mr.iid,
        });
        setInput("");

        // Fetch the full agent object using the ID from spawn
        const agent = await api.agentDetail(spawnResult.id);
        setActiveAgent(agent);
      } catch (err) {
        console.error("Failed to spawn:", err);
        showToast({ message: `Failed to spawn agent: ${err}` });
      } finally {
        setSpawning(false);
      }
    }
  }, [input, mr, activeAgent, jiraKey, showToast]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleChipSelect = useCallback((text: string) => {
    setInput(text);
    inputRef.current?.focus();
  }, []);

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* ----------------------------------------------------------------- */}
      {/* 1. Header                                                          */}
      {/* ----------------------------------------------------------------- */}
      <div className="shrink-0 border-b border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-2 mb-1.5">
          <Bot className="h-4 w-4 text-violet-400" />
          <h2 className="text-sm font-semibold text-zinc-200">Agent Review</h2>
          <div className="ml-auto flex items-center gap-1">
            {(onSendToMultiView || activeAgent) && (
              <button
                onClick={() => {
                  if (activeAgent) {
                    addAgentToAMV(activeAgent);
                  } else {
                    onSendToMultiView?.();
                  }
                  showToast({
                    message: "Agent added to Multi-View",
                    link: { label: "Go to AMV", href: "/multiview" },
                  });
                }}
                className="p-1 text-zinc-500 hover:text-amber-400 transition-colors"
                title="Add to Agent Multi-View"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
              </button>
            )}
            {onToggleMaximize && (
              <button
                onClick={onToggleMaximize}
                className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
                title={maximized ? "Restore (Esc)" : "Maximize"}
              >
                {maximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              </button>
            )}
          </div>
        </div>
        <ContextBadge mr={mr} selectedFile={selectedFile} />
      </div>

      {activeAgent ? (
        <>
          {/* Tab bar — switch between Chat (full height) and Summary */}
          <div className="shrink-0 border-b border-zinc-800 flex items-center px-2">
            <button
              className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === "chat"
                  ? "border-violet-400 text-violet-300"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
              onClick={() => setActiveTab("chat")}
            >
              <MessageSquare className="h-3 w-3 mr-1.5 inline" />
              Chat
            </button>
            <button
              className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === "summary"
                  ? "border-amber-400 text-amber-300"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
              onClick={() => setActiveTab("summary")}
            >
              <Sparkles className="h-3 w-3 mr-1.5 inline" />
              Summary
            </button>
          </div>

          {/* Tab content */}
          {activeTab === "chat" ? (
            <ChatView agent={activeAgent} className="flex-1 min-h-0" compact hideAMVButton source="mr-review" />
          ) : (
            <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-3">
              {/* Structured persona findings */}
              {findingsLoading && !reviewFindings ? (
                <div className="flex items-center gap-2 p-3 rounded-md bg-zinc-900/50 border border-zinc-800">
                  <Loader2 className="h-3.5 w-3.5 text-violet-400 animate-spin shrink-0" />
                  <span className="text-[11px] text-zinc-400 animate-pulse">Running audit personas...</span>
                </div>
              ) : reviewFindings && reviewFindings.personas.length > 0 ? (
                <div className="space-y-3">
                  {/* Merged verdict header */}
                  <div className="flex items-center justify-between p-3 rounded-md bg-zinc-900/50 border border-zinc-800">
                    <div className="flex items-center gap-2">
                      <VerdictIcon verdict={reviewFindings.verdict} />
                      <span className="text-sm font-medium text-zinc-200">
                        {verdictLabel(reviewFindings.verdict)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {reviewFindings.risk_level && (
                        <Badge variant="outline" className={riskBadgeClass(reviewFindings.risk_level)}>
                          {reviewFindings.risk_level} risk
                        </Badge>
                      )}
                      <span className="text-[10px] text-zinc-600">
                        {reviewFindings.finding_count} findings
                        {(reviewFindings.blocking_count ?? 0) > 0 && (
                          <span className="text-red-400"> ({reviewFindings.blocking_count} blocking)</span>
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Per-persona results */}
                  {reviewFindings.personas.map((p) => (
                    <PersonaCard key={p.persona} persona={p} />
                  ))}

                  {/* Cost footer */}
                  {(reviewFindings.total_cost_usd ?? 0) > 0 && (
                    <div className="text-[10px] text-zinc-600 text-right">
                      Total cost: ${reviewFindings.total_cost_usd?.toFixed(4)}
                    </div>
                  )}
                </div>
              ) : reviewFindings?.status === "pending" ? (
                <div className="flex items-center gap-2 p-3 rounded-md bg-zinc-900/50 border border-zinc-800">
                  <Loader2 className="h-3.5 w-3.5 text-amber-400 animate-spin shrink-0" />
                  <span className="text-[11px] text-zinc-400">Persona audits in progress...</span>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Fallback: agent summary or generate button */}
                  {agentSummary?.status === "ready" ? (
                    <div className="rounded-md bg-zinc-900/50 border border-zinc-800 p-3 space-y-2.5">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="h-3 w-3 text-amber-400" />
                        <span className="text-[11px] font-medium text-zinc-400">Agent Summary</span>
                      </div>
                      <div className="text-sm text-zinc-300 prose prose-invert prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-headings:mt-3 prose-headings:mb-2 prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-code:text-emerald-400 prose-code:bg-zinc-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {agentSummary.detailed || agentSummary.short || agentSummary.phrase || ""}
                        </ReactMarkdown>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                      <Shield className="h-6 w-6 text-zinc-700 mb-2" />
                      <p className="text-xs text-zinc-500 mb-3">No audit results yet</p>
                      <p className="text-[10px] text-zinc-600">Persona audits run automatically when a review is triggered</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        <>
          {/* Collapsible AI Summary (no agent yet) */}
          {mr && (
            <div className="shrink-0 border-b border-zinc-800 px-4 py-3">
              <div
                className="flex items-center gap-1.5 cursor-pointer select-none"
                onClick={() => setSummaryCollapsed(!summaryCollapsed)}
              >
                {summaryCollapsed ? (
                  <ChevronRight className="h-3 w-3 text-zinc-500" />
                ) : (
                  <ChevronDown className="h-3 w-3 text-zinc-500" />
                )}
                <Sparkles className="h-3 w-3 text-amber-400" />
                <span className="text-[11px] font-medium text-zinc-400">AI Summary</span>
              </div>
              {!summaryCollapsed && (
                <div className="mt-2">
                  <ReviewSummary mr={mr} />
                </div>
              )}
            </div>
          )}

          {/* Prompt Chips */}
          {mr && (
            <div className="shrink-0 border-b border-zinc-800 px-4 py-2.5">
              <PromptChips onSelect={handleChipSelect} />
            </div>
          )}

          {/* Empty state + composer to spawn */}
          <div className="flex-1 flex flex-col items-center justify-center text-center px-4 min-h-0">
            <MessageSquare className="h-8 w-8 text-zinc-800 mb-2" />
            <p className="text-xs text-zinc-600">
              {mr ? "Send a message to start a review agent for this MR" : "Select an MR to begin"}
            </p>
            {spawning && (
              <div className="flex items-center gap-2 mt-3">
                <Loader2 className="h-3.5 w-3.5 text-violet-400 animate-spin" />
                <span className="text-xs text-violet-300">Spawning agent...</span>
              </div>
            )}
          </div>
          <div className="shrink-0 border-t border-zinc-800 px-4 py-3">
            <div className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={mr ? "Ask about this MR..." : "Select an MR first"}
                disabled={!mr || spawning}
                rows={1}
                className="flex-1 resize-none min-h-[36px] max-h-[120px] rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
              />
              <Button
                variant="ghost"
                size="sm"
                className="h-9 w-9 p-0 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 shrink-0"
                onClick={handleSend}
                disabled={!mr || spawning || !input.trim()}
              >
                {spawning ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
