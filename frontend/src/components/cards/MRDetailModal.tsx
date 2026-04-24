"use client";

import { useState } from "react";
import { ExternalLink, CheckCircle, XCircle, FileText, GitBranch, Loader2, Eye, ThumbsUp } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, DetailedMR } from "@/lib/api";
import { formatHoursAgo } from "@/lib/time-utils";

interface MRDetailModalProps {
  mr: DetailedMR;
  open: boolean;
  onClose: () => void;
  onUpdate?: () => void;
}

function ReviewHistoryModal({
  reviews,
  open,
  onClose,
}: {
  reviews: Array<{ agent_id: string; session_id: string; commit_sha: string; timestamp: string }>;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">Review History</DialogTitle>
          <DialogDescription className="text-zinc-400">
            All review sessions for this MR
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {reviews.map((review, idx) => (
            <div
              key={idx}
              className="border border-zinc-800 rounded-md p-3 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-500">Review #{reviews.length - idx}</span>
                    <span className="text-xs text-zinc-600">•</span>
                    <span className="text-xs text-zinc-400">
                      {new Date(review.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-zinc-500">
                    Commit: {review.commit_sha.substring(0, 8)}
                  </div>
                </div>
                <a
                  href={`/agents/${review.agent_id}/chat`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:text-emerald-300 text-xs flex items-center gap-1"
                >
                  View Agent
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function MRDetailModal({ mr, open, onClose, onUpdate }: MRDetailModalProps) {
  const [loading, setLoading] = useState(false);
  const [showReviewHistory, setShowReviewHistory] = useState(false);
  const [localMR, setLocalMR] = useState(mr);

  const handleApprove = async () => {
    setLoading(true);
    try {
      const result = await api.mrApprove(localMR.project, localMR.iid);
      if (result.success) {
        // Show success feedback
        alert(result.message || "MR approved successfully");
      } else {
        alert(result.error || "Failed to approve MR");
      }
    } catch (error) {
      alert(`Error approving MR: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = async () => {
    if (!confirm("Are you sure you want to close this MR?")) return;

    setLoading(true);
    try {
      const result = await api.mrClose(localMR.project, localMR.iid);
      if (result.success) {
        alert(result.message || "MR closed successfully");
        onUpdate?.();
        onClose();
      } else {
        alert(result.error || "Failed to close MR");
      }
    } catch (error) {
      alert(`Error closing MR: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleDraft = async () => {
    setLoading(true);
    try {
      const newDraftStatus = !localMR.is_draft;
      const result = await api.mrToggleDraft(localMR.project, localMR.iid, newDraftStatus);
      if (result.success) {
        setLocalMR({ ...localMR, is_draft: result.is_draft });
      } else {
        alert(result.error || "Failed to toggle draft status");
      }
    } catch (error) {
      alert(`Error toggling draft: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async () => {
    // If there are existing reviews, show history modal
    if (localMR.reviews && localMR.reviews.length > 0) {
      setShowReviewHistory(true);
      return;
    }

    // Otherwise, trigger a new review
    if (!confirm(`This will spawn a headless agent to review this MR. Continue?`)) return;

    setLoading(true);
    try {
      const result = await api.mrReview(localMR.project, localMR.iid);
      if (result.success) {
        alert(
          `Review agent spawned successfully!\n\nAgent ID: ${result.agent_id}\n\nThe review will run in the background. Check the Agents page to see progress.`
        );
        onUpdate?.();
        onClose();
      } else {
        alert(result.error || "Failed to trigger review");
      }
    } catch (error) {
      alert(`Error triggering review: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <DialogTitle className="text-zinc-100 flex items-center gap-2">
                  <span className="text-zinc-500 font-mono text-sm uppercase">{localMR.project}</span>
                  <span>!{localMR.iid}</span>
                  {localMR.is_draft && (
                    <span className="text-xs bg-zinc-800 text-zinc-500 px-2 py-0.5 rounded">DRAFT</span>
                  )}
                </DialogTitle>
                <h3 className="text-lg font-medium text-zinc-200">{localMR.title}</h3>
              </div>
              <a
                href={localMR.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 text-sm"
              >
                GitLab
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </DialogHeader>

          {/* MR Details */}
          <div className="space-y-4 mt-4">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-zinc-500">Author:</span>
                <span className={`ml-2 ${localMR.is_mine ? 'text-emerald-400 font-medium' : 'text-zinc-300'}`}>
                  {localMR.author} {localMR.is_mine && '(you)'}
                </span>
              </div>
              <div>
                <span className="text-zinc-500">Created:</span>
                <span className="ml-2 text-zinc-300">{formatHoursAgo(localMR.age_created_hours)} ago</span>
              </div>
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-zinc-500" />
                <span className="font-mono text-xs text-zinc-400">{localMR.branch}</span>
                <span className="text-zinc-600">→</span>
                <span className="font-mono text-xs text-zinc-400">{localMR.target_branch || 'main'}</span>
              </div>
              <div>
                <span className="text-zinc-500">Last commit:</span>
                <span className="ml-2 text-zinc-300">{formatHoursAgo(localMR.age_last_commit_hours)} ago</span>
              </div>
            </div>

            {/* Description */}
            {localMR.description && (
              <div className="border-t border-zinc-800 pt-4">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="h-4 w-4 text-zinc-500" />
                  <span className="text-sm text-zinc-400">Description</span>
                </div>
                <div className="text-sm text-zinc-300 whitespace-pre-wrap bg-zinc-950/50 p-3 rounded border border-zinc-800 max-h-48 overflow-y-auto">
                  {localMR.description}
                </div>
              </div>
            )}

            {/* Review Status */}
            <div className="border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Eye className="h-4 w-4 text-zinc-500" />
                  <span className="text-sm text-zinc-400">Review Status</span>
                </div>
                {localMR.reviews && localMR.reviews.length > 0 ? (
                  <div className="flex items-center gap-2">
                    {localMR.needs_review ? (
                      <span className="text-sm text-amber-400 flex items-center gap-1">
                        <XCircle className="h-4 w-4" />
                        Needs re-review
                      </span>
                    ) : (
                      <span className="text-sm text-emerald-400 flex items-center gap-1">
                        <CheckCircle className="h-4 w-4" />
                        Reviewed
                      </span>
                    )}
                    <span className="text-xs text-zinc-500">({localMR.reviews.length} review{localMR.reviews.length > 1 ? 's' : ''})</span>
                  </div>
                ) : (
                  <span className="text-sm text-zinc-500">Not reviewed</span>
                )}
              </div>
            </div>

            {/* Labels */}
            {localMR.labels && localMR.labels.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                {localMR.labels.map(label => (
                  <span key={label} className="text-xs bg-zinc-800 text-zinc-400 px-2 py-1 rounded">
                    {label}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 mt-6 pt-4 border-t border-zinc-800">
            <Button
              onClick={handleReview}
              disabled={loading}
              variant="default"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Eye className="h-4 w-4 mr-2" />
                  {localMR.reviews && localMR.reviews.length > 0 ? 'View Reviews' : 'Review'}
                </>
              )}
            </Button>

            <Button
              onClick={handleApprove}
              disabled={loading}
              variant="outline"
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              <ThumbsUp className="h-4 w-4 mr-2" />
              Approve
            </Button>

            {localMR.is_mine && (
              <>
                <Button
                  onClick={handleClose}
                  disabled={loading}
                  variant="outline"
                  className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                >
                  <XCircle className="h-4 w-4 mr-2" />
                  Close
                </Button>

                <Button
                  onClick={handleToggleDraft}
                  disabled={loading}
                  variant="outline"
                  className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                >
                  {localMR.is_draft ? 'Mark Ready' : 'Mark Draft'}
                </Button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Review History Modal */}
      {showReviewHistory && localMR.reviews && (
        <ReviewHistoryModal
          reviews={localMR.reviews}
          open={showReviewHistory}
          onClose={() => setShowReviewHistory(false)}
        />
      )}
    </>
  );
}
