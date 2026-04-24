/**
 * Parse JIRA wiki markup and render as React elements.
 *
 * Supports:
 * - h1. h2. h3. h4. headers
 * - *bold*
 * - _italic_
 * - -strikethrough-
 * - {{code}}
 * - {code}...{code} code blocks
 * - * bullet lists, # numbered lists
 * - || header | cells | (tables)
 * - [link|url] and [url]
 * - {quote}blockquote{quote}
 * - {noformat}...{noformat}
 * - {panel}...{panel}, {info}, {note}, {warning}, {tip}
 * - COMPUTE-1234 ticket references (auto-linked)
 */

import React from "react";

export function parseJiraMarkup(text: string): React.ReactNode[] {
  if (!text) return [];

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: React.ReactNode[][] = [];
  let numberedItems: React.ReactNode[][] = [];
  let quoteLines: string[] = [];
  let tableRows: string[][] = [];
  let tableHasHeader = false;
  let inQuote = false;
  let inCode = false;
  let codeLines: string[] = [];
  let codeLang = "";
  let key = 0;

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${key++}`} className="list-disc list-inside space-y-0.5 my-1.5 text-xs">
          {listItems.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      );
      listItems = [];
    }
    if (numberedItems.length > 0) {
      elements.push(
        <ol key={`olist-${key++}`} className="list-decimal list-inside space-y-0.5 my-1.5 text-xs">
          {numberedItems.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ol>
      );
      numberedItems = [];
    }
  };

  const flushQuote = () => {
    if (quoteLines.length > 0) {
      elements.push(
        <blockquote key={`quote-${key++}`} className="border-l-2 border-zinc-600 pl-3 my-2 text-zinc-400 italic text-xs">
          {quoteLines.map((line, i) => (
            <p key={i} className="my-0.5">{parseInline(line)}</p>
          ))}
        </blockquote>
      );
      quoteLines = [];
    }
  };

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const headerRow = tableHasHeader ? tableRows[0] : null;
    const bodyRows = tableHasHeader ? tableRows.slice(1) : tableRows;
    elements.push(
      <div key={`table-${key++}`} className="my-2 overflow-x-auto">
        <table className="text-[11px] border-collapse w-full">
          {headerRow && (
            <thead>
              <tr>
                {headerRow.map((cell, i) => (
                  <th key={i} className="border border-zinc-700 bg-zinc-800/50 px-2 py-1 text-left text-zinc-300 font-semibold">
                    {parseInline(cell.trim())}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {bodyRows.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci} className="border border-zinc-700/50 px-2 py-1 text-zinc-400">
                    {parseInline(cell.trim())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    tableHasHeader = false;
  };

  const flushCode = () => {
    if (codeLines.length > 0) {
      elements.push(
        <pre key={`code-${key++}`} className="my-2 p-3 bg-zinc-800/80 rounded-lg text-[11px] text-cyan-300 font-mono overflow-x-auto whitespace-pre-wrap">
          {codeLines.join('\n')}
        </pre>
      );
      codeLines = [];
      codeLang = "";
    }
  };

  for (let line of lines) {
    const trimmed = line.trim();

    // Code block toggle
    if (trimmed.match(/^\{code(:[^}]*)?\}$/) || trimmed === '{noformat}') {
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        flushList();
        flushTable();
        const langMatch = trimmed.match(/\{code:(\w+)\}/);
        codeLang = langMatch ? langMatch[1] : "";
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    // Quote block toggle
    if (trimmed === '{quote}') {
      if (inQuote) {
        flushList();
        flushQuote();
        inQuote = false;
      } else {
        flushList();
        flushTable();
        inQuote = true;
      }
      continue;
    }

    if (inQuote) {
      if (trimmed) quoteLines.push(trimmed);
      continue;
    }

    // Panel/info/note markers — skip the marker, content flows normally
    if (trimmed.match(/^\{(panel|info|note|warning|tip)(:[^}]*)?\}$/)) continue;

    // Table row: || header || or | cell |
    if (trimmed.startsWith('||') || (trimmed.startsWith('|') && trimmed.endsWith('|'))) {
      flushList();
      const isHeader = trimmed.startsWith('||');
      const separator = isHeader ? '||' : '|';
      const cells = trimmed
        .split(separator)
        .filter((_, i, arr) => i > 0 && i < arr.length - 1); // drop first/last empty
      if (cells.length > 0) {
        // Skip separator rows like |---|---|
        if (cells.every(c => c.trim().match(/^[-:]+$/))) continue;
        if (tableRows.length === 0 && isHeader) tableHasHeader = true;
        tableRows.push(cells);
      }
      continue;
    } else {
      flushTable();
    }

    if (!trimmed) {
      flushList();
      continue;
    }

    // Headers
    const headerMatch = trimmed.match(/^h([1-6])\.\s+(.+)/);
    if (headerMatch) {
      flushList();
      const level = headerMatch[1];
      const htext = headerMatch[2];
      const className = level <= "2" ? 'text-sm font-bold text-zinc-200 mt-3 mb-1' :
                        level === "3" ? 'text-xs font-bold text-zinc-300 mt-2 mb-1' :
                        'text-xs font-semibold text-zinc-400 mt-2 mb-1';
      elements.push(
        <div key={`h-${key++}`} className={className}>
          {parseInline(htext)}
        </div>
      );
      continue;
    }

    // Bullet lists (*, **, ***)
    const bulletMatch = trimmed.match(/^(\*+)\s+(.+)/);
    if (bulletMatch) {
      listItems.push(parseInline(bulletMatch[2]));
      continue;
    }

    // Numbered lists (#, ##)
    const numMatch = trimmed.match(/^(#+)\s+(.+)/);
    if (numMatch) {
      numberedItems.push(parseInline(numMatch[2]));
      continue;
    }

    // Horizontal rule: ----
    if (trimmed.match(/^-{4,}$/)) {
      flushList();
      elements.push(<hr key={`hr-${key++}`} className="border-zinc-700 my-2" />);
      continue;
    }

    // Regular paragraph
    flushList();
    elements.push(
      <p key={`p-${key++}`} className="my-1 text-xs">
        {parseInline(trimmed)}
      </p>
    );
  }

  flushList();
  flushQuote();
  flushTable();
  flushCode();
  return elements;
}

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining) {
    // Find earliest match across all patterns
    type Match = { index: number; length: number; node: React.ReactNode };
    const candidates: Match[] = [];

    // Bold: *text*  (word-boundary aware)
    const boldMatch = remaining.match(/(?<!\w)\*([^*\n]+)\*(?!\w)/);
    if (boldMatch?.index != null) {
      candidates.push({ index: boldMatch.index, length: boldMatch[0].length,
        node: <strong key={`b-${key++}`} className="font-semibold text-zinc-200">{boldMatch[1]}</strong> });
    }

    // Italic: _text_  (word-boundary aware)
    const italicMatch = remaining.match(/(?<!\w)_([^_\n]+)_(?!\w)/);
    if (italicMatch?.index != null) {
      candidates.push({ index: italicMatch.index, length: italicMatch[0].length,
        node: <em key={`i-${key++}`} className="italic text-zinc-400">{italicMatch[1]}</em> });
    }

    // Strikethrough: -text-  (word-boundary, short text only)
    const strikeMatch = remaining.match(/(?<=\s|^)-([^\s-][^-\n]{0,40}[^\s-])-(?=[\s.,;:!?)]|$)/);
    if (strikeMatch?.index != null) {
      candidates.push({ index: strikeMatch.index, length: strikeMatch[0].length,
        node: <del key={`s-${key++}`} className="text-zinc-500">{strikeMatch[1]}</del> });
    }

    // Inline code: {{text}}
    const codeMatch = remaining.match(/\{\{([^}]+)\}\}/);
    if (codeMatch?.index != null) {
      candidates.push({ index: codeMatch.index, length: codeMatch[0].length,
        node: <code key={`c-${key++}`} className="px-1 py-0.5 bg-zinc-800 rounded text-cyan-400 font-mono text-[11px]">{codeMatch[1]}</code> });
    }

    // Link: [text|url]
    const linkMatch = remaining.match(/\[([^|\]]+)\|([^\]]+)\]/);
    if (linkMatch?.index != null) {
      candidates.push({ index: linkMatch.index, length: linkMatch[0].length,
        node: <a key={`l-${key++}`} href={linkMatch[2]} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline">{linkMatch[1]}</a> });
    }

    // Simple link: [url] (only if no pipe link matched earlier at same pos)
    if (!linkMatch) {
      const simpleLinkMatch = remaining.match(/\[([^\]|]+)\]/);
      if (simpleLinkMatch?.index != null) {
        candidates.push({ index: simpleLinkMatch.index, length: simpleLinkMatch[0].length,
          node: <a key={`sl-${key++}`} href={simpleLinkMatch[1]} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline">{simpleLinkMatch[1]}</a> });
      }
    }

    // JIRA ticket reference: COMPUTE-1234, PLTFRMOPS-567, etc.
    const ticketMatch = remaining.match(/\b([A-Z]{2,15}-\d{1,6})\b/);
    if (ticketMatch?.index != null) {
      candidates.push({ index: ticketMatch.index, length: ticketMatch[0].length,
        node: <a key={`tk-${key++}`} href={`https://hello.planet.com/jira/browse/${ticketMatch[1]}`} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 font-mono text-[11px]">{ticketMatch[1]}</a> });
    }

    // Pick earliest match
    candidates.sort((a, b) => a.index - b.index);
    const earliest = candidates[0] ?? null;

    if (earliest) {
      if (earliest.index > 0) {
        parts.push(<span key={`t-${key++}`}>{remaining.substring(0, earliest.index)}</span>);
      }
      parts.push(earliest.node);
      remaining = remaining.substring(earliest.index + earliest.length);
    } else {
      parts.push(<span key={`t-${key++}`}>{remaining}</span>);
      break;
    }
  }

  return parts;
}
