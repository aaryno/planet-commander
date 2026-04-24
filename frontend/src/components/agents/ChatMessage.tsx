"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Wrench, Brain, User, Bot, Pin, PinOff, GripVertical, CheckCircle2, XCircle, Clock, ListTodo } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as ChatMessageType } from "@/lib/api";
import { UserMessageContent, CodeBlock, Linkify } from "./RichText";
import { ArtifactPill } from "./ArtifactPill";

function formatTime(ts: string): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/**
 * Process React children to linkify plain text strings.
 * Passes through non-string children (existing links, code, etc.) untouched.
 */
function linkifyChildren(children: React.ReactNode): React.ReactNode {
  if (!children) return children;
  if (typeof children === "string") {
    return <Linkify text={children} />;
  }
  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") return <Linkify key={i} text={child} />;
      return child;
    });
  }
  return children;
}

interface TaskNotification {
  taskId: string;
  toolUseId?: string;
  outputFile?: string;
  status: string;
  summary: string;
  result: string;
}

function parseTaskNotification(content: string): { notification: TaskNotification; remaining: string } | null {
  const match = content.match(/<task-notification>([\s\S]*?)<\/task-notification>/);
  if (!match) return null;

  const xml = match[1];
  const extract = (tag: string) => {
    const m = xml.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
    return m ? m[1].trim() : "";
  };

  const remaining = content.slice(0, match.index) + content.slice(match.index! + match[0].length);

  return {
    notification: {
      taskId: extract("task-id"),
      toolUseId: extract("tool-use-id") || undefined,
      outputFile: extract("output-file") || undefined,
      status: extract("status"),
      summary: extract("summary"),
      result: extract("result"),
    },
    remaining: remaining.trim(),
  };
}

function TaskNotificationCard({ notification }: { notification: TaskNotification }) {
  const statusConfig = {
    completed: { icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
    failed: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
    running: { icon: Clock, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  } as const;
  const cfg = statusConfig[notification.status as keyof typeof statusConfig] || statusConfig.completed;
  const StatusIcon = cfg.icon;

  return (
    <div className={`rounded-lg border ${cfg.border} ${cfg.bg} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        <ListTodo className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
        <span className="text-xs font-medium text-zinc-300 flex-1 truncate">{notification.summary}</span>
        <div className="flex items-center gap-1">
          <StatusIcon className={`h-3.5 w-3.5 ${cfg.color}`} />
          <span className={`text-[10px] font-medium ${cfg.color}`}>{notification.status}</span>
        </div>
      </div>

      {/* Result content rendered as markdown */}
      {notification.result && (
        <div className="border-t border-zinc-800/50 px-3 py-2">
          <div className="text-sm text-zinc-300 prose prose-invert prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-headings:mt-3 prose-headings:mb-2 prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-code:text-emerald-400 prose-code:bg-zinc-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre({ children }) {
                  return <>{children}</>;
                },
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const codeStr = String(children).replace(/\n$/, "");
                  if (!className && !codeStr.includes("\n")) {
                    return <code className={className} {...props}>{children}</code>;
                  }
                  return <CodeBlock language={match?.[1]}>{codeStr}</CodeBlock>;
                },
                p({ children }) {
                  return <p>{linkifyChildren(children)}</p>;
                },
                li({ children }) {
                  return <li>{linkifyChildren(children)}</li>;
                },
              }}
            >
              {notification.result}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Metadata footer */}
      {notification.outputFile && (
        <div className="border-t border-zinc-800/50 px-3 py-1.5 flex items-center gap-2">
          <span className="text-[10px] text-zinc-600 truncate">
            <Linkify text={notification.outputFile} />
          </span>
        </div>
      )}
    </div>
  );
}

function stripInjectedContext(content: string): string {
  // Strip all injected context blocks (Commander, JIRA, Slack) — they stack at the start
  let cleaned = content;
  // Loop to handle multiple stacked prefixes
  let prev = "";
  while (prev !== cleaned) {
    prev = cleaned;
    // Remove "[Commander: ...]\n\n"
    cleaned = cleaned.replace(/^\[Commander: [^\]]+\]\n\n/i, '');
    // Remove "[Context: You are working on JIRA ticket...]\n\n"
    cleaned = cleaned.replace(/^\[Context: You are working on JIRA ticket [A-Z]+-\d+\. You can view it at https:\/\/[^\]]+\]\n\n/i, '');
    // Remove "[Slack Context: N new messages...]\n...\n\n"
    cleaned = cleaned.replace(/^\[Slack Context: [^\]]*\]\n[\s\S]*?\n\n/i, '');
    // Remove "[Slack Update: ...]\n...\n"
    cleaned = cleaned.replace(/^\[Slack Update: [^\]]*\]\n[\s\S]*?No action required[^\n]*\n*/i, '');
    // Remove "[URGENT Slack Alert: ...]\n...\n"
    cleaned = cleaned.replace(/^\[URGENT Slack Alert: [^\]]*\]\n[\s\S]*?This may require[^\n]*\n*/i, '');
  }
  return cleaned;
}

export function ChatMessage({
  message,
  defaultExpanded = false,
  showToolOutput = false,
  showThinking = false,
  useColoredBg = false,
  collapsed = false,
  onToggleCollapse,
  isPinned = false,
  onTogglePin,
  resizable = false,
  onViewArtifact,
}: {
  message: ChatMessageType;
  defaultExpanded?: boolean;
  showToolOutput?: boolean;
  showThinking?: boolean;
  useColoredBg?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  isPinned?: boolean;
  onTogglePin?: () => void;
  resizable?: boolean;
  onViewArtifact?: (path: string) => void;
}) {
  const [showDetails, setShowDetails] = useState(defaultExpanded);
  const [height, setHeight] = useState(150);
  const [isResizing, setIsResizing] = useState(false);
  const [hasBeenResized, setHasBeenResized] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);

  const MIN_HEIGHT_FOR_RESIZE = 150;

  // Sync with parent toggle
  useEffect(() => {
    setShowDetails(defaultExpanded);
  }, [defaultExpanded]);

  // Handle resize
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (resizeRef.current) {
        const rect = resizeRef.current.getBoundingClientRect();
        const newHeight = Math.max(80, e.clientY - rect.top);
        setHeight(newHeight);
        setHasBeenResized(true);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  if (message.role === "user") {
    // Check for task notification XML
    const taskParsed = parseTaskNotification(message.content || '');
    // Get content without JIRA context injection
    const rawContent = taskParsed ? taskParsed.remaining : (message.content || '');
    const displayContent = stripInjectedContext(rawContent);

    // Get preview text - show up to 34 lines
    const getPreviewText = () => {
      if (taskParsed) return taskParsed.notification.summary;
      if (!displayContent) return '';
      const lines = displayContent.split('\n');
      if (lines.length <= 34) return displayContent;
      return lines.slice(0, 34).join('\n') + '\n...';
    };

    return (
      <div
        ref={resizeRef}
        className={`py-3 px-3 -mx-3 rounded-md mb-2 relative ${useColoredBg ? "bg-blue-500/15 border-l-2 border-blue-500/30" : ""}`}
        style={{ height: resizable && !collapsed && hasBeenResized ? height : 'auto' }}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
      >
        <div
          className="flex gap-3 cursor-pointer"
          onClick={onToggleCollapse}
        >
          <div className="shrink-0 h-6 w-6 rounded-full bg-blue-500/20 flex items-center justify-center">
            <User className="h-3.5 w-3.5 text-blue-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-blue-400">You</span>
              <span className="text-[10px] text-zinc-600">{formatTime(message.timestamp)}</span>
              {onTogglePin && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onTogglePin();
                  }}
                  className="ml-auto text-zinc-600 hover:text-blue-400 transition-colors"
                  title={isPinned ? "Unpin" : "Pin"}
                >
                  {isPinned ? <Pin className="h-3 w-3 text-blue-400" /> : <PinOff className="h-3 w-3" />}
                </button>
              )}
            </div>
          </div>
        </div>
        {collapsed ? (
          <div className="ml-9 mt-1">
            <p className="text-sm text-zinc-400 whitespace-pre-wrap break-words line-clamp-2">
              {getPreviewText()}
            </p>
          </div>
        ) : (
          <div className={`ml-9 mt-1 space-y-2 ${resizable && hasBeenResized ? 'overflow-auto h-[calc(100%-2rem)]' : ''}`}>
            {taskParsed && <TaskNotificationCard notification={taskParsed.notification} />}
            {displayContent && <UserMessageContent content={displayContent} />}
          </div>
        )}
        {/* Resize handle - only show on hover and when tall enough */}
        {resizable && !collapsed && isHovering && hasBeenResized && height >= MIN_HEIGHT_FOR_RESIZE && (
          <div
            className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize flex items-center justify-center bg-blue-500/10 transition-all"
            onMouseDown={(e) => {
              e.stopPropagation();
              setIsResizing(true);
            }}
          >
            <GripVertical className="h-3 w-3 text-blue-500" />
          </div>
        )}
      </div>
    );
  }

  // Assistant message — also check for task notification XML
  const assistantTaskParsed = parseTaskNotification(message.summary || message.content || '');
  const assistantDisplayContent = assistantTaskParsed
    ? assistantTaskParsed.remaining
    : (message.summary || message.content || '');
  const toolCount = message.tool_call_count || 0;
  const hasExpandable = (showThinking && message.has_thinking) || (showToolOutput && toolCount > 0);

  // Get preview text - show up to 34 lines
  const getAssistantPreviewText = () => {
    if (assistantTaskParsed) return assistantTaskParsed.notification.summary;
    const text = message.summary || message.content || '';
    if (!text) return '';
    const lines = text.split('\n');
    if (lines.length <= 34) return text;
    return lines.slice(0, 34).join('\n') + '\n...';
  };

  return (
    <div
      ref={resizeRef}
      className={`py-3 px-3 -mx-3 rounded-md mb-2 relative ${useColoredBg ? "bg-violet-500/15 border-l-2 border-violet-500/30" : ""}`}
      style={{ height: resizable && !collapsed && hasBeenResized ? height : 'auto' }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div
        className="flex gap-3 cursor-pointer"
        onClick={onToggleCollapse}
      >
        <div className="shrink-0 h-6 w-6 rounded-full bg-violet-500/20 flex items-center justify-center">
          <Bot className="h-3.5 w-3.5 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-violet-400">Claude</span>
            <span className="text-[10px] text-zinc-600">{formatTime(message.timestamp)}</span>
            {message.model && (
              <span className="text-[10px] text-zinc-700">{message.model.replace("claude-", "").split("-202")[0]}</span>
            )}
            {onTogglePin && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onTogglePin();
                }}
                className="ml-auto text-zinc-600 hover:text-violet-400 transition-colors"
                title={isPinned ? "Unpin" : "Pin"}
              >
                {isPinned ? <Pin className="h-3 w-3 text-violet-400" /> : <PinOff className="h-3 w-3" />}
              </button>
            )}
          </div>
        </div>
      </div>

      {collapsed ? (
        <div className="ml-9 mt-1">
          <p className="text-sm text-zinc-400 whitespace-pre-wrap break-words line-clamp-2">
            {getAssistantPreviewText()}
          </p>
        </div>
      ) : (
        <div className={`ml-9 mt-1 space-y-2 ${resizable && hasBeenResized ? 'overflow-auto h-[calc(100%-2rem)] pb-2' : ''}`}>
          {assistantTaskParsed && <TaskNotificationCard notification={assistantTaskParsed.notification} />}
          {assistantDisplayContent && (
            <div className="text-sm text-zinc-300 prose prose-invert prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-headings:mt-3 prose-headings:mb-2 prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-code:text-emerald-400 prose-code:bg-zinc-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  pre({ children }) {
                    return <>{children}</>;
                  },
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeStr = String(children).replace(/\n$/, "");
                    if (!className && !codeStr.includes("\n")) {
                      return <code className={className} {...props}>{children}</code>;
                    }
                    return <CodeBlock language={match?.[1]}>{codeStr}</CodeBlock>;
                  },
                  p({ children }) {
                    return <p>{linkifyChildren(children)}</p>;
                  },
                  li({ children }) {
                    return <li>{linkifyChildren(children)}</li>;
                  },
                }}
              >
                {assistantDisplayContent}
              </ReactMarkdown>
            </div>
          )}

          {/* Expandable details */}
          {hasExpandable && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowDetails(!showDetails);
              }}
              className="flex items-center gap-1.5 mt-2 text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
            >
              {showDetails ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {showToolOutput && toolCount > 0 && (
                <span className="flex items-center gap-1">
                  <Wrench className="h-3 w-3" />
                  {toolCount} tool call{toolCount !== 1 ? "s" : ""}
                </span>
              )}
              {showThinking && message.has_thinking && (
                <span className="flex items-center gap-1">
                  <Brain className="h-3 w-3" />
                  thinking
                </span>
              )}
            </button>
          )}

          {showDetails && (
            <div className="mt-2 space-y-2 pl-3 border-l border-zinc-800">
              {showThinking && message.thinking && (
                <div className={`text-xs text-zinc-500 rounded p-2 max-h-40 overflow-auto ${useColoredBg ? "bg-amber-500/10 border border-amber-500/20" : "bg-zinc-900"}`}>
                  <span className={`font-medium ${useColoredBg ? "text-amber-400" : "text-zinc-600"}`}>Thinking:</span>
                  <pre className="mt-1 whitespace-pre-wrap">{message.thinking}</pre>
                </div>
              )}
              {showToolOutput && message.tool_calls && message.tool_calls.length > 0 && (
                <div className="space-y-1">
                  {message.tool_calls.map((tc, i) => (
                    <div key={i} className={`text-xs rounded p-2 ${useColoredBg ? "bg-cyan-500/10 border border-cyan-500/20" : "bg-zinc-900"}`}>
                      <span className={`font-mono ${useColoredBg ? "text-cyan-400" : "text-cyan-500"}`}>{tc.name}</span>
                      <span className="text-zinc-600 ml-2 break-all">{tc.input_preview}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Artifact pills */}
          {message.artifacts && message.artifacts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {message.artifacts.map((a, i) => (
                <ArtifactPill
                  key={i}
                  artifact={a}
                  onClick={() => onViewArtifact?.(a.path)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Resize handle - only show on hover and when tall enough */}
      {resizable && !collapsed && isHovering && hasBeenResized && height >= MIN_HEIGHT_FOR_RESIZE && (
        <div
          className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize flex items-center justify-center bg-violet-500/10 transition-all"
          onMouseDown={(e) => {
            e.stopPropagation();
            setIsResizing(true);
          }}
        >
          <GripVertical className="h-3 w-3 text-violet-500" />
        </div>
      )}
    </div>
  );
}
