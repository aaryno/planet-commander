"use client";

import { V2DocsMetadata } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { BookOpen, FileText, Layers } from "lucide-react";

interface V2DocsPanelProps {
  v2Docs: V2DocsMetadata;
}

export function V2DocsPanel({ v2Docs }: V2DocsPanelProps) {
  const budgetPercent = Math.round((v2Docs.total_tokens / v2Docs.budget_limit) * 100);

  // Group layers by type
  const layer0 = v2Docs.layers.filter(l => l.layer === 0);
  const layer1 = v2Docs.layers.filter(l => l.layer === 1);
  const layer2 = v2Docs.layers.filter(l => l.layer === 2);

  return (
    <div className="space-y-4">
      {/* Token Budget Header */}
      <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-zinc-400">Token Budget</h3>
          <Badge
            variant={v2Docs.budget_exceeded ? "destructive" : "outline"}
            className={v2Docs.budget_exceeded ? "" : "text-emerald-400 border-emerald-600/50"}
          >
            {v2Docs.total_tokens.toLocaleString()} / {v2Docs.budget_limit.toLocaleString()} ({budgetPercent}%)
          </Badge>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              v2Docs.budget_exceeded
                ? "bg-red-500"
                : budgetPercent > 80
                  ? "bg-amber-500"
                  : "bg-emerald-500"
            }`}
            style={{ width: `${Math.min(budgetPercent, 100)}%` }}
          />
        </div>

        {v2Docs.budget_exceeded && (
          <p className="text-xs text-red-400 mt-2">
            Budget exceeded - consider reducing loaded documentation
          </p>
        )}
      </div>

      {/* Layer 0: Core Index */}
      {layer0.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers className="w-3 h-3 text-zinc-500" />
            <h3 className="text-xs font-semibold text-zinc-400">Layer 0: Core Index</h3>
          </div>
          {layer0.map((doc) => (
            <div
              key={doc.name}
              className="p-2 rounded border border-zinc-800 bg-zinc-900/30 flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <FileText className="w-3 h-3 text-blue-400" />
                <span className="text-xs font-mono text-zinc-300">{doc.name}</span>
              </div>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {doc.tokens.toLocaleString()} tokens
              </Badge>
            </div>
          ))}
        </div>
      )}

      {/* Layer 1: Project Indexes */}
      {layer1.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers className="w-3 h-3 text-zinc-500" />
            <h3 className="text-xs font-semibold text-zinc-400">Layer 1: Project Indexes</h3>
          </div>
          {layer1.map((doc) => (
            <div
              key={doc.name}
              className="p-2 rounded border border-zinc-800 bg-zinc-900/30 flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <BookOpen className="w-3 h-3 text-cyan-400" />
                <span className="text-xs font-mono text-zinc-300">{doc.name}</span>
              </div>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {doc.tokens.toLocaleString()} tokens
              </Badge>
            </div>
          ))}
        </div>
      )}

      {/* Layer 2: Tool Quick-Refs */}
      {layer2.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers className="w-3 h-3 text-zinc-500" />
            <h3 className="text-xs font-semibold text-zinc-400">Layer 2: Tool Quick-Refs</h3>
          </div>
          {layer2.map((doc) => (
            <div
              key={doc.name}
              className="p-2 rounded border border-zinc-800 bg-zinc-900/30 flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <FileText className="w-3 h-3 text-violet-400" />
                <span className="text-xs font-mono text-zinc-300">{doc.name}</span>
              </div>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {doc.tokens.toLocaleString()} tokens
              </Badge>
            </div>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wide">Total Docs</p>
            <p className="text-lg font-semibold text-zinc-200 mt-1">{v2Docs.layers.length}</p>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wide">Total Tokens</p>
            <p className="text-lg font-semibold text-zinc-200 mt-1">{v2Docs.total_tokens.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-wide">Budget Used</p>
            <p className={`text-lg font-semibold mt-1 ${
              v2Docs.budget_exceeded ? "text-red-400" : budgetPercent > 80 ? "text-amber-400" : "text-emerald-400"
            }`}>
              {budgetPercent}%
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
