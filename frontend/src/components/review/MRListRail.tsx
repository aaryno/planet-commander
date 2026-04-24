"use client";

import { useState, useMemo } from "react";
import { Search, RefreshCw, CheckCircle, AlertCircle, Loader2, Circle } from "lucide-react";
import type { DetailedMR } from "@/lib/api";
import { formatHoursAgo } from "@/lib/time-utils";
import { extractJiraKey } from "@/lib/utils";

// --- Reused logic from OpenMRs.tsx ---

const MR_TYPES = [
  { key: "feat", label: "feat", color: "text-emerald-400", dot: "bg-emerald-400" },
  { key: "fix", label: "fix", color: "text-red-400", dot: "bg-red-400" },
  { key: "docs", label: "docs", color: "text-blue-400", dot: "bg-blue-400" },
  { key: "chore", label: "chore", color: "text-zinc-400", dot: "bg-zinc-400" },
  { key: "refactor", label: "refactor", color: "text-purple-400", dot: "bg-purple-400" },
  { key: "test", label: "test", color: "text-yellow-400", dot: "bg-yellow-400" },
  { key: "ci", label: "ci", color: "text-cyan-400", dot: "bg-cyan-400" },
  { key: "deploy", label: "deploy", color: "text-orange-400", dot: "bg-orange-400" },
  { key: "build", label: "build", color: "text-amber-400", dot: "bg-amber-400" },
  { key: "perf", label: "perf", color: "text-lime-400", dot: "bg-lime-400" },
  { key: "style", label: "style", color: "text-pink-400", dot: "bg-pink-400" },
  { key: "revert", label: "revert", color: "text-rose-400", dot: "bg-rose-400" },
] as const;

const MR_STATUSES = [
  { key: "draft", label: "draft", color: "text-zinc-400 border-zinc-600/50 bg-zinc-500/10" },
  { key: "unreviewed", label: "unreviewed", color: "text-yellow-400 border-yellow-600/50 bg-yellow-500/10" },
  { key: "needs-review", label: "needs-review", color: "text-amber-400 border-amber-600/50 bg-amber-500/10" },
  { key: "reviewed", label: "reviewed", color: "text-emerald-400 border-emerald-600/50 bg-emerald-500/10" },
] as const;

function extractMRType(title: string): string | null {
  const match = title.match(/^(feat|fix|docs|chore|refactor|test|ci|deploy|build|perf|style|revert)(\(|:)/i);
  return match ? match[1].toLowerCase() : null;
}

function cleanTitle(title: string): string {
  let cleaned = title.replace(/^Draft:\s*/i, "");
  cleaned = cleaned.replace(/\[DRAFT\]\s*/gi, "");
  cleaned = cleaned.replace(/^(feat|fix|docs|chore|refactor|test|ci|deploy|build|perf|style|revert)(\([^)]*\))?:\s*/i, "");
  return cleaned.trim();
}

// extractJiraKey imported from @/lib/utils

function getMRStatus(mr: DetailedMR): string {
  if (mr.is_draft) return "draft";
  if (!mr.reviews || mr.reviews.length === 0) return "unreviewed";
  if (mr.needs_review) return "needs-review";
  return "reviewed";
}

// --- Component ---

interface MRListRailProps {
  mrs: DetailedMR[];
  loading: boolean;
  selectedId: string | null; // "project-iid"
  onSelect: (mr: DetailedMR) => void;
  onRefresh: () => void;
}

export function MRListRail({ mrs, loading, selectedId, onSelect, onRefresh }: MRListRailProps) {
  const [search, setSearch] = useState("");
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [activeStatuses, setActiveStatuses] = useState<Set<string>>(new Set());

  // Filter MRs
  const filtered = useMemo(() => {
    let result = [...mrs];

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(mr => {
        const jira = extractJiraKey(mr.title, mr.branch);
        return (
          mr.title.toLowerCase().includes(q) ||
          mr.author.toLowerCase().includes(q) ||
          mr.branch.toLowerCase().includes(q) ||
          (jira && jira.toLowerCase().includes(q)) ||
          `!${mr.iid}`.includes(q)
        );
      });
    }

    // Type filter (empty = show all)
    if (activeTypes.size > 0) {
      result = result.filter(mr => {
        const type = extractMRType(mr.title) || "other";
        return activeTypes.has(type);
      });
    }

    // Status filter (empty = show all)
    if (activeStatuses.size > 0) {
      result = result.filter(mr => activeStatuses.has(getMRStatus(mr)));
    }

    return result;
  }, [mrs, search, activeTypes, activeStatuses]);

  const toggleType = (key: string) => {
    setActiveTypes(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleStatus = (key: string) => {
    setActiveStatuses(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Header */}
      <div className="shrink-0 px-3 py-2 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-zinc-200">MRs</span>
          <span className="text-[10px] text-zinc-500 font-mono">
            {filtered.length}/{mrs.length}
          </span>
        </div>
        <button
          onClick={onRefresh}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors"
         
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Search */}
      <div className="shrink-0 px-3 py-2 border-b border-zinc-800/50">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-zinc-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by title, author, branch..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-300 pl-7 pr-2 py-1.5 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600 transition-colors"
          />
        </div>
      </div>

      {/* Quick filters */}
      <div className="shrink-0 px-3 py-2 border-b border-zinc-800/50 space-y-1.5">
        {/* Type filters */}
        <div className="flex flex-wrap gap-1">
          {MR_TYPES.map(type => (
            <button
              key={type.key}
              onClick={() => toggleType(type.key)}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
                activeTypes.size === 0 || activeTypes.has(type.key)
                  ? `${type.color} border-current/30 bg-current/10 opacity-100`
                  : "text-zinc-600 border-zinc-700/50 bg-zinc-800/30 opacity-50"
              } hover:opacity-100`}
            >
              {type.label}
            </button>
          ))}
        </div>
        {/* Status filters */}
        <div className="flex flex-wrap gap-1">
          {MR_STATUSES.map(status => (
            <button
              key={status.key}
              onClick={() => toggleStatus(status.key)}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors ${
                activeStatuses.size === 0 || activeStatuses.has(status.key)
                  ? `${status.color}`
                  : "text-zinc-600 border-zinc-700/50 bg-zinc-800/30 opacity-50"
              } hover:opacity-80`}
            >
              {status.label}
            </button>
          ))}
        </div>
      </div>

      {/* MR List */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {loading && mrs.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />
          </div>
        )}

        {!loading && mrs.length === 0 && (
          <p className="text-xs text-zinc-500 text-center py-8">No open MRs</p>
        )}

        {mrs.length > 0 && filtered.length === 0 && (
          <p className="text-xs text-zinc-500 text-center py-8">No MRs match filters</p>
        )}

        {filtered.map(mr => {
          const id = `${mr.project}-${mr.iid}`;
          const isSelected = id === selectedId;
          const type = extractMRType(mr.title);
          const status = getMRStatus(mr);
          const typeInfo = MR_TYPES.find(t => t.key === type);
          const jiraKey = extractJiraKey(mr.title, mr.branch);

          return (
            <button
              key={id}
              onClick={() => onSelect(mr)}
              className={`w-full text-left px-3 py-2 border-l-2 transition-colors ${
                isSelected
                  ? "bg-blue-500/10 border-l-blue-500"
                  : "border-l-transparent hover:bg-zinc-800/50"
              }`}
            >
              {/* Row 1: MR number + type dot + title */}
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-[10px] text-zinc-500 font-mono shrink-0">
                  !{mr.iid}
                </span>
                {typeInfo && (
                  <span
                    className={`shrink-0 w-1.5 h-1.5 rounded-full ${typeInfo.dot}`}
                    title={type || undefined}
                  />
                )}
                <span className={`text-xs truncate ${mr.is_draft ? "text-zinc-500" : "text-zinc-200"}`}>
                  {cleanTitle(mr.title)}
                </span>
              </div>

              {/* Row 2: author + age + CI + review status */}
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`text-[10px] truncate ${mr.is_mine ? "text-emerald-400" : "text-zinc-500"}`}>
                  {mr.author}
                </span>
                <span className="text-[10px] text-zinc-600">
                  {formatHoursAgo(mr.age_created_hours)}
                </span>
                <span className="ml-auto flex items-center gap-1.5 shrink-0">
                  {/* CI status */}
                  <CIIndicator mr={mr} />
                  {/* Review status */}
                  <ReviewIndicator status={status} />
                </span>
              </div>

              {/* Row 3 (optional): JIRA key */}
              {jiraKey && (
                <div className="mt-0.5">
                  <span className="text-[10px] text-cyan-500 font-mono">{jiraKey}</span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// --- Sub-components ---

function CIIndicator({ mr }: { mr: DetailedMR }) {
  // Use the state field if available for CI info, otherwise infer from labels
  const state = mr.state?.toLowerCase();
  if (state === "merged") {
    return <CheckCircle className="h-3 w-3 text-purple-400" />;
  }

  // Check labels for CI hints
  const labels = mr.labels ?? [];
  const hasCIFail = labels.some(l => l.toLowerCase().includes("ci-fail"));
  const hasCIPass = labels.some(l => l.toLowerCase().includes("ci-pass"));

  if (hasCIFail) {
    return <Circle className="h-2.5 w-2.5 fill-red-400 text-red-400" />;
  }
  if (hasCIPass) {
    return <Circle className="h-2.5 w-2.5 fill-emerald-400 text-emerald-400" />;
  }

  // Default: neutral indicator (no CI info available)
  return <Circle className="h-2.5 w-2.5 fill-zinc-600 text-zinc-600" />;
}

function ReviewIndicator({ status }: { status: string }) {
  switch (status) {
    case "draft":
      return <span className="text-[10px] text-zinc-500 font-medium">DFT</span>;
    case "unreviewed":
      return <span className="text-[10px] text-yellow-400 font-medium">NEW</span>;
    case "needs-review":
      return <AlertCircle className="h-3 w-3 text-amber-400" />;
    case "reviewed":
      return <CheckCircle className="h-3 w-3 text-emerald-400" />;
    default:
      return null;
  }
}
