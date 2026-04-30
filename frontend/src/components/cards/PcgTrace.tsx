"use client";

import { useCallback, useState } from "react";
import { ScatterChart, Search } from "lucide-react";

import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { PcgTrace, PcgTraceStep } from "@/lib/api";

const SUGGESTED_QUERIES = [
  "jobs - prod - jobs success rate ratio - lt 40-perc for 10m",
  "wx/wx",
  "jobs/jobs",
  "go-lint-v1",
];

interface PcgTraceCardProps {
  /** Optional initial query to trace on mount. */
  initialName?: string;
}

/**
 * PCG Trace card — calls /api/pcg/full-trace and renders the upstream + downstream
 * tree from any starting node (alert, metric, function, repo, ci_pipeline, ci_job).
 *
 * For incident response: paste an alert name → see the metric, the code that
 * emits it, the CI pipeline that builds the code, the runner that runs the
 * pipeline, and any deploys that ship the result.
 */
export function PcgTraceCard({ initialName = "" }: PcgTraceCardProps) {
  const [name, setName] = useState(initialName);
  const [submittedName, setSubmittedName] = useState(initialName);
  const [depth, setDepth] = useState(6);
  const [fanout, setFanout] = useState(15);
  const [trace, setTrace] = useState<PcgTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runTrace = useCallback(
    async (queryName: string) => {
      if (!queryName.trim()) return;
      setLoading(true);
      setError(null);
      try {
        const result = await api.pcgFullTrace(queryName.trim(), depth, fanout);
        setTrace(result);
        setSubmittedName(queryName.trim());
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setTrace(null);
      } finally {
        setLoading(false);
      }
    },
    [depth, fanout],
  );

  const stickyHeader = (
    <div className="space-y-2 pt-2">
      <div className="flex gap-2">
        <Input
          placeholder="Alert name, metric, function, repo, ci_pipeline..."
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") runTrace(name);
          }}
          className="text-xs"
        />
        <Button
          size="sm"
          variant="default"
          onClick={() => runTrace(name)}
          disabled={loading || !name.trim()}
          className="h-9"
        >
          <Search className="h-3 w-3 mr-1" />
          {loading ? "Tracing..." : "Trace"}
        </Button>
      </div>
      <div className="flex items-center gap-3 text-xs text-zinc-500">
        <label className="flex items-center gap-1">
          depth
          <input
            type="number"
            min={1}
            max={10}
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="w-12 bg-zinc-800 border border-zinc-700 rounded px-1 text-zinc-200"
          />
        </label>
        <label className="flex items-center gap-1">
          fanout
          <input
            type="number"
            min={1}
            max={100}
            value={fanout}
            onChange={(e) => setFanout(Number(e.target.value))}
            className="w-12 bg-zinc-800 border border-zinc-700 rounded px-1 text-zinc-200"
          />
        </label>
        {submittedName && trace && (
          <span className="text-zinc-600">
            ({countNodes(trace.upstream) + countNodes(trace.downstream) - 1} nodes)
          </span>
        )}
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title="PCG Trace"
      icon={<ScatterChart className="h-4 w-4" />}
      stickyHeader={stickyHeader}
    >
      {error && (
        <div className="rounded border border-red-900 bg-red-950/40 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {!error && !trace && !loading && (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500">
            Enter an alert name, metric, function, repo, or CI pipeline. The
            trace walks upstream (what triggers this) and downstream (what
            depends on this) following PCG&apos;s known edge types.
          </p>
          <p className="text-xs text-zinc-600">Try:</p>
          <div className="flex flex-wrap gap-1">
            {SUGGESTED_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => {
                  setName(q);
                  runTrace(q);
                }}
                className="text-[11px] px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
              >
                {q.length > 50 ? q.slice(0, 47) + "..." : q}
              </button>
            ))}
          </div>
        </div>
      )}

      {trace && (
        <div className="space-y-3 text-xs font-mono">
          <div className="flex items-center gap-2 pb-2 border-b border-zinc-800">
            <Badge className="bg-blue-500/20 text-blue-400 hover:bg-blue-500/20">
              {trace.start.node_type}
            </Badge>
            <span className="text-zinc-200 truncate">
              {trace.start.short_name || trace.start.qualified_name}
            </span>
            {trace.start.repo_name && (
              <span className="text-zinc-500 text-[11px]">
                ({trace.start.repo_name})
              </span>
            )}
          </div>

          {trace.upstream.children.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-zinc-500 mb-1">
                ↑ Upstream (what triggers / depends-on this)
              </div>
              <TraceTree steps={trace.upstream.children} />
            </div>
          )}

          {trace.downstream.children.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-zinc-500 mb-1">
                ↓ Downstream (what this triggers / depends-on)
              </div>
              <TraceTree steps={trace.downstream.children} />
            </div>
          )}

          {trace.upstream.children.length === 0 &&
            trace.downstream.children.length === 0 && (
              <p className="text-zinc-500 text-[11px]">
                (no chain edges from this node — try a different starting point or increase depth)
              </p>
            )}
        </div>
      )}
    </ScrollableCard>
  );
}

function countNodes(step: PcgTraceStep): number {
  return 1 + step.children.reduce((acc, c) => acc + countNodes(c), 0);
}

function TraceTree({ steps }: { steps: PcgTraceStep[] }) {
  return (
    <ul className="space-y-0.5">
      {steps.map((step, idx) => (
        <TraceTreeNode key={`${step.node.id}-${idx}`} step={step} />
      ))}
    </ul>
  );
}

function TraceTreeNode({ step }: { step: PcgTraceStep }) {
  const truncated = step.node.node_type === "_truncated";
  if (truncated) {
    return (
      <li className="pl-4 text-zinc-600 text-[11px]">
        └─ {step.node.qualified_name}
      </li>
    );
  }
  return (
    <li>
      <div className="flex items-center gap-1 truncate">
        <span className="text-zinc-600">└─</span>
        {step.edge_type && (
          <span className="text-amber-500/80 text-[10px]">
            [{step.edge_type}]
          </span>
        )}
        <Badge
          variant="outline"
          className="border-zinc-700 text-zinc-400 text-[10px] px-1 py-0 h-4"
        >
          {step.node.node_type}
        </Badge>
        <span className="text-zinc-200 truncate">
          {step.node.short_name || step.node.qualified_name}
        </span>
        {step.node.repo_name && (
          <span className="text-zinc-500 text-[10px] flex-shrink-0">
            ({step.node.repo_name})
          </span>
        )}
      </div>
      {step.children.length > 0 && (
        <div className="pl-4 border-l border-zinc-800 ml-1">
          <TraceTree steps={step.children} />
        </div>
      )}
    </li>
  );
}
