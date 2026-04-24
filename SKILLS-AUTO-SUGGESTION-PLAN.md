# Skills Auto-Suggestion Implementation Plan

**Created**: 2026-03-20
**Integration**: Skills Auto-Suggestion (Phase 3)
**Priority**: MEDIUM (completes Phase 3)
**Complexity**: Low-Medium
**Impact**: Medium — improves discoverability and workflow efficiency

---

## Overview

Auto-suggest relevant skills based on work context (JIRA ticket, Slack thread, agent chat, etc.).

**Key Advantages**:
- Improves skill discoverability (users don't need to remember all skill names)
- Context-aware recommendations (ticket labels → relevant skills)
- Reduces time-to-action (skill suggested when most relevant)
- Foundation for workflow automation (auto-invoke skills)

---

## Architecture

### Data Flow

```
Work Context (JIRA/Slack/Chat/etc.)
    ↓
SkillSuggestionService.analyze_context()
    ↓
Extract signals (labels, keywords, entity types)
    ↓
Match against skill registry (keywords, patterns, conditions)
    ↓
Score and rank skills (confidence 0.0-1.0)
    ↓
Database (suggested_skills table)
    ↓
API Endpoint (/api/contexts/{id}/suggested-skills)
    ↓
React Component (SkillSuggestions in context panel)
```

### Skill Registry Structure

Skills are already defined in `~/.claude/skills/` with SKILL.md files. We need to:
1. **Parse existing skills** for trigger conditions
2. **Build registry** with keywords/patterns
3. **Store in database** for fast matching

**Example Skill File** (`~/.claude/skills/wx-task-debug/SKILL.md`):
```markdown
# wx-task-debug

**Trigger Conditions**:
- JIRA labels: `wx`, `workexchange`
- Keywords: `task failure`, `lease expiration`, `OOM`, `crashloop`
- Systems: `wxctl`, `kubectl`, `Grafana`

**Use Cases**:
- WX task stuck or failed
- Task lease expired
- OOM kills detected
```

---

## Database Schema

### Table: skill_registry

```sql
CREATE TABLE skill_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Skill metadata
    skill_name VARCHAR(200) UNIQUE NOT NULL,
    skill_path TEXT NOT NULL,  -- ~/.claude/skills/{skill_name}/
    title TEXT,
    description TEXT,

    -- Trigger conditions (from SKILL.md)
    trigger_keywords JSONB,  -- ["task failure", "lease expiration"]
    trigger_labels JSONB,     -- ["wx", "workexchange"]
    trigger_systems JSONB,    -- ["wxctl", "kubectl", "Grafana"]
    trigger_patterns JSONB,   -- [{"type": "regex", "pattern": "..."}]

    -- Metadata
    category VARCHAR(100),    -- investigation, onboarding, analysis, etc.
    complexity VARCHAR(50),   -- low, medium, high
    estimated_duration VARCHAR(100),  -- "5-10 minutes", "30-60 minutes"

    -- Usage stats
    invocation_count INTEGER DEFAULT 0,
    last_invoked_at TIMESTAMPTZ,

    -- Tracking
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_skill_registry_name ON skill_registry(skill_name);
CREATE INDEX idx_skill_registry_category ON skill_registry(category);
CREATE INDEX idx_skill_registry_keywords ON skill_registry USING GIN(trigger_keywords);
CREATE INDEX idx_skill_registry_labels ON skill_registry USING GIN(trigger_labels);
```

### Table: suggested_skills

```sql
CREATE TABLE suggested_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to work context
    work_context_id UUID REFERENCES work_contexts(id) ON DELETE CASCADE,

    -- Suggested skill
    skill_id UUID REFERENCES skill_registry(id) ON DELETE CASCADE,
    skill_name VARCHAR(200) NOT NULL,

    -- Confidence and reasoning
    confidence_score FLOAT NOT NULL,  -- 0.0 - 1.0
    match_reasons JSONB,  -- [{"type": "keyword", "value": "task failure", "weight": 0.3}]

    -- User interaction
    user_action VARCHAR(50),  -- null, "accepted", "dismissed", "deferred"
    user_feedback TEXT,
    actioned_at TIMESTAMPTZ,

    -- Tracking
    suggested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(work_context_id, skill_id)
);

-- Indexes
CREATE INDEX idx_suggested_skills_context ON suggested_skills(work_context_id);
CREATE INDEX idx_suggested_skills_skill ON suggested_skills(skill_id);
CREATE INDEX idx_suggested_skills_confidence ON suggested_skills(confidence_score DESC);
CREATE INDEX idx_suggested_skills_action ON suggested_skills(user_action);
```

---

## Implementation Plan (3 Days)

### Day 1: Database Schema and Skill Indexing

**Goal**: Create tables, parse existing skills, build registry

**Files**:
- `backend/alembic/versions/20260320_1400_create_skill_registry.py`
- `backend/alembic/versions/20260320_1405_create_suggested_skills.py`
- `backend/app/models/skill_registry.py`
- `backend/app/models/suggested_skill.py`
- `backend/app/services/skill_indexing.py`

**Skill Parsing Logic**:
```python
class SkillIndexingService:
    """Parse and index skills from ~/.claude/skills/"""

    SKILL_DIR = Path.home() / ".claude" / "skills"

    async def index_all_skills(self) -> Dict:
        """Scan and index all skills."""
        skills = []
        for skill_dir in self.SKILL_DIR.iterdir():
            if skill_dir.is_dir():
                skill_data = self.parse_skill(skill_dir)
                if skill_data:
                    skills.append(skill_data)

        # Bulk insert to database
        await self.bulk_insert_skills(skills)

    def parse_skill(self, skill_dir: Path) -> Optional[Dict]:
        """Parse SKILL.md to extract trigger conditions."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None

        content = skill_md.read_text()

        # Extract trigger conditions section
        triggers = self.extract_triggers(content)

        return {
            "skill_name": skill_dir.name,
            "skill_path": str(skill_dir),
            "title": self.extract_title(content),
            "description": self.extract_description(content),
            "trigger_keywords": triggers.get("keywords", []),
            "trigger_labels": triggers.get("labels", []),
            "trigger_systems": triggers.get("systems", []),
            "trigger_patterns": triggers.get("patterns", []),
            "category": self.infer_category(skill_dir.name),
        }

    def extract_triggers(self, content: str) -> Dict:
        """Extract trigger conditions from SKILL.md."""
        # Parse markdown sections for:
        # - "Trigger Conditions:"
        # - "Keywords:"
        # - "Labels:"
        # - "Systems:"
        # - "Use Cases:" (extract keywords)
        pass
```

**Acceptance**: Skill registry populated, all skills indexed

---

### Day 2: Suggestion Service and API

**Goal**: Implement context analysis and skill matching logic

**Files**:
- `backend/app/services/skill_suggestion.py`
- `backend/app/api/skills.py`

**Service Methods**:

```python
class SkillSuggestionService:
    """Analyze work contexts and suggest relevant skills."""

    async def suggest_skills_for_context(
        self,
        context_id: UUID,
        min_confidence: float = 0.3
    ) -> List[Dict]:
        """Analyze context and suggest skills.

        Returns list of:
        {
            "skill": SkillRegistry object,
            "confidence": 0.85,
            "match_reasons": [
                {"type": "label_match", "value": "wx", "weight": 0.4},
                {"type": "keyword_match", "value": "task failure", "weight": 0.3},
                {"type": "system_match", "value": "kubectl", "weight": 0.15}
            ]
        }
        """
        # Get work context
        context = await self.get_work_context(context_id)

        # Extract signals from context
        signals = await self.extract_context_signals(context)

        # Match against skill registry
        matches = await self.match_skills(signals)

        # Score and rank
        ranked = self.rank_skills(matches, min_confidence)

        # Store suggestions
        await self.store_suggestions(context_id, ranked)

        return ranked

    async def extract_context_signals(self, context: WorkContext) -> Dict:
        """Extract matching signals from context.

        Returns:
        {
            "labels": ["wx", "incident"],
            "keywords": ["task failure", "lease expiration"],
            "systems": ["kubectl", "Grafana"],
            "entity_types": ["jira_issue", "slack_thread"],
            "severity": "SEV2",
            "is_incident": True
        }
        """
        signals = {
            "labels": [],
            "keywords": [],
            "systems": [],
            "entity_types": [],
            "severity": None,
            "is_incident": False
        }

        # From JIRA issue
        if context.jira_issue:
            signals["labels"].extend(context.jira_issue.labels or [])
            signals["keywords"].extend(
                self.extract_keywords(context.jira_issue.description)
            )
            if "incident" in (context.jira_issue.labels or []):
                signals["is_incident"] = True

        # From linked entities
        for link in context.entity_links:
            signals["entity_types"].append(link.to_type)

            if link.to_type == "slack_thread":
                thread = link.to_entity
                if thread.is_incident:
                    signals["is_incident"] = True
                    signals["severity"] = thread.severity

        # From agent chat
        if context.agent:
            signals["keywords"].extend(
                self.extract_keywords_from_messages(context.agent.messages)
            )

        return signals

    async def match_skills(self, signals: Dict) -> List[Dict]:
        """Match signals against skill registry."""
        # Query all skills
        skills = await self.get_all_skills()

        matches = []
        for skill in skills:
            score, reasons = self.calculate_match_score(skill, signals)
            if score > 0:
                matches.append({
                    "skill": skill,
                    "score": score,
                    "reasons": reasons
                })

        return matches

    def calculate_match_score(
        self,
        skill: SkillRegistry,
        signals: Dict
    ) -> Tuple[float, List[Dict]]:
        """Calculate match score and reasons."""
        score = 0.0
        reasons = []

        # Label matching (weight: 0.4)
        label_matches = set(signals["labels"]) & set(skill.trigger_labels or [])
        if label_matches:
            label_score = len(label_matches) * 0.2  # 0.2 per label match
            score += min(label_score, 0.4)
            reasons.append({
                "type": "label_match",
                "values": list(label_matches),
                "weight": min(label_score, 0.4)
            })

        # Keyword matching (weight: 0.4)
        keyword_matches = []
        for keyword in skill.trigger_keywords or []:
            if any(keyword.lower() in kw.lower() for kw in signals["keywords"]):
                keyword_matches.append(keyword)
        if keyword_matches:
            keyword_score = len(keyword_matches) * 0.15
            score += min(keyword_score, 0.4)
            reasons.append({
                "type": "keyword_match",
                "values": keyword_matches,
                "weight": min(keyword_score, 0.4)
            })

        # System matching (weight: 0.2)
        system_matches = set(signals["systems"]) & set(skill.trigger_systems or [])
        if system_matches:
            system_score = len(system_matches) * 0.1
            score += min(system_score, 0.2)
            reasons.append({
                "type": "system_match",
                "values": list(system_matches),
                "weight": min(system_score, 0.2)
            })

        # Incident boost (if skill is incident-related)
        if signals["is_incident"] and "incident" in skill.skill_name:
            score += 0.2
            reasons.append({
                "type": "incident_boost",
                "weight": 0.2
            })

        return score, reasons

    def rank_skills(self, matches: List[Dict], min_confidence: float) -> List[Dict]:
        """Rank and filter by confidence threshold."""
        # Filter by min confidence
        filtered = [m for m in matches if m["score"] >= min_confidence]

        # Sort by score descending
        ranked = sorted(filtered, key=lambda m: m["score"], reverse=True)

        # Limit to top 5
        return ranked[:5]
```

**API Endpoints**:

```python
@router.get("/contexts/{context_id}/suggested-skills")
async def get_suggested_skills(
    context_id: UUID,
    min_confidence: float = Query(0.3),
    db: AsyncSession = Depends(get_db)
):
    """Get skill suggestions for a work context."""
    suggestion_service = SkillSuggestionService(db)
    suggestions = await suggestion_service.suggest_skills_for_context(
        context_id,
        min_confidence
    )
    return {
        "context_id": context_id,
        "suggestions": suggestions,
        "count": len(suggestions)
    }

@router.post("/contexts/{context_id}/suggested-skills/{skill_id}/action")
async def record_skill_action(
    context_id: UUID,
    skill_id: UUID,
    action: str = Body(...),  # "accepted", "dismissed", "deferred"
    feedback: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Record user action on suggested skill."""
    suggestion_service = SkillSuggestionService(db)
    await suggestion_service.record_user_action(
        context_id,
        skill_id,
        action,
        feedback
    )
    return {"status": "recorded"}

@router.get("/skills/registry")
async def list_skills(
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List all registered skills."""
    skill_service = SkillIndexingService(db)
    skills = await skill_service.get_all_skills(category)
    return {
        "skills": skills,
        "count": len(skills)
    }

@router.post("/skills/reindex")
async def reindex_skills(db: AsyncSession = Depends(get_db)):
    """Re-scan and index all skills."""
    skill_service = SkillIndexingService(db)
    stats = await skill_service.index_all_skills()
    return {
        "skills_indexed": stats["indexed"],
        "skills_updated": stats["updated"],
        "skills_removed": stats["removed"]
    }
```

**Acceptance**: API returns skill suggestions, scoring works correctly

---

### Day 3: Frontend Components and Background Jobs

**Goal**: Display skill suggestions in UI, auto-refresh

**Files**:
- `frontend/src/lib/api.ts` (add types and methods)
- `frontend/src/components/skills/SkillSuggestionCard.tsx`
- `frontend/src/components/skills/SkillBadge.tsx`
- `backend/app/jobs/skill_suggestion_refresh.py`

**TypeScript Types**:

```typescript
// frontend/src/lib/api.ts

export interface SkillRegistry {
  id: string;
  skill_name: string;
  title: string;
  description: string;
  category: string;
  complexity: string;
  estimated_duration: string;
  invocation_count: number;
}

export interface MatchReason {
  type: string;  // "label_match", "keyword_match", etc.
  values?: string[];
  weight: number;
}

export interface SuggestedSkill {
  skill: SkillRegistry;
  confidence: number;
  match_reasons: MatchReason[];
}

export interface SkillSuggestionsResponse {
  context_id: string;
  suggestions: SuggestedSkill[];
  count: number;
}

// API methods
export const api = {
  // ... existing methods ...

  skills: {
    getSuggestions: (contextId: string, minConfidence = 0.3) =>
      fetchApi<SkillSuggestionsResponse>(`/contexts/${contextId}/suggested-skills?min_confidence=${minConfidence}`),

    recordAction: (contextId: string, skillId: string, action: string, feedback?: string) =>
      fetchApi(`/contexts/${contextId}/suggested-skills/${skillId}/action`, {
        method: "POST",
        body: { action, feedback }
      }),

    listRegistry: (category?: string) =>
      fetchApi<{ skills: SkillRegistry[]; count: number }>(`/skills/registry${category ? `?category=${category}` : ""}`),

    reindex: () =>
      fetchApi(`/skills/reindex`, { method: "POST" })
  }
};
```

**React Components**:

```tsx
// frontend/src/components/skills/SkillSuggestionCard.tsx

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Lightbulb, CheckCircle, XCircle, Clock } from "lucide-react";
import { useState } from "react";
import { api, SuggestedSkill } from "@/lib/api";

interface SkillSuggestionCardProps {
  contextId: string;
  suggestion: SuggestedSkill;
  onAction?: (action: string) => void;
}

export function SkillSuggestionCard({
  contextId,
  suggestion,
  onAction
}: SkillSuggestionCardProps) {
  const [actioned, setActioned] = useState(false);

  const handleAction = async (action: string) => {
    await api.skills.recordAction(contextId, suggestion.skill.id, action);
    setActioned(true);
    onAction?.(action);
  };

  const confidenceColor =
    suggestion.confidence >= 0.7 ? "text-emerald-400" :
    suggestion.confidence >= 0.5 ? "text-blue-400" :
    "text-amber-400";

  return (
    <Card className="border-zinc-800 bg-zinc-900/50">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <Lightbulb className={`h-4 w-4 ${confidenceColor}`} />
            <span className="text-sm font-medium text-zinc-200">
              {suggestion.skill.title || suggestion.skill.skill_name}
            </span>
          </div>
          <Badge variant="outline" className="text-xs">
            {Math.round(suggestion.confidence * 100)}% match
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Description */}
        <p className="text-xs text-zinc-400">
          {suggestion.skill.description}
        </p>

        {/* Match reasons */}
        <div className="flex flex-wrap gap-1">
          {suggestion.match_reasons.map((reason, idx) => (
            <Badge key={idx} variant="secondary" className="text-xs">
              {reason.type === "label_match" && `Labels: ${reason.values?.join(", ")}`}
              {reason.type === "keyword_match" && `Keywords: ${reason.values?.join(", ")}`}
              {reason.type === "system_match" && `Systems: ${reason.values?.join(", ")}`}
              {reason.type === "incident_boost" && "Incident"}
            </Badge>
          ))}
        </div>

        {/* Metadata */}
        <div className="flex gap-3 text-xs text-zinc-500">
          <span>{suggestion.skill.category}</span>
          <span>•</span>
          <span>{suggestion.skill.estimated_duration}</span>
        </div>

        {/* Actions */}
        {!actioned && (
          <div className="flex gap-2 pt-2">
            <Button
              size="sm"
              variant="default"
              onClick={() => handleAction("accepted")}
              className="flex-1"
            >
              <CheckCircle className="h-3 w-3 mr-1" />
              Use Skill
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleAction("dismissed")}
            >
              <XCircle className="h-3 w-3" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => handleAction("deferred")}
            >
              <Clock className="h-3 w-3" />
            </Button>
          </div>
        )}

        {actioned && (
          <p className="text-xs text-zinc-500 italic">Action recorded</p>
        )}
      </CardContent>
    </Card>
  );
}
```

**Background Job** (`backend/app/jobs/skill_suggestion_refresh.py`): Refreshes suggestions for active contexts every 2 hours.

**Acceptance**: UI displays skill suggestions, users can accept/dismiss

---

## Success Criteria

- [ ] Skill registry table populated with all skills from `~/.claude/skills/`
- [ ] Trigger conditions extracted from SKILL.md files
- [ ] Context analysis extracts labels, keywords, systems correctly
- [ ] Skill matching algorithm returns relevant skills (>70% accuracy)
- [ ] Confidence scoring works (high-confidence skills ranked first)
- [ ] API endpoints return suggestions with reasons
- [ ] Frontend displays suggestions in context panel
- [ ] User can accept/dismiss suggestions
- [ ] Background job refreshes suggestions every 2 hours
- [ ] Feedback recorded for learning (future: improve scoring)

---

## Timeline

- **Day 1** (4 hours): Database schema, models, skill indexing
- **Day 2** (5 hours): Suggestion service, API endpoints
- **Day 3** (4 hours): Frontend components, background job

**Total**: ~13 hours (~2 days)

---

## Integration with Work Contexts

### Where to Display Suggestions

1. **Context Panel** (when viewing JIRA ticket, Slack thread, etc.)
   - Section: "Suggested Skills"
   - Show top 3-5 skills
   - Allow accept/dismiss actions

2. **Agent Chat View** (when working with agent)
   - Floating skill suggestion badge
   - Click to expand full list
   - "Use this skill" button → invoke skill

3. **Dashboard** (global view)
   - "Skill Usage Analytics" card
   - Show most-used skills
   - Show suggested-but-not-used (missed opportunities)

### User Workflow

```
1. User opens JIRA ticket COMPUTE-1234 (labels: wx, incident)
   ↓
2. Commander analyzes context:
   - Labels: wx, incident
   - Keywords: "task failure", "lease expiration"
   - Systems: kubectl, Grafana
   ↓
3. Skill matching:
   - wx-task-debug (confidence: 0.85)
   - incident-response (confidence: 0.75)
   - customer-impact-assessment (confidence: 0.65)
   ↓
4. Display suggestions in context panel
   ↓
5. User clicks "Use Skill" on wx-task-debug
   ↓
6. Skill invoked, feedback recorded
```

---

## Future Enhancements

### Phase 1: Basic Suggestions (This Plan)
- Parse skill files
- Build registry
- Match based on keywords/labels
- Display suggestions

### Phase 2: Learning & Improvement
- Track acceptance/dismissal rates
- Adjust scoring based on feedback
- A/B test different matching algorithms
- Personalized suggestions (per-user preferences)

### Phase 3: Proactive Automation
- Auto-invoke high-confidence skills (with user approval)
- Skill chaining (one skill triggers another)
- Context-aware skill parameters (pre-fill JIRA key, etc.)

---

## References

- **Auto-Context Enrichment Spec**: [AUTO-CONTEXT-ENRICHMENT-SPEC.md](./AUTO-CONTEXT-ENRICHMENT-SPEC.md) (lines 685-717)
- **Skills Directory**: `~/.claude/skills/`
- **Existing Skills**: incident-response, wx-task-debug, jobs-alert-triage, etc.
- **Work Context Model**: `backend/app/models/work_context.py`
