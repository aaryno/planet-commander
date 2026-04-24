"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CheckCircle2,
  ChevronDown,
  Play,
  RefreshCw,
  Wrench,
  HelpCircle,
  Zap,
} from "lucide-react";
import type { CTAState } from "@/lib/api";

/**
 * Style configuration mapping CTA style keys to Tailwind classes.
 *
 * Color semantics (from AUDIT-SYSTEM-SPEC.md section 4.2):
 *   primary-green  -> emerald  (ready / all clear)
 *   primary-blue   -> blue     (auto-fixable / analyze)
 *   primary-amber  -> amber    (human input needed)
 *   primary-default -> zinc    (fallback / re-analyze)
 */
const STYLE_MAP: Record<
  string,
  {
    button: string;
    badge: string;
    icon: typeof Play;
  }
> = {
  "primary-green": {
    button:
      "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30",
    badge: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    icon: CheckCircle2,
  },
  "primary-blue": {
    button:
      "bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30",
    badge: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    icon: Zap,
  },
  "primary-amber": {
    button:
      "bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30",
    badge: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    icon: HelpCircle,
  },
  "primary-default": {
    button:
      "bg-zinc-700/50 text-zinc-300 border border-zinc-600 hover:bg-zinc-700/70",
    badge: "bg-zinc-700/50 text-zinc-300 border-zinc-600",
    icon: RefreshCw,
  },
};

/**
 * Icon mapping for known action types.
 */
const ACTION_ICONS: Record<string, typeof Play> = {
  analyze: Play,
  ready: CheckCircle2,
  "fix-it": Wrench,
  "guide-me": HelpCircle,
  "re-analyze": RefreshCw,
  "view-previous": RefreshCw,
};

interface CTABarProps {
  /** CTA state derived from the audit system. */
  cta: CTAState;
  /** Called when the user clicks the primary or a secondary action. */
  onAction: (action: string) => void;
}

/**
 * Call-to-action bar for the audit system.
 *
 * Renders a color-coded primary action button with an optional dropdown
 * for secondary actions. Used inside ContextPanel and audit views.
 */
export function CTABar({ cta, onAction }: CTABarProps) {
  const styleConfig = STYLE_MAP[cta.style] || STYLE_MAP["primary-default"];
  const PrimaryIcon = ACTION_ICONS[cta.action] || styleConfig.icon;

  const hasSecondary = cta.secondary_actions.length > 0;

  return (
    <div className="flex items-center gap-2 p-3 rounded-lg bg-zinc-900/50 border border-zinc-800">
      {/* Primary action button */}
      <Button
        variant="ghost"
        size="sm"
        className={`flex-1 justify-start gap-2 h-auto py-2 px-3 ${styleConfig.button}`}
        onClick={() => onAction(cta.action)}
      >
        <PrimaryIcon className="w-4 h-4 flex-shrink-0" />
        <div className="flex flex-col items-start text-left min-w-0">
          <span className="text-sm font-medium leading-tight">
            {cta.label}
          </span>
          <span className="text-xs opacity-70 leading-tight truncate max-w-full">
            {cta.subtext}
          </span>
        </div>
      </Button>

      {/* Secondary actions dropdown */}
      {hasSecondary && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="flex-shrink-0 text-zinc-400 hover:text-zinc-300 hover:bg-zinc-800"
            >
              <ChevronDown className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[180px]">
            {cta.secondary_actions.map((sa) => {
              const SecondaryIcon =
                ACTION_ICONS[sa.action] || RefreshCw;
              return (
                <DropdownMenuItem
                  key={sa.action}
                  onClick={() => onAction(sa.action)}
                  className="cursor-pointer"
                >
                  <SecondaryIcon className="w-4 h-4 mr-2 text-zinc-400" />
                  {sa.label}
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
