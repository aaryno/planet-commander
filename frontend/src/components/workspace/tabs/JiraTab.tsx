"use client";

import { useState, useCallback } from "react";
import { Plus, Loader2, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { JiraCard } from "@/components/agents/JiraCard";
import type { WorkspaceDetail } from "@/lib/api";
import { api } from "@/lib/api";

interface JiraTabProps {
  workspace: WorkspaceDetail;
  onUpdate?: (workspace: WorkspaceDetail) => void;
}

export function JiraTab({ workspace, onUpdate }: JiraTabProps) {
  const [adding, setAdding] = useState(false);
  const [newJiraKey, setNewJiraKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const primaryTicket = workspace.jira_tickets.find(t => t.is_primary);
  const relatedTickets = workspace.jira_tickets.filter(t => !t.is_primary);

  const handleAddTicket = useCallback(async () => {
    if (!newJiraKey.trim()) return;

    setSubmitting(true);
    try {
      const updated = await api.workspaceAddJira(workspace.id, newJiraKey.toUpperCase(), false);
      onUpdate?.(updated);
      setNewJiraKey("");
      setAdding(false);
    } catch (error) {
      console.error("Failed to add JIRA ticket:", error);
      alert("Failed to add JIRA ticket");
    } finally {
      setSubmitting(false);
    }
  }, [workspace.id, newJiraKey, onUpdate]);

  const handleRemoveTicket = useCallback(async (jiraKey: string) => {
    try {
      await api.workspaceRemoveJira(workspace.id, jiraKey);
      // Reload workspace
      const updated = await api.workspaceGet(workspace.id);
      onUpdate?.(updated);
    } catch (error) {
      console.error("Failed to remove JIRA ticket:", error);
      alert("Failed to remove JIRA ticket");
    }
  }, [workspace.id, onUpdate]);

  const handleTogglePrimary = useCallback(async (jiraKey: string, isPrimary: boolean) => {
    try {
      const updated = await api.workspaceUpdateJira(workspace.id, jiraKey, {
        is_primary: !isPrimary,
      });
      onUpdate?.(updated);
    } catch (error) {
      console.error("Failed to update JIRA ticket:", error);
    }
  }, [workspace.id, onUpdate]);

  const handleToggleDescription = useCallback(async (jiraKey: string, expanded: boolean) => {
    try {
      const updated = await api.workspaceUpdateJira(workspace.id, jiraKey, {
        description_expanded: !expanded,
      });
      onUpdate?.(updated);
    } catch (error) {
      console.error("Failed to update JIRA ticket:", error);
    }
  }, [workspace.id, onUpdate]);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <div className="space-y-4">
        {/* Add Ticket Section */}
        <div className="flex items-center gap-2">
          {!adding ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAdding(true)}
              className="text-xs"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add JIRA Ticket
            </Button>
          ) : (
            <>
              <Input
                value={newJiraKey}
                onChange={(e) => setNewJiraKey(e.target.value.toUpperCase())}
                placeholder="COMPUTE-1234"
                className="h-8 text-xs flex-1"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddTicket();
                  if (e.key === "Escape") {
                    setNewJiraKey("");
                    setAdding(false);
                  }
                }}
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={handleAddTicket}
                disabled={submitting || !newJiraKey.trim()}
                className="h-8 px-3 text-xs"
              >
                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Add"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setNewJiraKey("");
                  setAdding(false);
                }}
                className="h-8 px-3 text-xs"
              >
                Cancel
              </Button>
            </>
          )}
        </div>

        {/* Primary Ticket */}
        {primaryTicket && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Star className="h-4 w-4 text-yellow-400 fill-yellow-400" />
              <h3 className="text-sm font-medium text-zinc-300">Primary Ticket</h3>
            </div>
            <JiraCard
              jiraKey={primaryTicket.key}
              onClose={() => handleRemoveTicket(primaryTicket.key)}
              isPinned={true}
              onTogglePin={() => handleTogglePrimary(primaryTicket.key, true)}
              showDescription={primaryTicket.description_expanded}
              onToggleDescription={() => handleToggleDescription(primaryTicket.key, primaryTicket.description_expanded || false)}
            />
          </div>
        )}

        {/* Related Tickets */}
        {relatedTickets.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Star className="h-4 w-4 text-zinc-500" />
              <h3 className="text-sm font-medium text-zinc-300">Related Tickets</h3>
            </div>
            <div className="space-y-2">
              {relatedTickets.map((ticket) => (
                <JiraCard
                  key={ticket.key}
                  jiraKey={ticket.key}
                  onClose={() => handleRemoveTicket(ticket.key)}
                  isPinned={false}
                  onTogglePin={() => handleTogglePrimary(ticket.key, false)}
                  showDescription={ticket.description_expanded}
                  onToggleDescription={() => handleToggleDescription(ticket.key, ticket.description_expanded || false)}
                />
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {workspace.jira_tickets.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-zinc-500">No JIRA tickets in this workspace</p>
            <p className="text-xs text-zinc-600 mt-1">Click "Add JIRA Ticket" to get started</p>
          </div>
        )}
      </div>
    </div>
  );
}
