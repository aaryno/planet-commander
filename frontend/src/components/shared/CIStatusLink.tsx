"use client";

import { Loader2 } from "lucide-react";

interface CIStatusLinkProps {
  status: "success" | "failed" | "running" | "pending" | "canceled" | null;
  pipelineUrl?: string;
  failingJobUrl?: string;
  label?: boolean;
}

const STATUS_CONFIG = {
  success: { icon: "✅", text: "passing", color: "text-emerald-400" },
  failed: { icon: "❌", text: "failing", color: "text-red-400" },
  running: { icon: null, text: "running", color: "text-amber-400" },
  pending: { icon: "–", text: "pending", color: "text-zinc-500" },
  canceled: { icon: "–", text: "canceled", color: "text-zinc-500" },
} as const;

export function CIStatusLink({ status, pipelineUrl, failingJobUrl, label = false }: CIStatusLinkProps) {
  if (!status) {
    return <span className="text-zinc-600 text-xs">–</span>;
  }

  const config = STATUS_CONFIG[status];
  const url = status === "failed" ? (failingJobUrl || pipelineUrl) : pipelineUrl;

  const content = (
    <span className={`inline-flex items-center gap-1 text-xs ${config.color}`}>
      {status === "running" ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <span>{config.icon}</span>
      )}
      {label && <span>{config.text}</span>}
    </span>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="hover:opacity-80 transition-opacity"
        onClick={(e) => e.stopPropagation()}
      >
        {content}
      </a>
    );
  }

  return content;
}
