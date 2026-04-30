"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
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
  FolderKanban,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCart } from "@/lib/cart";
import { api } from "@/lib/api";
import type { ProjectConfig } from "@/lib/api";

const STATIC_NAV_TOP = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/health", label: "Health", icon: Shield, color: "text-emerald-400" },
  { href: "/review", label: "Review", icon: GitPullRequest, color: "text-cyan-400" },
];

const STATIC_NAV_BOTTOM = [
  { href: "/infrastructure", label: "Infrastructure", icon: Server, color: "text-orange-400" },
  { href: "/warnings", label: "Warnings", icon: AlertTriangle, color: "text-red-400" },
  { href: "/sync", label: "Sync", icon: RefreshCw, color: "text-cyan-400" },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/multiview", label: "Multi-View", icon: LayoutGrid, color: "text-amber-400" },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavLink({
  href,
  label,
  icon: Icon,
  color,
  colorHex,
  collapsed,
  active,
}: {
  href: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  color?: string;
  colorHex?: string;
  collapsed: boolean;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center rounded-md py-2 text-sm transition-colors",
        collapsed ? "justify-center px-2" : "gap-3 px-3",
        active
          ? "bg-zinc-800 text-zinc-100"
          : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200",
      )}
      title={collapsed ? label : undefined}
    >
      {Icon ? (
        <Icon className={cn("h-4 w-4 shrink-0", color && active && color)} />
      ) : colorHex ? (
        <div
          className="h-3 w-3 rounded-full shrink-0"
          style={{ backgroundColor: colorHex }}
        />
      ) : (
        <FolderKanban className="h-4 w-4 shrink-0" />
      )}
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { count: cartCount, setDrawerOpen } = useCart();
  const [projects, setProjects] = useState<ProjectConfig[]>([]);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => {});
  }, []);

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
            <h1 className="text-lg font-bold text-zinc-100">Commander</h1>
            <p className="text-xs text-zinc-500">Planet Ops</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-zinc-500 hover:text-zinc-300 p-1 rounded hover:bg-zinc-800 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1">
        {/* Top static nav */}
        {STATIC_NAV_TOP.map((item) => (
          <NavLink
            key={item.href}
            {...item}
            collapsed={collapsed}
            active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)}
          />
        ))}

        {/* Projects section */}
        {!collapsed && projects.length > 0 && (
          <div className="text-[10px] uppercase tracking-wider text-zinc-600 px-3 pt-3 pb-1">
            Projects
          </div>
        )}
        {collapsed && projects.length > 0 && <div className="border-t border-zinc-800 my-1" />}

        {projects.map((p) => {
          const href = `/projects/${p.key}`;
          const active = pathname.startsWith(href) || pathname === `/${p.key}`;
          return (
            <NavLink
              key={p.key}
              href={href}
              label={p.name}
              colorHex={p.color}
              collapsed={collapsed}
              active={active}
            />
          );
        })}

        {/* Add project */}
        <NavLink
          href="/projects/new"
          label="Add Project"
          icon={Plus}
          collapsed={collapsed}
          active={pathname === "/projects/new"}
          color="text-zinc-600"
        />

        {/* Separator */}
        {!collapsed && <div className="border-t border-zinc-800 my-1" />}
        {collapsed && <div className="border-t border-zinc-800 my-1" />}

        {/* Bottom static nav */}
        {STATIC_NAV_BOTTOM.map((item) => (
          <NavLink
            key={item.href}
            {...item}
            collapsed={collapsed}
            active={pathname.startsWith(item.href)}
          />
        ))}
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
        <p className="text-xs text-zinc-600 text-center">{collapsed ? "v0.2" : "v0.2.0"}</p>
      </div>
    </aside>
  );
}
