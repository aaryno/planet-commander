# WX Deployments - Real-time Kubernetes Integration

**Date**: 2026-03-17
**Status**: ✅ Complete

## Overview

The WX Deployments card now displays **real-time deployment status** from Kubernetes clusters instead of mock data.

## What Changed

### Before (Mock Data)
- Hardcoded 4 environments: dev, staging, prod-us, prod-eu
- Fake commit SHAs and timestamps
- Missing actual environments: wx-dev-01, wx-loadtest-01
- No tier identification (staging vs prod)

### After (Live Data)
- **4 environments** queried from Kubernetes (sorted PROD first, then staging):
  - `prod-us` - Production US (production cluster) **[PROD]**
  - `dev-01` - Development environment (staging cluster) **[STAGING]**
  - `loadtest-01` - Load testing environment (staging cluster) **[STAGING]**
  - `staging` - Staging environment (staging cluster) **[STAGING]**

- **Real data** from kubectl:
  - Actual commit SHAs from deployment image tags
  - True deployment timestamps
  - Live cluster status
  - **Tier badges** (Staging/Prod) for quick identification

## Architecture

### Service Layer
**File**: `backend/app/services/wx_deployment_service.py`

- Queries kubectl for each environment's deployment
- Parses container image tags to extract:
  - Commit SHA (shortened to 8 chars for display)
  - Deployment timestamp
  - Version info
- Generates URLs for ArgoCD, GitLab commits, and tigercli

### API Endpoint
**File**: `backend/app/api/wx.py`

```python
@router.get("/deployments")
async def wx_deployments():
    service = WXDeploymentService()
    environments = service.get_all_deployments()
    return {
        "environments": environments,
        "last_updated": datetime.now().isoformat(),
    }
```

### Frontend
**File**: `frontend/src/components/cards/WXDeployments.tsx`

- Updated color scheme to include new environments:
  - `dev-01` - Blue
  - `loadtest-01` - Amber
  - `staging` - Purple
  - `prod-us` - Emerald

- Added **tier badges**:
  - **STAGING** - Gray badge for staging cluster environments
  - **PROD** - Red badge for production cluster environments

## Environment Configuration

Each environment maps to a specific Kubernetes cluster:

```python
ENVIRONMENTS = {
    "dev-01": {
        "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
        "namespace": "wx-staging",
        "deployment": "wx-dev-01-api",
        "argocd_app": "wx-dev-01",
        "tier": "staging",
    },
    "loadtest-01": {
        "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
        "namespace": "wx-staging",
        "deployment": "wx-loadtest-01-api",
        "argocd_app": "wx-loadtest-01",
        "tier": "staging",
    },
    "staging": {
        "context": "gke_planet-k8s-staging_us-central1_stg-wxctl-01",
        "namespace": "wx-staging",
        "deployment": "wx-staging-api",
        "argocd_app": "wx-staging",
        "tier": "staging",
    },
    "prod-us": {
        "context": "gke_wx-k8s-prod_us-central1_prd-wxctl-01",
        "namespace": "wx-prod",
        "deployment": "wx-prod-api",
        "argocd_app": "wx-prod-us",
        "tier": "prod",
    },
}
```

## Data Flow

1. **Frontend** polls `/api/wx/deployments` every 2 minutes
2. **Backend** calls `WXDeploymentService.get_all_deployments()`
3. **Service** queries all configured environments via `kubectl`:
   ```bash
   kubectl --context <ctx> get deployment <name> -n <ns> \
     -o jsonpath='{.spec.template.spec.containers[0].image}'
   ```
4. **Parsing** extracts data from image tag:
   ```
   us.gcr.io/planet-gcr/wx/wx-api:v0.8.2-33-gf8db14b29494-20260316195704
                                    └─┬─┘ └─┬┘ └───┬────┘ └─────┬──────┘
                                   version │   commit SHA    timestamp
                                         commits since tag
   ```
5. **Sorting** orders results by tier (prod first, then staging alphabetically)
6. **Response** includes:
   - `build_id`: Short commit SHA (8 chars)
   - `deployed_at`: ISO timestamp
   - `status`: "healthy" (TODO: query actual health)
   - `tier`: "staging" or "prod" (infrastructure tier)
   - URLs for ArgoCD, GitLab, tigercli

## Example Output

```json
{
  "environments": [
    {
      "name": "dev-01",
      "build_id": "ed151fc3",
      "deployed_at": "2026-03-10T15:32:16",
      "status": "healthy",
      "tier": "staging",
      "commit_url": "https://hello.planet.com/code/wx/wx/-/commit/ed151fc3208f",
      "argocd_url": "https://argocd.prod.planet-labs.com/applications/wx-dev-01",
      "tigercli_url": "https://tigercli.prod.planet-labs.com/deploy/wx/dev-01"
    },
    {
      "name": "loadtest-01",
      "build_id": "f8db14b2",
      "deployed_at": "2026-03-16T19:57:04",
      "status": "healthy",
      "tier": "staging",
      "commit_url": "https://hello.planet.com/code/wx/wx/-/commit/f8db14b29494",
      "argocd_url": "https://argocd.prod.planet-labs.com/applications/wx-loadtest-01",
      "tigercli_url": "https://tigercli.prod.planet-labs.com/deploy/wx/loadtest-01"
    },
    {
      "name": "staging",
      "build_id": "1660c3d0",
      "deployed_at": "2026-02-26T17:15:28",
      "status": "healthy",
      "tier": "staging",
      "commit_url": "https://hello.planet.com/code/wx/wx/-/commit/1660c3d02ea9",
      "argocd_url": "https://argocd.prod.planet-labs.com/applications/wx-staging",
      "tigercli_url": "https://tigercli.prod.planet-labs.com/deploy/wx/staging"
    },
    {
      "name": "prod-us",
      "build_id": "1660c3d0",
      "deployed_at": "2026-02-26T17:15:28",
      "status": "healthy",
      "tier": "prod",
      "commit_url": "https://hello.planet.com/code/wx/wx/-/commit/1660c3d02ea9",
      "argocd_url": "https://argocd.prod.planet-labs.com/applications/wx-prod-us",
      "tigercli_url": "https://tigercli.prod.planet-labs.com/deploy/wx/prod-us"
    }
  ],
  "last_updated": "2026-03-17T11:15:00.123456"
}
```

## Testing

Run the test script to verify integration:

```bash
cd ~/claude/dashboard
python test-wx-deployments.py
```

Expected output (PROD sorted first):
```
============================================================
WX Deployment Status
============================================================

Found 4 environments:

📦 PROD-US [PROD]
   Build ID:    1660c3d0
   Deployed:    2026-02-26T17:15:28
   Status:      healthy
   ...

📦 DEV-01 [STAGING]
   Build ID:    ed151fc3
   Deployed:    2026-03-10T15:32:16
   Status:      healthy
   ...

📦 LOADTEST-01 [STAGING]
   ...

📦 STAGING [STAGING]
   ...
```

## Requirements

- **kubectl** configured with access to WX clusters
- **Contexts** must be available:
  - `gke_planet-k8s-staging_us-central1_stg-wxctl-01`
  - `gke_wx-k8s-prod_us-central1_prd-wxctl-01`

## Error Handling

- If an environment fails to query (cluster unreachable, no kubectl access), it's **silently skipped**
- Partial success is acceptable (e.g., staging works but prod fails)
- No error entries in response - only successful queries are returned

## Future Enhancements

### TODO: Real Health Status
Currently hardcoded to "healthy". Could be enhanced to:
- Query ArgoCD API for sync status
- Check Kubernetes deployment conditions
- Monitor pod ready status

### TODO: Add More Environments
If additional environments are created (e.g., prod-eu), add to `ENVIRONMENTS` dict.

### TODO: Caching
Consider caching results for 30-60 seconds to reduce kubectl queries.

### TODO: ArgoCD Deep Links
Currently links to application page. Could link to specific:
- Deployment resource
- Live logs
- Sync status

## Files Modified

- ✅ `backend/app/services/wx_deployment_service.py` - New service
- ✅ `backend/app/api/wx.py` - Updated endpoint
- ✅ `frontend/src/components/cards/WXDeployments.tsx` - Updated colors
- ✅ `test-wx-deployments.py` - Test script

## Deployment

When the dashboard backend restarts, it will automatically pick up the changes and start serving live data.

No database migrations or configuration changes required.
