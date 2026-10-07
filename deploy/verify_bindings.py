"""Read deployed definitions and reject cross-environment write references.

Publication success alone does not prove isolation. This checks runtime payloads
after Fabric serialization and before any non-production data run. Source-only
shared connectors are allowlisted; Production workspace/item/write-connector IDs
are never allowed in Dev/Test executable definitions.
"""

import argparse
import base64
import json
from pathlib import Path

from fabric_api import FabricAPI

ROOT = Path(__file__).resolve().parents[1]
SHARED_SOURCE_IDS = {"e3607aae-ab0a-4954-968c-613ebd192eeb", "2977a806-dd08-4233-b4d1-bd1521ec0d16"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test", "production"], required=True)
    args = parser.parse_args()
    configurations = json.loads((ROOT / "config/environments.json").read_text())
    config = configurations[args.environment]
    inventory = json.loads((ROOT / "config/source_inventory.json").read_text())
    if not set(config.get("shared_read_connections", [])).issubset(SHARED_SOURCE_IDS):
        raise RuntimeError("Only PostgreSQL/S3 read-source connectors may be shared")
    api = FabricAPI()
    items = api.list_all(f"workspaces/{config['workspace_id']}/items")
    forbidden = set()
    for environment, other in configurations.items():
        if environment == args.environment:
            continue
        forbidden.add(other["workspace_id"])
        forbidden |= set(other["connections"].values()) - SHARED_SOURCE_IDS
        # Per-environment identities are Contributors only in their own workspace.
        # Other item IDs come from the reviewed inventory snapshot, not privileged
        # cross-workspace reads by the deployment identity.
        forbidden |= set(other.get("item_ids", {}).values())
    if args.environment != "production":
        forbidden |= {inventory["source_workspace_id"]} | {item["source_id"] for item in inventory["items"]}
    checked = []
    for item in items:
        if item["type"] not in ("Notebook", "DataPipeline", "SemanticModel"):
            continue
        result = api.call("POST", f"workspaces/{config['workspace_id']}/items/{item['id']}/getDefinition", {})
        for part in result["definition"]["parts"]:
            if part["path"] == ".platform":
                continue
            payload = base64.b64decode(part["payload"]).decode("utf-8").lower()
            present = {identifier for identifier in forbidden if identifier.lower() in payload}
            if present:
                raise RuntimeError(f"Cross-environment reference in {item['displayName']}/{part['path']}: {sorted(present)}")
        checked.append(item["displayName"])
    expected = {x["name"] for x in inventory["items"] if x["type"] in ("Notebook", "DataPipeline", "SemanticModel")}
    if expected - set(checked):
        raise RuntimeError(f"Application definitions missing: {sorted(expected - set(checked))}")
    print(json.dumps({"environment": args.environment, "status": "passed", "checked_definitions": len(checked)}))


if __name__ == "__main__":
    main()
