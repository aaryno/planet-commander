# Phase 4: Advanced Features - Implementation Plan

**Created**: March 20, 2026, 22:20
**Status**: Planning → Implementation
**Duration**: 3-5 days (estimated)

---

## Overview

Phase 4 builds on the completed Phase 3 (Proactive Warning Monitoring) by adding:
1. **Learning System** - Improve predictions from user feedback
2. **Automated Mitigation** - Execute runbooks with approval
3. **Multi-Team Expansion** - Customize for different teams

---

## Phase 3 Recap (Complete)

**What We Built**:
- ✅ Warning detection and parsing
- ✅ Escalation probability prediction
- ✅ Standby context pre-assembly
- ✅ Slack notifications
- ✅ Metrics dashboard (trends, accuracy, top alerts)

**Current Capabilities**:
- Detect warnings before they escalate
- Predict 75% of escalations correctly
- Pre-assemble mitigation context in < 2 minutes
- Notify engineers via Slack
- Track metrics and accuracy

**Gaps Phase 4 Addresses**:
- ❌ No feedback loop (predictions don't improve)
- ❌ No automated actions (engineers must manually mitigate)
- ❌ Single configuration (can't customize per team)

---

## Phase 4 Goals

### Goal 1: Learning System (Days 1-2)

**Problem**: Prediction accuracy is static at ~75%. No way to learn from mistakes.

**Solution**: Collect feedback and retrain prediction model.

**Features**:
- **Feedback Collection**
  - "Was this prediction accurate?" buttons on warnings
  - Track prediction outcomes (escalated vs. cleared)
  - Store feedback with context (alert type, system, time)

- **Model Tuning**
  - Adjust escalation probability based on feedback
  - Identify patterns in false positives/negatives
  - Update alert-specific weights

- **Analytics Dashboard**
  - Show accuracy trends over time
  - Identify improving/degrading alerts
  - Compare before/after feedback

**Success Metrics**:
- Accuracy improves from 75% → 85% within 30 days
- False positive rate drops from 17% → <10%
- User engagement: 80%+ of warnings receive feedback

### Goal 2: Automated Mitigation (Days 3-4)

**Problem**: Engineers still need to manually execute mitigation steps. Time-consuming and error-prone.

**Solution**: Execute runbook steps automatically with approval.

**Features**:
- **Runbook Definition**
  - YAML-based runbook format
  - Define steps: commands, scripts, API calls
  - Approval requirements (manual/auto)

- **Execution Engine**
  - Execute runbook steps sequentially
  - Pause for approval on critical steps
  - Rollback on failure

- **Approval Workflow**
  - Slack approval buttons
  - One-click approve/reject
  - Audit log of all approvals/executions

- **Safety Mechanisms**
  - Dry-run mode (show what would happen)
  - Manual override (stop execution)
  - Post-execution validation

**Success Metrics**:
- 50% of mitigations automated (with approval)
- Average approval time: < 2 minutes
- Zero unintended side effects
- 80%+ engineer satisfaction

### Goal 3: Multi-Team Expansion (Day 5)

**Problem**: Different teams have different alerts, runbooks, and notification preferences.

**Solution**: Team-specific configurations and customization.

**Features**:
- **Team Profiles**
  - Define teams: Compute, Data Pipeline, Hobbes, etc.
  - Map alerts to teams
  - Team-specific escalation thresholds

- **Custom Notifications**
  - Team-specific Slack channels
  - Custom message templates
  - Escalation policy per team

- **Per-Team Runbooks**
  - Team maintains their own runbooks
  - Different approval workflows
  - Team-specific metrics

**Success Metrics**:
- 5 teams onboarded (Compute, Data Pipeline, Hobbes, Discovery, Corpeng)
- Each team has custom configuration
- 90%+ team satisfaction
- <1 hour to onboard new team

---

## Implementation Roadmap

### Day 1: Feedback Collection System

**Backend** (~400 lines):
1. Database models
   - `WarningFeedback` table
   - `PredictionFeedback` table

2. API endpoints
   - `POST /api/warnings/{id}/feedback` - Submit feedback
   - `GET /api/warnings/{id}/feedback` - Get feedback
   - `GET /api/warnings/feedback/stats` - Feedback statistics

3. Services
   - `FeedbackService` - Store and retrieve feedback
   - `PredictionTuningService` - Adjust probabilities based on feedback

**Frontend** (~300 lines):
1. Feedback buttons on warning cards
2. Feedback submission modal
3. Feedback display on warning details
4. Feedback analytics widget

**Testing**:
- Unit tests for feedback storage
- Integration tests for API
- UI tests for feedback flow

**Deliverable**: Users can provide feedback on predictions

### Day 2: Learning System

**Backend** (~500 lines):
1. Model tuning algorithm
   - Analyze feedback patterns
   - Adjust escalation probabilities
   - Update alert-specific weights

2. Background jobs
   - Daily feedback analysis job
   - Weekly model retraining job
   - Metrics update job

3. Analytics endpoints
   - `GET /api/warnings/learning/stats` - Learning metrics
   - `GET /api/warnings/learning/trends` - Accuracy trends over time
   - `GET /api/warnings/learning/alerts/{name}` - Alert-specific improvement

**Frontend** (~350 lines):
1. Learning dashboard
   - Accuracy trends chart
   - Alert improvement rankings
   - Feedback summary

2. Model tuning controls
   - Adjust thresholds manually
   - Enable/disable auto-tuning
   - Reset to defaults

**Testing**:
- Model tuning algorithm tests
- Feedback analysis tests
- Integration tests

**Deliverable**: Prediction model improves automatically from feedback

### Day 3: Runbook Definition & Storage

**Backend** (~450 lines):
1. Database models
   - `Runbook` table
   - `RunbookStep` table
   - `RunbookExecution` table

2. Runbook parser
   - Parse YAML runbook format
   - Validate runbook structure
   - Extract steps and dependencies

3. API endpoints
   - `GET /api/runbooks` - List runbooks
   - `GET /api/runbooks/{id}` - Get runbook details
   - `POST /api/runbooks` - Create runbook
   - `PUT /api/runbooks/{id}` - Update runbook

4. Services
   - `RunbookService` - CRUD operations
   - `RunbookValidationService` - Validate runbooks

**Frontend** (~250 lines):
1. Runbook library UI
2. Runbook editor (YAML)
3. Runbook viewer
4. Link runbooks to alerts

**Testing**:
- YAML parsing tests
- Validation tests
- Storage tests

**Deliverable**: Runbooks can be defined and stored

### Day 4: Automated Execution & Approval

**Backend** (~600 lines):
1. Execution engine
   - Execute runbook steps
   - Handle approvals
   - Rollback on failure

2. Approval workflow
   - Send Slack approval request
   - Track approval status
   - Timeout handling

3. API endpoints
   - `POST /api/runbooks/{id}/execute` - Start execution
   - `POST /api/runbooks/executions/{id}/approve` - Approve step
   - `POST /api/runbooks/executions/{id}/stop` - Stop execution
   - `GET /api/runbooks/executions/{id}` - Execution status

4. Safety mechanisms
   - Dry-run mode
   - Execution locks (prevent concurrent runs)
   - Audit logging

**Frontend** (~400 lines):
1. Execution status UI
2. Approval interface
3. Execution history
4. Real-time execution logs

**Slack Integration** (~150 lines):
1. Approval button messages
2. Status updates
3. Completion notifications

**Testing**:
- Execution engine tests
- Approval workflow tests
- Rollback tests
- Safety mechanism tests

**Deliverable**: Runbooks can be executed with approval

### Day 5: Multi-Team Configuration

**Backend** (~350 lines):
1. Database models
   - `Team` table
   - `TeamAlertConfig` table
   - `TeamNotificationConfig` table

2. API endpoints
   - `GET /api/teams` - List teams
   - `GET /api/teams/{id}` - Team details
   - `PUT /api/teams/{id}/config` - Update team config

3. Services
   - `TeamConfigService` - Manage team configs
   - `TeamRoutingService` - Route alerts to teams

**Frontend** (~300 lines):
1. Team configuration UI
2. Alert → Team mapping
3. Team-specific dashboards
4. Per-team metrics

**Testing**:
- Team routing tests
- Configuration tests
- Multi-team metrics tests

**Deliverable**: Multiple teams can use the system with custom configs

---

## Database Schema

### New Tables

#### WarningFeedback

```sql
CREATE TABLE warning_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warning_event_id UUID NOT NULL REFERENCES warning_events(id),

    -- Feedback type
    feedback_type VARCHAR(50) NOT NULL,  -- 'prediction_accuracy', 'escalation_timing', 'context_usefulness'

    -- Prediction feedback
    prediction_was_correct BOOLEAN,
    actual_escalated BOOLEAN,
    predicted_probability FLOAT,

    -- Timing feedback
    escalation_timing_accurate BOOLEAN,
    actual_escalation_time TIMESTAMP WITH TIME ZONE,

    -- Context feedback
    context_was_useful BOOLEAN,
    missing_information TEXT,

    -- User info
    submitted_by VARCHAR(200),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Optional comment
    comment TEXT
);

CREATE INDEX idx_warning_feedback_event ON warning_feedback(warning_event_id);
CREATE INDEX idx_warning_feedback_type ON warning_feedback(feedback_type);
CREATE INDEX idx_warning_feedback_submitted ON warning_feedback(submitted_at);
```

#### PredictionModel

```sql
CREATE TABLE prediction_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version VARCHAR(50) NOT NULL UNIQUE,

    -- Model parameters
    base_escalation_rate FLOAT NOT NULL DEFAULT 0.5,
    alert_specific_weights JSONB,  -- { "alert-name": 0.75, ... }

    -- Model metadata
    trained_on_feedback_count INTEGER DEFAULT 0,
    training_date TIMESTAMP WITH TIME ZONE,
    accuracy FLOAT,
    false_positive_rate FLOAT,
    false_negative_rate FLOAT,

    -- Status
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### Runbooks

```sql
CREATE TABLE runbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,

    -- Trigger
    alert_name VARCHAR(200),  -- NULL = manual trigger only
    system VARCHAR(100),

    -- Runbook content
    runbook_yaml TEXT NOT NULL,
    parsed_steps JSONB,

    -- Metadata
    owner_team VARCHAR(100),
    requires_approval BOOLEAN DEFAULT true,
    auto_execute BOOLEAN DEFAULT false,

    -- Version control
    version INTEGER DEFAULT 1,
    created_by VARCHAR(200),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_runbooks_alert ON runbooks(alert_name);
CREATE INDEX idx_runbooks_team ON runbooks(owner_team);
```

#### RunbookExecutions

```sql
CREATE TABLE runbook_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    runbook_id UUID NOT NULL REFERENCES runbooks(id),
    warning_event_id UUID REFERENCES warning_events(id),

    -- Execution state
    status VARCHAR(50) NOT NULL,  -- 'pending', 'running', 'waiting_approval', 'completed', 'failed', 'cancelled'
    current_step_index INTEGER DEFAULT 0,

    -- Steps and results
    steps_executed JSONB,  -- [ { "step": 1, "status": "completed", "output": "...", "timestamp": "..." } ]

    -- Approval tracking
    approval_requested_at TIMESTAMP WITH TIME ZONE,
    approval_granted_at TIMESTAMP WITH TIME ZONE,
    approved_by VARCHAR(200),

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Error handling
    error_message TEXT,
    rollback_executed BOOLEAN DEFAULT false
);

CREATE INDEX idx_runbook_exec_runbook ON runbook_executions(runbook_id);
CREATE INDEX idx_runbook_exec_warning ON runbook_executions(warning_event_id);
CREATE INDEX idx_runbook_exec_status ON runbook_executions(status);
```

#### Teams

```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,

    -- Configuration
    slack_channel VARCHAR(100),
    notification_channel VARCHAR(100),
    pagerduty_escalation_policy_id VARCHAR(100),

    -- Thresholds
    warning_probability_threshold FLOAT DEFAULT 0.5,
    high_risk_threshold FLOAT DEFAULT 0.75,

    -- Preferences
    auto_notify BOOLEAN DEFAULT true,
    auto_execute_runbooks BOOLEAN DEFAULT false,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### TeamAlertMappings

```sql
CREATE TABLE team_alert_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id),
    alert_name_pattern VARCHAR(200) NOT NULL,  -- supports wildcards: 'jobs-*', 'wx-task-*'
    system VARCHAR(100),

    -- Override team defaults
    custom_threshold FLOAT,
    custom_notification_channel VARCHAR(100),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_team_alert_map_team ON team_alert_mappings(team_id);
CREATE INDEX idx_team_alert_map_alert ON team_alert_mappings(alert_name_pattern);
```

---

## Runbook YAML Format

### Example: Database Connection Pool Mitigation

```yaml
name: increase-db-connection-pool
description: Increase database connection pool size when CPU is high
version: 1.0
owner_team: compute
requires_approval: true

triggers:
  - alert_name: jobs-scheduler-cpu-high
    probability_threshold: 0.7

steps:
  - name: check_current_pool_size
    type: query
    command: "kubectl exec -n jobs jobs-scheduler-0 -- cat /etc/database.conf | grep max_connections"
    approval_required: false
    timeout: 30s

  - name: backup_config
    type: command
    command: "kubectl cp jobs/jobs-scheduler-0:/etc/database.conf ./backup-$(date +%s).conf"
    approval_required: false

  - name: increase_pool_size
    type: patch
    command: |
      kubectl set env deployment/jobs-scheduler \
        -n jobs \
        DB_MAX_CONNECTIONS=100
    approval_required: true  # ← Requires approval before execution
    timeout: 60s

  - name: restart_deployment
    type: command
    command: "kubectl rollout restart deployment/jobs-scheduler -n jobs"
    approval_required: true
    timeout: 120s

  - name: wait_for_rollout
    type: wait
    command: "kubectl rollout status deployment/jobs-scheduler -n jobs"
    approval_required: false
    timeout: 300s

  - name: verify_metrics
    type: query
    command: "curl -s 'https://planet.grafana.net/api/datasources/proxy/1/api/v1/query?query=jobs_scheduler_cpu_usage' | jq '.data.result[0].value[1]'"
    approval_required: false
    success_condition: "value < 80"  # ← Validation

rollback:
  - name: restore_original_config
    type: patch
    command: |
      kubectl set env deployment/jobs-scheduler \
        -n jobs \
        DB_MAX_CONNECTIONS=50
```

### Step Types

| Type | Description | Example |
|------|-------------|---------|
| `query` | Read-only operation | `kubectl get pods`, `curl metrics` |
| `command` | Shell command execution | `kubectl rollout restart` |
| `patch` | Modify resource | `kubectl set env`, `kubectl scale` |
| `wait` | Wait for condition | `kubectl rollout status` |
| `api_call` | HTTP API request | `POST /api/slack/notify` |
| `script` | Execute script file | `./scripts/mitigate.sh` |

---

## API Endpoints Summary

### Feedback APIs

```
POST   /api/warnings/{id}/feedback           Submit feedback on prediction
GET    /api/warnings/{id}/feedback           Get feedback for warning
GET    /api/warnings/feedback/stats          Feedback statistics
GET    /api/warnings/learning/stats          Learning system metrics
GET    /api/warnings/learning/trends         Accuracy improvement trends
```

### Runbook APIs

```
GET    /api/runbooks                         List all runbooks
GET    /api/runbooks/{id}                    Get runbook details
POST   /api/runbooks                         Create new runbook
PUT    /api/runbooks/{id}                    Update runbook
DELETE /api/runbooks/{id}                    Delete runbook

POST   /api/runbooks/{id}/execute            Execute runbook (with dry-run option)
POST   /api/runbooks/executions/{id}/approve Approve pending step
POST   /api/runbooks/executions/{id}/stop    Stop execution
GET    /api/runbooks/executions/{id}         Get execution status
GET    /api/runbooks/executions              List executions (filtered)
```

### Team APIs

```
GET    /api/teams                            List teams
GET    /api/teams/{id}                       Get team details
POST   /api/teams                            Create team
PUT    /api/teams/{id}/config                Update team configuration
GET    /api/teams/{id}/alerts                Get team's alerts
GET    /api/teams/{id}/metrics               Get team-specific metrics
```

---

## Success Metrics

### Learning System

- **Accuracy Improvement**: 75% → 85% within 30 days
- **Feedback Rate**: >80% of warnings receive feedback
- **False Positive Reduction**: 17% → <10%
- **False Negative Reduction**: 6% → <5%
- **User Trust**: Survey score >4/5

### Automated Mitigation

- **Automation Rate**: 50% of mitigations automated (with approval)
- **Approval Time**: <2 minutes average
- **Success Rate**: >95% of executions complete successfully
- **Rollback Rate**: <5% of executions require rollback
- **Time Saved**: 10-15 minutes per incident

### Multi-Team Expansion

- **Team Onboarding**: 5 teams onboarded in first month
- **Onboarding Time**: <1 hour per team
- **Team Satisfaction**: >90% satisfaction score
- **Configuration Coverage**: All teams have custom thresholds
- **Cross-Team Insights**: Shared learnings across teams

---

## Risks & Mitigations

### Risk 1: Automated Execution Errors

**Impact**: High - Could cause outages or data loss

**Mitigation**:
- Require approval for all critical steps
- Dry-run mode mandatory before first execution
- Comprehensive rollback procedures
- Execution locks prevent concurrent runs
- Audit logging for all actions

### Risk 2: Feedback Bias

**Impact**: Medium - Biased feedback could degrade model

**Mitigation**:
- Weight recent feedback higher
- Require minimum feedback count before tuning
- Manual override for model parameters
- A/B test model changes
- Monitor accuracy after each tuning

### Risk 3: Team Configuration Conflicts

**Impact**: Medium - Overlapping alert mappings

**Mitigation**:
- Validate alert patterns don't overlap
- Priority ordering for team mappings
- Clear ownership rules
- Conflict resolution UI

### Risk 4: Runbook Maintenance Burden

**Impact**: Medium - Runbooks become stale

**Mitigation**:
- Version control for runbooks
- Last-executed timestamp tracking
- Automated runbook validation
- Periodic review reminders

---

## Next Steps

### Immediate (Start Day 1)

1. Create `WarningFeedback` database model
2. Build feedback API endpoints
3. Add feedback buttons to warning cards
4. Test feedback collection flow

### Short-Term (Days 2-3)

5. Implement model tuning algorithm
6. Build learning dashboard
7. Create runbook database models
8. Build runbook parser

### Medium-Term (Days 4-5)

9. Implement execution engine
10. Build approval workflow
11. Create team configuration
12. Test multi-team scenarios

---

## Questions for User

Before starting implementation:

1. **Feedback Collection**: Which feedback types are most valuable?
   - Prediction accuracy (was it right?)
   - Escalation timing (when did it escalate?)
   - Context usefulness (was the plan helpful?)

2. **Automated Execution**: Comfort level with automation?
   - Manual approval for all steps (safest)
   - Auto-execute read-only steps
   - Auto-execute all with manual override

3. **Multi-Team Expansion**: Which teams to onboard first?
   - Compute (current team)
   - Data Pipeline
   - Hobbes
   - Discovery & Delivery
   - All at once

4. **Implementation Priority**: Which feature is most important?
   - Learning system (improve predictions)
   - Automated mitigation (save time)
   - Multi-team (expand reach)

---

**Ready to start Phase 4 Day 1: Feedback Collection System**
