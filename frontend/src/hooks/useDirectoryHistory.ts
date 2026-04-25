"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "agent-working-dir-history";
const MAX_ENTRIES = 20;

interface DirectoryEntry {
  path: string;
  lastUsed: number;
}

function load(): DirectoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(entries: DirectoryEntry[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

export function useDirectoryHistory() {
  const [history, setHistory] = useState<DirectoryEntry[]>([]);

  useEffect(() => {
    setHistory(load());
  }, []);

  const addToHistory = useCallback((path: string) => {
    if (!path.trim()) return;
    setHistory((prev) => {
      const filtered = prev.filter((e) => e.path !== path);
      const updated = [{ path, lastUsed: Date.now() }, ...filtered].slice(
        0,
        MAX_ENTRIES
      );
      save(updated);
      return updated;
    });
  }, []);

  const recentPaths = history
    .sort((a, b) => b.lastUsed - a.lastUsed)
    .slice(0, 5)
    .map((e) => e.path);

  const search = useCallback(
    (query: string): string[] => {
      if (!query) return recentPaths;
      const lower = query.toLowerCase();
      return history
        .filter((e) => e.path.toLowerCase().includes(lower))
        .sort((a, b) => b.lastUsed - a.lastUsed)
        .slice(0, 8)
        .map((e) => e.path);
    },
    [history, recentPaths]
  );

  return { recentPaths, addToHistory, search, allPaths: history.map((e) => e.path) };
}
