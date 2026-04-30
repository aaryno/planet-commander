"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { gitlabUrl } from "@/lib/urls";

interface BranchBadgeProps {
  branch: string;
  targetBranch?: string;
  project?: string;
  compact?: boolean;
}

export function BranchBadge({ branch, targetBranch, project, compact = false }: BranchBadgeProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(branch).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const maxLen = compact ? 24 : 40;
  const displayBranch = branch.length > maxLen ? branch.slice(0, maxLen) + "..." : branch;

  const branchUrl = project
    ? gitlabUrl(`${project}/-/tree/${encodeURIComponent(branch)}`)
    : undefined;

  const branchEl = branchUrl ? (
    <a
      href={branchUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="text-cyan-400 hover:text-cyan-300 transition-colors"
      onClick={(e) => e.stopPropagation()}
      title={branch}
    >
      {displayBranch}
    </a>
  ) : (
    <span className="text-cyan-400" title={branch}>
      {displayBranch}
    </span>
  );

  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
      {branchEl}

      {targetBranch && (
        <>
          <span className="text-zinc-600">&rarr;</span>
          <span className="text-zinc-500">{targetBranch}</span>
        </>
      )}

      <button
        onClick={handleCopy}
        className="text-zinc-600 hover:text-zinc-300 transition-colors"
        title="Copy branch name"
      >
        {copied ? (
          <Check className="h-3 w-3 text-emerald-400" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>
    </span>
  );
}
