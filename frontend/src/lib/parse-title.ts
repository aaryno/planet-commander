export interface TitleParts {
  cleanTitle: string;
  hasCommander: boolean;
  commanderText: string;
  jiraKey: string | null;
  jiraText: string;
  mrNumber: string | null;
  mrRepo: string | null;
  mrUrl: string | null;
}

export function parseTitle(raw: string): TitleParts {
  let text = raw;
  let hasCommander = false;
  let commanderText = "";
  let jiraKey: string | null = null;
  let jiraText = "";
  let mrNumber: string | null = null;
  let mrRepo: string | null = null;
  let mrUrl: string | null = null;

  const cmdMatch = text.match(/\[Commander:([^\]]*)\]?/);
  if (cmdMatch) {
    hasCommander = true;
    commanderText = cmdMatch[0];
    text = text.replace(cmdMatch[0], "").trim();
  }

  const ctxMatch = text.match(/\[Context:([^\]]*)\]?/);
  if (ctxMatch) {
    const keyMatch = ctxMatch[1].match(/([A-Z]+-\d+)/);
    if (keyMatch) {
      jiraKey = keyMatch[1];
      jiraText = ctxMatch[0];
    }
    text = text.replace(ctxMatch[0], "").trim();
  }

  text = text.replace(/\[Project Context:[^\]]*\]?/g, "").trim();
  text = text.replace(/\[JIRA Ticket:[^\]]*\]?/g, (m) => {
    const km = m.match(/([A-Z]+-\d+)/);
    if (km && !jiraKey) { jiraKey = km[1]; jiraText = m; }
    return "";
  }).trim();
  text = text.replace(/\[MR Context:[^\]]*\]?/g, "").trim();
  text = text.replace(/\[Slack Context:[^\]]*\]?/g, "").trim();

  if (!jiraKey) {
    const jm = text.match(/\b([A-Z]{2,}-\d+)\b/);
    if (jm) jiraKey = jm[1];
  }

  const mrMatch = text.match(/!(\d+)/);
  if (mrMatch) mrNumber = mrMatch[1];

  const repoPatterns = [
    /review\s+([\w-]+\/[\w-]+)\s+/i,
    /in\s+([\w-]+\/[\w-]+)/i,
    /([\w-]+\/[\w-]+)\s+(?:Merge|MR|merge)/i,
  ];
  for (const pat of repoPatterns) {
    const rm = text.match(pat);
    if (rm) { mrRepo = rm[1]; break; }
  }

  if (mrRepo && mrNumber) {
    mrUrl = `https://hello.planet.com/code/${mrRepo}/-/merge_requests/${mrNumber}`;
  }

  text = text.replace(/\s+/g, " ").trim();
  if (!text) text = "(agent)";
  if (text.length > 120) text = text.slice(0, 117) + "...";

  return { cleanTitle: text, hasCommander, commanderText, jiraKey, jiraText, mrNumber, mrRepo, mrUrl };
}
