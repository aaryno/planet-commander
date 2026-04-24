"use client";

import { useState, useCallback } from "react";
import { Check, Copy, ExternalLink, GitBranch } from "lucide-react";
import { useRepoContext, fileToGitLabUrl } from "@/lib/repo-context";

/**
 * Auto-linkify URLs and file paths in text content.
 * - URLs (http/https) become clickable links
 * - Absolute file paths matching the agent's repo become GitLab links
 * - Other absolute file paths become file:// links
 */
export function Linkify({ text, className = "" }: { text: string; className?: string }) {
  const repo = useRepoContext();

  // Combined regex — URLs first, then file paths (with optional :lineNumber suffix)
  const COMBINED = new RegExp(
    `(https?:\\/\\/[^\\s<>"')\\]]+)|((?:\\/Users\\/|\\/home\\/|\\/tmp\\/|\\/var\\/|\\/etc\\/|~\\/)[^\\s<>"')\\],:]+(:\\d+)?)`,
    "g"
  );

  const parts: (string | React.ReactNode)[] = [];
  let lastIndex = 0;
  let match;

  while ((match = COMBINED.exec(text)) !== null) {
    // Add text before match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const url = match[1];
    const filePath = match[2];

    if (url) {
      parts.push(
        <a
          key={match.index}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:text-blue-300 hover:underline break-all"
        >
          {url}
        </a>
      );
    } else if (filePath) {
      // Try GitLab URL first (if we have repo context)
      const gitlabResult = repo ? fileToGitLabUrl(filePath, repo) : null;

      if (gitlabResult) {
        parts.push(
          <a
            key={match.index}
            href={gitlabResult.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-400 hover:text-emerald-300 hover:underline break-all inline-flex items-center gap-1"
            title={`View on GitLab: ${gitlabResult.relativePath}${gitlabResult.line ? `:${gitlabResult.line}` : ""}`}
          >
            {filePath}
            <GitBranch className="h-2.5 w-2.5 inline shrink-0 opacity-60" />
          </a>
        );
      } else {
        // Fallback to file:// link
        const resolved = filePath.startsWith("~/")
          ? `/Users/aaryn/${filePath.slice(2)}`
          : filePath;
        // Strip line number for file:// URLs
        const cleanResolved = resolved.replace(/:\d+$/, "");
        parts.push(
          <a
            key={match.index}
            href={`file://${cleanResolved}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-emerald-400 hover:text-emerald-300 hover:underline break-all inline-flex items-center gap-1"
            title={`Open ${filePath}`}
          >
            {filePath}
            <ExternalLink className="h-2.5 w-2.5 inline shrink-0 opacity-60" />
          </a>
        );
      }
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return <span className={className}>{parts}</span>;
}

/**
 * Code block with copy-to-clipboard button.
 */
export function CodeBlock({ children, language }: { children: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement("textarea");
      textarea.value = children;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [children]);

  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1 rounded bg-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="Copy to clipboard"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </button>
      <pre className="bg-zinc-800 border border-zinc-700 rounded-md p-3 overflow-x-auto text-sm">
        {language && (
          <span className="text-[10px] text-zinc-500 absolute top-1 left-2">{language}</span>
        )}
        <code className="text-emerald-400">{children}</code>
      </pre>
    </div>
  );
}

/**
 * Render user message text with auto-linked URLs and file paths.
 */
export function UserMessageContent({ content }: { content: string }) {
  // Split by lines and linkify each
  return (
    <p className="text-sm text-zinc-300 whitespace-pre-wrap break-words">
      <Linkify text={content} />
    </p>
  );
}
