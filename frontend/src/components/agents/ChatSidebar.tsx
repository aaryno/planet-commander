"use client";

import { useEffect, useState } from "react";
import { X, Pin, PinOff } from "lucide-react";
import type { Agent } from "@/lib/api";
import { ChatView } from "./ChatView";
import { Button } from "@/components/ui/button";

interface ChatSidebarProps {
  agent: Agent | null;
  open: boolean;
  docked: boolean;
  onOpenChange: (open: boolean) => void;
  onDockedChange: (docked: boolean) => void;
  onHide?: (id: string) => void;
}

export function ChatSidebar({
  agent,
  open,
  docked,
  onOpenChange,
  onDockedChange,
  onHide,
}: ChatSidebarProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (open) {
      setIsVisible(true);
    } else {
      // Delay hiding to allow slide-out animation
      const timer = setTimeout(() => setIsVisible(false), 300);
      return () => clearTimeout(timer);
    }
  }, [open]);

  // Close on Escape (unless docked)
  useEffect(() => {
    if (!open || docked) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, docked, onOpenChange]);

  if (!isVisible || !agent) return null;

  return (
    <>
      {/* Sidebar */}
      <div
        className={`fixed top-0 right-0 h-full bg-zinc-900 border-l border-zinc-700 shadow-2xl z-50 transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        } ${docked ? "w-[600px]" : "w-[500px]"}`}
      >
        {/* Dock/Undock controls in top-right */}
        <div className="absolute top-2 right-2 flex items-center gap-1 z-10">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            onClick={() => onDockedChange(!docked)}
            title={docked ? "Undock (overlay)" : "Dock (pin open)"}
          >
            {docked ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
            onClick={() => onOpenChange(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <ChatView agent={agent} className="h-full pt-12" onHide={onHide} source="sidebar" />
      </div>
    </>
  );
}
