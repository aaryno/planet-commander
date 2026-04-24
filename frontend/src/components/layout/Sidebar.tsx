"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Box,
  Cpu,
  Briefcase,
  Clock,
  Bot,
  GitPullRequest,
  LayoutGrid,
  AlertTriangle,
  Shield,
  Settings,
  RefreshCw,
  PanelLeftClose,
  PanelLeftOpen,
  ShoppingCart,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCart } from "@/lib/cart";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/health", label: "Health", icon: Shield, color: "text-emerald-400" },
  { href: "/review", label: "Review", icon: GitPullRequest, color: "text-cyan-400" },
  { href: "/wx", label: "WX", icon: Box, color: "text-blue-400" },
  { href: "/g4", label: "G4", icon: Cpu, color: "text-violet-400" },
  { href: "/jobs", label: "Jobs", icon: Briefcase, color: "text-amber-400" },
  { href: "/temporal", label: "Temporal", icon: Clock, color: "text-emerald-400" },
  { href: "/infrastructure", label: "Infrastructure", icon: Server, color: "text-orange-400" },
  { href: "/warnings", label: "Warnings", icon: AlertTriangle, color: "text-red-400" },
  { href: "/sync", label: "Sync", icon: RefreshCw, color: "text-cyan-400" },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/multiview", label: "Multi-View", icon: LayoutGrid, color: "text-amber-400" },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { count: cartCount, setDrawerOpen } = useCart();

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r border-zinc-800 bg-zinc-950 py-4 transition-all duration-200",
        collapsed ? "w-14 px-2" : "w-56 px-3",
      )}
    >
      {/* Header */}
      <div className={cn("mb-6 flex items-center", collapsed ? "justify-center" : "justify-between px-3")}>
        {!collapsed && (
          <div>
            <h1 className="text-lg font-bold text-zinc-100">Planet Ops</h1>
            <p className="text-xs text-zinc-500">Compute Platform</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-zinc-500 hover:text-zinc-300 p-1 rounded hover:bg-zinc-800 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center rounded-md py-2 text-sm transition-colors",
                collapsed ? "justify-center px-2" : "gap-3 px-3",
                isActive
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200",
              )}
              title={collapsed ? item.label : undefined}
            >
              <item.icon
                className={cn("h-4 w-4 shrink-0", item.color && isActive && item.color)}
              />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Context Cart */}
      <div className={cn("border-t border-zinc-800 pt-3 mt-3", collapsed ? "px-1" : "px-3")}>
        <button
          onClick={() => setDrawerOpen(true)}
          className={cn(
            "flex items-center rounded-md py-2 text-sm transition-colors w-full relative",
            collapsed ? "justify-center px-2" : "gap-3 px-3",
            "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200",
          )}
          title={collapsed ? `Context Cart (${cartCount})` : undefined}
        >
          <ShoppingCart className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Context Cart</span>}
          {cartCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-cyan-500 px-1 text-[10px] font-medium text-white">
              {cartCount}
            </span>
          )}
        </button>
      </div>

      <div className={cn("mt-auto border-t border-zinc-800 pt-3", collapsed ? "px-1" : "px-3")}>
        <p className="text-xs text-zinc-600 text-center">{collapsed ? "v0.1" : "v0.1.0"}</p>
      </div>
    </aside>
  );
}
