"use client";

import { useCallback } from "react";
import { usePoll } from "@/lib/polling";
import { api, LinkResponse } from "@/lib/api";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LinkBadge } from "@/components/context/LinkBadge";
import { Check, X, Lightbulb, CheckCheck } from "lucide-react";

export function SuggestedLinksCard() {
  const { data: links, loading, error, refresh } = usePoll<LinkResponse[]>(
    () => api.suggestedLinks(),
    300_000 // 5 minutes
  );

  const handleConfirm = useCallback(async (linkId: string) => {
    try {
      await api.confirmLink(linkId);
      refresh();
    } catch (err) {
      console.error("Failed to confirm link:", err);
    }
  }, [refresh]);

  const handleReject = useCallback(async (linkId: string) => {
    try {
      await api.rejectLink(linkId);
      refresh();
    } catch (err) {
      console.error("Failed to reject link:", err);
    }
  }, [refresh]);

  const handleBatchConfirm = useCallback(async () => {
    if (!links || links.length === 0) return;
    try {
      const linkIds = links.map(l => l.id);
      await api.batchConfirmLinks(linkIds);
      refresh();
    } catch (err) {
      console.error("Failed to batch confirm links:", err);
    }
  }, [links, refresh]);

  const menuItems = [
    { label: "Refresh", onClick: refresh },
    ...(links && links.length > 0 ? [
      { label: "Confirm All", onClick: handleBatchConfirm }
    ] : [])
  ];

  return (
    <ScrollableCard
      title="Suggested Links"
      icon={<Lightbulb className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !links && (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs text-zinc-500">Loading suggested links...</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded border border-red-800 bg-red-900/20">
          <p className="text-xs text-red-400">Failed to load suggested links</p>
        </div>
      )}

      {links && links.length === 0 && (
        <div className="text-center py-8">
          <p className="text-sm text-zinc-500">No suggested links</p>
          <p className="text-xs text-zinc-600 mt-1">
            Links will be suggested automatically by background jobs
          </p>
        </div>
      )}

      {links && links.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-zinc-500">
              {links.length} link{links.length !== 1 ? 's' : ''} awaiting review
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={handleBatchConfirm}
              className="h-6 text-xs text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
            >
              <CheckCheck className="w-3 h-3 mr-1" />
              Confirm All
            </Button>
          </div>

          {links.map((link) => (
            <div
              key={link.id}
              className="p-3 rounded border border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/15 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <LinkBadge type={link.from_type} id={link.from_id} />
                    <span className="text-xs text-zinc-500">{link.link_type}</span>
                    <LinkBadge type={link.to_type} id={link.to_id} />
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500">
                    <span className="capitalize">{link.source_type}</span>
                    {link.confidence_score !== null && (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                        {(link.confidence_score * 100).toFixed(0)}% confidence
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleConfirm(link.id)}
                    className="h-7 w-7 hover:bg-emerald-500/20 hover:text-emerald-400"
                    title="Confirm link"
                  >
                    <Check className="w-3 h-3" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => handleReject(link.id)}
                    className="h-7 w-7 hover:bg-red-500/20 hover:text-red-400"
                    title="Reject link"
                  >
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </ScrollableCard>
  );
}
