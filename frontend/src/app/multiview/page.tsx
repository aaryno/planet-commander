"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  LayoutGrid,
  Rows3,
  AppWindow,
  PanelTop,
  Trash2,
  X,
  Minus,
  Maximize2,
  Palette,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  ChevronsUp,
  ChevronsDown,
  Search,
  Loader2,
  GripVertical,
  ShoppingCart,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useCart } from "@/lib/cart";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/api";
import { ChatView } from "@/components/agents/ChatView";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ViewMode = "tiled" | "stacked" | "tabs" | "floating";

interface AMVWindow {
  id: string;
  agentId?: string;
  color: string;
  createdAt: string;
  // Tab rename
  customTitle?: string;
  // Free-floating state
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  zIndex?: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLORS = [
  { name: "Blue", value: "#3b82f6" },
  { name: "Violet", value: "#8b5cf6" },
  { name: "Emerald", value: "#10b981" },
  { name: "Amber", value: "#f59e0b" },
  { name: "Red", value: "#ef4444" },
  { name: "Cyan", value: "#06b6d4" },
  { name: "Pink", value: "#ec4899" },
  { name: "Zinc", value: "#71717a" },
];

const VIEW_MODES: { mode: ViewMode; label: string; icon: typeof LayoutGrid }[] = [
  { mode: "tiled", label: "Tiled", icon: LayoutGrid },
  { mode: "stacked", label: "Stacked", icon: Rows3 },
  { mode: "tabs", label: "Tabs", icon: PanelTop },
  { mode: "floating", label: "Free-floating", icon: AppWindow },
];

const STORAGE_KEY = "amv-agents";
const MODE_KEY = "amv-mode";

function generateId(): string {
  return `amv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// ---------------------------------------------------------------------------
// ColorPicker
// ---------------------------------------------------------------------------

function ColorPicker({
  currentColor,
  onSelect,
}: {
  currentColor: string;
  onSelect: (color: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="p-1 rounded hover:bg-zinc-700 transition-colors"
        title="Change color"
      >
        <Palette className="h-3 w-3 text-zinc-400" />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg p-2 flex gap-1.5 shadow-xl">
          {COLORS.map((c) => (
            <button
              key={c.value}
              onClick={() => {
                onSelect(c.value);
                setOpen(false);
              }}
              className="w-5 h-5 rounded-full transition-transform hover:scale-125 ring-offset-1 ring-offset-zinc-800"
              style={{
                backgroundColor: c.value,
                boxShadow:
                  currentColor === c.value
                    ? `0 0 0 2px #18181b, 0 0 0 4px ${c.value}`
                    : "none",
              }}
              title={c.name}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AgentWindow — wraps ChatView with AMV-specific chrome
// ---------------------------------------------------------------------------

interface AgentWindowProps {
  window: AMVWindow;
  agent: Agent | null;
  loading: boolean;
  onRemove: () => void;
  onColorChange: (color: string) => void;
  onMinimize: () => void;
  onHide: (id: string) => void;
  minimized: boolean;
  // Floating mode extras
  floatingControls?: React.ReactNode;
  onHeaderDoubleClick?: () => void;
  onDragStart?: (e: React.MouseEvent) => void;
  style?: React.CSSProperties;
  className?: string;
}

function AgentWindow({
  window: win,
  agent,
  loading,
  onRemove,
  onColorChange,
  onMinimize,
  onHide,
  minimized,
  floatingControls,
  onHeaderDoubleClick,
  onDragStart,
  style,
  className = "",
}: AgentWindowProps) {
  const title = win.customTitle || agent?.title || "Loading...";

  return (
    <div
      className={`bg-zinc-900 rounded-lg border border-zinc-800 flex flex-col overflow-hidden ${className}`}
      style={{
        borderTopColor: win.color,
        borderTopWidth: "3px",
        height: minimized ? "44px" : undefined,
        ...style,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 bg-zinc-900/80 shrink-0 select-none"
        onDoubleClick={onHeaderDoubleClick}
        onMouseDown={onDragStart}
        style={onDragStart ? { cursor: "grab" } : undefined}
      >
        <div
          className="w-2 h-2 rounded-full shrink-0"
          style={{ backgroundColor: win.color }}
        />
        <span className="text-sm font-medium text-zinc-200 truncate">
          {title}
        </span>

        {agent && (
          <div className="flex items-center gap-1 overflow-hidden">
            {agent.jira_key && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 font-mono shrink-0">
                {agent.jira_key}
              </span>
            )}
            {agent.git_branch && agent.git_branch !== "HEAD" && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400 font-mono truncate max-w-[100px] shrink-0">
                {agent.git_branch.split("/").pop()}
              </span>
            )}
          </div>
        )}

        <div className="flex-1" />

        <div className="flex items-center gap-0.5 shrink-0">
          {floatingControls}
          <ColorPicker currentColor={win.color} onSelect={onColorChange} />
          <button
            onClick={onMinimize}
            className="p-1 rounded hover:bg-zinc-700 transition-colors"
            title={minimized ? "Expand" : "Minimize"}
          >
            {minimized ? (
              <Maximize2 className="h-3 w-3 text-zinc-400" />
            ) : (
              <Minus className="h-3 w-3 text-zinc-400" />
            )}
          </button>
          <button
            onClick={onRemove}
            className="p-1 rounded hover:bg-red-900/30 transition-colors"
            title="Remove"
          >
            <X className="h-3 w-3 text-zinc-500 hover:text-red-400" />
          </button>
        </div>
      </div>

      {/* Chat area */}
      {!minimized && (
        <div className="flex-1 min-h-0 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-5 w-5 text-zinc-500 animate-spin" />
            </div>
          )}
          {!loading && agent && (
            <ChatView
              agent={agent}
              className="h-full"
              onHide={onHide}
              hideAMVButton
              source="amv"
            />
          )}
          {!loading && !agent && (
            <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
              Agent not found
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TiledView — responsive grid
// ---------------------------------------------------------------------------

function TiledView({
  windows,
  agentCache,
  loadingAgents,
  minimized,
  onRemove,
  onColorChange,
  onMinimize,
  onHide,
}: {
  windows: AMVWindow[];
  agentCache: Record<string, Agent>;
  loadingAgents: Set<string>;
  minimized: Set<string>;
  onRemove: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
  onMinimize: (id: string) => void;
  onHide: (agentId: string) => void;
}) {
  const count = windows.length;
  let cols: number;
  let rows: number;
  if (count <= 1) { cols = 1; rows = 1; }
  else if (count === 2) { cols = 2; rows = 1; }
  else if (count <= 4) { cols = 2; rows = 2; }
  else if (count <= 6) { cols = 3; rows = 2; }
  else { cols = 3; rows = Math.ceil(count / 3); }

  return (
    <div
      className="grid gap-2 h-full"
      style={{
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gridTemplateRows: rows <= 2
          ? `repeat(${rows}, 1fr)`
          : `repeat(${rows}, minmax(350px, 1fr))`,
        overflow: rows > 2 ? "auto" : undefined,
      }}
    >
      {windows.map((win) => (
        <AgentWindow
          key={win.id}
          window={win}
          agent={win.agentId ? agentCache[win.agentId] || null : null}
          loading={win.agentId ? loadingAgents.has(win.agentId) : false}
          onRemove={() => onRemove(win.id)}
          onColorChange={(c) => onColorChange(win.id, c)}
          onMinimize={() => onMinimize(win.id)}
          onHide={onHide}
          minimized={minimized.has(win.id)}
          style={{ height: minimized.has(win.id) ? "44px" : "100%" }}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// StackedView — vertical stack (original behavior)
// ---------------------------------------------------------------------------

function StackedView({
  windows,
  agentCache,
  loadingAgents,
  minimized,
  onRemove,
  onColorChange,
  onMinimize,
  onHide,
}: {
  windows: AMVWindow[];
  agentCache: Record<string, Agent>;
  loadingAgents: Set<string>;
  minimized: Set<string>;
  onRemove: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
  onMinimize: (id: string) => void;
  onHide: (agentId: string) => void;
}) {
  const expandedCount = windows.filter(w => !minimized.has(w.id)).length;

  return (
    <div
      className="grid gap-2 h-full"
      style={{
        gridTemplateRows: expandedCount <= 2
          ? `repeat(${windows.length}, 1fr)`
          : `repeat(${windows.length}, minmax(500px, 1fr))`,
        gridTemplateColumns: "1fr",
        overflow: expandedCount > 2 ? "auto" : undefined,
      }}
    >
      {windows.map((win) => (
        <AgentWindow
          key={win.id}
          window={win}
          agent={win.agentId ? agentCache[win.agentId] || null : null}
          loading={win.agentId ? loadingAgents.has(win.agentId) : false}
          onRemove={() => onRemove(win.id)}
          onColorChange={(c) => onColorChange(win.id, c)}
          onMinimize={() => onMinimize(win.id)}
          onHide={onHide}
          minimized={minimized.has(win.id)}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TabsView — tabbed interface
// ---------------------------------------------------------------------------

function TabsView({
  windows,
  agentCache,
  loadingAgents,
  activeTabId,
  onSetActiveTab,
  onRemove,
  onColorChange,
  onHide,
  onRenameTab,
}: {
  windows: AMVWindow[];
  agentCache: Record<string, Agent>;
  loadingAgents: Set<string>;
  activeTabId: string | null;
  onSetActiveTab: (id: string) => void;
  onRemove: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
  onHide: (agentId: string) => void;
  onRenameTab: (id: string, title: string) => void;
}) {
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const editRef = useRef<HTMLInputElement>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (editingTabId) editRef.current?.focus();
  }, [editingTabId]);

  const startRename = (win: AMVWindow) => {
    const agent = win.agentId ? agentCache[win.agentId] : null;
    setEditValue(win.customTitle || agent?.title || "");
    setEditingTabId(win.id);
  };

  const commitRename = () => {
    if (editingTabId && editValue.trim()) {
      onRenameTab(editingTabId, editValue.trim());
    }
    setEditingTabId(null);
  };

  const activeWin = windows.find(w => w.id === activeTabId) || windows[0];

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-zinc-800 bg-zinc-900/50 overflow-x-auto shrink-0">
        {windows.map((win) => {
          const agent = win.agentId ? agentCache[win.agentId] || null : null;
          const isActive = win.id === (activeWin?.id);
          const title = win.customTitle || agent?.title || "Loading...";

          return (
            <div
              key={win.id}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm cursor-pointer border-b-2 transition-colors shrink-0 max-w-[200px] group ${
                isActive
                  ? "border-b-current text-zinc-100 bg-zinc-800/50"
                  : "border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30"
              }`}
              style={isActive ? { borderBottomColor: win.color } : undefined}
              onClick={() => onSetActiveTab(win.id)}
              onMouseDown={() => {
                longPressTimer.current = setTimeout(() => startRename(win), 500);
              }}
              onMouseUp={() => {
                if (longPressTimer.current) clearTimeout(longPressTimer.current);
              }}
              onMouseLeave={() => {
                if (longPressTimer.current) clearTimeout(longPressTimer.current);
              }}
            >
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: win.color }}
              />
              {editingTabId === win.id ? (
                <input
                  ref={editRef}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename();
                    if (e.key === "Escape") setEditingTabId(null);
                  }}
                  className="bg-zinc-700 text-zinc-200 text-sm px-1 py-0 rounded border border-zinc-600 w-full min-w-[60px] outline-none"
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="truncate text-xs">{title}</span>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(win.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-zinc-700 transition-opacity shrink-0"
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Active tab content */}
      {activeWin && (
        <div className="flex-1 min-h-0">
          <AgentWindow
            key={activeWin.id}
            window={activeWin}
            agent={activeWin.agentId ? agentCache[activeWin.agentId] || null : null}
            loading={activeWin.agentId ? loadingAgents.has(activeWin.agentId) : false}
            onRemove={() => onRemove(activeWin.id)}
            onColorChange={(c) => onColorChange(activeWin.id, c)}
            onMinimize={() => {}}
            onHide={onHide}
            minimized={false}
            style={{ height: "100%", borderTopWidth: "0px" }}
          />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FloatingView — absolute positioned, draggable, resizable windows
// ---------------------------------------------------------------------------

function FloatingView({
  windows,
  agentCache,
  loadingAgents,
  minimized,
  onRemove,
  onColorChange,
  onMinimize,
  onHide,
  onUpdateWindow,
}: {
  windows: AMVWindow[];
  agentCache: Record<string, Agent>;
  loadingAgents: Set<string>;
  minimized: Set<string>;
  onRemove: (id: string) => void;
  onColorChange: (id: string, color: string) => void;
  onMinimize: (id: string) => void;
  onHide: (agentId: string) => void;
  onUpdateWindow: (id: string, updates: Partial<AMVWindow>) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragState = useRef<{
    windowId: string;
    type: "move" | "resize";
    startX: number;
    startY: number;
    origX: number;
    origY: number;
    origW: number;
    origH: number;
  } | null>(null);

  const getMaxZ = () => Math.max(1, ...windows.map(w => w.zIndex || 1));

  const bringForward = (id: string) => {
    const win = windows.find(w => w.id === id);
    if (!win) return;
    onUpdateWindow(id, { zIndex: (win.zIndex || 1) + 1 });
  };

  const sendBackward = (id: string) => {
    const win = windows.find(w => w.id === id);
    if (!win) return;
    onUpdateWindow(id, { zIndex: Math.max(1, (win.zIndex || 1) - 1) });
  };

  const bringToFront = (id: string) => {
    onUpdateWindow(id, { zIndex: getMaxZ() + 1 });
  };

  const sendToBack = (id: string) => {
    onUpdateWindow(id, { zIndex: 1 });
  };

  const handleDoubleClickHeader = (id: string) => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    onUpdateWindow(id, { height: rect.height - 8, y: 0 });
  };

  const handleDragStart = (id: string, e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button, input")) return;
    e.preventDefault();
    const win = windows.find(w => w.id === id);
    if (!win) return;
    bringToFront(id);
    dragState.current = {
      windowId: id,
      type: "move",
      startX: e.clientX,
      startY: e.clientY,
      origX: win.x || 0,
      origY: win.y || 0,
      origW: win.width || 500,
      origH: win.height || 400,
    };
  };

  const handleResizeStart = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const win = windows.find(w => w.id === id);
    if (!win) return;
    dragState.current = {
      windowId: id,
      type: "resize",
      startX: e.clientX,
      startY: e.clientY,
      origX: win.x || 0,
      origY: win.y || 0,
      origW: win.width || 500,
      origH: win.height || 400,
    };
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!dragState.current) return;
      const { windowId, type, startX, startY, origX, origY, origW, origH } = dragState.current;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;

      if (type === "move") {
        onUpdateWindow(windowId, { x: origX + dx, y: origY + dy });
      } else {
        onUpdateWindow(windowId, {
          width: Math.max(300, origW + dx),
          height: Math.max(200, origH + dy),
        });
      }
    };

    const handleMouseUp = () => {
      dragState.current = null;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [onUpdateWindow]);

  // Initialize positions for new windows
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    windows.forEach((win, i) => {
      if (win.x === undefined) {
        onUpdateWindow(win.id, {
          x: 20 + i * 30,
          y: 20 + i * 30,
          width: Math.min(600, rect.width - 60),
          height: Math.min(500, rect.height - 60),
          zIndex: i + 1,
        });
      }
    });
  }, [windows.length]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={containerRef} className="relative h-full overflow-hidden">
      {windows.map((win) => {
        const isMin = minimized.has(win.id);
        return (
          <div
            key={win.id}
            className="absolute"
            style={{
              left: win.x || 0,
              top: win.y || 0,
              width: win.width || 500,
              height: isMin ? 44 : (win.height || 400),
              zIndex: win.zIndex || 1,
            }}
          >
            <AgentWindow
              window={win}
              agent={win.agentId ? agentCache[win.agentId] || null : null}
              loading={win.agentId ? loadingAgents.has(win.agentId) : false}
              onRemove={() => onRemove(win.id)}
              onColorChange={(c) => onColorChange(win.id, c)}
              onMinimize={() => onMinimize(win.id)}
              onHide={onHide}
              minimized={isMin}
              onHeaderDoubleClick={() => handleDoubleClickHeader(win.id)}
              onDragStart={(e) => handleDragStart(win.id, e)}
              style={{ height: "100%" }}
              floatingControls={
                <div className="flex items-center gap-0">
                  <button
                    onClick={() => bringToFront(win.id)}
                    className="p-1 rounded hover:bg-zinc-700 transition-colors"
                    title="Bring to Front"
                  >
                    <ChevronsUp className="h-3 w-3 text-zinc-400" />
                  </button>
                  <button
                    onClick={() => bringForward(win.id)}
                    className="p-1 rounded hover:bg-zinc-700 transition-colors"
                    title="Bring Forward"
                  >
                    <ChevronUp className="h-3 w-3 text-zinc-400" />
                  </button>
                  <button
                    onClick={() => sendBackward(win.id)}
                    className="p-1 rounded hover:bg-zinc-700 transition-colors"
                    title="Send Backward"
                  >
                    <ChevronDown className="h-3 w-3 text-zinc-400" />
                  </button>
                  <button
                    onClick={() => sendToBack(win.id)}
                    className="p-1 rounded hover:bg-zinc-700 transition-colors"
                    title="Send to Back"
                  >
                    <ChevronsDown className="h-3 w-3 text-zinc-400" />
                  </button>
                </div>
              }
            />
            {/* Resize handle */}
            {!isMin && (
              <div
                className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize group"
                onMouseDown={(e) => handleResizeStart(win.id, e)}
              >
                <GripVertical className="h-3 w-3 text-zinc-600 group-hover:text-zinc-400 rotate-[-45deg] absolute bottom-0.5 right-0.5" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MultiViewPage() {
  const [windows, setWindows] = useState<AMVWindow[]>([]);
  const [agentCache, setAgentCache] = useState<Record<string, Agent>>({});
  const [loadingAgents, setLoadingAgents] = useState<Set<string>>(new Set());
  const [minimized, setMinimized] = useState<Set<string>>(new Set());
  const [showLoadPicker, setShowLoadPicker] = useState(false);
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("tiled");
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const { addItem: addToCart, isInCart, count: cartCount, setDrawerOpen: openCart } = useCart();

  // Load windows + view mode from sessionStorage on mount
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const migrated: AMVWindow[] = parsed.map((item: any) => ({
            id: item.id,
            agentId: item.agentId || undefined,
            color: item.color || COLORS[0].value,
            createdAt: item.createdAt || new Date().toISOString(),
            customTitle: item.customTitle,
            x: item.x,
            y: item.y,
            width: item.width,
            height: item.height,
            zIndex: item.zIndex,
          }));
          setWindows(migrated);
          if (migrated.length > 0) setActiveTabId(migrated[0].id);
        }
      }
      const storedMode = sessionStorage.getItem(MODE_KEY);
      if (storedMode && ["tiled", "stacked", "tabs", "floating"].includes(storedMode)) {
        setViewMode(storedMode as ViewMode);
      }
    } catch {}
  }, []);

  // Persist windows to sessionStorage on change
  useEffect(() => {
    if (windows.length > 0) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(windows));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, [windows]);

  // Persist view mode
  useEffect(() => {
    sessionStorage.setItem(MODE_KEY, viewMode);
  }, [viewMode]);

  // Fetch Agent objects for windows that have agentIds
  useEffect(() => {
    windows.forEach(win => {
      if (!win.agentId) return;
      if (agentCache[win.agentId]) return;
      if (loadingAgents.has(win.agentId)) return;

      setLoadingAgents(prev => new Set(prev).add(win.agentId!));
      api.agents().then(data => {
        const found = (data.agents || []).find((a: Agent) => a.id === win.agentId);
        if (found) {
          setAgentCache(prev => ({ ...prev, [win.agentId!]: found }));
        }
      }).catch(() => {}).finally(() => {
        setLoadingAgents(prev => {
          const next = new Set(prev);
          next.delete(win.agentId!);
          return next;
        });
      });
    });
  }, [windows]); // eslint-disable-line react-hooks/exhaustive-deps

  // -- Handlers --

  const loadAgent = useCallback((agent: Agent) => {
    if (windows.find(w => w.agentId === agent.id)) {
      setShowLoadPicker(false);
      return;
    }
    const newWindow: AMVWindow = {
      id: generateId(),
      agentId: agent.id,
      color: COLORS[windows.length % COLORS.length].value,
      createdAt: new Date().toISOString(),
    };
    setAgentCache(prev => ({ ...prev, [agent.id]: agent }));
    setWindows(prev => [...prev, newWindow]);
    setActiveTabId(newWindow.id);
    setShowLoadPicker(false);
  }, [windows]);

  const clearAll = useCallback(() => {
    setWindows([]);
    setMinimized(new Set());
    setAgentCache({});
    setActiveTabId(null);
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const removeWindow = useCallback((id: string) => {
    setWindows(prev => {
      const next = prev.filter(w => w.id !== id);
      if (activeTabId === id && next.length > 0) {
        setActiveTabId(next[0].id);
      }
      return next;
    });
    setMinimized(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, [activeTabId]);

  const changeColor = useCallback((id: string, color: string) => {
    setWindows(prev =>
      prev.map(w => (w.id === id ? { ...w, color } : w))
    );
  }, []);

  const toggleMinimize = useCallback((id: string) => {
    setMinimized(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleHideAgent = useCallback((agentId: string) => {
    setWindows(prev => prev.filter(w => {
      const agent = w.agentId ? agentCache[w.agentId] : null;
      return agent?.id !== agentId;
    }));
  }, [agentCache]);

  const updateWindow = useCallback((id: string, updates: Partial<AMVWindow>) => {
    setWindows(prev =>
      prev.map(w => (w.id === id ? { ...w, ...updates } : w))
    );
  }, []);

  const renameTab = useCallback((id: string, title: string) => {
    updateWindow(id, { customTitle: title });
  }, [updateWindow]);

  // Shared props for view components
  const viewProps = {
    windows,
    agentCache,
    loadingAgents,
    minimized,
    onRemove: removeWindow,
    onColorChange: changeColor,
    onMinimize: toggleMinimize,
    onHide: handleHideAgent,
  };

  return (
    <div className="flex flex-col bg-zinc-950 text-zinc-200" style={{ height: "calc(100vh - 2rem)" }}>
      {/* Page Header */}
      <div className={`shrink-0 border-b border-zinc-800 transition-all ${headerCollapsed ? "py-0" : ""}`}>
        {headerCollapsed ? (
          <div className="px-2 py-1 flex items-center gap-2">
            <button
              onClick={() => setHeaderCollapsed(false)}
              className="p-0.5 text-zinc-600 hover:text-zinc-300 transition-colors"
              title="Show header"
            >
              <ChevronRight className="h-3 w-3 rotate-90" />
            </button>
            <span className="text-[10px] text-zinc-600">AMV · {windows.length}</span>
            {/* Compact mode switcher */}
            <div className="flex items-center gap-0.5 ml-2">
              {VIEW_MODES.map(({ mode, label, icon: Icon }) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`p-0.5 rounded transition-colors ${
                    viewMode === mode ? "text-violet-400" : "text-zinc-600 hover:text-zinc-400"
                  }`}
                  title={label}
                >
                  <Icon className="h-3 w-3" />
                </button>
              ))}
            </div>
            <div className="flex-1" />
            <button
              onClick={() => setShowLoadPicker(true)}
              className="text-[10px] text-cyan-500 hover:text-cyan-400"
            >
              + Load
            </button>
          </div>
        ) : (
          <div className="px-4 py-3 flex items-center gap-4">
            <div className="flex items-center gap-2">
              <LayoutGrid className="h-5 w-5 text-violet-400" />
              <h1 className="text-lg font-semibold text-zinc-100">
                Agent Multi-View
              </h1>
              <Badge
                variant="outline"
                className="text-[11px] px-1.5 py-0 h-5 border-zinc-700 text-zinc-400"
              >
                {windows.length} agent{windows.length !== 1 ? "s" : ""}
              </Badge>
            </div>

            {/* View mode switcher */}
            <div className="flex items-center gap-0.5 bg-zinc-800/50 rounded-lg p-0.5">
              {VIEW_MODES.map(({ mode, label, icon: Icon }) => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors ${
                    viewMode === mode
                      ? "bg-zinc-700 text-violet-300"
                      : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                  }`}
                  title={label}
                >
                  <Icon className="h-3 w-3" />
                  <span className="hidden sm:inline">{label}</span>
                </button>
              ))}
            </div>

            <div className="flex-1" />

            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs border-cyan-700 text-cyan-300 hover:bg-cyan-900/30"
              onClick={() => setShowLoadPicker(true)}
            >
              <Search className="h-3.5 w-3.5 mr-1" />
              Load Agent
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs border-zinc-700 text-zinc-400 hover:text-cyan-300 hover:border-cyan-700 relative"
              onClick={() => openCart(true)}
            >
              <ShoppingCart className="h-3.5 w-3.5 mr-1" />
              Cart
              {cartCount > 0 && (
                <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-cyan-500 px-1 text-[10px] font-medium text-white">
                  {cartCount}
                </span>
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 text-xs text-zinc-500 hover:text-red-400"
              onClick={clearAll}
              disabled={windows.length === 0}
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Clear All
            </Button>
            <button
              onClick={() => setHeaderCollapsed(true)}
              className="p-1 text-zinc-600 hover:text-zinc-300 transition-colors"
              title="Collapse header"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-auto p-2">
        {windows.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <LayoutGrid className="h-12 w-12 text-zinc-700 mb-4" />
            <h2 className="text-lg font-medium text-zinc-400 mb-2">
              No agents in view
            </h2>
            <p className="text-sm text-zinc-600 mb-6 max-w-md">
              Load agents to create a multi-view workspace. Send agents here
              from any chat using &quot;Add to AMV&quot;.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="border-cyan-700 text-cyan-300 hover:bg-cyan-900/30"
              onClick={() => setShowLoadPicker(true)}
            >
              <Search className="h-3.5 w-3.5 mr-1.5" />
              Load Agent
            </Button>
          </div>
        ) : (
          <>
            {viewMode === "tiled" && <TiledView {...viewProps} />}
            {viewMode === "stacked" && <StackedView {...viewProps} />}
            {viewMode === "tabs" && (
              <TabsView
                {...viewProps}
                activeTabId={activeTabId}
                onSetActiveTab={setActiveTabId}
                onRenameTab={renameTab}
              />
            )}
            {viewMode === "floating" && (
              <FloatingView {...viewProps} onUpdateWindow={updateWindow} />
            )}
          </>
        )}
      </div>

      {/* Load Agent Picker Modal */}
      {showLoadPicker && (
        <LoadAgentPicker
          onSelect={loadAgent}
          onClose={() => setShowLoadPicker(false)}
          existingAgentIds={new Set(windows.map(w => w.agentId).filter(Boolean) as string[])}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Load Agent Picker — searchable modal
// ---------------------------------------------------------------------------

function LoadAgentPicker({
  onSelect,
  onClose,
  existingAgentIds,
}: {
  onSelect: (agent: Agent) => void;
  onClose: () => void;
  existingAgentIds: Set<string>;
}) {
  const [search, setSearch] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.agents().then(data => {
      setAgents(data.agents || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const filtered = search
    ? agents.filter(a => {
        const q = search.toLowerCase();
        return a.title.toLowerCase().includes(q) ||
          a.project.toLowerCase().includes(q) ||
          (a.jira_key && a.jira_key.toLowerCase().includes(q)) ||
          (a.git_branch && a.git_branch.toLowerCase().includes(q));
      })
    : agents;

  const formatAge = (ts: string) => {
    if (!ts) return "";
    const h = Math.floor((Date.now() - new Date(ts).getTime()) / 3600000);
    if (h < 1) return "just now";
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative w-full max-w-lg mx-4 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-200">Load Agent</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300"><X className="h-4 w-4" /></button>
        </div>
        <div className="px-4 py-3 border-b border-zinc-800">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-zinc-500" />
            <Input ref={inputRef} value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search by title, project, JIRA key, branch..."
              className="pl-9 bg-zinc-800 border-zinc-700 text-zinc-200 placeholder:text-zinc-500 text-sm" />
          </div>
        </div>
        <div className="max-h-[400px] overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="h-5 w-5 text-zinc-500 animate-spin" /></div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-12 text-sm text-zinc-500">{search ? "No agents match" : "No agents found"}</div>
          ) : (
            <div className="divide-y divide-zinc-800/60">
              {filtered.map(agent => {
                const loaded = existingAgentIds.has(agent.id);
                return (
                  <button key={agent.id} onClick={() => !loaded && onSelect(agent)} disabled={loaded}
                    className={`w-full text-left px-4 py-3 transition-colors ${loaded ? "opacity-40 cursor-not-allowed" : "hover:bg-zinc-800/50"}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`h-2 w-2 rounded-full shrink-0 ${agent.status === "live" ? "bg-emerald-400" : agent.status === "idle" ? "bg-amber-400" : "bg-zinc-600"}`} />
                      <span className="text-sm text-zinc-200 truncate flex-1">{agent.title}</span>
                      <span className="text-[10px] text-zinc-600">{formatAge(agent.created_at)}</span>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <Badge variant="outline" className="text-[9px] px-1 py-0 text-zinc-400 border-zinc-600/30">{agent.project}</Badge>
                      {agent.jira_key && <span className="text-[9px] font-mono text-cyan-400">{agent.jira_key}</span>}
                      {agent.git_branch && <span className="text-[9px] font-mono text-zinc-500 truncate max-w-[150px]">{agent.git_branch}</span>}
                      <span className="text-[9px] text-zinc-600 ml-auto">{agent.message_count} msgs</span>
                      {loaded && <span className="text-[9px] text-emerald-500">loaded</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
