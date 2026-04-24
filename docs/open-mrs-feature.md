# Open MRs Feature - Multi-Project MR Management

**Date**: 2026-03-12
**Status**: Implemented

## Overview

The Open MRs feature provides comprehensive multi-project merge request management in the Commander Dashboard. It supports viewing, reviewing, approving, and managing MRs across WX, Jobs, G4, and Temporal projects.

## Features

### 1. Multi-Project Selection
- Checkbox selector for each project (WX, Jobs, G4, Temporal)
- "Select All" option
- Persists selection in component state
- Fetches MRs only from selected projects

### 2. MR Table View
- Displays all open MRs across selected projects
- Columns:
  - Project (uppercase abbreviation)
  - MR number (clickable link to GitLab)
  - Title (with DRAFT indicator)
  - Author (highlighted if mine)
  - Created age
  - Last commit age
  - Review status (Not reviewed / Reviewed / Needs re-review)

### 3. MR Detail Modal
Clicking any MR opens a detailed view with:
- Full MR metadata (author, branches, ages, labels)
- Description
- Review status
- Action buttons:
  - **Review**: Opens review history if reviewed, or spawns new review agent
  - **Approve**: Calls GitLab API to approve MR
  - **Close**: Closes the MR (only visible for your own MRs)
  - **Draft Toggle**: Marks MR as draft or ready (only for your own MRs)

### 4. Review System

#### Review Triggering
When clicking "Review" on an unreviewed MR:
1. Spawns a headless agent
2. Creates a worktree for the MR branch
3. Sends initial prompt to run `/mr-review` skill
4. Records review session in database

#### Review Tracking
- Tracks all review sessions for each MR
- Each review records:
  - Agent ID
  - Session ID
  - Commit SHA
  - Timestamp
- Detects when new commits are made after review
- Marks MR as "Needs re-review" if commit SHA changes

#### Review History
If MR has been reviewed, clicking "Review" shows history modal with:
- All review sessions
- Timestamp of each review
- Commit SHA reviewed
- Link to agent session for each review

### 5. Auto-Refresh
- Polls for MR updates every 2 minutes
- Manual refresh via menu

## Architecture

### Backend

#### New Files
- `app/models/mr_review.py` - Database model for tracking reviews
- `app/services/gitlab_service.py` - GitLab integration service
- `alembic/versions/b5e7f8c9d0a1_add_mr_review_table.py` - Migration

#### Updated Files
- `app/api/gitlab.py` - API endpoints for MR operations

#### Database Schema
```sql
CREATE TABLE mr_reviews (
    id INTEGER PRIMARY KEY,
    project VARCHAR NOT NULL,
    mr_iid INTEGER NOT NULL,
    last_commit_sha VARCHAR,
    needs_review BOOLEAN DEFAULT TRUE,
    reviews JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_mr_reviews_project ON mr_reviews(project);
CREATE INDEX ix_mr_reviews_mr_iid ON mr_reviews(mr_iid);
```

#### API Endpoints

**GET /api/mrs**
- Query params: `projects[]` (optional, list of project keys)
- Returns: List of MRs with detailed info

**GET /api/mrs/{project}/{mr_iid}**
- Returns: Detailed MR information

**POST /api/mrs/{project}/{mr_iid}/approve**
- Approves the MR via GitLab API

**POST /api/mrs/{project}/{mr_iid}/close**
- Closes the MR

**POST /api/mrs/{project}/{mr_iid}/draft**
- Query params: `is_draft` (boolean)
- Toggles draft status

**POST /api/mrs/{project}/{mr_iid}/review**
- Spawns review agent
- Records review in database
- Returns agent ID and session ID

### Frontend

#### New Components
- `components/cards/OpenMRs.tsx` - Main MR list component
- `components/cards/MRDetailModal.tsx` - MR detail modal with actions
- `components/ui/checkbox.tsx` - Checkbox UI component

#### Updated Files
- `app/page.tsx` - Added OpenMRs component to dashboard
- `lib/api.ts` - Added MR-related API methods and types

#### Key Types
```typescript
interface DetailedMR {
  project: string;
  iid: number;
  title: string;
  description?: string;
  author: string;
  url: string;
  branch: string;
  target_branch?: string;
  sha?: string;
  age_created_hours: number;
  age_last_commit_hours: number;
  is_draft: boolean;
  is_mine: boolean;
  state?: string;
  labels?: string[];
  needs_review?: boolean;
  reviews?: Array<{
    agent_id: string;
    session_id: string;
    commit_sha: string;
    timestamp: string;
  }>;
}
```

## Project Configuration

Projects are configured in `backend/app/services/gitlab_service.py`:

```python
PROJECTS = {
    "wx": {
        "repo": "wx/wx",
        "web_url": "https://hello.planet.com/code/wx/wx",
        "worktree_base": "~/workspaces",
    },
    "jobs": {
        "repo": "jobs/jobs",
        "web_url": "https://hello.planet.com/code/jobs/jobs",
        "worktree_base": "~/workspaces",
    },
    "g4": {
        "repo": "product/g4-wk/g4",
        "web_url": "https://hello.planet.com/code/product/g4-wk/g4",
        "worktree_base": "~/code/product/g4-wk",
    },
    "temporal": {
        "repo": "temporal/temporalio-cloud",
        "web_url": "https://hello.planet.com/code/temporal/temporalio-cloud",
        "worktree_base": "~/workspaces/temporalio",
    },
}
```

## Integration with Existing Systems

### GitLab CLI (glab)
- Uses `~/tools/glab/glab-mr` for MR operations
- Leverages existing GitLab authentication
- API calls via `glab api` command

### Agent System
- Spawns headless agents via `/api/agents` endpoint
- Creates worktrees for MR branches
- Integrates with `/mr-review` skill

### Review Skill
The system expects the `/mr-review` skill to:
1. Analyze the MR changes
2. Check for code quality issues
3. Verify tests
4. Post review comments to GitLab
5. Provide structured feedback

## Usage

1. **View MRs**: Select projects using checkboxes to filter MRs
2. **Review MR**: Click on MR row to open detail modal, then click "Review"
3. **Check Review Status**: Look for review indicators in the table
4. **Approve MR**: Open detail modal and click "Approve"
5. **Manage Drafts**: Toggle draft status from detail modal (your MRs only)

## Future Enhancements

- [ ] Filter by author, draft status, review status
- [ ] Sort by different columns
- [ ] Batch operations (approve multiple MRs)
- [ ] Review comment integration
- [ ] CI/CD pipeline status in table
- [ ] Conflict detection
- [ ] Auto-merge after approval
- [ ] Review assignment
- [ ] Notification system for new MRs
