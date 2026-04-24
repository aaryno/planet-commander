"use client";

import React, { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface ChannelMessagesModalProps {
  channel: string;
  days: number;
  onClose: () => void;
}

export function ChannelMessagesModal({
  channel,
  days,
  onClose,
}: ChannelMessagesModalProps) {
  const [messages, setMessages] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    api
      .slackChannelMessages(channel, days)
      .then((r) => setMessages(r.content))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setIsLoading(false));
  }, [channel, days]);

  return (
    <div className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg w-full max-w-4xl max-h-[600px] flex flex-col my-8">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">
              #{channel}
            </h2>
            <p className="text-xs text-zinc-500">Last {days} day{days !== 1 ? "s" : ""}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0 text-zinc-400 hover:text-zinc-100"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 min-h-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
            </div>
          ) : error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : messages ? (
            <div className="space-y-3">
              <SlackMessageContent content={messages} />
            </div>
          ) : (
            <p className="text-sm text-zinc-500">No messages found</p>
          )}
        </div>
      </div>
    </div>
  );
}

/** Render Slack messages with proper link formatting */
function SlackMessageContent({ content }: { content: string }) {
  // Split by message boundaries (date headers or message markers)
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let currentLine = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Check if it's a date header (starts with ##)
    if (line.startsWith('## ')) {
      if (currentLine) {
        elements.push(
          <div key={`msg-${i}`} className="text-xs text-zinc-300">
            {formatSlackLine(currentLine)}
          </div>
        );
        currentLine = '';
      }
      elements.push(
        <h3 key={`date-${i}`} className="text-xs font-semibold text-zinc-400 mt-4 mb-2 first:mt-0">
          {line.replace('## ', '')}
        </h3>
      );
    }
    // Check if it's a message header (**Username** `timestamp`)
    else if (line.match(/^\*\*[^*]+\*\*\s+`\d{2}:\d{2}:\d{2}`/)) {
      if (currentLine) {
        elements.push(
          <div key={`msg-${i}`} className="text-xs text-zinc-300 mb-3">
            {formatSlackLine(currentLine)}
          </div>
        );
        currentLine = '';
      }
      // Parse username and timestamp
      const match = line.match(/^\*\*([^*]+)\*\*\s+`(\d{2}:\d{2}:\d{2})`(.*)$/);
      if (match) {
        const [, username, timestamp, restOfLine] = match;
        elements.push(
          <div key={`header-${i}`} className="flex items-baseline gap-2 mt-3">
            <span className="text-xs font-semibold text-zinc-200">{username}</span>
            <span className="text-[10px] text-zinc-600">{timestamp}</span>
          </div>
        );
        if (restOfLine.trim()) {
          currentLine = restOfLine.trim();
        }
      }
    }
    // Regular content line
    else if (line.trim()) {
      currentLine += (currentLine ? '\n' : '') + line;
    }
    // Empty line - end of current message
    else if (currentLine) {
      elements.push(
        <div key={`msg-${i}`} className="text-xs text-zinc-300 mb-3">
          {formatSlackLine(currentLine)}
        </div>
      );
      currentLine = '';
    }
  }

  // Handle remaining content
  if (currentLine) {
    elements.push(
      <div key="msg-final" className="text-xs text-zinc-300">
        {formatSlackLine(currentLine)}
      </div>
    );
  }

  return <>{elements}</>;
}

/** Format a single line of Slack content with link parsing */
function formatSlackLine(text: string): React.ReactNode {
  // Parse Slack-style links: <URL|text> or <URL>
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  const linkRegex = /<(https?:\/\/[^|>]+)(?:\|([^>]+))?>/g;
  let match;

  while ((match = linkRegex.exec(text)) !== null) {
    // Add text before the link
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const [, url, linkText] = match;
    parts.push(
      <a
        key={match.index}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 hover:text-blue-300 underline"
      >
        {linkText || url}
      </a>
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? <>{parts}</> : text;
}
