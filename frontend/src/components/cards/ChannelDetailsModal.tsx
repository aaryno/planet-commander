"use client";

import { useEffect, useState } from "react";
import { Loader2, X, Calendar, MessageCircle, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, SlackChannelDetails } from "@/lib/api";

interface ChannelDetailsModalProps {
  channel: string;
  onClose: () => void;
}

export function ChannelDetailsModal({
  channel,
  onClose,
}: ChannelDetailsModalProps) {
  const [details, setDetails] = useState<SlackChannelDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    api
      .slackChannelDetails(channel)
      .then((r) => setDetails(r))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setIsLoading(false));
  }, [channel]);

  return (
    <div className="fixed inset-0 z-[9999] flex items-start justify-center bg-black/50 p-4 overflow-y-auto">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg w-full max-w-md flex flex-col my-8">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-100">
            #{channel}
          </h2>
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
        <div className="p-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
            </div>
          ) : error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : details ? (
            <>
              {/* Date Range */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-zinc-400">
                  <Calendar className="h-4 w-4" />
                  <span className="text-xs font-medium">Date Range</span>
                </div>
                <div className="pl-6 space-y-1">
                  <div className="text-xs">
                    <span className="text-zinc-500">Earliest:</span>{" "}
                    <span className="text-zinc-300">{details.earliest_date || "—"}</span>
                  </div>
                  <div className="text-xs">
                    <span className="text-zinc-500">Latest:</span>{" "}
                    <span className="text-zinc-300">{details.latest_date || "—"}</span>
                  </div>
                </div>
              </div>

              {/* Message Counts */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-zinc-400">
                  <MessageCircle className="h-4 w-4" />
                  <span className="text-xs font-medium">Message Counts</span>
                </div>
                <div className="pl-6 space-y-1">
                  <div className="text-xs">
                    <span className="text-zinc-500">Total:</span>{" "}
                    <span className="text-zinc-300">{details.total_messages.toLocaleString()}</span>
                  </div>
                  <div className="text-xs">
                    <span className="text-zinc-500">Last day:</span>{" "}
                    <span className="text-zinc-300">{details.last_day_count}</span>
                  </div>
                </div>
              </div>

              {/* Averages */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-zinc-400">
                  <TrendingUp className="h-4 w-4" />
                  <span className="text-xs font-medium">Activity</span>
                </div>
                <div className="pl-6 space-y-1">
                  <div className="text-xs">
                    <span className="text-zinc-500">7-day avg:</span>{" "}
                    <span className="text-zinc-300">{details.last_week_avg} msg/day</span>
                  </div>
                  <div className="text-xs">
                    <span className="text-zinc-500">Total files:</span>{" "}
                    <span className="text-zinc-300">{details.total_files}</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-zinc-500">No data available</p>
          )}
        </div>
      </div>
    </div>
  );
}
