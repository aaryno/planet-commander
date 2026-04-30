"use client";

import { useEffect, useState } from "react";
import { ScatterChart } from "lucide-react";

import { PcgTraceCard } from "@/components/cards/PcgTrace";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { api } from "@/lib/api";
import type { PcgStatus } from "@/lib/api";

export default function PcgPage() {
  const [status, setStatus] = useState<PcgStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .pcgStatus()
      .then((s) => {
        if (!cancelled) {
          setStatus(s);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <div className="container mx-auto px-4 py-6 space-y-4">
        <header className="flex items-center gap-3">
          <ScatterChart className="h-6 w-6 text-blue-400" />
          <div>
            <h1 className="text-xl font-semibold">Planet Code Graph</h1>
            <p className="text-xs text-zinc-500">
              Cross-repo knowledge graph: trace alerts → metrics → code → CI → runners → workloads
            </p>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* Status panel: 1 column on lg+ */}
          <div className="lg:col-span-1 h-[600px]">
            <ScrollableCard title="Graph Status" icon={<ScatterChart className="h-4 w-4" />}>
              {loading && <p className="text-xs text-zinc-500">Loading...</p>}
              {error && (
                <p className="text-xs text-red-400">Failed to load: {error}</p>
              )}
              {status && (
                <div className="space-y-3 text-xs">
                  <div className="grid grid-cols-3 gap-2">
                    <Stat label="repos" value={status.repos} />
                    <Stat label="nodes" value={status.nodes} />
                    <Stat label="edges" value={status.edges} />
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] uppercase tracking-wide mb-1">
                      Top node types
                    </div>
                    <ul className="space-y-0.5 font-mono">
                      {status.top_node_types.slice(0, 12).map((nt) => (
                        <li
                          key={nt.node_type}
                          className="flex justify-between text-[11px]"
                        >
                          <span className="text-zinc-300 truncate">
                            {nt.node_type}
                          </span>
                          <span className="text-zinc-500">
                            {nt.n.toLocaleString()}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <div className="text-zinc-500 text-[11px] uppercase tracking-wide mb-1">
                      Top edge types
                    </div>
                    <ul className="space-y-0.5 font-mono">
                      {status.top_edge_types.slice(0, 12).map((et) => (
                        <li
                          key={et.edge_type}
                          className="flex justify-between text-[11px]"
                        >
                          <span className="text-zinc-300 truncate">
                            {et.edge_type}
                          </span>
                          <span className="text-zinc-500">
                            {et.n.toLocaleString()}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </ScrollableCard>
          </div>

          {/* Trace card: 3 columns on lg+ */}
          <div className="lg:col-span-3 h-[600px]">
            <PcgTraceCard />
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/50 px-2 py-1.5 text-center">
      <div className="text-[10px] text-zinc-500 uppercase">{label}</div>
      <div className="text-sm font-semibold text-zinc-200">
        {value.toLocaleString()}
      </div>
    </div>
  );
}
