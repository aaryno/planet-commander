"use client";

import { useCallback, useRef, useState } from "react";
import { ChevronDown, Play, Send, Square, Clock, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const MODELS = [
  { id: "opus", label: "Opus", color: "text-violet-400" },
  { id: "sonnet", label: "Sonnet", color: "text-blue-400" },
  { id: "haiku", label: "Haiku", color: "text-emerald-400" },
] as const;

type ModelId = typeof MODELS[number]["id"];

interface ChatInputProps {
  agentStatus: "live" | "idle" | "dead";
  managedBy?: "vscode" | "dashboard";
  onSend?: (message: string, model?: string) => void;
  onResume?: (message?: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  processing?: boolean;
  defaultModel?: string;
  /** Queued messages waiting to be sent */
  queue?: string[];
  onRemoveFromQueue?: (index: number) => void;
}

export function ChatInput({
  agentStatus,
  managedBy,
  onSend,
  onResume,
  onCancel,
  disabled,
  processing,
  defaultModel,
  queue = [],
  onRemoveFromQueue,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [selectedModel, setSelectedModel] = useState<ModelId>((defaultModel as ModelId) || "sonnet");
  const [showModelPicker, setShowModelPicker] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const needsResume = agentStatus === "dead" && managedBy !== "dashboard";
  const currentModel = MODELS.find(m => m.id === selectedModel) || MODELS[1];

  const handleSend = useCallback(() => {
    const trimmed = value.trim();

    if (needsResume && onResume) {
      onResume(trimmed || undefined);
      setValue("");
    } else if (onSend && trimmed) {
      onSend(trimmed, selectedModel);
      setValue("");
    }

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, onSend, onResume, needsResume, selectedModel]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isVscode = managedBy === "vscode";
  const placeholder = isVscode
    ? "Send a message to take over this VS Code session..."
    : needsResume
      ? "Type a message and click Resume to continue..."
      : processing
        ? "Type a message to queue it for when processing completes..."
        : agentStatus === "live"
          ? "Send a message..."
          : "Agent is idle — send a message to wake it...";

  return (
    <div className="flex flex-col gap-1.5">
      {isVscode && (
        <div className="text-[10px] text-amber-500/80 px-1">
          VS Code session — sending a message will take over this session to the dashboard
        </div>
      )}

      {/* Queued messages */}
      {queue.length > 0 && (
        <div className="flex flex-col gap-1 px-1">
          <span className="text-[10px] text-zinc-500 font-medium flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Queued ({queue.length})
          </span>
          {queue.map((msg, i) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px] text-zinc-400 bg-zinc-800/50 rounded px-2 py-1">
              <span className="flex-1 truncate">{msg}</span>
              {onRemoveFromQueue && (
                <button
                  onClick={() => onRemoveFromQueue(i)}
                  className="shrink-0 text-zinc-600 hover:text-red-400 transition-colors"
                  title="Remove from queue"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-y min-h-[36px] max-h-[200px] rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
        />

        {/* Model selector */}
        <div className="relative shrink-0">
          <button
            onClick={() => setShowModelPicker(!showModelPicker)}
            className="h-9 px-2 rounded-md border border-zinc-700 bg-zinc-800/50 flex items-center gap-1 hover:bg-zinc-700/50 transition-colors"
            title="Select model"
          >
            <span className={`text-[11px] font-medium ${currentModel.color}`}>
              {currentModel.label}
            </span>
            <ChevronDown className="h-3 w-3 text-zinc-500" />
          </button>
          {showModelPicker && (
            <div className="absolute bottom-full right-0 mb-1 bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl overflow-hidden z-50">
              {MODELS.map(m => (
                <button
                  key={m.id}
                  onClick={() => {
                    setSelectedModel(m.id);
                    setShowModelPicker(false);
                  }}
                  className={`w-full px-4 py-2 text-left text-sm flex items-center gap-2 transition-colors ${
                    selectedModel === m.id
                      ? "bg-zinc-700/50"
                      : "hover:bg-zinc-700/30"
                  }`}
                >
                  <span className={`font-medium ${m.color}`}>{m.label}</span>
                  {selectedModel === m.id && (
                    <span className="text-[10px] text-zinc-500 ml-auto">active</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Cancel button — shown when processing */}
        {processing && onCancel && (
          <Button
            variant="outline"
            size="sm"
            className="h-9 px-3 border-red-700 bg-red-900/20 text-red-400 hover:bg-red-900/40 hover:text-red-300 shrink-0"
            onClick={onCancel}
            title="Cancel current processing"
          >
            <Square className="h-3 w-3 mr-1.5 fill-current" />
            Stop
          </Button>
        )}

        {needsResume ? (
          <Button
            variant="outline"
            size="sm"
            className="h-9 px-3 border-green-700 bg-green-900/20 text-green-400 hover:bg-green-900/40 hover:text-green-300 shrink-0"
            onClick={handleSend}
            disabled={disabled || !onResume}
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            Resume
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="h-9 w-9 p-0 text-zinc-400 hover:text-zinc-200 shrink-0"
            onClick={handleSend}
            disabled={disabled || !onSend || !value.trim()}
            title={processing ? "Queue message" : "Send message"}
          >
            {processing ? (
              <Clock className="h-4 w-4 text-amber-400" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
