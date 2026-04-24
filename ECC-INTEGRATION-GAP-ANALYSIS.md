# ECC Integration Gap Analysis — Selective Adoption Plan

**Created**: 2026-03-20
**Purpose**: Identify and prioritize ECC patterns to integrate with Planet Commander
**Status**: Planning → Implementation
**Reference**: [Claude Setup Evaluation](../artifacts/20260320-1445-claude-setup-evaluation-REVISED.md)

---

## Executive Summary

**Verdict**: Selectively adopt ECC automation patterns while keeping Commander's advanced infrastructure.

**What to adopt from ECC**:
1. ✅ Lifecycle hooks (integrate with Commander enrichment)
2. ✅ Language-specific agents (Go, Python, TypeScript reviewers)
3. ✅ Continuous learning patterns (auto-extract from artifacts)
4. ✅ Verification loops (add to multi-step skills)

**What NOT to replace**:
- ❌ Work context management (Commander's EntityLink architecture is superior)
- ❌ Proactive incident response (ECC has nothing like this)
- ❌ Cross-system enrichment (Commander's background jobs are domain-optimized)
- ❌ Artifact repository (250+ real artifacts > synthetic patterns)

**Implementation timeline**: 4-6 weeks
**Effort**: ~80-120 hours total

---

## Gap 1: Lifecycle Hooks

### What ECC Has

**Hook system** with pre-defined lifecycle triggers:
- `user-prompt-submit-hook`: Runs on every user prompt
- `tool-call-pre-hook`: Before tool execution
- `tool-call-post-hook`: After tool execution
- `session-start-hook`: On session initialization
- `session-end-hook`: On session completion

**Hook profiles**:
- `minimal`: Essential hooks only
- `standard`: Balanced automation
- `strict`: Maximum automation

**Runtime controls**:
- `ECC_HOOK_PROFILE`: Set hook level
- `ECC_DISABLED_HOOKS`: Disable specific hooks (comma-separated IDs)

### What Commander Has

**Background jobs** (scheduled):
- `pagerduty_enrichment.py`: Every 30 min, scan JIRA for PD references
- `grafana_sync.py`: Every 30 min, sync alert definitions
- `jira_sync.py`: Every 30 min, sync JIRA issues
- `artifact_indexing.py`: Continuous artifact scanning
- `git_scanner.py`: Track branches/worktrees

**Real-time monitoring**:
- SSE for WX deployments (active)
- Planned: Slack warning channel monitoring

### The Gap

**Commander lacks**:
- Hooks triggered by user actions (prompt submit, tool call)
- Session-level automation (start/end hooks)
- User-configurable automation levels
- Generic automation framework (everything is domain-specific)

**Impact**: Commander requires background jobs for all automation (not user-triggered)

### Integration Strategy

**Adopt ECC's hook framework, trigger Commander enrichment**:

```python
# ~/.claude/hooks/user-prompt-submit.py (ECC pattern)

from commander_client import CommanderAPI

commander = CommanderAPI(base_url="http://localhost:9000")

def on_user_prompt_submit(prompt: str, context: dict):
    """
    Triggered on every user prompt.
    Auto-loads v2 context + triggers Commander enrichment.
    """
    # Layer 0: Auto-load universal index (v2 pattern)
    if should_load_layer0(prompt, context):
        load_index_md()

    # Layer 1: Detect project, load project context (v2 pattern)
    project = detect_project(prompt, context)
    if project:
        load_project_index(project)

    # Commander: Detect references, trigger enrichment
    detected_refs = detect_all_references(prompt)

    for ref in detected_refs:
        if ref.type == "jira":
            # Trigger Commander enrichment job
            commander.enrich_from_jira(ref.value)

        elif ref.type == "pagerduty":
            # Fetch PD incident, create context
            commander.enrich_from_pagerduty(ref.value)

        elif ref.type == "slack":
            # Parse Slack thread, create links
            commander.enrich_from_slack_thread(ref.value)

        elif ref.type == "artifact":
            # Load artifact, show related
            commander.enrich_from_artifact(ref.value)

    # Layer 2: Detect tool mentions, load tool docs (v2 pattern)
    tools = detect_tool_mentions(prompt)
    for tool in tools:
        load_tool_quick_ref(tool)

def detect_all_references(prompt: str) -> list[Reference]:
    """Extract all detectable references from prompt."""
    import re

    refs = []

    # JIRA tickets
    for match in re.finditer(r'\b(COMPUTE-\d+)\b', prompt):
        refs.append(Reference(type="jira", value=match.group(1)))

    # PagerDuty incidents
    for match in re.finditer(r'\b(PD-[A-Z0-9]+)\b', prompt):
        refs.append(Reference(type="pagerduty", value=match.group(1)))

    # Slack URLs
    for match in re.finditer(r'https://planetlabs\.slack\.com/archives/([A-Z0-9]+)/p(\d+)', prompt):
        refs.append(Reference(
            type="slack",
            value=f"{match.group(1)}/{match.group(2)}"
        ))

    # Artifact filenames
    for match in re.finditer(r'(\d{8}-\d{4}-[\w-]+\.md)', prompt):
        refs.append(Reference(type="artifact", value=match.group(1)))

    return refs
```

**Tool call post-hook** (auto-create artifacts):

```python
# ~/.claude/hooks/tool-call-post.py (ECC pattern)

def on_tool_call_post(tool_name: str, result: dict, context: dict):
    """
    Triggered after tool execution.
    Auto-creates artifacts, extracts patterns, indexes.
    """
    # After investigation skill completes
    if tool_name == "investigation-complete":
        # Extract patterns (ECC pattern)
        patterns = extract_patterns(result)
        store_instincts(patterns)

        # Create artifact (Commander pattern)
        artifact = create_artifact(
            title=f"{date}-{result['jira_key']}-{result['description']}.md",
            content=result['summary'],
            metadata={
                "project": result['project'],
                "jira_keys": [result['jira_key']],
                "keywords": extract_keywords(result['content'])
            }
        )

        # Index with embedding (Commander pattern)
        artifact.embedding = embed(artifact.content)
        commander.index_artifact(artifact)

        # Auto-link to JIRA (Commander pattern)
        commander.create_entity_link(
            from_type="jira_issue",
            from_id=result["jira_issue_id"],
            to_type="artifact",
            to_id=artifact.id,
            link_type="documented_in"
        )

    # After skill execution
    if tool_name == "Skill" and result.get("skill_name"):
        # Track skill usage for auto-suggestion
        commander.track_skill_usage(
            skill_name=result["skill_name"],
            context=context,
            outcome=result.get("outcome")
        )
```

### Implementation Plan

**Week 1: Hook Framework Setup**
- [ ] Day 1: Install ECC hooks infrastructure
  - [ ] Create `~/.claude/hooks/` directory structure
  - [ ] Install hook registry and runner
  - [ ] Configure hook profiles (minimal/standard/strict)
- [ ] Day 2: Implement `user-prompt-submit` hook
  - [ ] Add v2 Layer 0/1/2 auto-loading
  - [ ] Add Commander reference detection
  - [ ] Add Commander enrichment triggers
- [ ] Day 3: Implement `tool-call-post` hook
  - [ ] Add artifact auto-creation
  - [ ] Add pattern extraction
  - [ ] Add skill usage tracking
- [ ] Day 4: Testing & Validation
  - [ ] Test hook execution on prompts
  - [ ] Verify Commander enrichment triggers
  - [ ] Test artifact auto-creation

**Week 2: Integration & Polish**
- [ ] Day 5: Commander API client
  - [ ] Create `commander_client.py` for hook integration
  - [ ] Async API calls to Commander backend
  - [ ] Error handling and retries
- [ ] Day 6: Session hooks
  - [ ] `session-start-hook`: Load Commander contexts
  - [ ] `session-end-hook`: Save session summary
- [ ] Day 7: Documentation
  - [ ] Create HOOKS-INTEGRATION-COMPLETE.md
  - [ ] Update CLAUDE.md with hook usage
  - [ ] Update PROGRESS.md

**Effort**: ~40 hours (1 week full-time, 2 weeks part-time)

**Success Criteria**:
- ✅ Hooks execute on user prompts and tool calls
- ✅ Commander enrichment triggered automatically
- ✅ Artifacts auto-created after investigations
- ✅ v2 context auto-loaded based on mentions

---

## Gap 2: Language-Specific Agents

### What ECC Has

**28 specialized agents** including:
- **Language reviewers** (10+):
  - Go, Python, TypeScript, Java, Kotlin, Rust, C++, PHP, Perl, Swift
- **Generic agents**:
  - Planning, architecture, TDD guidance
  - Build error resolution
  - Security review
  - Database review

**Agent capabilities**:
- Code review (style, bugs, performance)
- Test generation (unit, integration)
- Refactoring suggestions
- Security vulnerability detection
- Performance optimization

### What Commander Has

**6 domain agents** (in `~/tools/agents/`):
- `jira-code-linker`: Link code to JIRA tickets
- `slack-synthesizer`: Slack message summarization
- `wx-debugger`: WX-specific debugging
- `investigation-resumption`: Resume interrupted investigations
- `incident-responder`: Incident workflow orchestration
- `artifact-auditor`: Audit artifact quality

**Domain agents are excellent**, but lack:
- Language-specific code review
- Generic development patterns
- Test generation capabilities

### The Gap

**Commander lacks**:
- Code review agents for Go, Python, TypeScript
- Security review agents
- Test generation capabilities
- Generic development workflow agents

**Impact**: MR reviews require manual code review (no automated feedback on style, bugs, security)

### Integration Strategy

**Adopt ECC's language agents, integrate into Commander MR review workflow**:

```python
# backend/app/services/mr_review_service.py

from ecc_agents import GoReviewer, PythonReviewer, TypeScriptReviewer, SecurityReviewer

class MRReviewService:
    """Enhanced MR review with ECC language agents."""

    def __init__(self):
        self.domain_agents = {
            "wx": WXDebugger(),
            "g4": G4Debugger(),
            "jobs": JobsDebugger(),
        }
        self.language_agents = {
            "go": GoReviewer(),
            "python": PythonReviewer(),
            "typescript": TypeScriptReviewer(),
        }
        self.security_agent = SecurityReviewer()

    async def review_mr(self, mr_id: str, repo: str) -> MRReview:
        """
        Complete MR review using domain + language agents.
        """
        # Fetch MR details
        mr = await self.fetch_mr(mr_id, repo)

        # Detect languages in MR
        languages = self.detect_languages(mr.changed_files)

        # Run language-specific reviews
        code_reviews = []
        for lang in languages:
            if agent := self.language_agents.get(lang):
                review = await agent.review_code(
                    files=mr.changed_files,
                    context=mr.description
                )
                code_reviews.append(review)

        # Run security review
        security_review = await self.security_agent.review_code(
            files=mr.changed_files
        )

        # Run domain-specific review (if applicable)
        domain_review = None
        project = self.detect_project(repo)
        if project and (agent := self.domain_agents.get(project)):
            domain_review = await agent.review_mr(mr)

        # Synthesize final review
        return self.synthesize_review(
            mr=mr,
            code_reviews=code_reviews,
            security_review=security_review,
            domain_review=domain_review
        )

    def detect_languages(self, files: list[ChangedFile]) -> set[str]:
        """Detect languages from file extensions."""
        lang_map = {
            ".go": "go",
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
        }

        languages = set()
        for file in files:
            ext = os.path.splitext(file.path)[1]
            if lang := lang_map.get(ext):
                languages.add(lang)

        return languages
```

**Commander Overview Agent** (integrates ECC agents):

```python
# backend/app/services/overview_agent.py

class OverviewAgent:
    """
    Commander overview agent orchestrates domain + ECC agents.
    """

    def __init__(self):
        # Commander domain agents
        self.domain_agents = {
            "wx": WXDebugger(),
            "g4": G4Debugger(),
            "jobs": JobsDebugger(),
        }

        # ECC language agents
        self.code_reviewers = {
            "go": GoReviewer(),
            "python": PythonReviewer(),
            "typescript": TypeScriptReviewer(),
        }

        # ECC generic agents
        self.security_agent = SecurityReviewer()
        self.architecture_agent = ArchitectureReviewer()

    async def run_overview(self, context: WorkContext) -> OverviewResult:
        """
        Comprehensive overview using all available agents.
        """
        results = []

        # Domain-specific audits (Commander)
        if context.project:
            agent = self.domain_agents.get(context.project)
            if agent:
                domain_audit = await agent.audit_context(context)
                results.append(domain_audit)

        # Code review (ECC) if MRs present
        if context.merge_requests:
            for mr in context.merge_requests:
                languages = self.detect_languages(mr)
                for lang in languages:
                    reviewer = self.code_reviewers.get(lang)
                    if reviewer:
                        code_review = await reviewer.review_mr(mr)
                        results.append(code_review)

        # Security review (ECC) if code changes
        if context.has_code_changes:
            security_audit = await self.security_agent.audit_context(context)
            results.append(security_audit)

        # Architecture review (ECC) if new features
        if context.is_new_feature:
            arch_review = await self.architecture_agent.review_design(context)
            results.append(arch_review)

        # Synthesize results
        return self.synthesize_overview(results)
```

### Implementation Plan

**Week 3: Agent Integration Setup**
- [ ] Day 1: Install ECC agents
  - [ ] Install ECC agent framework
  - [ ] Configure Go, Python, TypeScript reviewers
  - [ ] Test agents on sample code
- [ ] Day 2: MR Review Integration
  - [ ] Update `mr_review_service.py` with language detection
  - [ ] Integrate language agents into review flow
  - [ ] Add security review step
- [ ] Day 3: Overview Agent Extension
  - [ ] Update `overview_agent.py` with ECC agents
  - [ ] Add code review dispatch logic
  - [ ] Add architecture review for new features

**Week 4: Testing & Polish**
- [ ] Day 4: Testing
  - [ ] Test MR review with Go code (WX project)
  - [ ] Test MR review with Python code (backend)
  - [ ] Test security review
- [ ] Day 5: UI Integration
  - [ ] Update MR review UI to show agent results
  - [ ] Add code review section to ContextPanel
  - [ ] Add security findings display
- [ ] Day 6: Documentation
  - [ ] Create LANGUAGE-AGENTS-INTEGRATION-COMPLETE.md
  - [ ] Update mr-review skill docs
  - [ ] Update PROGRESS.md

**Effort**: ~30 hours (1.5 weeks part-time)

**Success Criteria**:
- ✅ Language agents review MRs automatically
- ✅ Security review detects vulnerabilities
- ✅ Overview agent orchestrates domain + ECC agents
- ✅ UI displays agent results

---

## Gap 3: Continuous Learning Patterns

### What ECC Has

**Pattern extraction**:
- Auto-extract patterns from sessions
- Confidence scoring for patterns
- Pattern library (instincts)
- Pattern evolution over time

**Learning workflow**:
1. Session completes
2. Extract patterns from interactions
3. Score pattern confidence (0.0-1.0)
4. Store in instinct library
5. Surface patterns in future sessions

**Example patterns**:
- "When X error occurs, check Y first"
- "For Z issue, run these 3 commands"
- "Alert A usually escalates if B condition"

### What Commander Has

**Manual artifact creation**:
- Investigations documented in markdown
- Artifacts stored in `~/claude/projects/*/artifacts/`
- Metadata extraction (JIRA keys, keywords, date)
- Semantic search (embeddings, cosine similarity)

**Artifacts are excellent**, but lack:
- Automatic pattern extraction
- Confidence scoring
- Pattern surfacing in future sessions

### The Gap

**Commander lacks**:
- Automatic pattern extraction from artifacts
- Confidence scoring for mitigation plans
- Pattern library (structured instincts)
- Auto-surfacing of patterns in new investigations

**Impact**: Patterns exist in artifacts but require manual search (not auto-suggested)

### Integration Strategy

**Extract patterns from artifacts, store as instincts**:

```python
# backend/app/services/pattern_extraction.py

from ecc_learning import PatternExtractor, InstinctLibrary

class ArtifactPatternExtractor:
    """
    Extract patterns from Commander artifacts,
    store in ECC instinct library.
    """

    def __init__(self):
        self.extractor = PatternExtractor()
        self.instincts = InstinctLibrary()

    async def extract_from_artifact(self, artifact: Artifact) -> list[Pattern]:
        """
        Extract reusable patterns from investigation artifact.
        """
        # Parse artifact content
        content = artifact.content

        # Extract patterns (ECC)
        patterns = self.extractor.extract(content)

        # Enhance with Commander metadata
        for pattern in patterns:
            pattern.project = artifact.project
            pattern.jira_keys = artifact.jira_keys
            pattern.created_at = artifact.created_at
            pattern.artifact_id = artifact.id

            # Calculate confidence score
            pattern.confidence = self.calculate_confidence(pattern, artifact)

        return patterns

    def calculate_confidence(self, pattern: Pattern, artifact: Artifact) -> float:
        """
        Calculate confidence score for pattern.

        Factors:
        - Artifact recency (recent = higher confidence)
        - Pattern specificity (specific = higher confidence)
        - Outcome success (successful fix = higher confidence)
        - Frequency (seen multiple times = higher confidence)
        """
        score = 0.5  # Base score

        # Recency bonus (decay over time)
        days_old = (datetime.now() - artifact.created_at).days
        if days_old < 30:
            score += 0.2
        elif days_old < 90:
            score += 0.1

        # Specificity bonus
        if pattern.is_specific:
            score += 0.1

        # Outcome bonus
        if artifact.outcome == "resolved":
            score += 0.2

        # Frequency bonus (check if pattern seen before)
        similar_patterns = self.instincts.find_similar(pattern)
        if len(similar_patterns) > 2:
            score += 0.1

        return min(score, 1.0)

    async def surface_patterns(
        self,
        context: WorkContext
    ) -> list[Pattern]:
        """
        Surface relevant patterns for current investigation.

        Uses:
        - JIRA ticket keywords
        - Alert names
        - Project
        - Recent similar artifacts
        """
        # Search instinct library
        patterns = self.instincts.search(
            keywords=context.keywords,
            project=context.project,
            alert_names=context.alert_names,
            min_confidence=0.6
        )

        # Rank by relevance
        ranked = self.rank_patterns(patterns, context)

        return ranked[:5]  # Top 5 most relevant
```

**Integration with mitigation plan generation**:

```python
# backend/app/services/mitigation_plan_generator.py

class MitigationPlanGenerator:
    """
    Generate mitigation plans using artifacts + extracted patterns.
    """

    async def generate_plan(
        self,
        alert_name: str,
        context: WorkContext
    ) -> MitigationPlan:
        """
        Generate plan from artifacts + patterns.
        """
        # Search artifacts (Commander)
        similar_artifacts = await self.artifact_service.search(
            alert_name=alert_name,
            project=context.project,
            limit=5
        )

        # Surface patterns (ECC + Commander)
        patterns = await self.pattern_extractor.surface_patterns(context)

        # Generate plan
        plan = MitigationPlan(alert_name=alert_name)

        # Add steps from artifacts (Commander)
        for artifact in similar_artifacts:
            if steps := self.extract_mitigation_steps(artifact):
                plan.add_steps(steps, source=artifact.id)

        # Add steps from patterns (ECC)
        for pattern in patterns:
            if pattern.type == "mitigation":
                plan.add_steps(
                    pattern.steps,
                    source="pattern",
                    confidence=pattern.confidence
                )

        # Rank steps by confidence
        plan.rank_steps()

        return plan
```

### Implementation Plan

**Week 5: Pattern Extraction**
- [ ] Day 1: Install ECC learning framework
  - [ ] Install PatternExtractor
  - [ ] Install InstinctLibrary
  - [ ] Configure pattern storage
- [ ] Day 2: Artifact pattern extraction
  - [ ] Create `pattern_extraction.py` service
  - [ ] Implement `extract_from_artifact()`
  - [ ] Implement confidence scoring
- [ ] Day 3: Batch extraction
  - [ ] Run pattern extraction on top 50 artifacts
  - [ ] Store patterns in instinct library
  - [ ] Verify pattern quality

**Week 6: Pattern Surfacing**
- [ ] Day 4: Pattern search integration
  - [ ] Implement `surface_patterns()` in context resolver
  - [ ] Add pattern results to API responses
  - [ ] Update UI to display patterns
- [ ] Day 5: Mitigation plan enhancement
  - [ ] Integrate patterns into plan generation
  - [ ] Add confidence scores to plan steps
  - [ ] Test with warning monitor
- [ ] Day 6: Documentation
  - [ ] Create PATTERN-EXTRACTION-COMPLETE.md
  - [ ] Update artifact creation workflow
  - [ ] Update PROGRESS.md

**Effort**: ~25 hours (1.5 weeks part-time)

**Success Criteria**:
- ✅ Patterns extracted from top 50 artifacts
- ✅ Patterns surfaced in new investigations
- ✅ Mitigation plans include pattern-based steps
- ✅ Confidence scores displayed in UI

---

## Gap 4: Verification Loops

### What ECC Has

**Checkpoint evaluation**:
- After each major step, verify outcome
- Ask: "Did this work?"
- If no, adjust approach

**Continuous evaluation**:
- During multi-step workflows
- Evaluate intermediate results
- Adjust execution based on feedback

**Observer loop prevention**:
- Deterministic scoring
- Anti-cycle measures
- Prevent infinite retry loops

**Configurable grading**:
- Different models for different verification tasks
- Fast models for simple checks
- Advanced models for complex validation

### What Commander Has

**Manual verification**:
- Skills execute steps
- User manually verifies
- No automated checkpoints

**Test plans in artifacts**:
- Testing steps documented
- Manual execution required

### The Gap

**Commander lacks**:
- Automated verification checkpoints
- Continuous evaluation during workflows
- Observer loop prevention
- Self-correcting execution

**Impact**: Skills can fail silently (no automated verification)

### Integration Strategy

**Add verification loops to multi-step skills**:

```python
# ~/.claude/skills/wx-task-debug/SKILL.md

## Verification Checkpoints (ECC pattern)

After each major step, verify outcome before proceeding.

### Step 1: Check Task Status
**Command**: `wxctl task get <task-id>`
**Expected**: Task status visible
**Verification**:
- ✅ If status returned → Continue
- ❌ If error → Check kubectl auth, retry once

### Step 2: Check Pod Logs
**Command**: `kubectl logs -n wx <pod-name>`
**Expected**: Logs visible
**Verification**:
- ✅ If logs visible → Analyze for errors
- ❌ If pod not found → Check task.pod_name field
- ❌ If "Forbidden" → Check kubeconfig context

### Step 3: Check Grafana Dashboard
**Expected**: Metrics visible for task
**Verification**:
- ✅ If metrics visible → Analyze patterns
- ❌ If no metrics → Check task.created_at (might be too old)

### Step 4: Root Cause Identified
**Verification**:
- ✅ Clear root cause → Document in artifact
- ❌ Unclear → Run extended debugging (check Loki, database)
- ❌ Multiple causes → Prioritize by likelihood

### Observer Loop Prevention
**Max retries per step**: 2
**If stuck**: Escalate to human, don't retry infinitely
```

**Continuous evaluation in background jobs**:

```python
# backend/app/jobs/pagerduty_enrichment.py

class PagerDutyEnrichmentJob:
    """
    PagerDuty enrichment with continuous evaluation.
    """

    async def run(self):
        """Run enrichment with verification checkpoints."""

        # Step 1: Scan JIRA for PD references
        jira_issues = await self.scan_jira_for_pd_refs()

        # Checkpoint: Verify JIRA scan worked
        if not jira_issues:
            logger.warning("No JIRA issues found with PD refs")
            # Don't fail, might be legitimate
            return {"status": "complete", "enriched": 0}

        # Step 2: Extract PD incident IDs
        pd_ids = []
        for issue in jira_issues:
            refs = self.detect_pd_refs(issue.description)
            pd_ids.extend(refs)

        # Checkpoint: Verify detection worked
        if not pd_ids:
            logger.warning("PD refs detected but failed to extract IDs")
            # This is suspicious, investigate
            await self.alert_on_extraction_failure(jira_issues)
            return {"status": "failed", "reason": "extraction_failed"}

        # Step 3: Fetch incidents from PagerDuty
        incidents = []
        failed_fetches = []

        for pd_id in pd_ids:
            try:
                incident = await self.fetch_incident(pd_id)
                incidents.append(incident)
            except Exception as e:
                failed_fetches.append((pd_id, str(e)))

        # Checkpoint: Verify fetch success rate
        success_rate = len(incidents) / len(pd_ids)
        if success_rate < 0.5:
            logger.error(f"PD fetch success rate too low: {success_rate}")
            # Alert on systemic failure
            await self.alert_on_fetch_failures(failed_fetches)
            return {"status": "partial", "failures": len(failed_fetches)}

        # Step 4: Create EntityLinks
        links_created = 0
        for incident in incidents:
            try:
                await self.create_entity_link(incident)
                links_created += 1
            except Exception as e:
                logger.error(f"Failed to create link for {incident.id}: {e}")

        # Checkpoint: Verify link creation
        if links_created == 0:
            logger.error("No EntityLinks created despite incidents fetched")
            await self.alert_on_link_failure()
            return {"status": "failed", "reason": "link_creation_failed"}

        # Success
        return {
            "status": "complete",
            "enriched": links_created,
            "fetch_failures": len(failed_fetches)
        }
```

### Implementation Plan

**Week 7: Verification Checkpoints**
- [ ] Day 1: Update wx-task-debug skill
  - [ ] Add verification checkpoints to each step
  - [ ] Add observer loop prevention (max retries)
  - [ ] Add escalation paths
- [ ] Day 2: Update incident-response skill
  - [ ] Add checkpoint evaluation
  - [ ] Add success criteria per step
  - [ ] Add failure recovery paths
- [ ] Day 3: Update background jobs
  - [ ] Add continuous evaluation to enrichment jobs
  - [ ] Add alerting on systemic failures
  - [ ] Add success rate tracking

**Week 8: Testing & Monitoring**
- [ ] Day 4: Test verification loops
  - [ ] Simulate failures at each checkpoint
  - [ ] Verify recovery paths work
  - [ ] Test observer loop prevention
- [ ] Day 5: Add monitoring
  - [ ] Track verification checkpoint outcomes
  - [ ] Alert on repeated failures
  - [ ] Dashboard for verification metrics
- [ ] Day 6: Documentation
  - [ ] Create VERIFICATION-LOOPS-COMPLETE.md
  - [ ] Update skill documentation
  - [ ] Update PROGRESS.md

**Effort**: ~15 hours (1 week part-time)

**Success Criteria**:
- ✅ Skills have verification checkpoints
- ✅ Background jobs evaluate continuously
- ✅ Observer loop prevention works
- ✅ Failures trigger appropriate alerts

---

## Implementation Timeline

### Overall Roadmap (6 weeks)

**Weeks 1-2: Lifecycle Hooks** (40 hours)
- Hook framework setup
- User prompt submit hook
- Tool call post hook
- Commander integration

**Weeks 3-4: Language Agents** (30 hours)
- Install ECC agents
- MR review integration
- Overview agent extension
- UI integration

**Weeks 5-6: Continuous Learning** (25 hours)
- Pattern extraction framework
- Batch artifact processing
- Pattern surfacing
- Mitigation plan enhancement

**Weeks 7-8: Verification Loops** (15 hours)
- Skill checkpoint updates
- Background job evaluation
- Testing and monitoring

**Total Effort**: ~110 hours (6 weeks part-time, 3 weeks full-time)

### Milestone Deliverables

**Milestone 1 (Week 2)**: Hooks Integration Complete
- ✅ Hooks execute on prompts and tool calls
- ✅ Commander enrichment triggered automatically
- ✅ Artifacts auto-created
- 📄 HOOKS-INTEGRATION-COMPLETE.md

**Milestone 2 (Week 4)**: Language Agents Complete
- ✅ MR reviews include language-specific feedback
- ✅ Security reviews detect vulnerabilities
- ✅ Overview agent orchestrates all agents
- 📄 LANGUAGE-AGENTS-INTEGRATION-COMPLETE.md

**Milestone 3 (Week 6)**: Continuous Learning Complete
- ✅ Patterns extracted from top 50 artifacts
- ✅ Patterns surfaced in investigations
- ✅ Mitigation plans include pattern steps
- 📄 PATTERN-EXTRACTION-COMPLETE.md

**Milestone 4 (Week 8)**: Verification Loops Complete
- ✅ Skills have checkpoints
- ✅ Background jobs evaluate continuously
- ✅ Observer loop prevention works
- 📄 VERIFICATION-LOOPS-COMPLETE.md

---

## Dependencies & Risks

### Dependencies

1. **ECC Installation**:
   - Requires ECC plugin or source installation
   - May need customization for Planet environment
   - Risk: ECC may not support Commander's architecture

2. **Commander API Stability**:
   - Hooks need stable Commander API endpoints
   - Risk: Breaking changes during integration

3. **Resource Allocation**:
   - ~110 hours of development time needed
   - Risk: Other priorities may delay integration

### Mitigation Strategies

1. **Phased Implementation**:
   - Start with hooks (highest value, lowest risk)
   - Validate each phase before continuing
   - Can stop at any milestone if priorities change

2. **Incremental Adoption**:
   - Start with one skill (wx-task-debug) for verification loops
   - Start with one language (Go) for agents
   - Expand based on success

3. **Fallback Plans**:
   - If ECC integration fails, implement patterns manually
   - If hooks don't work, keep background jobs
   - If agents are too complex, defer to Phase 2

---

## Success Metrics

### Quantitative Metrics

**Lifecycle Hooks**:
- Hook execution latency: < 100ms
- Commander enrichment trigger rate: > 80% of detected refs
- Artifact auto-creation rate: 100% of completed investigations

**Language Agents**:
- MR review coverage: > 90% of MRs get language review
- Security findings per MR: Track over time
- Agent feedback usefulness: > 80% positive (survey)

**Continuous Learning**:
- Pattern extraction rate: > 50 patterns from top 50 artifacts
- Pattern surfacing accuracy: > 70% relevant in new investigations
- Mitigation plan confidence: Average > 0.7

**Verification Loops**:
- Checkpoint pass rate: > 85%
- Observer loop incidents: 0 (should never happen)
- Skill success rate improvement: +15% (due to better error handling)

### Qualitative Metrics

**Developer Experience**:
- "I don't have to manually trigger enrichment anymore"
- "MR reviews catch bugs I would have missed"
- "Mitigation plans suggest the same fix I would have done"

**On-Call Experience**:
- "Verification loops catch issues before they become incidents"
- "Pattern suggestions are actually helpful"
- "Less time debugging, more time fixing"

---

## Next Steps

### Immediate Actions (This Week)

1. ✅ Read ECC "Shortform Guide"
2. ✅ Install ECC plugin via Claude Code marketplace
3. ⏸️ Prototype `user-prompt-submit` hook
4. ⏸️ Test hook integration with Commander

### Short-Term (Next 2 Weeks)

5. ⏸️ Implement hook framework
6. ⏸️ Integrate hooks with Commander API
7. ⏸️ Test artifact auto-creation
8. ⏸️ Document Milestone 1

### Medium-Term (Next 6 Weeks)

9. ⏸️ Complete all 4 integration phases
10. ⏸️ Document all milestones
11. ⏸️ Measure success metrics
12. ⏸️ Prepare for community contribution

---

## Appendix: ECC Resources

### Documentation
- **ECC GitHub**: https://github.com/affaan-m/everything-claude-code
- **Shortform Guide**: Read first for foundations
- **Longform Guide**: Advanced patterns and best practices

### Installation
```bash
# Plugin installation (recommended)
# Via Claude Code marketplace: Search "Everything Claude Code"

# Manual installation (alternative)
git clone https://github.com/affaan-m/everything-claude-code.git
cd everything-claude-code
./install.sh typescript  # Or python, go, etc.
```

### Configuration
```bash
# Set hook profile
export ECC_HOOK_PROFILE=standard  # minimal|standard|strict

# Disable specific hooks
export ECC_DISABLED_HOOKS=hook1,hook2

# Package manager
export CLAUDE_PACKAGE_MANAGER=npm  # Or pip, go mod, etc.
```

---

**Status**: Ready to implement
**Owner**: Aaryn Olsson
**Next Review**: After Milestone 1 (Week 2)
