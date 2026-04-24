"use client";

import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/api";
import { ChatMessage } from "./ChatMessage";

interface ChatHistoryProps {
  messages: ChatMessageType[];
  loading: boolean;
  error: Error | null;
}

export function ChatHistory({ messages, loading, error }: ChatHistoryProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-6 w-6 text-zinc-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-red-400">Failed to load history: {error.message}</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-zinc-500">No messages in this session.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-zinc-800/50">
      {messages.map((msg, i) => (
        <ChatMessage key={`${msg.timestamp}-${i}`} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
