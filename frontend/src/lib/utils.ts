import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Extract a JIRA ticket key from text (title, branch, description).
 * Case-insensitive, returns uppercase key.
 * Checks multiple inputs in order — first match wins.
 */
export function extractJiraKey(...texts: (string | null | undefined)[]): string | null {
  // Known JIRA project prefixes (case-insensitive)
  const pattern = /\b(COMPUTE|PLTFRMOPS|PRODISSUE|PE|EXPLORER|MOSAIC|IMAGERY|DATA|INFRA|OPS|PLATFORM)-(\d+)\b/i;
  for (const text of texts) {
    if (!text) continue;
    const match = text.match(pattern);
    if (match) return `${match[1].toUpperCase()}-${match[2]}`;
  }
  return null;
}
