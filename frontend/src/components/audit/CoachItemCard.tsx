"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  MessageSquare,
  CheckCircle2,
  Clock,
  AlertCircle,
  CircleDot,
  Send,
  Loader2,
  ChevronDown,
  ChevronUp,
  Ban,
  SkipForward,
  Lightbulb,
  ArrowRight,
} from "lucide-react";
import type { CoachItem, ExplainResponse, EvaluateResponse } from "@/lib/api";

// ---------------------------------------------------------------------------
// Status display configuration
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  string,
  { classes: string; label: string; icon: typeof CircleDot }
> = {
  open: {
    classes: "text-zinc-400 border-zinc-600/30",
    label: "Open",
    icon: CircleDot,
  },
  in_progress: {
    classes: "text-blue-400 border-blue-500/30",
    label: "In Progress",
    icon: MessageSquare,
  },
  answered: {
    classes: "text-amber-400 border-amber-500/30",
    label: "Answered",
    icon: MessageSquare,
  },
  resolved: {
    classes: "text-emerald-400 border-emerald-500/30",
    label: "Resolved",
    icon: CheckCircle2,
  },
  deferred: {
    classes: "text-zinc-500 border-zinc-600/30",
    label: "Deferred",
    icon: Clock,
  },
  blocked: {
    classes: "text-red-400 border-red-500/30",
    label: "Blocked",
    icon: Ban,
  },
};

// ---------------------------------------------------------------------------
// Conversation entry type for displaying the interaction history
// ---------------------------------------------------------------------------

interface ConversationEntry {
  type: "question" | "response" | "follow_up" | "resolution";
  text: string;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoachItemCardProps {
  item: CoachItem;
  isActive: boolean;
  onResolve: (itemId: string, resolution?: string) => void;
  onDefer: (itemId: string) => void;
  onSkip: (itemId: string) => void;
  onRespond: (itemId: string, response: string) => Promise<EvaluateResponse>;
  onExplain: (itemId: string) => Promise<ExplainResponse>;
}

export function CoachItemCard({
  item,
  isActive,
  onResolve,
  onDefer,
  onSkip,
  onRespond,
  onExplain,
}: CoachItemCardProps) {
  // Explanation state
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  // User response state
  const [responseText, setResponseText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Conversation history
  const [conversation, setConversation] = useState<ConversationEntry[]>([]);

  // Latest evaluation result
  const [evaluation, setEvaluation] = useState<EvaluateResponse | null>(null);

  // Expand/collapse for non-active items
  const [expanded, setExpanded] = useState(false);

  const status = STATUS_CONFIG[item.status] || STATUS_CONFIG.open;
  const StatusIcon = status.icon;
  const isTerminal = item.status === "resolved" || item.status === "deferred";
  const showContent = isActive || expanded;

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------

  const handleExplain = async () => {
    setLoadingExplanation(true);
    setExplainError(null);
    try {
      const result = await onExplain(item.id);
      setExplanation(result);
      // Add the question to conversation history
      setConversation((prev) => [
        ...prev,
        { type: "question", text: result.question },
      ]);
    } catch (e) {
      setExplainError(
        e instanceof Error ? e.message : "Failed to load explanation"
      );
    } finally {
      setLoadingExplanation(false);
    }
  };

  const handleSubmitResponse = async () => {
    if (!responseText.trim() || submitting) return;

    const text = responseText.trim();
    setSubmitting(true);

    // Add user response to conversation
    setConversation((prev) => [...prev, { type: "response", text }]);
    setResponseText("");

    try {
      const result = await onRespond(item.id, text);
      setEvaluation(result);

      if (result.complete) {
        // Add suggested resolution to conversation
        setConversation((prev) => [
          ...prev,
          { type: "resolution", text: result.suggested_resolution },
        ]);
      } else if (result.follow_up) {
        // Add follow-up question to conversation
        setConversation((prev) => [
          ...prev,
          { type: "follow_up", text: result.follow_up! },
        ]);
      }
    } catch {
      // Remove the response entry on failure
      setConversation((prev) => prev.slice(0, -1));
      setResponseText(text);
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmitResponse();
    }
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div
      className={`rounded-lg border transition-colors ${
        isActive
          ? "border-blue-500/40 bg-zinc-900/80"
          : isTerminal
          ? "border-zinc-800/50 bg-zinc-900/30 opacity-70"
          : "border-zinc-800 hover:border-zinc-700 bg-zinc-900/50"
      }`}
    >
      {/* Header: always visible */}
      <div
        className={`flex items-start justify-between gap-2 p-4 ${
          !isActive && !isTerminal ? "cursor-pointer" : ""
        }`}
        onClick={
          !isActive && !isTerminal
            ? () => setExpanded(!expanded)
            : undefined
        }
      >
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <StatusIcon
            className={`w-4 h-4 flex-shrink-0 mt-0.5 ${
              status.classes.split(" ")[0]
            }`}
          />
          <div className="flex-1 min-w-0">
            <h4 className="text-sm font-medium text-zinc-200 leading-snug">
              {item.title || "Untitled item"}
            </h4>
            {item.description && !showContent && (
              <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">
                {item.description}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Category badge */}
          {item.category && (
            <Badge
              variant="outline"
              className="text-xs text-zinc-400 border-zinc-600/30"
            >
              {item.category}
            </Badge>
          )}

          {/* Status badge */}
          <Badge variant="outline" className={`text-xs ${status.classes}`}>
            <StatusIcon className="w-3 h-3 mr-1" />
            {status.label}
          </Badge>

          {/* Expand/collapse for non-active */}
          {!isActive && !isTerminal && (
            <Button
              variant="ghost"
              size="icon-xs"
              className="text-zinc-500 hover:text-zinc-300"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Body: expanded content */}
      {showContent && (
        <div className="px-4 pb-4 space-y-3 border-t border-zinc-800">
          {/* Description */}
          {item.description && (
            <p className="text-xs text-zinc-400 leading-relaxed pt-3">
              {item.description}
            </p>
          )}

          {/* Resolution display (for resolved/deferred items) */}
          {item.resolution && (
            <div className="p-2 rounded bg-emerald-500/5 border border-emerald-500/20 text-xs text-emerald-400">
              <span className="font-medium">Resolution:</span>{" "}
              {item.resolution}
            </div>
          )}

          {/* Explain button — only shown if not yet explained and not terminal */}
          {!explanation && !isTerminal && (
            <div className="pt-1">
              {loadingExplanation ? (
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Loading explanation...
                </div>
              ) : explainError ? (
                <div className="text-xs text-red-400">
                  {explainError}
                  <Button
                    variant="ghost"
                    size="xs"
                    className="ml-2 text-zinc-400 hover:text-zinc-300"
                    onClick={handleExplain}
                  >
                    Retry
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                  onClick={handleExplain}
                >
                  <Lightbulb className="w-3 h-3 mr-1" />
                  Explain this finding
                </Button>
              )}
            </div>
          )}

          {/* Explanation section */}
          {explanation && (
            <div className="space-y-2">
              {/* Why this needs attention */}
              <div className="p-2.5 rounded bg-zinc-800/50 border border-zinc-700/50">
                <p className="text-xs font-medium text-zinc-300 mb-1">
                  Why human input is required
                </p>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {explanation.explanation}
                </p>
              </div>

              {/* Recommended approach */}
              <div className="p-2.5 rounded bg-blue-500/5 border border-blue-500/20">
                <p className="text-xs font-medium text-blue-400 mb-1">
                  Recommended approach
                </p>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {explanation.recommended_approach}
                </p>
              </div>

              {/* Exact edit suggestion (if available) */}
              {explanation.exact_edit && (
                <div className="p-2.5 rounded bg-zinc-800/70 border border-zinc-700/50">
                  <p className="text-xs font-medium text-zinc-300 mb-1">
                    Suggested edit
                  </p>
                  <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap overflow-x-auto">
                    {explanation.exact_edit}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Conversation history */}
          {conversation.length > 0 && (
            <div className="space-y-2 pt-1">
              {conversation.map((entry, idx) => (
                <div
                  key={idx}
                  className={`flex items-start gap-2 text-xs ${
                    entry.type === "response"
                      ? "justify-end"
                      : "justify-start"
                  }`}
                >
                  {entry.type !== "response" && (
                    <div className="flex-shrink-0 mt-0.5">
                      {entry.type === "question" ? (
                        <MessageSquare className="w-3 h-3 text-blue-400" />
                      ) : entry.type === "follow_up" ? (
                        <ArrowRight className="w-3 h-3 text-amber-400" />
                      ) : (
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      )}
                    </div>
                  )}
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 leading-relaxed ${
                      entry.type === "response"
                        ? "bg-blue-500/10 text-zinc-300 border border-blue-500/20"
                        : entry.type === "question"
                        ? "bg-zinc-800/70 text-zinc-300 border border-zinc-700/50"
                        : entry.type === "follow_up"
                        ? "bg-amber-500/5 text-zinc-300 border border-amber-500/20"
                        : "bg-emerald-500/5 text-emerald-400 border border-emerald-500/20"
                    }`}
                  >
                    {entry.text}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Evaluation result — suggested resolution when complete */}
          {evaluation?.complete && evaluation.suggested_resolution && (
            <div className="p-2.5 rounded bg-emerald-500/5 border border-emerald-500/20">
              <p className="text-xs font-medium text-emerald-400 mb-1">
                Ready to resolve
              </p>
              <p className="text-xs text-zinc-400 leading-relaxed">
                {evaluation.suggested_resolution}
              </p>
              <Button
                variant="ghost"
                size="xs"
                className="mt-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                onClick={() =>
                  onResolve(item.id, evaluation.suggested_resolution)
                }
              >
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Accept &amp; Resolve
              </Button>
            </div>
          )}

          {/* Response textarea — only when conversation started and not terminal */}
          {explanation && !isTerminal && !evaluation?.complete && (
            <div className="space-y-2 pt-1">
              <textarea
                value={responseText}
                onChange={(e) => setResponseText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your response..."
                rows={3}
                disabled={submitting}
                className="w-full text-xs text-zinc-300 bg-zinc-800/50 border border-zinc-700 rounded-md px-3 py-2 resize-none outline-none focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 placeholder:text-zinc-600 disabled:opacity-50"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-600">
                  {"\u2318"}+Enter to submit
                </span>
                <Button
                  variant="ghost"
                  size="xs"
                  className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                  onClick={handleSubmitResponse}
                  disabled={!responseText.trim() || submitting}
                >
                  {submitting ? (
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  ) : (
                    <Send className="w-3 h-3 mr-1" />
                  )}
                  Submit
                </Button>
              </div>
            </div>
          )}

          {/* Action buttons */}
          {!isTerminal && (
            <div className="flex items-center gap-2 pt-2 border-t border-zinc-800">
              <Button
                variant="ghost"
                size="xs"
                className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                onClick={() => onResolve(item.id)}
              >
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Resolve
              </Button>
              <Button
                variant="ghost"
                size="xs"
                className="text-amber-400 hover:text-amber-300 hover:bg-amber-500/10"
                onClick={() => onDefer(item.id)}
              >
                <Clock className="w-3 h-3 mr-1" />
                Defer
              </Button>
              <Button
                variant="ghost"
                size="xs"
                className="text-zinc-500 hover:text-zinc-400 hover:bg-zinc-500/10"
                onClick={() => onSkip(item.id)}
              >
                <SkipForward className="w-3 h-3 mr-1" />
                Skip
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
