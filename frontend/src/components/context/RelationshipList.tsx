"use client";

import { ContextResponse, CreateLinkRequest } from "@/lib/api";
import { LinkBadge } from "./LinkBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Check, X, Trash2, Plus } from "lucide-react";
import { useState } from "react";

interface RelationshipListProps {
  context: ContextResponse;
  onLinkCreate?: (request: CreateLinkRequest) => void;
  onLinkConfirm?: (linkId: string) => void;
  onLinkReject?: (linkId: string) => void;
  onLinkDelete?: (linkId: string) => void;
}

export function RelationshipList({
  context,
  onLinkCreate,
  onLinkConfirm,
  onLinkReject,
  onLinkDelete,
}: RelationshipListProps) {
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Group links by status
  const confirmedLinks = context.links.filter((link) => link.status === "confirmed");
  const suggestedLinks = context.links.filter((link) => link.status === "suggested");
  const rejectedLinks = context.links.filter((link) => link.status === "rejected");

  return (
    <div className="space-y-4">
      {/* Create Link Button */}
      {onLinkCreate && (
        <div className="flex justify-end">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            <Plus className="w-3 h-3 mr-1" />
            Add Link
          </Button>
        </div>
      )}

      {/* Suggested Links (need review) */}
      {suggestedLinks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-amber-400 flex items-center gap-2">
            <Badge variant="outline" className="bg-amber-500/20 text-amber-400">
              {suggestedLinks.length}
            </Badge>
            Suggested Links (Need Review)
          </h3>
          {suggestedLinks.map((link) => (
            <div
              key={link.id}
              className="p-3 rounded border border-amber-500/30 bg-amber-500/10"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <LinkBadge type={link.from_type} id={link.from_id} />
                    <span className="text-xs text-zinc-500">{link.link_type}</span>
                    <LinkBadge type={link.to_type} id={link.to_id} />
                  </div>
                  <div className="flex flex-col gap-1 mt-2 text-xs text-zinc-500">
                    <div className="flex items-center gap-2">
                      <span>Source: {link.source_type}</span>
                      {link.confidence_score !== null && (
                        <span>
                          Confidence: {(link.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {link.link_metadata?.url && (
                      <div className="flex items-start gap-1 text-[10px] text-blue-400/70">
                        <span className="shrink-0">Extracted from:</span>
                        <a
                          href={link.link_metadata.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono truncate hover:text-blue-300 hover:underline"
                          title={link.link_metadata.url}
                        >
                          {link.link_metadata.url}
                        </a>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 ml-2">
                  {onLinkConfirm && (
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => onLinkConfirm(link.id)}
                      className="h-7 w-7 hover:bg-emerald-500/20 hover:text-emerald-400"
                      title="Confirm link"
                    >
                      <Check className="w-3 h-3" />
                    </Button>
                  )}
                  {onLinkReject && (
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => onLinkReject(link.id)}
                      className="h-7 w-7 hover:bg-red-500/20 hover:text-red-400"
                      title="Reject link"
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confirmed Links */}
      {confirmedLinks.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-emerald-400 flex items-center gap-2">
            <Badge variant="outline" className="bg-emerald-500/20 text-emerald-400">
              {confirmedLinks.length}
            </Badge>
            Confirmed Links
          </h3>
          {confirmedLinks.map((link) => (
            <div
              key={link.id}
              className="p-3 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <LinkBadge type={link.from_type} id={link.from_id} />
                    <span className="text-xs text-zinc-500">{link.link_type}</span>
                    <LinkBadge type={link.to_type} id={link.to_id} />
                  </div>
                  <div className="flex flex-col gap-1 mt-1 text-xs text-zinc-500">
                    <div className="flex items-center gap-2">
                      <span>Source: {link.source_type}</span>
                      {link.confidence_score !== null && (
                        <span>
                          Confidence: {(link.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {link.link_metadata?.url && (
                      <div className="flex items-start gap-1 text-[10px] text-blue-400/70">
                        <span className="shrink-0">Extracted from:</span>
                        <a
                          href={link.link_metadata.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono truncate hover:text-blue-300 hover:underline"
                          title={link.link_metadata.url}
                        >
                          {link.link_metadata.url}
                        </a>
                      </div>
                    )}
                  </div>
                </div>
                {onLinkDelete && (
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => onLinkDelete(link.id)}
                    className="h-7 w-7 hover:bg-red-500/20 hover:text-red-400"
                    title="Delete link"
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Rejected Links (collapsed by default) */}
      {rejectedLinks.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-semibold text-zinc-500 hover:text-zinc-400 flex items-center gap-2">
            <Badge variant="outline" className="bg-zinc-800 text-zinc-500">
              {rejectedLinks.length}
            </Badge>
            Rejected Links (Hidden)
          </summary>
          <div className="space-y-2 mt-2">
            {rejectedLinks.map((link) => (
              <div
                key={link.id}
                className="p-3 rounded border border-zinc-800 bg-zinc-900/30 opacity-50"
              >
                <div className="flex items-center gap-2 flex-wrap text-sm">
                  <LinkBadge type={link.from_type} id={link.from_id} />
                  <span className="text-xs text-zinc-600">{link.link_type}</span>
                  <LinkBadge type={link.to_type} id={link.to_id} />
                </div>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* No Links Message */}
      {context.links.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-zinc-500">No entity links found</p>
          <p className="text-xs text-zinc-600 mt-1">
            Links will be suggested automatically or can be created manually
          </p>
        </div>
      )}
    </div>
  );
}
