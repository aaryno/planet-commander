"use client";

import { useState } from "react";
import { Lightbulb, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { ScrollableCard } from "@/components/ui/scrollable-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface SuggestedPattern {
  title: string;
  pattern_type: string;
  confidence: number;
  similarity_score: number;
  combined_score: number;
  matched_keywords: string[];
  relevance: string;
  trigger: string;
  approach: string;
  source_artifact: string;
}

interface SuggestedPatternsProps {
  patterns: SuggestedPattern[];
}

export function SuggestedPatterns({ patterns }: SuggestedPatternsProps) {
  if (!patterns || patterns.length === 0) {
    return null; // Don't show component if no patterns
  }

  const stickyHeader = (
    <div className="space-y-2">
      <div className="text-xs text-zinc-400">
        Based on your prompt, here are relevant patterns from past investigations:
      </div>
    </div>
  );

  return (
    <ScrollableCard
      title="Suggested Patterns"
      icon={<Lightbulb className="w-4 h-4 text-amber-400" />}
      stickyHeader={stickyHeader}
    >
      <div className="space-y-3">
        {patterns.map((pattern, index) => (
          <PatternCard key={index} pattern={pattern} rank={index + 1} />
        ))}
      </div>
    </ScrollableCard>
  );
}

interface PatternCardProps {
  pattern: SuggestedPattern;
  rank: number;
}

function PatternCard({ pattern, rank }: PatternCardProps) {
  const [expanded, setExpanded] = useState(rank === 1); // Auto-expand top match

  const getPatternTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      integration: "text-blue-400 bg-blue-500/20",
      investigation: "text-purple-400 bg-purple-500/20",
      root_cause: "text-red-400 bg-red-500/20",
      resolution: "text-emerald-400 bg-emerald-500/20",
      cost_analysis: "text-amber-400 bg-amber-500/20",
      alert_correlation: "text-orange-400 bg-orange-500/20",
      deployment: "text-cyan-400 bg-cyan-500/20",
      performance: "text-pink-400 bg-pink-500/20",
    };
    return colors[type] || "text-zinc-400 bg-zinc-500/20";
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return "text-emerald-400";
    if (confidence >= 0.6) return "text-amber-400";
    return "text-zinc-400";
  };

  const formatPatternType = (type: string) => {
    return type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const openSourceArtifact = () => {
    // Extract filename from full path
    const filename = pattern.source_artifact.split("/").pop() || "";
    // Open in VS Code (requires VS Code extension integration)
    // For now, just log - this would need proper VS Code command integration
    console.log("Open artifact:", pattern.source_artifact);
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50">
      {/* Header */}
      <div
        className="p-3 cursor-pointer hover:bg-zinc-800/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            {/* Rank badge */}
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-zinc-500">#{rank}</span>
              <Badge className={getPatternTypeColor(pattern.pattern_type)}>
                {formatPatternType(pattern.pattern_type)}
              </Badge>
            </div>

            {/* Title */}
            <div className="font-medium text-sm text-zinc-200 mb-1">
              {pattern.title}
            </div>

            {/* Relevance */}
            <div className="text-xs text-zinc-400">{pattern.relevance}</div>
          </div>

          {/* Expand button */}
          <div className="flex items-center gap-2">
            <div className="text-right">
              <div className="text-xs text-zinc-500">Match</div>
              <div
                className={`text-lg font-bold ${getConfidenceColor(pattern.combined_score)}`}
              >
                {Math.round(pattern.combined_score * 100)}%
              </div>
            </div>
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-400" />
            )}
          </div>
        </div>

        {/* Matched keywords */}
        <div className="flex gap-1 mt-2 flex-wrap">
          {pattern.matched_keywords.map((keyword, i) => (
            <span
              key={i}
              className="text-xs px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400"
            >
              {keyword}
            </span>
          ))}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-zinc-800">
          {/* Scores breakdown */}
          <div className="grid grid-cols-3 gap-2 text-xs pt-3">
            <div>
              <div className="text-zinc-500">Similarity</div>
              <div className={getConfidenceColor(pattern.similarity_score)}>
                {Math.round(pattern.similarity_score * 100)}%
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Confidence</div>
              <div className={getConfidenceColor(pattern.confidence)}>
                {Math.round(pattern.confidence * 100)}%
              </div>
            </div>
            <div>
              <div className="text-zinc-500">Combined</div>
              <div className={getConfidenceColor(pattern.combined_score)}>
                {Math.round(pattern.combined_score * 100)}%
              </div>
            </div>
          </div>

          {/* Trigger */}
          {pattern.trigger && (
            <div>
              <div className="text-xs font-semibold text-zinc-400 mb-1">
                When to use:
              </div>
              <div className="text-xs text-zinc-300 bg-zinc-800/50 rounded p-2">
                {pattern.trigger}
              </div>
            </div>
          )}

          {/* Approach */}
          {pattern.approach && (
            <div>
              <div className="text-xs font-semibold text-zinc-400 mb-1">
                Approach:
              </div>
              <div className="text-xs text-zinc-300 bg-zinc-800/50 rounded p-2 whitespace-pre-wrap">
                {pattern.approach}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={openSourceArtifact}
              className="text-xs"
            >
              <ExternalLink className="w-3 h-3 mr-1" />
              View Full Artifact
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
