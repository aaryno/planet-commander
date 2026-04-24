"use client";

import { ContextResponse } from "@/lib/api";
import { HealthStrip } from "./HealthStrip";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Edit2, Check, X } from "lucide-react";
import { useState } from "react";

interface ContextHeaderProps {
  context: ContextResponse;
  onTitleUpdate?: (newTitle: string) => void;
}

export function ContextHeader({ context, onTitleUpdate }: ContextHeaderProps) {
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState(context.title);

  const handleSaveTitle = () => {
    if (editedTitle.trim() && editedTitle !== context.title) {
      onTitleUpdate?.(editedTitle.trim());
    }
    setIsEditingTitle(false);
  };

  const handleCancelEdit = () => {
    setEditedTitle(context.title);
    setIsEditingTitle(false);
  };

  return (
    <div className="space-y-3">
      {/* Title and Metadata */}
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0 mr-4">
          {isEditingTitle ? (
            <div className="flex items-center gap-2">
              <Input
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveTitle();
                  if (e.key === "Escape") handleCancelEdit();
                }}
                className="text-base font-semibold"
                autoFocus
              />
              <Button
                size="icon"
                variant="ghost"
                onClick={handleSaveTitle}
                className="h-8 w-8"
              >
                <Check className="w-4 h-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                onClick={handleCancelEdit}
                className="h-8 w-8"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-zinc-200 truncate">
                {context.title}
              </h2>
              {onTitleUpdate && (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setIsEditingTitle(true)}
                  className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Edit2 className="w-3 h-3" />
                </Button>
              )}
            </div>
          )}

          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline" className="text-xs">
              {context.origin_type}
            </Badge>
            <Badge
              variant={context.status === "active" ? "default" : "secondary"}
              className="text-xs"
            >
              {context.status}
            </Badge>
            {context.owner && (
              <span className="text-xs text-zinc-500">Owner: {context.owner}</span>
            )}
          </div>
        </div>
      </div>

      {/* Health Strip */}
      <HealthStrip health={context.health} />

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-zinc-500">
        <span>{context.jira_issues.length} issues</span>
        <span>{context.chats.length} chats</span>
        <span>{context.branches.length} branches</span>
        <span>{context.worktrees.length} worktrees</span>
        <span>{context.links.length} links</span>
        {context.v2_docs && (
          <Badge
            variant={context.v2_docs.budget_exceeded ? "destructive" : "outline"}
            className={`text-[10px] px-1.5 py-0 ${
              context.v2_docs.budget_exceeded
                ? ""
                : "text-emerald-400 border-emerald-600/50"
            }`}
          >
            📚 {context.v2_docs.total_tokens.toLocaleString()} tokens
          </Badge>
        )}
      </div>
    </div>
  );
}
