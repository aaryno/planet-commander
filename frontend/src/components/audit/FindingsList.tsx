"use client";

import { useState, useMemo } from "react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FindingCard } from "./FindingCard";
import { ClipboardCheck, Filter, ShieldAlert } from "lucide-react";
import type { AuditFinding } from "@/lib/api";

interface FindingsListProps {
  findings: AuditFinding[];
  title?: string;
  onResolve?: (findingId: string) => void;
  onDefer?: (findingId: string) => void;
  onReject?: (findingId: string) => void;
  /** When true, renders without the ScrollableCard wrapper (for embedding) */
  embedded?: boolean;
}

export function FindingsList({
  findings,
  title = "Findings",
  onResolve,
  onDefer,
  onReject,
  embedded = false,
}: FindingsListProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [blockingOnly, setBlockingOnly] = useState(false);

  // Derive unique categories from the data
  const categories = useMemo(() => {
    const cats = new Set(findings.map((f) => f.category));
    return Array.from(cats).sort();
  }, [findings]);

  // Severity counts
  const severityCounts = useMemo(() => {
    const counts = { error: 0, warning: 0, info: 0 };
    for (const f of findings) {
      if (f.severity in counts) {
        counts[f.severity as keyof typeof counts]++;
      }
    }
    return counts;
  }, [findings]);

  // Filtered findings
  const filtered = useMemo(() => {
    return findings.filter((f) => {
      if (categoryFilter !== "all" && f.category !== categoryFilter) return false;
      if (severityFilter !== "all" && f.severity !== severityFilter) return false;
      if (statusFilter !== "all" && f.status !== statusFilter) return false;
      if (blockingOnly && !f.blocking) return false;
      return true;
    });
  }, [findings, categoryFilter, severityFilter, statusFilter, blockingOnly]);

  const hasActiveFilters =
    categoryFilter !== "all" ||
    severityFilter !== "all" ||
    statusFilter !== "all" ||
    blockingOnly;

  const filterHeader = (
    <div className="space-y-2">
      {/* Count summary */}
      <div className="flex items-center gap-2 flex-wrap">
        {severityCounts.error > 0 && (
          <Badge className="text-xs border-0 bg-red-500/20 text-red-400">
            {severityCounts.error} error{severityCounts.error !== 1 ? "s" : ""}
          </Badge>
        )}
        {severityCounts.warning > 0 && (
          <Badge className="text-xs border-0 bg-amber-500/20 text-amber-400">
            {severityCounts.warning} warning{severityCounts.warning !== 1 ? "s" : ""}
          </Badge>
        )}
        {severityCounts.info > 0 && (
          <Badge className="text-xs border-0 bg-blue-500/20 text-blue-400">
            {severityCounts.info} info
          </Badge>
        )}
        {hasActiveFilters && (
          <span className="text-xs text-zinc-500 ml-auto">
            {filtered.length} of {findings.length} shown
          </span>
        )}
      </div>

      {/* Filter controls */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter className="w-3 h-3 text-zinc-500 flex-shrink-0" />

        {/* Category */}
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded px-2 py-1 outline-none focus:border-zinc-600"
        >
          <option value="all">All categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>

        {/* Severity */}
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded px-2 py-1 outline-none focus:border-zinc-600"
        >
          <option value="all">All severities</option>
          <option value="error">Error</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>

        {/* Status */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-xs bg-zinc-800 text-zinc-300 border border-zinc-700 rounded px-2 py-1 outline-none focus:border-zinc-600"
        >
          <option value="all">All statuses</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
          <option value="deferred">Deferred</option>
          <option value="rejected">Rejected</option>
        </select>

        {/* Blocking toggle */}
        <Button
          variant={blockingOnly ? "default" : "ghost"}
          size="xs"
          onClick={() => setBlockingOnly(!blockingOnly)}
          className={
            blockingOnly
              ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
              : "text-zinc-500 hover:text-zinc-300"
          }
        >
          <ShieldAlert className="w-3 h-3 mr-1" />
          Blocking
        </Button>

        {/* Clear filters */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="xs"
            className="text-zinc-500 hover:text-zinc-300 ml-auto"
            onClick={() => {
              setCategoryFilter("all");
              setSeverityFilter("all");
              setStatusFilter("all");
              setBlockingOnly(false);
            }}
          >
            Clear
          </Button>
        )}
      </div>
    </div>
  );

  const content = (
    <div className="space-y-2">
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-zinc-500">
          <ClipboardCheck className="w-8 h-8 mb-2 text-zinc-600" />
          <p className="text-sm">
            {findings.length === 0
              ? "No findings to display"
              : "No findings match the current filters"}
          </p>
        </div>
      ) : (
        filtered.map((finding) => (
          <FindingCard
            key={finding.id}
            finding={finding}
            onResolve={onResolve}
            onDefer={onDefer}
            onReject={onReject}
          />
        ))
      )}
    </div>
  );

  if (embedded) {
    return (
      <div className="space-y-3">
        {filterHeader}
        {content}
      </div>
    );
  }

  return (
    <ScrollableCard
      title={title}
      icon={<ClipboardCheck className="w-4 h-4" />}
      stickyHeader={filterHeader}
    >
      {content}
    </ScrollableCard>
  );
}
