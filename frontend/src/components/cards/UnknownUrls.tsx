"use client";

import { useCallback, useState } from "react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, AlertCircle, Check, X, Sparkles, Eye, Code } from "lucide-react";
import { usePoll } from "@/lib/polling";
import { api } from "@/lib/api";

interface UnknownUrl {
  id: string;
  url: string;
  domain: string;
  first_seen_in_chat_id: string | null;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  reviewed: boolean;
  promoted_to_pattern: boolean;
  ignored: boolean;
}

interface UnknownUrlsResponse {
  unknown_urls: UnknownUrl[];
  total: number;
  unreviewed_count: number;
}

export function UnknownUrls() {
  const fetcher = useCallback(() => api.unknownUrls(), []);
  const { data, loading, error, refresh: refetch } = usePoll<UnknownUrlsResponse>(
    fetcher,
    300_000 // 5 minutes
  );

  const [generatedPattern, setGeneratedPattern] = useState<{ url_id: string; template: string } | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  const menuItems = [
    { label: "Refresh", onClick: refetch },
  ];

  const handleMarkReviewed = useCallback(async (id: string) => {
    setUpdating(id);
    try {
      await api.unknownUrlUpdate(id, { reviewed: true });
      await refetch();
    } catch (error) {
      console.error("Failed to mark as reviewed:", error);
    } finally {
      setUpdating(null);
    }
  }, [refetch]);

  const handleIgnore = useCallback(async (id: string) => {
    setUpdating(id);
    try {
      await api.unknownUrlUpdate(id, { ignored: true, reviewed: true });
      await refetch();
    } catch (error) {
      console.error("Failed to ignore URL:", error);
    } finally {
      setUpdating(null);
    }
  }, [refetch]);

  const handleGeneratePattern = useCallback(async (id: string) => {
    setUpdating(id);
    try {
      const result = await api.unknownUrlGeneratePattern(id);
      setGeneratedPattern({ url_id: id, template: result.code_template });
      // Also mark as promoted
      await api.unknownUrlUpdate(id, { promoted_to_pattern: true, reviewed: true });
      await refetch();
    } catch (error) {
      console.error("Failed to generate pattern:", error);
    } finally {
      setUpdating(null);
    }
  }, [refetch]);

  return (
    <ScrollableCard
      title="Unknown URLs"
      icon={<AlertCircle className="w-4 h-4" />}
      menuItems={menuItems}
    >
      {loading && !data && (
        <p className="text-xs text-zinc-500 text-center py-4">Loading...</p>
      )}

      {error && (
        <div className="p-3 rounded border border-red-800 bg-red-900/20">
          <p className="text-sm text-red-400">Failed to load unknown URLs</p>
          <p className="text-xs text-red-500 mt-1">{error.message}</p>
        </div>
      )}

      {data && data.total === 0 && (
        <p className="text-xs text-zinc-500 text-center py-4">
          No unknown URLs found. All URLs are recognized!
        </p>
      )}

      {data && data.total > 0 && (
        <>
          {/* Summary */}
          <div className="p-3 rounded border border-zinc-800 bg-zinc-900/50 mb-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-400">Total Unknown URLs:</span>
              <Badge variant="outline">{data.total}</Badge>
            </div>
            {data.unreviewed_count > 0 && (
              <div className="flex items-center justify-between text-xs mt-1">
                <span className="text-amber-400">Needs Review:</span>
                <Badge variant="outline" className="bg-amber-500/20 text-amber-400">
                  {data.unreviewed_count}
                </Badge>
              </div>
            )}
          </div>

          {/* URL List */}
          <div className="space-y-2">
            {data.unknown_urls.map((unknownUrl) => (
              <div
                key={unknownUrl.id}
                className={`p-3 rounded border transition-colors ${
                  unknownUrl.reviewed
                    ? "border-zinc-800 bg-zinc-900/30 opacity-70"
                    : "border-amber-500/30 bg-amber-500/10"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-zinc-300 font-mono truncate">
                        {unknownUrl.domain}
                      </span>
                      <Badge
                        variant="outline"
                        className="text-[10px] bg-zinc-800 text-zinc-400"
                      >
                        {unknownUrl.occurrence_count}x
                      </Badge>
                      {unknownUrl.promoted_to_pattern && (
                        <Badge
                          variant="outline"
                          className="text-[10px] bg-emerald-500/20 text-emerald-400"
                        >
                          Promoted
                        </Badge>
                      )}
                      {unknownUrl.ignored && (
                        <Badge
                          variant="outline"
                          className="text-[10px] bg-zinc-700 text-zinc-500"
                        >
                          Ignored
                        </Badge>
                      )}
                    </div>
                    <a
                      href={unknownUrl.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:text-blue-300 hover:underline font-mono break-all"
                      title={unknownUrl.url}
                    >
                      {unknownUrl.url.length > 80
                        ? unknownUrl.url.substring(0, 80) + "..."
                        : unknownUrl.url}
                    </a>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-zinc-500">
                      <span>
                        First seen:{" "}
                        {new Date(unknownUrl.first_seen_at).toLocaleDateString()}
                      </span>
                      {unknownUrl.last_seen_at !== unknownUrl.first_seen_at && (
                        <span>
                          Last seen:{" "}
                          {new Date(unknownUrl.last_seen_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>

                    {/* Review Actions */}
                    {!unknownUrl.reviewed && (
                      <div className="flex items-center gap-1 mt-3">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleMarkReviewed(unknownUrl.id)}
                          disabled={updating === unknownUrl.id}
                          className="h-6 px-2 text-[10px] text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                          title="Mark as reviewed (no action needed)"
                        >
                          <Eye className="h-3 w-3 mr-1" />
                          Reviewed
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleIgnore(unknownUrl.id)}
                          disabled={updating === unknownUrl.id}
                          className="h-6 px-2 text-[10px] text-zinc-500 hover:text-zinc-400 hover:bg-zinc-700/50"
                          title="Ignore this URL (won't show in review list)"
                        >
                          <X className="h-3 w-3 mr-1" />
                          Ignore
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleGeneratePattern(unknownUrl.id)}
                          disabled={updating === unknownUrl.id}
                          className="h-6 px-2 text-[10px] text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                          title="Generate URL pattern template"
                        >
                          <Sparkles className="h-3 w-3 mr-1" />
                          Generate Pattern
                        </Button>
                      </div>
                    )}
                  </div>
                  <a
                    href={unknownUrl.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0"
                  >
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-6 w-6 text-zinc-500 hover:text-zinc-300"
                      title="Open URL"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Generated Pattern Modal */}
          {generatedPattern && (
            <div className="mt-4 p-4 rounded border border-blue-500/30 bg-blue-500/10">
              <div className="flex items-start justify-between mb-2">
                <h4 className="text-xs font-semibold text-blue-400 flex items-center gap-1">
                  <Code className="h-3 w-3" />
                  Generated Pattern Template
                </h4>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setGeneratedPattern(null)}
                  className="h-5 w-5 p-0 text-zinc-500 hover:text-zinc-300"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
              <pre className="text-[10px] text-zinc-300 bg-zinc-900 p-3 rounded overflow-x-auto font-mono">
                {generatedPattern.template}
              </pre>
              <p className="text-[10px] text-zinc-500 mt-2">
                Copy this code to <code className="text-blue-400">url_classifier.py</code> and restart the backend.
              </p>
            </div>
          )}

          {/* Help Text */}
          <div className="mt-4 p-3 rounded border border-zinc-800 bg-zinc-900/30">
            <p className="text-[10px] text-zinc-500 leading-relaxed">
              <strong className="text-zinc-400">What are Unknown URLs?</strong>
              <br />
              These URLs were found in chat messages but don't match any known
              patterns. Review options:
              <br />• <strong className="text-emerald-400">Reviewed:</strong> Mark as seen (no action needed)
              <br />• <strong className="text-zinc-400">Ignore:</strong> Hide from review list
              <br />• <strong className="text-blue-400">Generate Pattern:</strong> Create code template for new URL type
            </p>
          </div>
        </>
      )}
    </ScrollableCard>
  );
}
