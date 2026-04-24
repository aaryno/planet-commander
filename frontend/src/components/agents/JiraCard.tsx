"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, GripVertical, Loader2, Pin, PinOff, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { parseJiraMarkup } from "@/lib/jira-formatting";
import type { JiraTicketResult } from "@/lib/api";

interface JiraCardProps {
  jiraKey: string;
  onClose: () => void;
  isPinned?: boolean;
  onTogglePin?: () => void;
  showDescription?: boolean;
  onToggleDescription?: () => void;
  height?: number;
  onHeightChange?: (height: number) => void;
}

export function JiraCard({
  jiraKey,
  onClose,
  isPinned = false,
  onTogglePin,
  showDescription: externalShowDescription,
  onToggleDescription,
  height: externalHeight = 400,
  onHeightChange,
}: JiraCardProps) {
  const [ticket, setTicket] = useState<JiraTicketResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const resizeRef = useRef<HTMLDivElement>(null);

  // Use external state if provided, otherwise use local state
  const [localShowDescription, setLocalShowDescription] = useState(false);
  const [localHeight, setLocalHeight] = useState(400);
  const [showComments, setShowComments] = useState(false);
  const [isHovering, setIsHovering] = useState(false);

  const showDescription = externalShowDescription ?? localShowDescription;
  const height = externalHeight ?? localHeight;

  // Minimum height to show resize handle (collapsed card is ~150px)
  const MIN_HEIGHT_FOR_RESIZE = 200;

  const handleToggleDescription = () => {
    if (onToggleDescription) {
      onToggleDescription();
    } else {
      setLocalShowDescription(!localShowDescription);
    }
  };

  const handleHeightChange = (newHeight: number) => {
    if (onHeightChange) {
      onHeightChange(newHeight);
    } else {
      setLocalHeight(newHeight);
    }
  };

  // Generate a unique background color for each participant
  const getAuthorColor = (author: string) => {
    const colors = [
      'bg-blue-500/15 border-l-2 border-blue-500/50',
      'bg-green-500/15 border-l-2 border-green-500/50',
      'bg-purple-500/15 border-l-2 border-purple-500/50',
      'bg-pink-500/15 border-l-2 border-pink-500/50',
      'bg-yellow-500/15 border-l-2 border-yellow-500/50',
      'bg-orange-500/15 border-l-2 border-orange-500/50',
      'bg-red-500/15 border-l-2 border-red-500/50',
      'bg-teal-500/15 border-l-2 border-teal-500/50',
      'bg-indigo-500/15 border-l-2 border-indigo-500/50',
      'bg-rose-500/15 border-l-2 border-rose-500/50',
    ];

    // Simple hash function
    let hash = 0;
    for (let i = 0; i < author.length; i++) {
      hash = ((hash << 5) - hash) + author.charCodeAt(i);
      hash = hash & hash; // Convert to 32bit integer
    }

    return colors[Math.abs(hash) % colors.length];
  };

  // Extract mentioned user from automated comments
  const extractMentionedUser = (body: string): { name: string; username: string } | null => {
    // Pattern: [Aaryn Olsson|https://hello.planet.com/code/aaryn]
    const match = body.match(/^\[([^\]]+)\|https:\/\/hello\.planet\.com\/code\/([^\]]+)\]/);
    if (match) {
      return { name: match[1], username: match[2] };
    }
    return null;
  };

  // Get avatar URL for a mentioned user (by username from code.earth.planet.com)
  const getMentionedUserAvatar = (username: string): string => {
    // GitLab avatar URL pattern
    return `https://hello.planet.com/code/uploads/-/system/user/avatar/${username}.png`;
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .jiraTicket(jiraKey)
      .then((t) => {
        setTicket(t);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, [jiraKey]);

  // Handle resize
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (resizeRef.current) {
        const rect = resizeRef.current.getBoundingClientRect();
        const newHeight = Math.max(200, e.clientY - rect.top);
        handleHeightChange(newHeight);
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
  }, [isResizing, handleHeightChange]);

  if (loading) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/90 p-4 mb-2">
        <div className="flex items-center justify-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
          <span className="text-sm text-zinc-400">Loading JIRA ticket...</span>
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/90 p-4 mb-2">
        <div className="flex items-center justify-between">
          <p className="text-sm text-red-400">Failed to load JIRA ticket: {error}</p>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={resizeRef}
      className="rounded-lg border border-cyan-700/50 bg-cyan-500/5 border-l-2 mb-2 relative group"
      style={{ height: (showDescription || showComments) ? height : 'auto' }}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      <div className="p-4 h-full flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <a
                href={`https://hello.planet.com/jira/browse/${ticket.key}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                {ticket.key}
                <ExternalLink className="h-3 w-3" />
              </a>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-zinc-700 text-zinc-400">
                {ticket.status}
              </Badge>
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-zinc-700 text-zinc-400">
                {ticket.type}
              </Badge>
              {ticket.priority && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-zinc-700 text-zinc-400">
                  {ticket.priority}
                </Badge>
              )}
            </div>
            <h3
              className="text-sm text-zinc-200 font-medium cursor-pointer hover:text-cyan-300 transition-colors"
              onClick={handleToggleDescription}
              title="Click to expand/collapse description"
            >
              {ticket.summary}
            </h3>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {onTogglePin && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
                onClick={onTogglePin}
                title={isPinned ? "Unpin" : "Pin"}
              >
                {isPinned ? <Pin className="h-3.5 w-3.5 text-cyan-400" /> : <PinOff className="h-3.5 w-3.5" />}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Details */}
        <div className="flex items-center gap-4 text-xs mb-3 flex-wrap">
          <div>
            <span className="text-zinc-600">Assignee:</span>{" "}
            <span className="text-zinc-300">{ticket.assignee}</span>
          </div>
          {ticket.labels && ticket.labels.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {ticket.labels.map((label, i) => (
                <Badge
                  key={i}
                  variant="outline"
                  className="text-[9px] px-1.5 py-0 border-zinc-700 text-zinc-400"
                >
                  {label}
                </Badge>
              ))}
            </div>
          )}
          {ticket.fix_versions && ticket.fix_versions.length > 0 && (
            <div>
              <span className="text-zinc-600">Fix:</span>{" "}
              <span className="text-zinc-300">{ticket.fix_versions.join(", ")}</span>
            </div>
          )}
        </div>

        {/* Description and Comments - scrollable content area */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {/* Description section */}
          <div className={showDescription ? "flex-1 min-h-0 flex flex-col" : ""}>
            <button
              onClick={handleToggleDescription}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors mb-2 shrink-0"
            >
              {showDescription ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Description
            </button>
            {showDescription && (
              <div className="text-xs text-zinc-400 bg-zinc-950/50 rounded p-3 overflow-auto flex-1 min-h-0 mb-2">
                {ticket.description ? (
                  <div>{parseJiraMarkup(ticket.description)}</div>
                ) : (
                  <p className="text-zinc-500 italic">No description</p>
                )}
              </div>
            )}
          </div>

          {/* Comments section */}
          <div className={showComments ? "flex-1 min-h-0 flex flex-col" : ""}>
            <button
              onClick={() => setShowComments(!showComments)}
              className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
            >
              {showComments ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              {ticket.comments.length === 0 ? "0 comments" : `${ticket.comments.length} comment${ticket.comments.length !== 1 ? 's' : ''}`}
            </button>
            {showComments && ticket.comments.length > 0 && (
              <div className="mt-2 space-y-2 overflow-auto flex-1 min-h-0">
                {ticket.comments.map((comment) => {
                  const isAutomated = comment.author.includes("Hello Planet Code") || comment.author.includes("Planet Code");
                  const mentionedUser = isAutomated ? extractMentionedUser(comment.body) : null;
                  const effectiveAuthor = mentionedUser ? mentionedUser.name : comment.author;

                  return (
                    <div
                      key={comment.id}
                      className={`rounded p-2 ${getAuthorColor(effectiveAuthor)}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {/* Show both avatars for automated comments */}
                        {isAutomated && comment.avatar_url && (
                          <img
                            src={comment.avatar_url}
                            alt={comment.author}
                            className="w-4 h-4 rounded-full border border-zinc-600"
                            title={comment.author}
                          />
                        )}
                        {mentionedUser && (
                          <div
                            className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[8px] font-bold text-zinc-300 border border-zinc-600"
                            title={mentionedUser.name}
                          >
                            {mentionedUser.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                          </div>
                        )}
                        {!isAutomated && comment.avatar_url && (
                          <img
                            src={comment.avatar_url}
                            alt={comment.author}
                            className="w-5 h-5 rounded-full"
                          />
                        )}
                        <span className="text-[10px] font-medium text-zinc-200">
                          {effectiveAuthor}
                          {isAutomated && <span className="text-zinc-500 ml-1">(automated)</span>}
                        </span>
                        <span className="text-[9px] text-zinc-600">
                          {new Date(comment.created).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-300">
                        {parseJiraMarkup(comment.body)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Resize handle - only show on hover and when card is tall enough */}
      {(showDescription || showComments) && isHovering && height >= MIN_HEIGHT_FOR_RESIZE && (
        <div
          className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize flex items-center justify-center bg-cyan-500/10 transition-all"
          onMouseDown={() => setIsResizing(true)}
        >
          <GripVertical className="h-3 w-3 text-cyan-500" />
        </div>
      )}
    </div>
  );
}
