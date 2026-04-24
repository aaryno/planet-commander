"use client";

import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Lightbulb, RefreshCw } from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import { api, SuggestedSkill } from "@/lib/api";
import { SkillSuggestionCard } from "./SkillSuggestionCard";

interface SkillSuggestionsSectionProps {
  contextId: string;
  minConfidence?: number;
  autoLoad?: boolean;
}

export function SkillSuggestionsSection({
  contextId,
  minConfidence = 0.3,
  autoLoad = true
}: SkillSuggestionsSectionProps) {
  const [suggestions, setSuggestions] = useState<SuggestedSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSuggestions = useCallback(async () => {
    if (!contextId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.skillsSuggestions(contextId, minConfidence);
      setSuggestions(response.suggestions);
    } catch (err) {
      console.error("Failed to load skill suggestions:", err);
      setError("Failed to load suggestions");
    } finally {
      setLoading(false);
    }
  }, [contextId, minConfidence]);

  useEffect(() => {
    if (autoLoad) {
      loadSuggestions();
    }
  }, [autoLoad, loadSuggestions]);

  const handleAction = () => {
    // Reload suggestions after action
    loadSuggestions();
  };

  if (loading && suggestions.length === 0) {
    return (
      <p className="text-xs text-zinc-500 py-4">Loading skill suggestions...</p>
    );
  }

  if (error) {
    return (
      <p className="text-xs text-red-400 py-4">{error}</p>
    );
  }

  if (suggestions.length === 0) {
    return null; // Don't show section if no suggestions
  }

  return (
    <ScrollableCard
      title="Suggested Skills"
      icon={<Lightbulb className="h-4 w-4" />}
      menuItems={[
        {
          label: "Refresh",
          onClick: loadSuggestions,
        }
      ]}
    >
      <div className="space-y-2">
        {suggestions.map((suggestion) => (
          <SkillSuggestionCard
            key={suggestion.skill.id}
            contextId={contextId}
            suggestion={suggestion}
            onAction={handleAction}
          />
        ))}
      </div>

      {suggestions.length > 0 && (
        <div className="mt-3 pt-3 border-t border-zinc-800">
          <p className="text-xs text-zinc-500">
            Showing {suggestions.length} skill{suggestions.length !== 1 ? "s" : ""} with {Math.round(minConfidence * 100)}%+ confidence
          </p>
        </div>
      )}
    </ScrollableCard>
  );
}
