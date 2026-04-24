"""Temporal API key health service.

Reads inventory.eap.json from the temporalio-cloud repo to track
API key expiration dates across all tenants.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

INVENTORY_PATH = Path.home() / "workspaces/temporalio/temporalio-cloud/example/inventory.eap.json"


def _parse_expiry(expiry_str: str) -> datetime:
    """Parse ISO 8601 expiry timestamp."""
    return datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))


def _classify_key(days_until: float) -> str:
    if days_until < 0:
        return "expired"
    elif days_until <= 14:
        return "expiring"
    return "ok"


def _extract_keys_from_account(account: dict) -> list[dict]:
    """Extract all API keys (admin + custom) from a tenant account."""
    keys = []
    tenant = account.get("tenant_uid", "unknown")

    # Admin service account keys
    admin_sa = account.get("admin_serviceaccount", {})
    apikeys = admin_sa.get("apikeys", {})
    current = admin_sa.get("current_apikey", "")

    for color in ("red", "black"):
        key_data = apikeys.get(color)
        if not key_data:
            continue
        keys.append({
            "tenant": tenant,
            "key_name": key_data["display_name"],
            "color": color,
            "account_type": "admin",
            "is_current": key_data["display_name"] == current,
            "expiry": key_data["expiry_time"],
        })

    # Custom service account keys
    for custom_sa in account.get("custom_serviceaccounts", []):
        custom_keys = custom_sa.get("apikeys", {})
        custom_current = custom_sa.get("current_apikey", "")

        for color in ("red", "black"):
            key_data = custom_keys.get(color)
            if not key_data:
                continue
            keys.append({
                "tenant": tenant,
                "key_name": key_data["display_name"],
                "color": color,
                "account_type": "custom",
                "sa_name": custom_sa.get("name", ""),
                "is_current": key_data["display_name"] == custom_current,
                "expiry": key_data["expiry_time"],
            })

    return keys


def get_key_health() -> dict:
    """Return key expiration status for all tenants."""
    if not INVENTORY_PATH.exists():
        return {
            "error": f"Inventory not found: {INVENTORY_PATH}",
            "keys": [],
            "expired_count": 0,
            "expiring_count": 0,
            "ok_count": 0,
        }

    now = datetime.now(timezone.utc)
    inventory_mtime = datetime.fromtimestamp(INVENTORY_PATH.stat().st_mtime, tz=timezone.utc)

    try:
        inventory = json.loads(INVENTORY_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read inventory: %s", e)
        return {"error": str(e), "keys": [], "expired_count": 0, "expiring_count": 0, "ok_count": 0}

    all_keys = []
    for account in inventory:
        for key in _extract_keys_from_account(account):
            expiry = _parse_expiry(key["expiry"])
            days_until = (expiry - now).total_seconds() / 86400
            status = _classify_key(days_until)
            all_keys.append({
                **key,
                "days_until": round(days_until, 1),
                "status": status,
            })

    # Sort: expired first, then expiring, then ok (by days ascending)
    all_keys.sort(key=lambda k: k["days_until"])

    expired = sum(1 for k in all_keys if k["status"] == "expired")
    expiring = sum(1 for k in all_keys if k["status"] == "expiring")
    ok = sum(1 for k in all_keys if k["status"] == "ok")

    return {
        "keys": all_keys,
        "expired_count": expired,
        "expiring_count": expiring,
        "ok_count": ok,
        "total_tenants": len(inventory),
        "inventory_updated": inventory_mtime.isoformat(),
        "inventory_age_days": round((now - inventory_mtime).total_seconds() / 86400, 1),
    }
