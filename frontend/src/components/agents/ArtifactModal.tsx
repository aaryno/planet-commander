"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, FileText, Loader2, Maximize2, Minimize2, Search, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";
import type { ArtifactContent } from "@/lib/api";
import { CodeBlock } from "./RichText";

const MARKDOWN_EXTENSIONS = new Set(["md", "mdx", "markdown"]);

interface ArtifactModalProps {
  agentId: string;
  path: string;
  onClose: () => void;
}

export function ArtifactModal({ agentId, path, onClose }: ArtifactModalProps) {
  const [artifact, setArtifact] = useState<ArtifactContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [maximized, setMaximized] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchIndex, setSearchIndex] = useState(0);
  const [matchCount, setMatchCount] = useState(0);
  const contentRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.agentArtifactContent(agentId, path)
      .then(setArtifact)
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, [agentId, path]);

  // Search highlighting
  useEffect(() => {
    if (!searchQuery || !contentRef.current) {
      setMatchCount(0);
      return;
    }
    const text = contentRef.current.textContent || "";
    const regex = new RegExp(searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    const matches = text.match(regex);
    setMatchCount(matches?.length || 0);
    setSearchIndex(0);
  }, [searchQuery, artifact]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if ((e.metaKey || e.ctrlKey) && e.key === "f") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const navigateMatch = useCallback((delta: number) => {
    if (matchCount === 0) return;
    setSearchIndex((prev) => (prev + delta + matchCount) % matchCount);
  }, [matchCount]);

  const isMarkdown = artifact && MARKDOWN_EXTENSIONS.has(artifact.language);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className={`bg-zinc-900 border border-zinc-700 shadow-2xl flex flex-col transition-all duration-200 ${
          maximized
            ? "w-full h-full rounded-none"
            : "w-[90vw] max-w-4xl h-[80vh] rounded-lg"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="h-4 w-4 text-emerald-400 shrink-0" />
            <span className="text-sm font-semibold text-zinc-200 truncate">
              {artifact?.filename || path.split("/").pop()}
            </span>
            <span className="text-[10px] text-zinc-500 truncate hidden sm:block">
              {path.replace(/^\/Users\/aaryn\//, "~/")}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => {
                const url = `http://localhost:9000/api/agents/${agentId}/artifact-content?path=${encodeURIComponent(path)}&raw=true`;
                window.open(url, "_blank");
              }}
              className="p-1 text-zinc-500 hover:text-blue-400 transition-colors"
              title="Open in new tab"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setMaximized(!maximized)}
              className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
              title={maximized ? "Restore" : "Maximize"}
            >
              {maximized ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
            <button
              onClick={onClose}
              className="p-1 text-zinc-500 hover:text-zinc-200 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Search bar */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-zinc-800 shrink-0">
          <Search className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
          <input
            ref={searchRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 outline-none"
          />
          {searchQuery && (
            <div className="flex items-center gap-1 shrink-0">
              <span className="text-[10px] text-zinc-500">
                {matchCount > 0 ? `${searchIndex + 1}/${matchCount}` : "0 matches"}
              </span>
              <button onClick={() => navigateMatch(-1)} className="p-0.5 text-zinc-500 hover:text-zinc-300">
                <ChevronUp className="h-3 w-3" />
              </button>
              <button onClick={() => navigateMatch(1)} className="p-0.5 text-zinc-500 hover:text-zinc-300">
                <ChevronDown className="h-3 w-3" />
              </button>
              <button onClick={() => setSearchQuery("")} className="p-0.5 text-zinc-500 hover:text-zinc-300">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Content */}
        <div ref={contentRef} className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="h-6 w-6 text-zinc-500 animate-spin" />
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}
          {artifact && !loading && (
            isMarkdown ? (
              <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5 prose-headings:mt-4 prose-headings:mb-2 prose-a:text-blue-400 prose-code:text-emerald-400 prose-code:bg-zinc-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-table:text-sm">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    pre({ children }) { return <>{children}</>; },
                    code({ className, children }) {
                      const match = /language-(\w+)/.exec(className || "");
                      const codeStr = String(children).replace(/\n$/, "");
                      if (!className && !codeStr.includes("\n")) {
                        return <code className={className}>{children}</code>;
                      }
                      return <CodeBlock language={match?.[1]}>{codeStr}</CodeBlock>;
                    },
                  }}
                >
                  {artifact.content}
                </ReactMarkdown>
              </div>
            ) : (
              <CodeBlock language={artifact.language}>{artifact.content}</CodeBlock>
            )
          )}
        </div>

        {/* Footer */}
        {artifact && (
          <div className="flex items-center gap-3 px-4 py-2 border-t border-zinc-800 shrink-0">
            <span className="text-[10px] text-zinc-500">
              {(artifact.size / 1024).toFixed(1)} KB
            </span>
            <span className="text-[10px] text-zinc-600">·</span>
            <span className="text-[10px] text-zinc-500">{artifact.language}</span>
          </div>
        )}
      </div>
    </div>
  );
}
