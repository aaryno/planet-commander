"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Lightbulb, CheckCircle, XCircle, Clock } from "lucide-react";
import { useState } from "react";
import { api, SuggestedSkill } from "@/lib/api";

interface SkillSuggestionCardProps {
  contextId: string;
  suggestion: SuggestedSkill;
  onAction?: (action: string) => void;
}

export function SkillSuggestionCard({
  contextId,
  suggestion,
  onAction
}: SkillSuggestionCardProps) {
  const [actioned, setActioned] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleAction = async (action: string) => {
    setLoading(true);
    try {
      await api.skillsRecordAction(contextId, suggestion.skill.id, action);
      setActioned(true);
      onAction?.(action);
    } catch (error) {
      console.error("Failed to record skill action:", error);
    } finally {
      setLoading(false);
    }
  };

  const confidenceColor =
    suggestion.confidence >= 0.7 ? "text-emerald-400" :
    suggestion.confidence >= 0.5 ? "text-blue-400" :
    "text-amber-400";

  const confidenceBg =
    suggestion.confidence >= 0.7 ? "bg-emerald-500/20" :
    suggestion.confidence >= 0.5 ? "bg-blue-500/20" :
    "bg-amber-500/20";

  return (
    <Card className="border-zinc-800 bg-zinc-900/50 hover:bg-zinc-900/70 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Lightbulb className={`h-4 w-4 ${confidenceColor}`} />
            <span className="text-sm font-medium text-zinc-200">
              {suggestion.skill.title || suggestion.skill.skill_name}
            </span>
          </div>
          <Badge variant="outline" className={`text-xs ${confidenceBg} ${confidenceColor} border-none`}>
            {Math.round(suggestion.confidence * 100)}% match
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Description */}
        {suggestion.skill.description && (
          <p className="text-xs text-zinc-400 line-clamp-2">
            {suggestion.skill.description}
          </p>
        )}

        {/* Match reasons */}
        {suggestion.match_reasons.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {suggestion.match_reasons.map((reason, idx) => (
              <Badge key={idx} variant="secondary" className="text-xs">
                {reason.type === "label_match" && `Labels: ${reason.values?.join(", ")}`}
                {reason.type === "keyword_match" && `Keywords: ${reason.values?.join(", ")}`}
                {reason.type === "system_match" && `Systems: ${reason.values?.join(", ")}`}
                {reason.type === "incident_boost" && "Incident"}
              </Badge>
            ))}
          </div>
        )}

        {/* Metadata */}
        <div className="flex gap-3 text-xs text-zinc-500">
          {suggestion.skill.category && <span className="capitalize">{suggestion.skill.category}</span>}
          {suggestion.skill.category && suggestion.skill.estimated_duration && <span>•</span>}
          {suggestion.skill.estimated_duration && <span>{suggestion.skill.estimated_duration}</span>}
        </div>

        {/* Actions */}
        {!actioned && (
          <div className="flex gap-2 pt-2">
            <Button
              size="sm"
              variant="default"
              onClick={() => handleAction("accepted")}
              disabled={loading}
              className="flex-1"
            >
              <CheckCircle className="h-3 w-3 mr-1" />
              Use Skill
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleAction("dismissed")}
              disabled={loading}
              title="Dismiss"
            >
              <XCircle className="h-3 w-3" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleAction("deferred")}
              disabled={loading}
              title="Defer"
            >
              <Clock className="h-3 w-3" />
            </Button>
          </div>
        )}

        {actioned && (
          <p className="text-xs text-zinc-500 italic">Action recorded</p>
        )}
      </CardContent>
    </Card>
  );
}
