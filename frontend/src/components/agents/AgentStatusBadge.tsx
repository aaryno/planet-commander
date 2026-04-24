"use client";

const STATUS_CONFIG = {
  live: {
    dot: "bg-green-400",
    text: "text-green-400",
    bg: "bg-green-400/10",
    border: "border-green-400/30",
    label: "LIVE",
  },
  idle: {
    dot: "bg-yellow-400",
    text: "text-yellow-400",
    bg: "bg-yellow-400/10",
    border: "border-yellow-400/30",
    label: "IDLE",
  },
  dead: {
    dot: "bg-zinc-500",
    text: "text-zinc-500",
    bg: "bg-zinc-500/10",
    border: "border-zinc-500/30",
    label: "DEAD",
  },
} as const;

export function AgentStatusBadge({ status }: { status: "live" | "idle" | "dead" }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${config.bg} ${config.text} ${config.border}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot} ${status === "live" ? "animate-pulse" : ""}`} />
      {config.label}
    </span>
  );
}
