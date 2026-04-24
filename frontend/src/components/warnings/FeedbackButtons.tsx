"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, WarningEvent } from "@/lib/api";

interface FeedbackButtonsProps {
  warning: WarningEvent;
  onFeedbackSubmitted?: () => void;
}

export function FeedbackButtons({ warning, onFeedbackSubmitted }: FeedbackButtonsProps) {
  const [submitting, setSubmitting] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<"correct" | "incorrect" | null>(null);

  const handlePredictionFeedback = async (wasCorrect: boolean) => {
    if (submitting || feedbackGiven) return;

    setSubmitting(true);

    try {
      // Determine if it actually escalated
      const actualEscalated = warning.escalated;

      await api.submitPredictionFeedback(warning.id, {
        prediction_was_correct: wasCorrect,
        actual_escalated: actualEscalated,
        predicted_probability: warning.escalation_probability,
        submitted_by: "user", // TODO: Get actual user from auth
      });

      setFeedbackGiven(wasCorrect ? "correct" : "incorrect");

      if (onFeedbackSubmitted) {
        onFeedbackSubmitted();
      }
    } catch (error) {
      console.error("Failed to submit feedback:", error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {!feedbackGiven ? (
        <>
          <span className="text-xs text-zinc-500">Was prediction accurate?</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handlePredictionFeedback(true)}
            disabled={submitting}
            className="h-7 px-2 text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/10"
          >
            <ThumbsUp className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handlePredictionFeedback(false)}
            disabled={submitting}
            className="h-7 px-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/10"
          >
            <ThumbsDown className="w-3.5 h-3.5" />
          </Button>
        </>
      ) : (
        <div className="flex items-center gap-1.5 text-xs">
          {feedbackGiven === "correct" ? (
            <>
              <ThumbsUp className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Thanks for your feedback!</span>
            </>
          ) : (
            <>
              <ThumbsDown className="w-3.5 h-3.5 text-red-400" />
              <span className="text-red-400">Thanks! We'll improve.</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
