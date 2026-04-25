"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronRight, Clock, Folder, FolderGit, FolderUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { DirectoryEntry } from "@/lib/api";
import { useDirectoryHistory } from "@/hooks/useDirectoryHistory";

interface DirectoryPickerProps {
  value: string;
  onChange: (path: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function DirectoryPicker({
  value,
  onChange,
  disabled,
  placeholder = "~/workspaces/wx-1",
}: DirectoryPickerProps) {
  const [open, setOpen] = useState(false);
  const [browsePath, setBrowsePath] = useState<string | null>(null);
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { recentPaths, search } = useDirectoryHistory();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const browse = useCallback(async (path: string) => {
    setLoading(true);
    try {
      const data = await api.browseDirectory(path);
      setEntries(data.entries);
      setParentPath(data.parent);
      setBrowsePath(data.path);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleFocus = () => {
    if (disabled) return;
    setOpen(true);
    if (!browsePath) {
      setBrowsePath(null);
    }
  };

  const handleInputChange = (val: string) => {
    onChange(val);
    if (!open) setOpen(true);
  };

  const handleSelect = (path: string) => {
    onChange(path);
    setOpen(false);
    inputRef.current?.blur();
  };

  const handleBrowseInto = (path: string) => {
    browse(path);
  };

  const handleSelectAndClose = (path: string) => {
    onChange(path);
    setOpen(false);
  };

  const matches = value ? search(value) : recentPaths;
  const showHistory = !browsePath && matches.length > 0;
  const showBrowser = !!browsePath;

  return (
    <div ref={containerRef} className="relative">
      <div className="flex gap-1">
        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={handleFocus}
          placeholder={placeholder}
          disabled={disabled}
          className="bg-zinc-800 border-zinc-700 text-zinc-200 placeholder:text-zinc-600 text-sm flex-1"
        />
        <button
          type="button"
          onClick={() => {
            if (disabled) return;
            browse(value || "~");
            setOpen(true);
          }}
          disabled={disabled}
          className="px-2 rounded-md border border-zinc-700 bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-50"
          title="Browse directories"
        >
          <Folder className="h-4 w-4" />
        </button>
      </div>

      {open && !disabled && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-md border border-zinc-700 bg-zinc-900 shadow-lg">
          {showHistory && !showBrowser && (
            <>
              <div className="px-3 py-1.5 text-xs text-zinc-500 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Recent directories
              </div>
              {matches.map((path) => (
                <button
                  key={path}
                  onClick={() => handleSelect(path)}
                  className="w-full text-left px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 flex items-center gap-2"
                >
                  <Folder className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                  <span className="truncate">{path}</span>
                </button>
              ))}
              <div className="border-t border-zinc-800 px-3 py-1.5">
                <button
                  onClick={() => browse(value || "~")}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Browse files...
                </button>
              </div>
            </>
          )}

          {!showHistory && !showBrowser && (
            <div className="px-3 py-2">
              <button
                onClick={() => browse(value || "~")}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Browse files...
              </button>
            </div>
          )}

          {showBrowser && (
            <>
              <div className="px-3 py-1.5 text-xs text-zinc-500 border-b border-zinc-800 flex items-center justify-between">
                <span className="truncate">{browsePath}</span>
                <button
                  onClick={() => handleSelectAndClose(browsePath || "")}
                  className="text-blue-400 hover:text-blue-300 ml-2 shrink-0"
                >
                  Select
                </button>
              </div>

              {parentPath && (
                <button
                  onClick={() => browse(parentPath)}
                  className="w-full text-left px-3 py-1.5 text-sm text-zinc-400 hover:bg-zinc-800 flex items-center gap-2"
                >
                  <FolderUp className="h-3.5 w-3.5 shrink-0" />
                  <span>..</span>
                </button>
              )}

              {loading ? (
                <div className="px-3 py-3 text-xs text-zinc-500 text-center">Loading...</div>
              ) : entries.length === 0 ? (
                <div className="px-3 py-3 text-xs text-zinc-500 text-center">No subdirectories</div>
              ) : (
                entries.map((entry) => (
                  <div
                    key={entry.path}
                    className="flex items-center hover:bg-zinc-800 group"
                  >
                    <button
                      onClick={() => handleSelectAndClose(entry.path)}
                      className="flex-1 text-left px-3 py-1.5 text-sm text-zinc-300 flex items-center gap-2 min-w-0"
                    >
                      {entry.is_git ? (
                        <FolderGit className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                      ) : (
                        <Folder className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                      )}
                      <span className="truncate">{entry.name}</span>
                      {entry.is_git && (
                        <span className="text-xs text-emerald-500/60 shrink-0">git</span>
                      )}
                    </button>
                    <button
                      onClick={() => handleBrowseInto(entry.path)}
                      className="px-2 py-1.5 text-zinc-600 hover:text-zinc-300 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Browse into"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}

              <div className="border-t border-zinc-800 px-3 py-1.5">
                <button
                  onClick={() => { setBrowsePath(null); }}
                  className="text-xs text-zinc-500 hover:text-zinc-300"
                >
                  Back to history
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
