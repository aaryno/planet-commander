"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExpandableRowProps {
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  className?: string;
}

export function ExpandableRow({
  summary,
  children,
  defaultExpanded = false,
  onToggle,
  className,
}: ExpandableRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    onToggle?.(next);
  };

  return (
    <div
      className={cn(
        "rounded-lg border border-zinc-800 transition-colors",
        expanded && "bg-zinc-900/80 border-zinc-700",
        className
      )}
    >
      <div
        className="flex items-center gap-2 cursor-pointer hover:bg-zinc-800/40 rounded-lg px-3 py-2 transition-colors"
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
      >
        <div className="flex-1 min-w-0">{summary}</div>
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-zinc-500 transition-transform duration-200",
            expanded && "rotate-90"
          )}
        />
      </div>
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-in-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          {expanded && (
            <div className="px-3 pb-3 pt-1 border-t border-zinc-800/60">
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
