"use client";

import { useCallback, useState, useMemo, useEffect } from "react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CoachItemCard } from "./CoachItemCard";
import {
  MessageSquare,
  RefreshCw,
  CheckCircle2,
  CircleDot,
  Clock,
  Ban,
  AlertCircle,
  PartyPopper,
  Loader2,
} from "lucide-react";
import type {
  CoachSession,
  CoachItem,
  ExplainResponse,
  EvaluateResponse,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Status icon mapping for the sidebar item list
// ---------------------------------------------------------------------------

const ITEM_STATUS_ICONS: Record<string, typeof CircleDot> = {
  open: CircleDot,
  in_progress: MessageSquare,
  answered: MessageSquare,
  resolved: CheckCircle2,
  deferred: Clock,
  blocked: Ban,
};

const ITEM_STATUS_COLORS: Record<string, string> = {
  open: "text-zinc-400",
  in_progress: "text-blue-400",
  answered: "text-amber-400",
  resolved: "text-emerald-400",
  deferred: "text-zinc-500",
  blocked: "text-red-400",
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoachPanelProps {
  targetType: string;
  targetId: string;
}

export function CoachPanel({ targetType, targetId }: CoachPanelProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeItemId, setActiveItemId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // -----------------------------------------------------------------------
  // Create or retrieve the session on mount
  // -----------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    async function initSession() {
      setCreating(true);
      setCreateError(null);
      try {
        const session = await api.coachCreateSession(targetType, targetId);
        if (!cancelled) {
          setSessionId(session.id);
          setActiveItemId(session.active_item_id);
        }
      } catch (e) {
        if (!cancelled) {
          setCreateError(
            e instanceof Error ? e.message : "Failed to create session"
          );
        }
      } finally {
        if (!cancelled) setCreating(false);
      }
    }

    initSession();
    return () => {
      cancelled = true;
    };
  }, [targetType, targetId]);

  // -----------------------------------------------------------------------
  // Poll session state
  // -----------------------------------------------------------------------

  const fetcher = useCallback(async () => {
    if (!sessionId) return null;
    return api.coachGetSession(sessionId);
  }, [sessionId]);

  const {
    data: session,
    loading,
    error,
    refresh,
  } = usePoll<CoachSession | null>(fetcher, 30_000, !!sessionId);

  // Sync active item from polled data
  useEffect(() => {
    if (session?.active_item_id && !activeItemId) {
      setActiveItemId(session.active_item_id);
    }
  }, [session?.active_item_id, activeItemId]);

  // -----------------------------------------------------------------------
  // Derived data
  // -----------------------------------------------------------------------

  const items = session?.items ?? [];
  const totalCount = session?.total_count ?? 0;
  const completedCount = session?.completed_count ?? 0;
  const progressPct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
  const allDone = totalCount > 0 && completedCount >= totalCount;

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of items) {
      counts[item.status] = (counts[item.status] || 0) + 1;
    }
    return counts;
  }, [items]);

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------

  const handleResolve = useCallback(
    async (itemId: string, resolution?: string) => {
      if (!sessionId) return;
      try {
        const result = await api.coachTransitionItem(
          sessionId,
          itemId,
          "resolved",
          resolution
        );
        if (result.all_done) {
          setActiveItemId(null);
        } else if (result.next_item) {
          setActiveItemId(result.next_item.id);
        }
        refresh();
      } catch {
        // Refresh to get consistent state
        refresh();
      }
    },
    [sessionId, refresh]
  );

  const handleDefer = useCallback(
    async (itemId: string) => {
      if (!sessionId) return;
      try {
        const result = await api.coachTransitionItem(
          sessionId,
          itemId,
          "deferred"
        );
        if (result.all_done) {
          setActiveItemId(null);
        } else if (result.next_item) {
          setActiveItemId(result.next_item.id);
        }
        refresh();
      } catch {
        refresh();
      }
    },
    [sessionId, refresh]
  );

  const handleSkip = useCallback(
    (itemId: string) => {
      // Skip moves to the next open item without changing status
      const currentIdx = items.findIndex((i) => i.id === itemId);
      const nextItem = items.find(
        (i, idx) =>
          idx > currentIdx &&
          i.status !== "resolved" &&
          i.status !== "deferred"
      );
      if (nextItem) {
        setActiveItemId(nextItem.id);
      }
    },
    [items]
  );

  const handleRespond = useCallback(
    async (itemId: string, response: string): Promise<EvaluateResponse> => {
      if (!sessionId) throw new Error("No session");
      return api.coachRespondItem(sessionId, itemId, response);
    },
    [sessionId]
  );

  const handleExplain = useCallback(
    async (itemId: string): Promise<ExplainResponse> => {
      if (!sessionId) throw new Error("No session");
      return api.coachExplainItem(sessionId, itemId);
    },
    [sessionId]
  );

  const handleItemClick = useCallback(
    (itemId: string) => {
      const item = items.find((i) => i.id === itemId);
      if (item && item.status !== "resolved" && item.status !== "deferred") {
        setActiveItemId(itemId);
      }
    },
    [items]
  );

  // -----------------------------------------------------------------------
  // Render: loading / error / create states
  // -----------------------------------------------------------------------

  if (creating) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin mr-2 text-zinc-400" />
        <span className="text-sm text-zinc-400">
          Initializing coach session...
        </span>
      </div>
    );
  }

  if (createError) {
    return (
      <div className="p-4 rounded border border-red-800 bg-red-900/20">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <p className="text-sm text-red-400">Failed to start coach session</p>
        </div>
        <p className="text-xs text-red-500">{createError}</p>
      </div>
    );
  }

  if (!session && loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-zinc-400" />
        <span className="text-sm text-zinc-400">Loading session...</span>
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="p-4 rounded border border-red-800 bg-red-900/20">
        <p className="text-sm text-red-400">Failed to load session</p>
        <p className="text-xs text-red-500 mt-1">{error.message}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          className="mt-2"
        >
          Retry
        </Button>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Render: empty state
  // -----------------------------------------------------------------------

  if (totalCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
        <CheckCircle2 className="w-8 h-8 mb-2 text-zinc-600" />
        <p className="text-sm font-medium">No items to review</p>
        <p className="text-xs mt-1">
          This session has no coaching items yet.
        </p>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Render: all done state
  // -----------------------------------------------------------------------

  if (allDone) {
    return (
      <div className="space-y-4">
        <div className="flex flex-col items-center justify-center py-8 text-zinc-400">
          <PartyPopper className="w-8 h-8 mb-2 text-emerald-400" />
          <p className="text-sm font-medium text-emerald-400">
            All items resolved
          </p>
          <p className="text-xs mt-1 text-zinc-500">
            {completedCount} of {totalCount} items completed
          </p>
        </div>

        {/* Progress bar */}
        <ProgressBar completed={completedCount} total={totalCount} />

        {/* Summary of resolved items */}
        <div className="space-y-1.5 pt-2">
          {items.map((item) => (
            <CompactItemRow key={item.id} item={item} isActive={false} />
          ))}
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Render: main walkthrough UI
  // -----------------------------------------------------------------------

  const stickyHeader = (
    <div className="space-y-3">
      {/* Progress bar */}
      <ProgressBar completed={completedCount} total={totalCount} />

      {/* Status counts */}
      <div className="flex items-center gap-2 flex-wrap">
        {statusCounts.open ? (
          <Badge
            variant="outline"
            className="text-xs text-zinc-400 border-zinc-600/30"
          >
            {statusCounts.open} open
          </Badge>
        ) : null}
        {statusCounts.in_progress ? (
          <Badge
            variant="outline"
            className="text-xs text-blue-400 border-blue-500/30"
          >
            {statusCounts.in_progress} in progress
          </Badge>
        ) : null}
        {statusCounts.answered ? (
          <Badge
            variant="outline"
            className="text-xs text-amber-400 border-amber-500/30"
          >
            {statusCounts.answered} answered
          </Badge>
        ) : null}
        {statusCounts.resolved ? (
          <Badge
            variant="outline"
            className="text-xs text-emerald-400 border-emerald-500/30"
          >
            {statusCounts.resolved} resolved
          </Badge>
        ) : null}
        {statusCounts.deferred ? (
          <Badge
            variant="outline"
            className="text-xs text-zinc-500 border-zinc-600/30"
          >
            {statusCounts.deferred} deferred
          </Badge>
        ) : null}
      </div>

      {/* Item list / sidebar — clickable items */}
      <div className="space-y-0.5 border-t border-zinc-800 pt-2">
        {items.map((item) => (
          <CompactItemRow
            key={item.id}
            item={item}
            isActive={item.id === activeItemId}
            onClick={() => handleItemClick(item.id)}
          />
        ))}
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title={`Coach: ${targetId}`}
      icon={<MessageSquare className="w-4 h-4" />}
      menuItems={[{ label: "Refresh", onClick: refresh }]}
      stickyHeader={stickyHeader}
    >
      <div className="space-y-3">
        {/* Active item card */}
        {activeItemId && (
          <div>
            {items
              .filter((item) => item.id === activeItemId)
              .map((item) => (
                <CoachItemCard
                  key={item.id}
                  item={item}
                  isActive={true}
                  onResolve={handleResolve}
                  onDefer={handleDefer}
                  onSkip={handleSkip}
                  onRespond={handleRespond}
                  onExplain={handleExplain}
                />
              ))}
          </div>
        )}

        {/* Remaining items (non-active, non-terminal) */}
        {items
          .filter(
            (item) =>
              item.id !== activeItemId &&
              item.status !== "resolved" &&
              item.status !== "deferred"
          )
          .map((item) => (
            <CoachItemCard
              key={item.id}
              item={item}
              isActive={false}
              onResolve={handleResolve}
              onDefer={handleDefer}
              onSkip={handleSkip}
              onRespond={handleRespond}
              onExplain={handleExplain}
            />
          ))}

        {/* Completed items (collapsed) */}
        {items.filter(
          (item) =>
            item.status === "resolved" || item.status === "deferred"
        ).length > 0 && (
          <div className="pt-2 border-t border-zinc-800">
            <p className="text-xs text-zinc-500 mb-2">
              Completed ({completedCount})
            </p>
            {items
              .filter(
                (item) =>
                  item.status === "resolved" || item.status === "deferred"
              )
              .map((item) => (
                <CoachItemCard
                  key={item.id}
                  item={item}
                  isActive={false}
                  onResolve={handleResolve}
                  onDefer={handleDefer}
                  onSkip={handleSkip}
                  onRespond={handleRespond}
                  onExplain={handleExplain}
                />
              ))}
          </div>
        )}
      </div>
    </ScrollableCard>
  );
}

// ---------------------------------------------------------------------------
// Progress bar sub-component
// ---------------------------------------------------------------------------

function ProgressBar({
  completed,
  total,
}: {
  completed: number;
  total: number;
}) {
  const pct = total > 0 ? (completed / total) * 100 : 0;
  const barColor =
    pct >= 100
      ? "bg-emerald-500"
      : pct >= 50
      ? "bg-amber-500"
      : "bg-red-500";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-400">Progress</span>
        <span className="text-zinc-300 font-medium">
          {completed}/{total}
        </span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compact item row for sidebar / item list
// ---------------------------------------------------------------------------

function CompactItemRow({
  item,
  isActive,
  onClick,
}: {
  item: CoachItem;
  isActive: boolean;
  onClick?: () => void;
}) {
  const Icon = ITEM_STATUS_ICONS[item.status] || CircleDot;
  const color = ITEM_STATUS_COLORS[item.status] || "text-zinc-400";
  const isTerminal = item.status === "resolved" || item.status === "deferred";

  return (
    <div
      className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors ${
        isActive
          ? "bg-blue-500/10 border border-blue-500/20"
          : isTerminal
          ? "opacity-50"
          : onClick
          ? "hover:bg-zinc-800/50 cursor-pointer"
          : ""
      }`}
      onClick={!isTerminal ? onClick : undefined}
    >
      <Icon className={`w-3 h-3 flex-shrink-0 ${color}`} />
      <span
        className={`flex-1 truncate ${
          isActive
            ? "text-zinc-200 font-medium"
            : isTerminal
            ? "text-zinc-500 line-through"
            : "text-zinc-400"
        }`}
      >
        {item.title || "Untitled"}
      </span>
      {item.blocking && (
        <span className="text-red-400 text-[10px] font-medium">BLOCK</span>
      )}
    </div>
  );
}
