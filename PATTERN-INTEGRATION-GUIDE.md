# Pattern System Integration Guide

**Status**: Pattern extraction system complete, UI components ready for integration

**Demo Page**: http://localhost:3000/patterns-demo (when dashboard is running)

---

## Quick Start

### 1. View the Demo

```bash
cd ~/claude/dashboard
make start
# Open http://localhost:3000/patterns-demo
```

### 2. Integrate into Your Page

```typescript
import { SuggestedPatterns } from "@/components/patterns";
import type { SuggestedPattern } from "@/lib/api";

export default function MyPage() {
  // Mock data for testing (replace with real hook result)
  const patterns: SuggestedPattern[] = [
    {
      title: "Example Pattern",
      pattern_type: "investigation",
      confidence: 0.85,
      similarity_score: 0.75,
      combined_score: 0.80,
      matched_keywords: ["kubernetes", "oom"],
      relevance: "Keywords: kubernetes, oom | Type: Investigation",
      trigger: "Investigating multi-system production issue",
      approach: "1. Step one\n2. Step two\n3. Step three",
      source_artifact: "/path/to/artifact.md",
    },
  ];

  return (
    <div>
      <SuggestedPatterns patterns={patterns} />
      {/* Rest of your page */}
    </div>
  );
}
```

---

## Integration Points

### Option 1: Chat Interface (Best UX)

**Where**: Agent chat pages (`/agents/[id]/chat`)

**When**: After user sends a message

**Flow**:
```
User sends message
  ↓
Backend processes message
  ↓
ECC hook triggers (user-prompt-submit)
  ↓
Patterns matched and returned
  ↓
UI displays patterns above chat response
```

**Implementation**:
```typescript
// In ChatView component
const { data: hookResult } = useQuery(['ecc-hook', messageText], async () => {
  return await api.eccHook('user-prompt-submit', { prompt: messageText });
});

return (
  <div>
    {hookResult?.suggested_patterns && (
      <SuggestedPatterns patterns={hookResult.suggested_patterns} />
    )}
    <ChatMessage content={response} />
  </div>
);
```

### Option 2: Context Panel (Contextual)

**Where**: Work context pages (`/context/[id]`)

**When**: User opens a JIRA ticket or work context

**Flow**:
```
User opens JIRA-1234
  ↓
Backend resolves work context
  ↓
Extract JIRA summary + description as "prompt"
  ↓
Match patterns
  ↓
Display relevant investigation patterns
```

**Implementation**:
```typescript
// In ContextPanel component
const contextPrompt = `${context.jira_summary} ${context.jira_description}`;

const { data: patterns } = useQuery(['patterns', context.id], async () => {
  const result = await api.eccHook('user-prompt-submit', {
    prompt: contextPrompt
  });
  return result?.suggested_patterns || [];
});

return (
  <div>
    <ContextHeader {...context} />
    {patterns.length > 0 && <SuggestedPatterns patterns={patterns} />}
    <ContextTabs {...context} />
  </div>
);
```

### Option 3: Dedicated Patterns Page

**Where**: New route `/patterns` or `/knowledge`

**When**: User searches for patterns

**Flow**:
```
User searches "kubernetes oom"
  ↓
Match patterns against search query
  ↓
Display all matching patterns
  ↓
User can filter/sort/expand
```

**Implementation**:
```typescript
// In PatternsSearchPage
const [query, setQuery] = useState("");

const { data: patterns } = useQuery(['pattern-search', query], async () => {
  if (!query) return [];
  const result = await api.eccHook('user-prompt-submit', { prompt: query });
  return result?.suggested_patterns || [];
});

return (
  <div>
    <SearchInput value={query} onChange={setQuery} />
    <SuggestedPatterns patterns={patterns} />
  </div>
);
```

---

## Backend API (TODO)

Currently patterns are returned by the hook system. To integrate with frontend, you need an API endpoint:

### Option A: Hook Execution Endpoint

```python
# backend/app/api/ecc.py
@router.post("/ecc/hook/{hook_id}")
async def execute_hook(hook_id: str, context: dict):
    """Execute an ECC hook and return results."""
    registry = HookRegistry()
    result = await registry.execute_hooks(hook_id, context)
    return result
```

### Option B: Pattern Search Endpoint

```python
# backend/app/api/patterns.py
@router.get("/patterns/search")
async def search_patterns(q: str, limit: int = 5):
    """Search for patterns matching query."""
    from patterns.matcher import PatternMatcher

    matcher = PatternMatcher.from_library("patterns-library.json")
    matches = matcher.match(q, limit=limit, min_similarity=0.3)

    return {
        "patterns": [
            {
                "title": m.pattern["title"],
                "pattern_type": m.pattern["pattern_type"],
                "confidence": m.pattern.get("confidence", 0),
                "similarity_score": m.similarity_score,
                "combined_score": m.combined_score,
                "matched_keywords": m.matched_keywords[:5],
                "relevance": m.relevance_context,
                "trigger": m.pattern.get("trigger", ""),
                "approach": m.pattern.get("approach", "")[:300],
                "source_artifact": m.pattern.get("source_artifact", ""),
            }
            for m in matches
            if m.should_surface()
        ]
    }
```

### Option C: Context Enrichment (Automatic)

```python
# backend/app/services/context_resolver.py
async def resolve_from_jira(self, jira_key: str) -> ResolvedContext:
    # ... existing context resolution

    # Auto-add patterns based on JIRA summary
    from patterns.matcher import PatternMatcher
    matcher = PatternMatcher.from_library("patterns-library.json")

    prompt = f"{jira_issue.summary} {jira_issue.description[:200]}"
    matches = matcher.match(prompt, limit=5)

    resolved.suggested_patterns = [m for m in matches if m.should_surface()]

    return resolved
```

---

## Frontend API Client (TODO)

Add to `frontend/src/lib/api.ts`:

```typescript
export const api = {
  // ... existing methods

  // Option A: Hook execution
  eccHook: (hookId: string, context: { prompt: string }) =>
    fetchApi<{
      v2_docs: any;
      enriched_contexts: any[];
      references_detected: any[];
      suggested_patterns: SuggestedPattern[];
      errors: string[];
    }>(`/ecc/hook/${hookId}`, {
      method: "POST",
      body: JSON.stringify(context),
    }),

  // Option B: Pattern search
  patternSearch: (query: string, limit: number = 5) =>
    fetchApi<{ patterns: SuggestedPattern[] }>(
      `/patterns/search?q=${encodeURIComponent(query)}&limit=${limit}`
    ),
};
```

---

## Testing Checklist

- [ ] Build succeeds (`npm run build`)
- [ ] Demo page renders (`/patterns-demo`)
- [ ] Cards collapse/expand correctly
- [ ] Scores display with correct colors
- [ ] Pattern type badges show correct colors
- [ ] Matched keywords render as pills
- [ ] Auto-expand works for top match
- [ ] TypeScript types are correct

---

## Deployment Checklist

### Backend

- [ ] Copy pattern library to production
  ```bash
  cp ~/.claude/ecc-integration/patterns/patterns-library.json \
     ~/claude/dashboard/backend/patterns-library.json
  ```

- [ ] Install pattern matcher in backend environment
  ```bash
  cd ~/claude/dashboard/backend
  # Add patterns/ module to backend/app/
  ```

- [ ] Create API endpoint (choose Option A, B, or C above)

- [ ] Test hook execution
  ```bash
  curl -X POST http://localhost:8000/api/ecc/hook/user-prompt-submit \
    -H "Content-Type: application/json" \
    -d '{"prompt": "kubernetes pod oom killed"}'
  ```

### Frontend

- [ ] Add API client method
- [ ] Integrate component in target page(s)
- [ ] Test with real data
- [ ] Verify performance (pattern library loads quickly)
- [ ] Monitor usage and effectiveness

---

## Performance Considerations

### Pattern Library Size

- Current: 869 KB (496 patterns)
- Load time: ~50ms (local file)
- Memory: ~2-3 MB in-memory (full library)

**Optimization Options**:
1. Lazy load library (only when needed)
2. Server-side matching (don't send full library to client)
3. Compress library (gzip to ~200 KB)
4. Cache matcher instance (reuse across requests)

### Recommended: Server-Side Matching

```typescript
// Frontend (lightweight)
const patterns = await api.patternSearch(userPrompt);
// Only receives top 5 matches (~5 KB response)

// Backend (handles full library)
matcher = PatternMatcher.from_library("patterns-library.json")
matches = matcher.match(prompt, limit=5)
// Returns only matched patterns
```

---

## Future Enhancements

### Phase 1: Core Features (3-4 hours)

- [ ] VS Code integration (open artifacts)
- [ ] Copy approach button
- [ ] Feedback buttons (helpful/not)
- [ ] Pattern effectiveness tracking

### Phase 2: Advanced (5-6 hours)

- [ ] Related patterns navigation
- [ ] Pattern search/filter UI
- [ ] Pattern comparison view
- [ ] Pattern timeline/versioning

### Phase 3: Intelligence (8-10 hours)

- [ ] Semantic search with embeddings
- [ ] Pattern deduplication (22 → 3 per artifact)
- [ ] Auto-refresh from new artifacts
- [ ] Learning from user feedback

---

## Troubleshooting

### Patterns Not Showing

1. Check hook result: `console.log(hookResult?.suggested_patterns)`
2. Verify pattern library exists: `ls ~/.claude/ecc-integration/patterns/patterns-library.json`
3. Check matcher import: Pattern matcher module in Python path?
4. Review match threshold: Try lowering `min_similarity` to 0.2

### Build Errors

1. Check TypeScript types: `SuggestedPattern` interface imported?
2. Verify component exports: `export { SuggestedPatterns } from "./SuggestedPatterns"`
3. Check icon imports: `lucide-react` icons available?

### Styling Issues

1. Verify Tailwind classes: `bg-zinc-900`, `text-zinc-400`, etc.
2. Check ScrollableCard: Component imported correctly?
3. Review color utilities: Pattern type colors defined?

---

## Contact & Support

- **Pattern System**: `~/.claude/ecc-integration/patterns/`
- **UI Components**: `~/claude/dashboard/frontend/src/components/patterns/`
- **Documentation**: This file + completion artifacts

**Completion Artifacts**:
- [Pattern Extraction](../artifacts/20260321-0100-ecc-week4-5-pattern-extraction-complete.md)
- [Final Complete with UI](../artifacts/20260321-0130-ecc-week4-5-FINAL-complete.md)

---

**Last Updated**: 2026-03-21
**Status**: Ready for integration
**Demo**: http://localhost:3000/patterns-demo
