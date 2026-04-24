#!/usr/bin/env python3
"""Test script for WX deployments service."""
import sys
import json

sys.path.insert(0, 'backend')

from app.services.wx_deployment_service import WXDeploymentService


def main():
    """Test the WX deployment service."""
    service = WXDeploymentService()

    print("=" * 60)
    print("WX Deployment Status")
    print("=" * 60)

    deployments = service.get_all_deployments()

    if not deployments:
        print("❌ No deployments found!")
        return 1

    print(f"\nFound {len(deployments)} environments:\n")

    for env in deployments:
        tier_label = f"[{env.get('tier', 'unknown').upper()}]"
        print(f"📦 {env['name'].upper()} {tier_label}")
        print(f"   Build ID:    {env['build_id']}")
        print(f"   Deployed:    {env.get('deployed_at', 'unknown')}")
        print(f"   Status:      {env.get('status', 'unknown')}")
        print(f"   ArgoCD:      {env.get('argocd_url', 'N/A')}")
        print(f"   Commit:      {env.get('commit_url', 'N/A')}")
        print()

    print("=" * 60)
    print("✅ All environments queried successfully!")
    print("=" * 60)

    # Also output JSON for debugging
    print("\nJSON Output:")
    print(json.dumps({"environments": deployments}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
