"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { X, ExternalLink } from "lucide-react";
import type { Agent } from "@/lib/api";
import { ChatView } from "./ChatView";

interface ChatModalProps {
  agent: Agent;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onHide?: (id: string) => void;
}

export function ChatModal({ agent, open, onOpenChange, onHide }: ChatModalProps) {
  const router = useRouter();

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
      />

      {/* Modal */}
      <div className="relative w-full max-w-3xl h-[80vh] mx-4 rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl overflow-hidden">
        <ChatView
          agent={agent}
          className="h-full"
          onHide={onHide}
          headerActions={
            <>
              <button
                onClick={() => {
                  onOpenChange(false);
                  router.push(`/agents/${agent.id}/chat`);
                }}
                className="rounded-md p-1 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                title="Open in full page"
              >
                <ExternalLink className="h-4 w-4" />
              </button>
              <button
                onClick={() => onOpenChange(false)}
                className="rounded-md p-1 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          }
        />
      </div>
    </div>
  );
}
