"""Promote Fabric-native definitions with explicit isolation and no item deletion.

Stages separate empty infrastructure shells, notebooks/pipelines, and the
semantic model that depends on published Gold schemas. This command never
executes ingestion, resets a checkpoint, enables a schedule or unpublishes an item.
"""

import argparse
import json
import shutil
from pathlib import Path

import yaml
from fabric_cicd import FabricWorkspace, publish_all_items, append_feature_flag

from fabric_api import CliCredential, FabricAPI

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    "foundation": ["Lakehouse", "Warehouse"],
    "application": ["Notebook", "DataPipeline"],
    "semantic": ["SemanticModel"],
}


def connection_references(directory):
    """Find static connector IDs from structured pipeline JSON, including nesting."""
    result = set()
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "connection" and isinstance(value, str):
                    result.add(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    for path in directory.rglob("pipeline-content.json"):
        walk(json.loads(path.read_text()))
    return result


def prepare(environment, stage):
    """Build a disposable, parameterized release without editing Git source files."""
    config = json.loads((ROOT / "config/environments.json").read_text())[environment]
    inventory = json.loads((ROOT / "config/source_inventory.json").read_text())
    if stage != "foundation" and not config["release_enabled"]:
        raise RuntimeError(f"{environment} release is disabled until bindings and integration gates pass")
    if stage == "semantic" and not config["semantic_enabled"]:
        raise RuntimeError("Semantic schema and connection readiness gate is not approved")
    output = ROOT / "build" / environment
    shutil.rmtree(output, ignore_errors=True)
    shutil.copytree(ROOT / "workspace", output / "workspace")
    # Exported schedules are never included in a code release, even in Production.
    for path in (output / "workspace").rglob(".schedules"):
        path.unlink()
    rules = [{"find_value": inventory["source_workspace_id"],
              "replace_value": {environment: "$workspace.$id"}}]
    if stage != "foundation":
        # Runtime Python strings are not all native item-reference fields. Explicit
        # rules also cover notebook REST calls and Gold-health model identifiers.
        for item in inventory["items"]:
            rules.append({"find_value": item["source_id"],
                          "replace_value": {environment: f"$items.{item['type']}.{item['name']}.$id"}})
    if stage == "application":
        for source in connection_references(output / "workspace"):
            target = config["connections"].get(source)
            if not target:
                raise RuntimeError(f"Missing {environment} connection binding for {source}")
            if environment != "production" and source == target and source not in config.get("shared_read_connections", []):
                raise RuntimeError(f"Non-production cannot silently reuse a Production connector: {source}")
            rules.append({"find_value": source, "replace_value": {environment: target}})
    old_endpoint = "ogzcft3boiduvg2pubg5425bwe-wk5kd64yabsuxh2pzmye24nxaa.datawarehouse.fabric.microsoft.com"
    if stage != "foundation":
        rules.append({"find_value": old_endpoint, "ignore_case": "true",
                      "replace_value": {environment: "$items.Warehouse.wh_retail_gold.$sqlendpoint"}})
    parameter_file = output / "parameter.yml"
    parameter_file.write_text(yaml.safe_dump({"find_replace": rules}, sort_keys=False))
    return config, output / "workspace", parameter_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "test", "production"], required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--execute", action="store_true", help="Without this flag, only prepare and validate locally")
    args = parser.parse_args()
    config, directory, parameters = prepare(args.environment, args.stage)
    if not args.execute:
        print(json.dumps({"status": "prepared", "environment": args.environment, "stage": args.stage}))
        return
    # Root-level Fabric folders are unsupported in the current trial workspace.
    append_feature_flag("disable_workspace_folder_publish")
    target = FabricWorkspace(workspace_id=config["workspace_id"],
                             repository_directory=str(directory),
                             environment=args.environment,
                             item_type_in_scope=STAGES[args.stage],
                             parameter_file_path=str(parameters),
                             token_credential=CliCredential())
    publish_all_items(target)
    items = FabricAPI().list_all(f"workspaces/{config['workspace_id']}/items")
    inventory = json.loads((ROOT / "config/source_inventory.json").read_text())
    expected = {(x["type"], x["name"]) for x in inventory["items"] if x["type"] in STAGES[args.stage]}
    actual = {(x["type"], x["displayName"]) for x in items}
    if expected - actual:
        raise RuntimeError(f"Missing deployed definitions: {sorted(expected - actual)}")
    print(json.dumps({"status": "deployed", "environment": args.environment,
                      "stage": args.stage, "verified_items": len(expected)}))


if __name__ == "__main__":
    main()
