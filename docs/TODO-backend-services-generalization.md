# TODO: Wire Backend Services to Project Entity

## Goal
Replace hardcoded project lists in backend services with queries to the `projects` table. When a user adds a project via the API/UI, backend services should automatically start tracking its repos, syncing its JIRA tickets, and scanning its MRs — no code changes needed.

## Current Hardcoded Project Data

### 1. `backend/app/services/gitlab_service.py` — PROJECTS dict (line 27)
```python
PROJECTS = {
    "wx": {"repo": "wx/wx", "web_url": "...", "worktree_base": "..."},
    "jobs": {"repo": "jobs/jobs", ...},
    "g4": {"repo": "product/g4-wk/g4", ...},
    "temporal": {"repo": "temporal/temporalio-cloud", ...},
}
```
**Used by**: `list_open_mrs()`, `_fetch_project_mrs()`, `get_mr_details()`, `approve_mr()`, `close_mr()`, `toggle_draft()` — 10+ references

**Fix**: Replace with a function that queries `Project.repositories` from DB:
```python
async def _get_project_config(project_key: str, db: AsyncSession) -> dict:
    from app.models.project import Project
    result = await db.execute(select(Project).where(Project.key == project_key))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Unknown project: {project_key}")
    repos = project.repositories or []
    return {
        "repo": repos[0]["path"] if repos else "",
        "web_url": f"https://hello.planet.com/code/{repos[0]['path']}" if repos else "",
        "worktree_base": "~/workspaces",
    }

async def _get_all_project_keys(db: AsyncSession) -> list[str]:
    result = await db.execute(select(Project.key).where(Project.is_active == True))
    return [r[0] for r in result.fetchall()]
```

**Challenge**: gitlab_service functions are currently sync (not async). They shell out to `glab` CLI. Adding DB queries means either:
- A) Make them async (larger refactor)
- B) Cache project configs at startup and refresh periodically (simpler)
- C) Pass project config as a parameter from the API layer (cleanest)

**Recommended: Option C** — API endpoints already have `db` sessions, query Project there and pass config down.

### 2. `backend/app/config.py` — team_repos (line 37)
```python
team_repos: list[str] = [
    "wx/wx", "wx/eso-golang",
    "product/g4-wk/g4", "product/g4-wk/g4-task",
    "temporal/temporalio-cloud",
]
```
**Used by**: `config_service.get_repos_to_scan()` → `git_scanner` background job

**Fix**: `get_repos_to_scan()` already uses config, but should also query Project.repositories:
```python
def get_repos_to_scan(self) -> list[str]:
    # Merge config file repos with DB project repos
    config_repos = [...]  # from config.yaml
    # DB repos loaded at startup or via periodic refresh
    return list(set(config_repos + db_repos))
```

### 3. `backend/app/config.py` — project_path_map (line 27)
```python
project_path_map: dict[str, str] = {
    "-Users-aaryn-workspaces-wx-1": "wx",
    "-Users-aaryn-workspaces-g4": "g4",
    ...
}
```
**Used by**: Agent sync — maps Claude session project dirs to project keys

**Fix**: Build this map dynamically from Project.repositories local_path field:
```python
# At sync time, build map from projects with local_path set
for project in projects:
    for repo in project.repositories:
        if repo.get("local_path"):
            dir_name = repo["local_path"].replace("/", "-").lstrip("-")
            path_map[dir_name] = project.key
```

### 4. `backend/app/services/jira_service.py` — _default_project() (line 58)
```python
def _default_project() -> str:
    return _load_config()["JIRA_PROJECT"]  # Returns "COMPUTE"
```
**Used by**: `search_tickets()`, `get_summary()` — fallback when no project specified

**Fix**: Instead of a single default, use the requesting project's `jira_project_keys`:
```python
async def _get_jira_keys_for_project(project_key: str, db: AsyncSession) -> list[str]:
    project = await db.execute(select(Project).where(Project.key == project_key))
    p = project.scalar_one_or_none()
    return p.jira_project_keys if p else ["COMPUTE"]
```

### 5. `backend/app/services/config_service.py` — default repo config (line 33)
```python
{"path": str(Path.home() / "code/wx/wx"), "name": "wx"},
{"path": str(Path.home() / "code/product/g4-wk/g4"), "name": "g4"},
...
```
**Used by**: Fallback when config.yaml doesn't exist

**Fix**: Query Project table as fallback, keep config.yaml as override.

## Implementation Order

### Phase A: Low-risk, high-value (do first)
1. **config_service.get_repos_to_scan()** — merge DB repos into scan list
   - Effort: 30 min
   - Impact: New projects' repos get scanned automatically
   
2. **jira_service default project** — use Project.jira_project_keys
   - Effort: 30 min
   - Impact: Project-specific JIRA queries use correct keys

### Phase B: Medium-risk (API layer changes)
3. **gitlab_service PROJECTS dict** — pass config from API endpoints
   - Effort: 2-3 hours
   - Impact: MR listing/approval works for any project's repos
   - Risk: Many callsites to update

4. **project_path_map** — build dynamically from Project.repositories
   - Effort: 1 hour
   - Impact: Agent sync maps sessions to correct projects

### Phase C: Background job changes
5. **git_scanner** — iterate Project rows instead of config list
   - Effort: 1 hour
   - Impact: Branch/worktree scanning covers all projects

6. **MR sync job** — scan all Project.repositories
   - Effort: 1 hour
   - Impact: MR sync covers dynamically added repos

## Total Estimated Effort
- Phase A: 1 hour
- Phase B: 3-4 hours
- Phase C: 2 hours
- **Total: 6-7 hours**

## Testing
- Add a new project via API with a repo path
- Verify: git_scanner picks it up, MRs appear, JIRA filters work
- Verify: existing projects still work unchanged
- Verify: removing a project stops scanning its repos
