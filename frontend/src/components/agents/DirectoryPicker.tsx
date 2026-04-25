"use client";

import { useEffect, useRef, useState } from "react";
import { Clock, Folder, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
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
  const [picking, setPicking] = useState(false);
  const { recentPaths, search } = useDirectoryHistory();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleInputChange = (val: string) => {
    onChange(val);
    if (!open && val) setOpen(true);
  };

  const handleFocus = () => {
    if (disabled) return;
    const matches = value ? search(value) : recentPaths;
    if (matches.length > 0) setOpen(true);
  };

  const handleSelect = (path: string) => {
    onChange(path);
    setOpen(false);
  };

  const handleNativePick = async () => {
    if (disabled || picking) return;
    setPicking(true);
    try {
      const result = await api.pickDirectory();
      if (result.path) {
        onChange(result.path);
      }
    } catch (err) {
      console.error("Directory picker failed:", err);
    } finally {
      setPicking(false);
    }
  };

  const matches = value ? search(value) : recentPaths;
  const showDropdown = open && !disabled && matches.length > 0;

  return (
    <div ref={containerRef} className="relative">
      <div className="flex gap-1">
        <Input
          value={value}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={handleFocus}
          placeholder={placeholder}
          disabled={disabled}
          className="bg-zinc-800 border-zinc-700 text-zinc-200 placeholder:text-zinc-600 text-sm flex-1"
        />
        <button
          type="button"
          onClick={handleNativePick}
          disabled={disabled || picking}
          className="px-2 rounded-md border border-zinc-700 bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors disabled:opacity-50"
          title="Open folder picker"
        >
          {picking ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Folder className="h-4 w-4" />
          )}
        </button>
      </div>

      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-md border border-zinc-700 bg-zinc-900 shadow-lg">
          {!value && (
            <div className="px-3 py-1.5 text-xs text-zinc-500 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Recent directories
            </div>
          )}
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
        </div>
      )}
    </div>
  );
}
