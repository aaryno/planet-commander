"""Temporal tenant/team data service.

Combines inventory data (tenant configs, namespaces, users) with
known metadata about teams, their Slack channels, repos, and products.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

INVENTORY_PATH = Path.home() / "workspaces/temporalio/temporalio-cloud/example/inventory.eap.json"

# Known team metadata (enriches inventory data)
TEAM_METADATA: dict[str, dict] = {
    "ag": {
        "name": "Photo Voyager (AG)",
        "slack_channels": [],
        "repos": [],
        "products": ["Photo Voyager"],
    },
    "bedrock": {
        "name": "Bedrock Development",
        "slack_channels": ["bedrock-dev"],
        "repos": [],
        "products": ["Bedrock"],
    },
    "compute": {
        "name": "Compute Platform",
        "slack_channels": ["compute-platform", "temporal-dev"],
        "repos": ["temporal/temporalio-cloud"],
        "products": ["Temporal Cloud (platform owner)"],
    },
    "delta": {
        "name": "Delta Engineering",
        "slack_channels": ["delta-engineering"],
        "repos": ["delta/microfilm", "delta/delta-analytics"],
        "products": ["Delta Analytics", "Microfilm"],
    },
    "dnd": {
        "name": "Discovery & Delivery",
        "slack_channels": ["discovery-and-delivery"],
        "repos": ["subscriptions/iris", "ordersv2", "sif", "fairqueue"],
        "products": ["Subscriptions", "Events"],
    },
    "dti": {
        "name": "DTI (Data Technology & Infrastructure)",
        "slack_channels": [],
        "repos": ["dti/ppc-nexus"],
        "products": ["PPC Nexus"],
    },
    "gms": {
        "name": "GMS Data Ops",
        "slack_channels": [],
        "repos": ["gms/fleet-management"],
        "products": ["GMS Fleet Management"],
    },
    "hobbes": {
        "name": "Hobbes Infrastructure",
        "slack_channels": ["hobbes"],
        "repos": ["hobbes/hobbes"],
        "products": ["Hobbes (legacy)"],
    },
    "storage": {
        "name": "Storage",
        "slack_channels": [],
        "repos": [],
        "products": ["Storage Platform"],
    },
    "tardis": {
        "name": "TARDIS (Fusion)",
        "slack_channels": [],
        "repos": ["tardis/fusion"],
        "products": ["Fusion"],
    },
}


def _extract_users_from_tenant(tenant: dict) -> list[dict]:
    """Extract unique users from a tenant's namespace configurations."""
    seen = set()
    users = []
    for ns in tenant.get("namespaces", []):
        for u in ns.get("allowed_users", []):
            email = u.get("email", "")
            if email and email not in seen:
                seen.add(email)
                # Derive display name from email
                name_part = email.split("@")[0]
                display = name_part.replace(".", " ").title()
                users.append({
                    "email": email,
                    "name": display,
                    "permission": u.get("permission", "read"),
                })
    return users


def get_tenants() -> dict:
    """Return enriched tenant data combining inventory + known metadata."""
    if not INVENTORY_PATH.exists():
        return {"tenants": [], "error": f"Inventory not found: {INVENTORY_PATH}"}

    try:
        inventory = json.loads(INVENTORY_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read inventory: %s", e)
        return {"tenants": [], "error": str(e)}

    tenants = []
    all_users = []
    for account in inventory:
        uid = account.get("tenant_uid", "unknown")
        meta = TEAM_METADATA.get(uid, {})
        users = _extract_users_from_tenant(account)
        namespaces = [ns["name"] for ns in account.get("namespaces", [])]

        tenant = {
            "uid": uid,
            "name": meta.get("name", uid.title()),
            "email": account.get("email", ""),
            "namespaces": namespaces,
            "namespace_count": len(namespaces),
            "users": users,
            "user_count": len(users),
            "slack_channels": meta.get("slack_channels", []),
            "repos": meta.get("repos", []),
            "products": meta.get("products", []),
            "has_export": any(
                ns.get("export", {}).get("enabled", False)
                for ns in account.get("namespaces", [])
            ),
            "has_nexus": len(account.get("nexus_endpoints", [])) > 0,
            "has_custom_sa": len(account.get("custom_serviceaccounts", [])) > 0,
        }
        tenants.append(tenant)

        for u in users:
            all_users.append({**u, "tenant": uid, "team": meta.get("name", uid.title())})

    # Deduplicate users across tenants (some users appear in multiple)
    seen_emails = {}
    for u in all_users:
        email = u["email"]
        if email not in seen_emails:
            seen_emails[email] = {**u, "tenants": [u["tenant"]]}
        else:
            if u["tenant"] not in seen_emails[email]["tenants"]:
                seen_emails[email]["tenants"].append(u["tenant"])

    unique_users = sorted(seen_emails.values(), key=lambda u: u["name"])

    return {
        "tenants": sorted(tenants, key=lambda t: t["uid"]),
        "users": unique_users,
        "total_tenants": len(tenants),
        "total_users": len(unique_users),
    }
