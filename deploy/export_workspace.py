"""Export only approved retail definitions, never source rows or credentials."""

import argparse
import base64
import json
from pathlib import Path, PurePosixPath

from fabric_api import FabricAPI

APPROVED_TYPES = {"Lakehouse", "Warehouse", "Notebook", "DataPipeline", "SemanticModel"}
ROOT = Path(__file__).resolve().parents[1]


def safe_path(base, name):
    """Reject traversal and absolute paths from external definition responses."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Unsafe definition part: {name}")
    return base.joinpath(*path.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True)
    args = parser.parse_args()
    api = FabricAPI()
    workspace = api.call("GET", f"workspaces/{args.workspace_id}")
    inventory = []
    for item in api.list_all(f"workspaces/{args.workspace_id}/items"):
        if item["type"] not in APPROVED_TYPES:
            continue
        folder = ROOT / "workspace" / f"{item['displayName']}.{item['type']}"
        folder.mkdir(parents=True, exist_ok=True)
        # Warehouse releases create an item shell; reviewed SQL migrations own
        # schema deployment. Never export table rows or pretend a shell is DDL.
        result = {} if item["type"] == "Warehouse" else api.call(
            "POST", f"workspaces/{args.workspace_id}/items/{item['id']}/getDefinition", {})
        parts = result.get("definition", result).get("parts", [])
        for part in parts:
            # Schedule enablement is an operator-controlled runtime concern.
            # Promoting the production schedule must never start Test ingestion.
            if part["path"] == ".schedules":
                continue
            output = safe_path(folder, part["path"])
            output.parent.mkdir(parents=True, exist_ok=True)
            content = base64.b64decode(part["payload"])
            if output.suffix == ".ipynb":
                notebook = json.loads(content)
                for cell in notebook.get("cells", []):
                    if cell.get("cell_type") == "code":
                        cell["outputs"] = []
                        cell["execution_count"] = None
                content = json.dumps(notebook, indent=2).encode()
            output.write_bytes(content)
        platform_path = folder / ".platform"
        platform = json.loads(platform_path.read_text()) if platform_path.exists() else {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": item["type"], "displayName": item["displayName"],
                         "description": item.get("description", "")},
            "config": {"version": "2.0", "logicalId": item["id"]},
        }
        if platform.get("config", {}).get("logicalId") in (None, "", "00000000-0000-0000-0000-000000000000"):
            platform["config"]["logicalId"] = item["id"]
        platform_path.write_text(json.dumps(platform, indent=2) + "\n")
        inventory.append({"name": item["displayName"], "type": item["type"],
                          "source_id": item["id"], "logical_id": platform["config"]["logicalId"]})
        print(f"Exported {item['type']} {item['displayName']}", flush=True)
    target = ROOT / "config" / "source_inventory.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"source_workspace_id": args.workspace_id,
                                 "capacity_id": workspace.get("capacityId"),
                                 "items": inventory}, indent=2) + "\n")


if __name__ == "__main__":
    main()
