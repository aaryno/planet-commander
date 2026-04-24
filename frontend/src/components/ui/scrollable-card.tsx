"use client";

import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { MoreVertical } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScrollableCardProps {
  title: string;
  icon?: ReactNode;
  menuItems?: Array<{ label: string; href?: string; onClick?: () => void }>;
  stickyHeader?: ReactNode; // Optional sticky content below title (filters, search, etc.)
  children: ReactNode; // Scrollable content
  maxHeight?: string; // Max height for scrollable area (default: full height)
  className?: string;
}

/**
 * Scrollable card component with sticky header and optional sticky filters.
 *
 * Used for cards that need:
 * - Sticky title/header at top
 * - Optional sticky filters/search bar
 * - Scrollable content area with consistent padding
 *
 * Examples: JIRA Summary, Agents list, WX Deployments
 */
export function ScrollableCard({
  title,
  icon,
  menuItems,
  stickyHeader,
  children,
  maxHeight,
  className,
}: ScrollableCardProps) {
  return (
    <Card
      className={cn(
        "border-zinc-800 bg-zinc-900/50 backdrop-blur-sm h-full flex flex-col overflow-hidden",
        className,
      )}
    >
      {/* Sticky Header */}
      <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-3 px-4 border-b border-zinc-800 cursor-move hover:bg-zinc-800/30 transition-colors">
        <div className="flex items-center gap-2">
          {icon && <span className="text-zinc-400">{icon}</span>}
          <CardTitle className="text-sm font-medium text-zinc-200">
            {title}
          </CardTitle>
        </div>

        {menuItems && menuItems.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              >
                <MoreVertical className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-zinc-900 border-zinc-700">
              {menuItems.map((item, i) => (
                <DropdownMenuItem
                  key={i}
                  onClick={item.onClick}
                  className="text-zinc-300 focus:bg-zinc-800 focus:text-zinc-100"
                >
                  {item.href ? (
                    <a href={item.href} target="_blank" rel="noopener noreferrer">
                      {item.label}
                    </a>
                  ) : (
                    item.label
                  )}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </CardHeader>

      {/* Optional Sticky Filters/Search */}
      {stickyHeader && (
        <div className="flex-shrink-0 px-4 pt-3 pb-3 border-b border-zinc-800">
          {stickyHeader}
        </div>
      )}

      {/* Scrollable Content */}
      <CardContent
        className="flex-1 px-4 py-3 overflow-y-auto"
      >
        {children}
      </CardContent>
    </Card>
  );
}
