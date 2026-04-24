"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import type { Agent } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CartItem {
  agentId: string;
  agentTitle: string;
  project: string;
  jiraKey: string | null;
  gitBranch: string | null;
  addedAt: string;
}

interface CartContextType {
  items: CartItem[];
  addItem: (agent: Agent) => void;
  removeItem: (agentId: string) => void;
  clearCart: () => void;
  isInCart: (agentId: string) => boolean;
  count: number;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CartContext = createContext<CartContextType | null>(null);

const STORAGE_KEY = "context-cart";

function loadCart(): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch {}
  return [];
}

function saveCart(items: CartItem[]) {
  if (typeof window === "undefined") return;
  if (items.length > 0) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } else {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Load from sessionStorage on mount
  useEffect(() => {
    setItems(loadCart());
    setMounted(true);
  }, []);

  // Persist on change (skip initial mount to avoid clearing)
  useEffect(() => {
    if (mounted) saveCart(items);
  }, [items, mounted]);

  const addItem = useCallback((agent: Agent) => {
    setItems(prev => {
      if (prev.some(i => i.agentId === agent.id)) return prev;
      return [
        ...prev,
        {
          agentId: agent.id,
          agentTitle: agent.title,
          project: agent.project,
          jiraKey: agent.jira_key,
          gitBranch: agent.git_branch,
          addedAt: new Date().toISOString(),
        },
      ];
    });
  }, []);

  const removeItem = useCallback((agentId: string) => {
    setItems(prev => prev.filter(i => i.agentId !== agentId));
  }, []);

  const clearCart = useCallback(() => {
    setItems([]);
  }, []);

  const isInCart = useCallback(
    (agentId: string) => items.some(i => i.agentId === agentId),
    [items],
  );

  return (
    <CartContext.Provider
      value={{
        items,
        addItem,
        removeItem,
        clearCart,
        isInCart,
        count: items.length,
        drawerOpen,
        setDrawerOpen,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCart(): CartContextType {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
