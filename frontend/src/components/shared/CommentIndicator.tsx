"use client";

import { MessageSquare } from "lucide-react";
import { formatTimestampAgo } from "@/lib/time-utils";

interface CommentIndicatorProps {
  count: number;
  unresolvedCount?: number;
  lastActivityAt?: string;
}

export function CommentIndicator({ count, unresolvedCount, lastActivityAt }: CommentIndicatorProps) {
  if (count === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-zinc-600">
        <MessageSquare className="h-3 w-3" />
        No comments
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <MessageSquare className="h-3 w-3 text-zinc-500" />

      <span className="text-zinc-400">
        {count} {count === 1 ? "comment" : "comments"}
      </span>

      {unresolvedCount !== undefined && unresolvedCount > 0 && (
        <span className="text-red-400">
          {unresolvedCount} unresolved
        </span>
      )}

      {lastActivityAt && (
        <span className="text-zinc-600">
          last {formatTimestampAgo(lastActivityAt)}
        </span>
      )}
    </span>
  );
}
