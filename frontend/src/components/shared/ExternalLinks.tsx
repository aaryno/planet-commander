"use client";

import { ExternalLink } from "lucide-react";

interface ExternalLinksProps {
  links: Array<{ label: string; url: string; icon?: React.ReactNode }>;
}

export function ExternalLinks({ links }: ExternalLinksProps) {
  if (links.length === 0) return null;

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {links.map((link) => (
        <a
          key={link.url}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          {link.icon || <ExternalLink className="h-2.5 w-2.5" />}
          {link.label}
        </a>
      ))}
    </div>
  );
}
