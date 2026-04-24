"use client";

import { ReactNode, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  MoreVertical,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CardShellProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  menuItems?: Array<{ label: string; href?: string; onClick?: () => void }>;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  className?: string;
}

export function CardShell({
  title,
  icon,
  children,
  menuItems,
  collapsible = true,
  defaultCollapsed = false,
  className,
}: CardShellProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <Card
      className={cn(
        "border-zinc-800 bg-zinc-900/50 backdrop-blur-sm h-full flex flex-col",
        className,
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between py-3 px-4 cursor-move hover:bg-zinc-800/30 transition-colors">
        <div className="flex items-center gap-2">
          {collapsible && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="text-zinc-400 hover:text-zinc-200"
            >
              {collapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          )}
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

      {!collapsed && (
        <CardContent className="flex-1 px-4 pb-4 pt-0 overflow-auto overscroll-contain">{children}</CardContent>
      )}
    </Card>
  );
}
