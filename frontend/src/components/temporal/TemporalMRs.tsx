"use client";

import { useCallback } from "react";
import { GitPullRequest, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { usePoll } from "@/lib/polling";
import { api, TemporalMRsResponse } from "@/lib/api";

function PipelineIcon({ status }: { status: string }) {
  if (status === "success" || status === "passed") {
    return <CheckCircle className="h-3 w-3 text-emerald-400" />;
  }
  if (status === "failed") {
    return <XCircle className="h-3 w-3 text-red-400" />;
  }
  if (status === "running") {
    return <Loader2 className="h-3 w-3 text-yellow-400 animate-spin" />;
  }
  return <span className="h-3 w-3 rounded-full bg-zinc-600 inline-block" />;
}

export function TemporalMRs() {
  const fetcher = useCallback(() => api.temporalMRs(), []);
  const { data, loading, error } = usePoll<TemporalMRsResponse>(fetcher, 120_000);

  return (
    <ScrollableCard
      title={`Merge Requests${data?.total ? ` (${data.total})` : ""}`}
      icon={<GitPullRequest className="h-4 w-4" />}
    >
      {loading && <p className="text-xs text-zinc-500">Loading...</p>}
      {error && <p className="text-xs text-red-400">Failed to load MRs</p>}
      {data && (
        <div className="space-y-2">
          {data.open_mrs.length === 0 && (
            <p className="text-xs text-zinc-500">No open MRs</p>
          )}
          {data.open_mrs.map((mr) => (
            <div key={mr.iid} className="text-xs py-0.5">
              <div className="flex items-start gap-2">
                <a
                  href={mr.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-500 font-mono shrink-0 hover:text-emerald-400 transition-colors"
                >
                  !{mr.iid}
                </a>
                <a
                  href={mr.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-300 truncate hover:text-emerald-400 transition-colors"
                >
                  {mr.title}
                </a>
              </div>
              {mr.branch && (
                <span className="text-[10px] text-zinc-600 ml-8 font-mono">{mr.branch}</span>
              )}
            </div>
          ))}

          {/* Main branch pipeline */}
          <div className="flex items-center gap-2 text-xs pt-1 border-t border-zinc-800">
            <PipelineIcon status={data.main_pipeline?.status ?? "unknown"} />
            <span className="text-zinc-400">
              main: {data.main_pipeline?.status ?? "unknown"}
            </span>
          </div>
        </div>
      )}
    </ScrollableCard>
  );
}
