"""Prepare an eligible Production destination without moving or deleting data.

Run locally with an authorized operator after the reviewed Terraform apply.
Only four empty foundation items and the vacant stage assignment are changed.
The legacy workspace, its definitions, data, checkpoints and schedules stay intact.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fabric_api import FabricAPI

LEGACY = "fba1bab2-0098-4b65-9f4f-cb304d71b700"
TARGET = "300b8bbe-ee03-4a93-913f-16293c6117e4"
PIPELINE = "36eae116-42d0-498d-a280-8060a4aecccb"
STAGE = "2a7292c1-0e30-426c-9e71-6c9d64a7a77f"
FOUNDATIONS = {
    "lh_retail_bronze": "Lakehouse",
    "lh_retail_silver": "Lakehouse",
    "wh_retail_control": "Warehouse",
    "wh_retail_gold": "Warehouse",
}


def main():
    """Validate ownership and assignment, then prepare only the approved target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    api = FabricAPI()
    target = api.call("GET", f"workspaces/{TARGET}")
    if target["displayName"] != "Retail Order Intelligence Platform - Production":
        raise RuntimeError("Unexpected target workspace; refusing bootstrap")
    stages = api.call("GET", f"deploymentPipelines/{PIPELINE}/stages")["value"]
    stage = next(s for s in stages if s["id"] == STAGE)
    if stage.get("workspaceId") not in (None, TARGET):
        raise RuntimeError("Production stage already assigned elsewhere")
    legacy_before = api.list_all(f"workspaces/{LEGACY}/items")
    items = api.list_all(f"workspaces/{TARGET}/items")
    if args.execute:
        for name, kind in FOUNDATIONS.items():
            matches = [x for x in items if x["displayName"] == name and x["type"] == kind]
            if len(matches) > 1:
                raise RuntimeError(f"Duplicate foundation item {name}")
            if not matches:
                api.call("POST", f"workspaces/{TARGET}/items", {
                    "displayName": name, "type": kind,
                    "description": "Production cutover destination. Empty foundation only; data migration, schema deployment, bindings and runtime acceptance are pending.",
                })
        if not stage.get("workspaceId"):
            api.call("POST", f"deploymentPipelines/{PIPELINE}/stages/{STAGE}/assignWorkspace", {
                "workspaceId": TARGET,
            })
    stages = api.call("GET", f"deploymentPipelines/{PIPELINE}/stages")["value"]
    items = api.list_all(f"workspaces/{TARGET}/items")
    legacy_after = api.list_all(f"workspaces/{LEGACY}/items")
    if {x["id"] for x in legacy_before} != {x["id"] for x in legacy_after}:
        raise RuntimeError("Legacy item inventory changed during bootstrap")
    if args.execute and next(s for s in stages if s["id"] == STAGE).get("workspaceId") != TARGET:
        raise RuntimeError("Production stage assignment read-back failed")
    evidence = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if args.execute else "read_only",
        "legacy_workspace_id": LEGACY, "legacy_items_preserved": len(legacy_after),
        "legacy_items": legacy_after, "target_workspace": target,
        "target_items": items, "deployment_stages": stages,
        "data_migrated": False, "legacy_deleted": False,
        "release_enabled": False, "schedule_enabled": False,
        "note": "Inventory preservation is not a backup of business data. Deletion requires verified migration and recovery.",
    }
    path = Path(args.evidence)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: evidence[k] for k in (
        "mode", "legacy_items_preserved", "data_migrated", "legacy_deleted")
    }))
    print(json.dumps({"target_id": TARGET, "foundation_items": len(items), "stages": stages}))


if __name__ == "__main__":
    main()
