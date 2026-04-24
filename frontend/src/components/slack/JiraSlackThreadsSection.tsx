"use client";

import { useState, useCallback, useEffect } from "react";
import { Loader2, RefreshCw, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SlackThreadCard } from "./SlackThreadCard";
import { SlackThreadSummary } from "./SlackThreadSummary";
import { api, SlackThread, SlackThreadDetail } from "@/lib/api";

interface JiraSlackThreadsSectionProps {
  jiraKey: string;
}

export function JiraSlackThreadsSection({ jiraKey }: JiraSlackThreadsSectionProps) {
  const [threads, setThreads] = useState<SlackThread[]>([]);
  const [selectedThread, setSelectedThread] = useState<SlackThreadDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch threads for this JIRA key
  const fetchThreads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.slackThreadsByJira(jiraKey);
      setThreads(response.threads);
    } catch (err) {
      console.error("Failed to fetch Slack threads:", err);
      setError("Failed to load Slack threads");
    } finally {
      setLoading(false);
    }
  }, [jiraKey]);

  // Parse JIRA ticket for new Slack threads
  const parseJiraForThreads = useCallback(async () => {
    setParsing(true);
    setError(null);
    try {
      const response = await api.slackThreadParseJira(jiraKey, false);
      setThreads(response.threads);
      if (response.threads_found === 0) {
        setError("No Slack threads found in JIRA ticket description");
      }
    } catch (err) {
      console.error("Failed to parse JIRA for Slack threads:", err);
      setError("Failed to parse JIRA ticket");
    } finally {
      setParsing(false);
    }
  }, [jiraKey]);

  // Load thread details when clicked
  const handleThreadClick = useCallback(async (threadId: string) => {
    try {
      const thread = await api.slackThread(threadId);
      setSelectedThread(thread);
    } catch (err) {
      console.error("Failed to load thread details:", err);
    }
  }, []);

  // Fetch threads on mount
  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  if (loading && threads.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-zinc-400" />
          <h3 className="text-sm font-medium text-zinc-300">
            Slack Threads
            {threads.length > 0 && (
              <span className="ml-2 text-zinc-500">({threads.length})</span>
            )}
          </h3>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchThreads}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={parseJiraForThreads}
            disabled={parsing}
            className="gap-2"
          >
            <MessageSquare className="h-4 w-4" />
            {parsing ? "Parsing..." : "Parse JIRA"}
          </Button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3">
          <p className="text-sm text-amber-400">{error}</p>
        </div>
      )}

      {/* Thread list */}
      {threads.length === 0 && !loading && !error && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-8 text-center">
          <MessageSquare className="h-12 w-12 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-500 mb-4">
            No Slack threads found for this JIRA ticket
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={parseJiraForThreads}
            disabled={parsing}
            className="gap-2"
          >
            <MessageSquare className="h-4 w-4" />
            {parsing ? "Parsing..." : "Parse JIRA Description"}
          </Button>
        </div>
      )}

      {threads.length > 0 && (
        <div className="space-y-3">
          {threads.map((thread) => (
            <SlackThreadCard
              key={thread.id}
              thread={thread}
              onThreadClick={handleThreadClick}
            />
          ))}
        </div>
      )}

      {/* Selected thread detail view */}
      {selectedThread && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-zinc-300">Thread Details</h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedThread(null)}
              className="text-zinc-500 hover:text-zinc-300"
            >
              Close
            </Button>
          </div>
          <SlackThreadSummary thread={selectedThread} />
        </div>
      )}
    </div>
  );
}
