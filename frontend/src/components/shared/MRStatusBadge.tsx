"use client";

import { CIStatusLink } from "./CIStatusLink";

interface MRStatusBadgeProps {
  iid: number;
  status: "opened" | "closed" | "merged";
  pipelineStatus?: "success" | "failed" | "running" | "pending" | "canceled" | null;
  pipelineUrl?: string;
  failingJobUrl?: string;
  hasConflicts?: boolean;
  unresolvedCount?: number;
  approved?: boolean;
  url?: string;
  project?: string;
  compact?: boolean;
}

const MR_STATUS_COLORS = {
  opened: "text-emerald-400",
  closed: "text-zinc-500",
  merged: "text-violet-400",
} as const;

export function MRStatusBadge({
  iid,
  status,
  pipelineStatus,
  pipelineUrl,
  failingJobUrl,
  hasConflicts = false,
  unresolvedCount = 0,
  approved = false,
  url,
  compact = false,
}: MRStatusBadgeProps) {
  const iidEl = url ? (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-zinc-400 hover:text-zinc-200 transition-colors"
      onClick={(e) => e.stopPropagation()}
    >
      !{iid}
    </a>
  ) : (
    <span className="font-mono text-zinc-400">!{iid}</span>
  );

  return (
    <span className="inline-flex items-center gap-1.5 text-xs flex-wrap">
      {iidEl}
      <span className={MR_STATUS_COLORS[status]}>{status}</span>

      {pipelineStatus && (
        <CIStatusLink
          status={pipelineStatus}
          pipelineUrl={pipelineUrl}
          failingJobUrl={failingJobUrl}
          label={!compact}
        />
      )}

      {!compact && (
        <>
          {unresolvedCount > 0 ? (
            <span className="text-red-400">
              {unresolvedCount} unresolved
            </span>
          ) : unresolvedCount === 0 && pipelineStatus ? (
            <span className="text-zinc-500">0 unresolved</span>
          ) : null}

          {approved && <span className="text-emerald-400">approved</span>}

          {hasConflicts && (
            <span className="text-amber-400">rebase needed</span>
          )}
        </>
      )}

      {compact && hasConflicts && (
        <span className="text-amber-400">!</span>
      )}
    </span>
  );
}
