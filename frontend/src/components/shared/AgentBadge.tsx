"use client";

import { formatTimestampAgo } from "@/lib/time-utils";

interface AgentBadgeProps {
  id: string;
  title: string;
  status: "live" | "idle" | "dead";
  createdAt?: string;
  lastActivity?: string;
  messageCount?: number;
  onClick?: () => void;
}

const STATUS_DOT = {
  live: "bg-green-400 animate-pulse",
  idle: "bg-amber-400",
  dead: "bg-zinc-500",
} as const;

export function AgentBadge({
  title,
  status,
  lastActivity,
  messageCount,
  onClick,
}: AgentBadgeProps) {
  const maxLen = 32;
  const displayTitle = title.length > maxLen ? title.slice(0, maxLen) + "..." : title;

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      className="inline-flex items-center gap-2 text-xs text-zinc-300 hover:text-zinc-100 transition-colors group"
      title={title}
    >
      <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${STATUS_DOT[status]}`} />

      <span className="truncate text-zinc-300 group-hover:text-zinc-100">
        {displayTitle}
      </span>

      {lastActivity && (
        <span className="text-zinc-500 shrink-0">
          {formatTimestampAgo(lastActivity)}
        </span>
      )}

      {messageCount !== undefined && messageCount > 0 && (
        <span className="text-zinc-500 shrink-0">
          {messageCount} prompts
        </span>
      )}
    </button>
  );
}
