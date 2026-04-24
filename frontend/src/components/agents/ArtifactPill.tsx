"use client";

import { FileText, Pencil } from "lucide-react";

interface ArtifactPillProps {
  artifact: { path: string; type: string; tool: string };
  onClick: () => void;
}

export function ArtifactPill({ artifact, onClick }: ArtifactPillProps) {
  const filename = artifact.path.split("/").pop() || artifact.path;
  const isEdit = artifact.type === "edit";

  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-500/20 hover:text-emerald-300 transition-colors cursor-pointer"
      title={artifact.path.replace(/^\/Users\/aaryn\//, "~/")}
    >
      {isEdit ? (
        <Pencil className="h-2.5 w-2.5 shrink-0" />
      ) : (
        <FileText className="h-2.5 w-2.5 shrink-0" />
      )}
      <span className="truncate max-w-[200px]">{filename}</span>
    </button>
  );
}
